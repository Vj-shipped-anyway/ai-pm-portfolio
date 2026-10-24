"""swapbrief: a go or no-go brief for moving a GenAI feature from one model version to another.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 swapbrief.py --demo
    python3 swapbrief.py brief RESULTS.csv PRICES.csv --baseline NAME --candidate NAME
                         [--critical SLICE,SLICE] [--tolerance-pp 5] [--fail-on nogo|guardrails|never]
                         [--format text|json] [--resamples 1000] [--seed N]

The input is two files.
  RESULTS.csv  one row per (item, system): item_id, slice, system, correct, input_tokens,
               output_tokens, latency_ms. Every item must appear once for the baseline and once for
               the candidate. Rows of any other system are ignored and counted.
  PRICES.csv   one row per system: system, input_usd_per_1k, output_usd_per_1k.
Systems are matched by the exact text in the `system` column; nothing is inferred from names.

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or
malformed input. The decision is NO-GO, GO WITH GUARDRAILS or GO. There is no model in this file:
paired bootstrap intervals and fixed thresholds.

Extends project 13 (SwapBrief). The thresholds in POLICY are assumptions copied from its policy
file; they are not taken from any regulation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

RESULT_COLUMNS = ("item_id", "slice", "system", "correct", "input_tokens", "output_tokens", "latency_ms")
PRICE_COLUMNS = ("system", "input_usd_per_1k", "output_usd_per_1k")

POLICY = {
    "tolerance_pp": 5.0,          # a slice that falls this far, beyond noise, is a regression
    "inconclusive_half_width": 0.10,
    "cost_watch": 1.05, "cost_block": 1.25,
    "p95_watch": 1.10, "p95_block": 1.50,
    "confidence": 0.95,
    "min_pairs": 30,
    "min_correct": 5,
}
WINDOWS = {"cost": "24 hours", "p95": "1 hour, 3 windows in a row", "slice": "7 days rolling"}
DEFAULT_SEED = 20261024
DEMO = {"baseline": "incumbent", "candidate": "successor",
        "critical": ["card_disputes", "wire_exceptions", "kyc_refresh"]}
GO, GUARD, NOGO = "GO", "GO WITH GUARDRAILS", "NO-GO"
STATUS_ORDER = ("REGRESSED", "WATCH", "INCONCLUSIVE", "OK", "IMPROVED")


class InputError(Exception):
    """Malformed or unusable input. The command line turns it into exit status 2."""


def clean(text) -> str:
    """Make untrusted text safe for a log line or a workflow command: % first, then control characters."""
    out = []
    for ch in str(text):
        if ch == "%":
            out.append("%25")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("%%%02X" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------- reading the two files
def _read_rows(path: str, required) -> list:
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames
            if not header:
                raise InputError("%s is empty" % clean(path))
            missing = [c for c in required if c not in header]
            if missing:
                raise InputError("%s is missing column(s): %s" % (clean(path), ", ".join(missing)))
            rows = list(reader)
    except OSError as e:
        raise InputError("cannot read %s: %s" % (clean(path), e.strerror or "unreadable"))
    except UnicodeDecodeError:
        raise InputError("%s is not UTF-8 text" % clean(path))
    except csv.Error as e:
        raise InputError("%s is not valid CSV (%s)" % (clean(path), e))
    for n, row in enumerate(rows, start=2):
        if None in row or any(v is None for v in row.values()):
            raise InputError("%s line %d has the wrong number of fields (truncated or extra)" % (clean(path), n))
    if not rows:
        raise InputError("%s has a header and no data rows" % clean(path))
    return rows


def _text(row: dict, column: str, line: int) -> str:
    value = row[column]
    if not value.strip():
        raise InputError("line %d: %s is empty" % (line, column))
    return value


def _flag(value: str, line: int) -> int:
    if value not in ("0", "1"):
        raise InputError("line %d: correct must be 0 or 1, got %s" % (line, clean(value)[:20]))
    return int(value)


def _count(value: str, column: str, line: int) -> int:
    try:
        n = int(value)
    except ValueError:
        raise InputError("line %d: %s must be a whole number, got %s" % (line, column, clean(value)[:20]))
    if n < 0:
        raise InputError("line %d: %s must not be negative" % (line, column))
    return n


def _number(value: str, column: str, line: int, positive: bool) -> float:
    try:
        x = float(value)
    except ValueError:
        raise InputError("line %d: %s must be a number, got %s" % (line, column, clean(value)[:20]))
    if not math.isfinite(x) or x < 0 or (positive and x == 0):
        raise InputError("line %d: %s must be a finite %s number" % (line, column, "positive" if positive else "non-negative"))
    return x


def build_pairs(rows, baseline: str, candidate: str) -> dict:
    """Validate result rows (dicts of text) and pair them by item_id into columns."""
    if baseline == candidate:
        raise InputError("baseline and candidate must be different systems")
    kept = {baseline: {}, candidate: {}}
    systems, ignored = set(), 0
    for line, row in enumerate(rows, start=2):
        system = row["system"]
        systems.add(system)
        if system not in kept:
            ignored += 1
            continue
        item = _text(row, "item_id", line)
        entry = (_text(row, "slice", line), _flag(row["correct"], line),
                 _count(row["input_tokens"], "input_tokens", line), _count(row["output_tokens"], "output_tokens", line),
                 _number(row["latency_ms"], "latency_ms", line, True))
        if item in kept[system]:
            raise InputError("line %d: item %s appears twice for system %s" % (line, clean(item), clean(system)))
        kept[system][item] = entry
    for name in (baseline, candidate):
        if not kept[name]:
            raise InputError("no rows for system %s; systems in the file: %s" % (
                clean(name), ", ".join(clean(s) for s in sorted(systems)[:5])))
    unpaired = sorted(set(kept[baseline]) ^ set(kept[candidate]))
    if unpaired:
        raise InputError("%d item(s) do not appear for both systems, first: %s" % (len(unpaired), clean(unpaired[0])))
    pairs = {"item": sorted(kept[baseline]), "slice": [], "base": {"ok": [], "tin": [], "tout": [], "lat": []},
             "cand": {"ok": [], "tin": [], "tout": [], "lat": []}, "ignored": ignored}
    for item in pairs["item"]:
        a, b = kept[baseline][item], kept[candidate][item]
        if a[0] != b[0]:
            raise InputError("item %s is in slice %s for one system and %s for the other" % (
                clean(item), clean(a[0]), clean(b[0])))
        pairs["slice"].append(a[0])
        for key, entry in (("base", a), ("cand", b)):
            for field, value in zip(("ok", "tin", "tout", "lat"), entry[1:]):
                pairs[key][field].append(value)
    return pairs


def read_results(path: str, baseline: str, candidate: str) -> dict:
    return build_pairs(_read_rows(path, RESULT_COLUMNS), baseline, candidate)


def read_prices(path: str, baseline: str, candidate: str) -> dict:
    """{"base": (input, output), "cand": (input, output)} in USD per 1,000 tokens."""
    found = {}
    for line, row in enumerate(_read_rows(path, PRICE_COLUMNS), start=2):
        system = row["system"]
        if system not in (baseline, candidate):
            continue
        if system in found:
            raise InputError("line %d: system %s has two price rows" % (line, clean(system)))
        pin = _number(row["input_usd_per_1k"], "input_usd_per_1k", line, False)
        pout = _number(row["output_usd_per_1k"], "output_usd_per_1k", line, False)
        if pin == 0 and pout == 0:
            raise InputError("line %d: both prices are zero for system %s" % (line, clean(system)))
        found[system] = (pin, pout)
    for name in (baseline, candidate):
        if name not in found:
            raise InputError("%s has no price row for system %s" % (clean(os.path.basename(path)), clean(name)))
    return {"base": found[baseline], "cand": found[candidate]}


# ---------------------------------------------------------------- statistics
def percentile(sorted_values: list, q: float) -> float:
    """Linear interpolation between the two nearest ranks."""
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def _interval(reps: list, tail: float) -> tuple:
    s = sorted(reps)
    return percentile(s, tail), percentile(s, 1.0 - tail)


def _bootstrap(members: list, cols: tuple, resamples: int, seed: int, tail: float) -> dict:
    """One stratified paired bootstrap: items are resampled within each slice, and every
    interval in the brief comes from the same resamples."""
    diff, cost_a, cost_b, ok_a, ok_b, lat_a, lat_b = cols
    rand = random.Random(seed).random
    slice_reps = [[] for _ in members]
    acc_reps, cost_reps, p50_reps, p95_reps = [], [], [], []
    for _ in range(resamples):
        picked = []
        for k, m in enumerate(members):
            size = len(m)
            samp = [m[int(rand() * size)] for _ in range(size)]
            picked.extend(samp)
            slice_reps[k].append(sum([diff[i] for i in samp]) / size)
        acc_reps.append(sum([diff[i] for i in picked]) / len(picked))
        right_a, right_b = sum([ok_a[i] for i in picked]), sum([ok_b[i] for i in picked])
        if right_a and right_b:
            cost_reps.append((sum([cost_b[i] for i in picked]) / right_b) / (sum([cost_a[i] for i in picked]) / right_a))
        la, lb = sorted([lat_a[i] for i in picked]), sorted([lat_b[i] for i in picked])
        p50_reps.append(percentile(lb, 0.50) / percentile(la, 0.50))
        p95_reps.append(percentile(lb, 0.95) / percentile(la, 0.95))
    if len(cost_reps) < resamples // 2:
        raise InputError("too few correct answers to resample cost per correct answer")
    return {"slice": [_interval(r, tail) for r in slice_reps], "acc": _interval(acc_reps, tail),
            "cost": _interval(cost_reps, tail), "p50": _interval(p50_reps, tail), "p95": _interval(p95_reps, tail)}


def slice_status(delta: float, lo: float, hi: float, tol: float, half_width_limit: float) -> str:
    if hi < 0 and delta <= -tol:
        return "REGRESSED"      # confirmed, and beyond the tolerance
    if hi < 0 or delta <= -tol:
        return "WATCH"          # confirmed but small, or large but unconfirmed
    if lo > 0:
        return "IMPROVED"
    if (hi - lo) / 2.0 > half_width_limit and lo < -tol:
        return "INCONCLUSIVE"   # too few items to rule a regression out
    return "OK"


def ratio_status(point: float, lo: float, watch: float, block: float) -> str:
    if lo >= block:
        return "BLOCK"
    if point >= watch and lo > 1.0:
        return "WATCH"
    return "OK"


def headline_rule(delta: float) -> str:
    """The rule most teams start with: GO when the candidate's average accuracy is not lower."""
    return GO if delta >= 0 else NOGO


