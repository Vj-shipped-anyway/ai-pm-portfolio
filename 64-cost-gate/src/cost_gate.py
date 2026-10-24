"""cost_gate: fail a build when the cost per correct answer of an eval run goes over a budget.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 cost_gate.py --demo
    python3 cost_gate.py check RESULTS.csv BUDGET.json [--fail-on fail|warn|never] [--format text|github]

RESULTS.csv holds one eval run, one row per item, with the columns
    item_id, slice, model, correct (0 or 1), input_tokens, output_tokens
Extra columns are ignored. Tokens are what the item billed in total, retries included.
BUDGET.json holds the price of each model, min_items, a ceiling for the whole run ("overall") and
a ceiling per slice ("slices"). Every ceiling is "max_cost_per_correct_usd".

Cost per correct answer is the money spent on every call, right or wrong, divided by the number of
right answers. The 95% interval is the delta-method interval for a ratio of two means (z = 1.96).
There is no model call and no random number in this file.

A scope (the whole run, or one slice) gets one status:
    FAIL       the lower end of the interval is above the ceiling: over budget, with confidence
    WARN       the point estimate is above the ceiling but the interval still reaches it: a person decides
    PASS       the point estimate is at or under the ceiling
    THIN       a slice with fewer than min_items items: not judged alone, still counted in the overall
    NO_BUDGET  a slice in the results with no ceiling in the budget (counts as WARN)
    NO_ROWS    a budgeted slice with no rows in the results (counts as WARN)
A run with fewer than min_items items in total is WARN: nothing can be judged.

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad input.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

Z95 = 1.96
REQUIRED_COLUMNS = ("item_id", "slice", "model", "correct", "input_tokens", "output_tokens")
MAX_TOKENS = 1_000_000_000
MIN_ITEMS_FLOOR = 5
STATUS_RANK = {"PASS": 0, "THIN": 0, "WARN": 1, "NO_BUDGET": 1, "NO_ROWS": 1, "FAIL": 2}
DECISION_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}
DECISION_NAME = {v: k for k, v in DECISION_RANK.items()}
FAIL_ON_RANK = {"warn": 1, "fail": 2}


# ---------------------------------------------------------------- text safety
def clean(text, limit: int = 80) -> str:
    """Make untrusted text safe for one line of a log: control characters become \\uXXXX, length is capped."""
    s = "".join(ch if ch.isprintable() else "\\u%04x" % ord(ch) for ch in str(text))
    return s if len(s) <= limit else s[:limit - 3] + "..."


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- budget and rows
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ceiling(obj, label: str) -> float:
    c = obj.get("max_cost_per_correct_usd") if isinstance(obj, dict) else None
    if not _num(c) or c <= 0:
        raise ValueError(f"budget: {label} needs max_cost_per_correct_usd, a number above 0")
    return float(c)


def parse_budget(obj) -> dict:
    """Validate a decoded budget file and return it in the shape evaluate() reads. Raises ValueError."""
    if not isinstance(obj, dict):
        raise ValueError(f"budget: expected a JSON object, got {type(obj).__name__}")
    prices = obj.get("prices_usd_per_1k_tokens")
    if not isinstance(prices, dict) or not prices:
        raise ValueError("budget: prices_usd_per_1k_tokens must be an object with at least one model")
    table = {}
    for model, p in prices.items():
        if not isinstance(p, dict) or not all(_num(p.get(k)) and p[k] >= 0 for k in ("input", "output")):
            raise ValueError(f"budget: price of {clean(model)} needs input and output, numbers of 0 or more")
        table[model] = {"input": float(p["input"]), "output": float(p["output"])}
    min_items = obj.get("min_items", 30)
    if isinstance(min_items, bool) or not isinstance(min_items, int) or min_items < MIN_ITEMS_FLOOR:
        raise ValueError(f"budget: min_items must be a whole number of {MIN_ITEMS_FLOOR} or more")
    slices = obj.get("slices", {})
    if not isinstance(slices, dict):
        raise ValueError("budget: slices must be an object")
    return {"prices": table, "min_items": min_items,
            "overall": _ceiling(obj.get("overall"), "overall"),
            "slices": {name: _ceiling(v, f"slice {clean(name)}") for name, v in slices.items()}}


def parse_rows(rows: list, prices: dict) -> list:
    """Validate csv.DictReader rows of one run. Returns [{slice, correct, cost}]. Raises ValueError."""
    if not rows:
        raise ValueError("results: no rows")
    out, seen = [], set()
    for i, r in enumerate(rows, start=2):
        where = f"results line {i}"
        vals = {}
        for col in REQUIRED_COLUMNS:
            v = r.get(col)
            if v is None:
                raise ValueError(f"{where}: missing value for {col}")
            vals[col] = v.strip()
        for col in ("item_id", "slice", "model"):
            if not vals[col]:
                raise ValueError(f"{where}: {col} is empty")
        if vals["item_id"] in seen:
            raise ValueError(f"{where}: item_id {clean(vals['item_id'])} appears twice; one file holds one run")
        seen.add(vals["item_id"])
        if vals["model"] not in prices:
            raise ValueError(f"{where}: model {clean(vals['model'])} has no price in the budget")
        if vals["correct"] not in ("0", "1"):
            raise ValueError(f"{where}: correct must be 0 or 1, got {clean(vals['correct'])}")
        tokens = {}
        for col in ("input_tokens", "output_tokens"):
            t = vals[col]
            if not (t.isascii() and t.isdigit()) or int(t) > MAX_TOKENS:
                raise ValueError(f"{where}: {col} must be a whole number from 0 to {MAX_TOKENS}, got {clean(t)}")
            tokens[col] = int(t)
        p = prices[vals["model"]]
        cost = tokens["input_tokens"] / 1000.0 * p["input"] + tokens["output_tokens"] / 1000.0 * p["output"]
        out.append({"slice": vals["slice"], "correct": int(vals["correct"]), "cost": cost})
    return out


def read_results(path: str) -> list:
    """Read a results CSV into raw dict rows. Raises ValueError when the header lacks a required column."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("results: missing column(s) " + ", ".join(missing))
        return list(reader)