# ---------------------------------------------------------------- the brief
def analyze(pairs: dict, prices: dict, critical=(), policy=None, resamples: int = 1000, seed: int = DEFAULT_SEED,
            baseline: str = "baseline", candidate: str = "candidate") -> dict:
    pol = dict(POLICY)
    pol.update(policy or {})
    n = len(pairs["item"])
    if n < pol["min_pairs"]:
        raise InputError("%d paired items; at least %d are needed" % (n, pol["min_pairs"]))
    base, cand = pairs["base"], pairs["cand"]
    for label, col in (("baseline", base), ("candidate", cand)):
        if sum(col["ok"]) < pol["min_correct"]:
            raise InputError("the %s has fewer than %d correct answers; cost per correct answer is not defined" % (
                label, pol["min_correct"]))
    names = sorted(set(pairs["slice"]))
    unknown = [c for c in critical if c not in names]
    if unknown:
        raise InputError("--critical names no slice in the results: %s" % ", ".join(clean(u) for u in unknown))
    members = [[i for i, s in enumerate(pairs["slice"]) if s == name] for name in names]

    def costs(col, price):
        return [(a * price[0] + b * price[1]) / 1000.0 for a, b in zip(col["tin"], col["tout"])]

    cost_a, cost_b = costs(base, prices["base"]), costs(cand, prices["cand"])
    diff = [b - a for a, b in zip(base["ok"], cand["ok"])]
    tail = (1.0 - pol["confidence"]) / 2.0
    boot = _bootstrap(members, (diff, cost_a, cost_b, base["ok"], cand["ok"], base["lat"], cand["lat"]), resamples, seed, tail)

    tol = pol["tolerance_pp"] / 100.0
    slices = []
    for k, name in enumerate(names):
        idx = members[k]
        acc_a = sum(base["ok"][i] for i in idx) / len(idx)
        acc_b = sum(cand["ok"][i] for i in idx) / len(idx)
        lo, hi = boot["slice"][k]
        slices.append({"slice": name, "critical": name in critical, "n": len(idx), "acc_a": acc_a, "acc_b": acc_b,
                       "delta": acc_b - acc_a, "lo": lo, "hi": hi,
                       "status": slice_status(acc_b - acc_a, lo, hi, tol, pol["inconclusive_half_width"])})
    acc_a, acc_b = sum(base["ok"]) / n, sum(cand["ok"]) / n
    accuracy = {"a": acc_a, "b": acc_b, "delta": acc_b - acc_a, "lo": boot["acc"][0], "hi": boot["acc"][1]}
    cpc_a, cpc_b = sum(cost_a) / sum(base["ok"]), sum(cost_b) / sum(cand["ok"])
    cost = {"cpc_a": cpc_a, "cpc_b": cpc_b, "ratio": cpc_b / cpc_a, "lo": boot["cost"][0], "hi": boot["cost"][1]}
    cost["status"] = ratio_status(cost["ratio"], cost["lo"], pol["cost_watch"], pol["cost_block"])
    la, lb = sorted(base["lat"]), sorted(cand["lat"])
    latency = {"p50_a": percentile(la, 0.50), "p50_b": percentile(lb, 0.50), "p95_a": percentile(la, 0.95),
               "p95_b": percentile(lb, 0.95), "lo": boot["p95"][0], "hi": boot["p95"][1],
               "p50_lo": boot["p50"][0], "p50_hi": boot["p50"][1]}
    latency["p50_ratio"] = latency["p50_b"] / latency["p50_a"]
    latency["p95_ratio"] = latency["p95_b"] / latency["p95_a"]
    latency["status"] = ratio_status(latency["p95_ratio"], latency["lo"], pol["p95_watch"], pol["p95_block"])

    block, guard = [], []
    for s in slices:
        label = clean(s["slice"])
        text = "slice %s fell %.1f pp, interval %+.1f to %+.1f pp, beyond the %.0f pp tolerance" % (
            label, -s["delta"] * 100, s["lo"] * 100, s["hi"] * 100, pol["tolerance_pp"])
        if s["status"] == "REGRESSED":
            (block if s["critical"] else guard).append(("critical " if s["critical"] else "") + text)
        elif s["status"] == "WATCH" or (s["status"] == "INCONCLUSIVE" and s["critical"]):
            guard.append("slice %s is %s: change %+.1f pp, interval %+.1f to %+.1f pp" % (
                label, s["status"].lower(), s["delta"] * 100, s["lo"] * 100, s["hi"] * 100))
    for name, block_at, point, d in (("cost per correct answer", pol["cost_block"], cost["ratio"], cost),
                                     ("p95 latency", pol["p95_block"], latency["p95_ratio"], latency)):
        if d["status"] == "BLOCK":
            block.append("%s is at least %.2fx the baseline at the interval's lower bound (%.2fx)" % (name, block_at, d["lo"]))
        elif d["status"] == "WATCH":
            guard.append("%s is %.2fx the baseline and the interval stays above 1.00x" % (name, point))
    decision = NOGO if block else (GUARD if guard else GO)
    result = {"baseline": baseline, "candidate": candidate, "pairs": n, "ignored_rows": pairs["ignored"],
              "accuracy": accuracy, "headline": headline_rule(accuracy["delta"]), "cost": cost, "latency": latency,
              "slices": slices, "decision": decision, "block_reasons": block, "guard_reasons": guard, "policy": pol}
    result["triggers"] = triggers(result)
    return result