# ---------------------------------------------------------------- the statistic
def cost_per_correct(items: list):
    """(point, low, high) for total cost / total correct over `items`, or None when nothing is correct.

    Delta method for a ratio of means: with R = sum(cost) / sum(correct) and e_i = cost_i - R * correct_i,
    the variance of R is sum(e_i^2) / (n * (n - 1) * mean(correct)^2).
    """
    n = len(items)
    y = sum(it["correct"] for it in items)
    if n < 2 or y == 0:
        return None
    r = sum(it["cost"] for it in items) / y
    ss = sum((it["cost"] - r * it["correct"]) ** 2 for it in items)
    se = math.sqrt(ss / (n * (n - 1))) / (y / n)
    return r, max(0.0, r - Z95 * se), r + Z95 * se


def judge(name: str, items: list, ceiling, min_items: int, is_overall: bool = False) -> dict:
    n = len(items)
    res = {"scope": name, "items": n, "correct": sum(it["correct"] for it in items), "cpc": None, "low": None,
           "high": None, "ceiling": ceiling, "status": "PASS", "reason": ""}
    if n == 0:
        res["status"], res["reason"] = "NO_ROWS", "the budget names this slice but the results have no rows for it, so nothing was checked"
        return res
    est = cost_per_correct(items)
    if est:
        res["cpc"], res["low"], res["high"] = est
    if n < min_items:
        if is_overall:
            res["status"], res["reason"] = "WARN", f"{n} items is below min_items {min_items}, so nothing can be judged"
        else:
            res["status"], res["reason"] = "THIN", f"{n} items is below min_items {min_items}; not judged alone, still counted in the overall"
        return res
    if ceiling is None:
        res["status"], res["reason"] = "NO_BUDGET", "the results have this slice but the budget sets no ceiling for it"
    elif est is None:
        res["status"], res["reason"] = "FAIL", "no correct answers, so every call was spend with nothing to show"
    elif res["low"] > ceiling:
        res["status"], res["reason"] = "FAIL", f"the interval's lower end {res['low']:.5f} is above the ceiling {ceiling:.5f}"
    elif res["cpc"] > ceiling:
        res["status"], res["reason"] = "WARN", f"the estimate {res['cpc']:.5f} is above the ceiling {ceiling:.5f} but the interval {res['low']:.5f} to {res['high']:.5f} still reaches it"
    return res