def triggers(result: dict) -> list:
    """Rollback triggers: metric, threshold, window, action. Cost and p95 always get one."""
    pol = result["policy"]
    out = [{"metric": "cost per correct answer", "threshold": ">= %.2fx baseline" % pol["cost_block"],
            "window": WINDOWS["cost"], "action": "send traffic back to the baseline"},
           {"metric": "p95 latency", "threshold": ">= %.2fx baseline" % pol["p95_block"],
            "window": WINDOWS["p95"], "action": "send traffic back to the baseline"}]
    for s in result["slices"]:
        if s["status"] in ("REGRESSED", "WATCH") or (s["status"] == "INCONCLUSIVE" and s["critical"]):
            out.append({"metric": "accuracy in slice %s" % clean(s["slice"]),
                        "threshold": "%.0f pp or more below baseline" % pol["tolerance_pp"],
                        "window": WINDOWS["slice"], "action": "send that slice back to the baseline"})
    return out


def render_text(r: dict) -> str:
    a, c, lt = r["accuracy"], r["cost"], r["latency"]
    counts = {}
    for s in r["slices"]:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    lines = ["swapbrief: %s -> %s   %d paired items, %d slices" % (clean(r["baseline"]), clean(r["candidate"]),
                                                                  r["pairs"], len(r["slices"]))]
    if r["ignored_rows"]:
        lines.append("  note: %d row(s) of other systems were ignored" % r["ignored_rows"])
    lines.append("  accuracy          %.1f%% -> %.1f%%   %+.1f pp   interval %+.1f to %+.1f pp   the average says %s" % (
        a["a"] * 100, a["b"] * 100, a["delta"] * 100, a["lo"] * 100, a["hi"] * 100, r["headline"]))
    lines.append("  cost per correct  $%.5f -> $%.5f   %.2fx   interval %.2fx to %.2fx   %s" % (
        c["cpc_a"], c["cpc_b"], c["ratio"], c["lo"], c["hi"], c["status"]))
    lines.append("  p95 latency       %.0f ms -> %.0f ms   %.2fx   interval %.2fx to %.2fx   %s   (p50 %.2fx)" % (
        lt["p95_a"], lt["p95_b"], lt["p95_ratio"], lt["lo"], lt["hi"], lt["status"], lt["p50_ratio"]))
    lines.append("  slices            " + ", ".join("%d %s" % (counts[k], k.lower()) for k in STATUS_ORDER if k in counts))
    for s in r["slices"]:
        if s["status"] in ("REGRESSED", "WATCH", "INCONCLUSIVE"):
            lines.append("    %s%s (%d items): %+.1f pp, interval %+.1f to %+.1f pp   %s" % (
                clean(s["slice"]), " [critical]" if s["critical"] else "", s["n"], s["delta"] * 100,
                s["lo"] * 100, s["hi"] * 100, s["status"]))
    lines.append("decision: %s" % r["decision"])
    for reason in r["block_reasons"] + r["guard_reasons"]:
        lines.append("  because: " + reason)
    lines.append("rollback triggers (write these down before launch):")
    for t in r["triggers"]:
        lines.append("  - %s %s over %s: %s" % (t["metric"], t["threshold"], t["window"], t["action"]))
    return "\n".join(lines)