def evaluate(items: list, budget: dict) -> dict:
    """Judge one run (rows from parse_rows) against a parsed budget. Slices are grouped by the slice field."""
    groups = {}
    for it in items:
        groups.setdefault(it["slice"], []).append(it)
    scopes = [judge("overall", items, budget["overall"], budget["min_items"], is_overall=True)]
    for name in sorted(set(budget["slices"]) | set(groups)):
        scopes.append(judge(name, groups.get(name, []), budget["slices"].get(name), budget["min_items"]))
    rank = max(STATUS_RANK[s["status"]] for s in scopes)
    return {"items": len(items), "scopes": scopes, "decision": DECISION_NAME[rank],
            "slice_budgets": len(budget["slices"])}


# ---------------------------------------------------------------- rendering and command line
def render(report: dict, fmt: str) -> str:
    scopes = report["scopes"]
    if fmt == "github":
        lines = []
        for s in scopes:
            if STATUS_RANK[s["status"]] == 0:
                continue
            level = "error" if s["status"] == "FAIL" else "warning"
            lines.append(f"::{level} title=cost-gate {s['status']}::" + escape_annotation(f"{s['scope']}: {s['reason']}"))
        lines.append(f"::notice title=cost-gate::decision {report['decision']}; {report['items']} items"
                     + ("" if report["slice_budgets"] else "; the budget sets no slice ceilings, so only the whole run was checked"))
        return "\n".join(lines)

    def num(v):
        return "-" if v is None else f"{v:.5f}"

    lines = [f"run: {report['items']} items, {len(scopes) - 1} slices",
             f"{'scope':<18}{'items':>6}{'correct':>9}{'$/correct':>11}  {'95% interval':<19}{'ceiling':>9}  status"]
    for s in scopes:
        iv = "-" if s["low"] is None else f"{s['low']:.5f} to {s['high']:.5f}"
        lines.append(f"{clean(s['scope'], 17):<18}{s['items']:>6}{s['correct']:>9}{num(s['cpc']):>11}  {iv:<19}{num(s['ceiling']):>9}  {s['status']}")
    for s in scopes:
        if s["reason"]:
            lines.append(f"  {s['status']} {clean(s['scope'])}: {s['reason']}")
    if not report["slice_budgets"]:
        lines.append("  the budget sets no slice ceilings, so only the whole run was checked")
    lines.append(f"decision: {report['decision']}")
    return "\n".join(lines)


def run_check(results_path: str, budget_path: str, fail_on: str, fmt: str) -> int:
    try:
        with open(budget_path, encoding="utf-8") as fh:
            budget = parse_budget(json.load(fh))
        items = parse_rows(read_results(results_path), budget["prices"])
    except (OSError, ValueError, csv.Error, RecursionError) as e:
        print("input error: " + clean(e, 300), file=sys.stderr)
        return 2
    report = evaluate(items, budget)
    print(render(report, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[report["decision"]] >= FAIL_ON_RANK[fail_on] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cost_gate")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_results.csv against data/budget.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="judge one eval run against a budget")
    c.add_argument("results")
    c.add_argument("budget")
    c.add_argument("--fail-on", choices=["fail", "warn", "never"], default="fail")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_results.csv"), os.path.join(d, "budget.json"), "never", "text")
    if a.cmd == "check":
        return run_check(a.results, a.budget, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