def exit_code(decision: str, fail_on: str) -> int:
    if fail_on == "never":
        return 0
    if decision == NOGO or (decision == GUARD and fail_on == "guardrails"):
        return 1
    return 0


# ---------------------------------------------------------------- command line
def _run(args) -> int:
    if args.resamples < 100:
        raise InputError("--resamples must be at least 100")
    if not math.isfinite(args.tolerance_pp) or args.tolerance_pp <= 0:
        raise InputError("--tolerance-pp must be a positive number")
    critical = [c for c in args.critical.split(",") if c] if args.critical else []
    pairs = read_results(args.results, args.baseline, args.candidate)
    prices = read_prices(args.prices, args.baseline, args.candidate)
    result = analyze(pairs, prices, critical, {"tolerance_pp": args.tolerance_pp}, args.resamples, args.seed,
                     args.baseline, args.candidate)
    print(json.dumps(result, indent=1, sort_keys=True) if args.format == "json" else render_text(result))
    return exit_code(result["decision"], args.fail_on)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="swapbrief", description="A go or no-go brief for a model migration.")
    ap.add_argument("--demo", action="store_true", help="run on the bundled sample data")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("brief", help="brief on two files: results and prices")
    b.add_argument("results")
    b.add_argument("prices")
    b.add_argument("--baseline", required=True, help="system name of the current model, exactly as in the file")
    b.add_argument("--candidate", required=True, help="system name of the successor, exactly as in the file")
    b.add_argument("--critical", default="", help="comma-separated slice names where a regression blocks the move")
    b.add_argument("--tolerance-pp", type=float, default=POLICY["tolerance_pp"])
    b.add_argument("--resamples", type=int, default=1000)
    b.add_argument("--seed", type=int, default=DEFAULT_SEED)
    b.add_argument("--fail-on", choices=("nogo", "guardrails", "never"), default="nogo")
    b.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args(argv)
    if args.demo:
        args = ap.parse_args(["brief", os.path.join(DATA, "results.csv"), os.path.join(DATA, "prices.csv"),
                              "--baseline", DEMO["baseline"], "--candidate", DEMO["candidate"],
                              "--critical", ",".join(DEMO["critical"]), "--fail-on", "never"])
    elif args.cmd != "brief":
        ap.print_usage(sys.stderr)
        return 2
    try:
        return _run(args)
    except InputError as e:
        print("input error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
