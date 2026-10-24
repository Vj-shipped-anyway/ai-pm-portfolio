"""shadow_score: a scorecard over two CSV files, the proposals an agent made in shadow mode and the
outcomes people recorded for the same cases. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 shadow_score.py --demo
    python3 shadow_score.py check PROPOSALS.csv OUTCOMES.csv [--risky PROPOSED:HUMAN ...] [--detail]
                                  [--format text|json] [--fail-on hold|never] [threshold options]

Exit status: 0 when no check fails, 1 when at least one check fails (decision HOLD), 2 for bad or
malformed input. There is no model in this file: the join, the counts and the ten checks are plain
rules. The thresholds are defaults I chose; change them with the options.

PROPOSALS.csv columns: case_id, segment, day, proposed_outcome, proposed_value, confidence
    A blank proposed_outcome means the agent abstained. day is an integer; week = day // 7.
OUTCOMES.csv columns:  case_id, human_outcome, human_value, handled_by
Labels are compared as written after trimming spaces. Values compare as numbers when both parse.
A case is scored only when its case_id is in both files. Proposals with no outcome yet and outcomes
with no proposal are counted and reported, not scored.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

PROPOSAL_COLS = ("case_id", "segment", "day", "proposed_outcome", "proposed_value", "confidence")
OUTCOME_COLS = ("case_id", "human_outcome", "human_value", "handled_by")
ABSTAINED = "(abstained)"
DEMO_RISKY = (("REFUND", "DENY"), ("REFUND", "ESCALATE_FRAUD"), ("DENY", "ESCALATE_FRAUD"))


@dataclass(frozen=True)
class Rules:
    """Thresholds for the checks. The defaults are assumptions, not values from any standard."""
    min_cases: int = 300
    min_coverage: float = 0.90
    min_class_coverage: float = 0.70
    min_lower: float = 0.90
    min_lift: float = 0.15
    max_risky: float = 0.01
    min_group: int = 30
    group_floor: float = 0.85
    high_conf: float = 0.90
    max_spread: float = 0.10
    week_days: int = 7
    risky: tuple = ()


class InputError(ValueError):
    """Malformed or mismatched input. The command line prints it and exits 2."""


def clean(text, limit: int = 80) -> str:
    """Make a value from an input file safe to print on one line: control characters become escapes."""
    out = "".join(ch if ch.isprintable() else ("\\x%02x" % ord(ch) if ord(ch) < 256 else "\\u%04x" % ord(ch))
                  for ch in str(text))
    return out if len(out) <= limit else out[:limit] + "..."


def pct(x) -> str:
    return "n/a" if x is None else "%.1f%%" % (100 * x)


# ---------------------------------------------------------------- loading
def read_rows(path: str, required: tuple) -> list:
    label = clean(os.path.basename(path))
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames
            if not header:
                raise InputError(f"{label}: the file is empty")
            if len(set(header)) != len(header):
                raise InputError(f"{label}: the header repeats a column name")
            missing = [c for c in required if c not in header]
            if missing:
                raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
            rows = []
            for line, row in enumerate(reader, start=2):
                if None in row:
                    raise InputError(f"{label}: row {line} has more fields than the header")
                if any(v is None for v in row.values()):
                    raise InputError(f"{label}: row {line} is truncated")
                rows.append({k: v.strip() for k, v in row.items()})
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{label}: cannot read the file ({type(e).__name__})") from e
    if not rows:
        raise InputError(f"{label}: the file has a header and no rows")
    return rows


def parse_proposals(rows: list, label: str) -> list:
    out, seen = [], set()
    for line, r in enumerate(rows, start=2):
        if not r["case_id"]:
            raise InputError(f"{label}: row {line} has a blank case_id")
        if r["case_id"] in seen:
            raise InputError(f"{label}: case_id {clean(r['case_id'])} appears twice")
        seen.add(r["case_id"])
        try:
            day = int(r["day"])
        except ValueError:
            raise InputError(f"{label}: row {line} has a day that is not a whole number") from None
        if day < 0:
            raise InputError(f"{label}: row {line} has a negative day")
        conf = None
        if r["proposed_outcome"]:
            try:
                conf = float(r["confidence"])
            except ValueError:
                raise InputError(f"{label}: row {line} has a confidence that is not a number") from None
            if not (math.isfinite(conf) and 0.0 <= conf <= 1.0):
                raise InputError(f"{label}: row {line} has a confidence outside 0 to 1")
        out.append({"case_id": r["case_id"], "segment": r["segment"] or "(blank)", "day": day,
                    "outcome": r["proposed_outcome"], "value": r["proposed_value"], "conf": conf})
    return out


def parse_outcomes(rows: list, label: str) -> list:
    out, seen = [], set()
    for line, r in enumerate(rows, start=2):
        if not r["case_id"]:
            raise InputError(f"{label}: row {line} has a blank case_id")
        if r["case_id"] in seen:
            raise InputError(f"{label}: case_id {clean(r['case_id'])} appears twice")
        seen.add(r["case_id"])
        if not r["human_outcome"]:
            raise InputError(f"{label}: row {line} has a blank human_outcome")
        out.append({"case_id": r["case_id"], "outcome": r["human_outcome"], "value": r["human_value"],
                    "reviewer": r["handled_by"] or "(blank)"})
    return out


# ---------------------------------------------------------------- scoring
def same_value(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:
        return False


def judge(p: dict, o: dict) -> str:
    """abstained, disagree_outcome, disagree_value (same outcome, different value) or agree."""
    if not p["outcome"]:
        return "abstained"
    if p["outcome"] != o["outcome"]:
        return "disagree_outcome"
    return "agree" if same_value(p["value"], o["value"]) else "disagree_value"


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson score interval for k successes in n trials."""
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - half) / denom, (centre + half) / denom


def tally(records: list) -> dict:
    proposed = sum(1 for r in records if r["kind"] != "abstained")
    agree = sum(1 for r in records if r["kind"] == "agree")
    return {"n": len(records), "proposed": proposed, "agree": agree, "rate": agree / proposed if proposed else None,
            "coverage": proposed / len(records) if records else None}


def groups(records: list, field: str, rules: Rules) -> list:
    """Agreement per group. A group is judged only with min_group proposals; a smaller group whose rate
    would have been flagged is reported as too_few instead."""
    by = {}
    for r in records:
        by.setdefault(r[field], []).append(r)
    out = []
    for name in sorted(by):
        t = tally(by[name])
        t["name"] = str(name)
        t["judged"] = t["proposed"] >= rules.min_group
        low = t["rate"] is None or t["rate"] < rules.group_floor
        t["status"] = ("below" if low else "ok") if t["judged"] else ("too_few" if low else "ok")
        out.append(t)
    return out


def reviewer_groups(records: list, rules: Rules) -> list:
    out = groups(records, "reviewer", rules)
    total = tally(records)
    for g in out:
        rest_p, rest_a = total["proposed"] - g["proposed"], total["agree"] - g["agree"]
        g["rest_rate"] = rest_a / rest_p if rest_p else None
        gap = None if g["rate"] is None or g["rest_rate"] is None else g["rest_rate"] - g["rate"]
        g["gap"] = gap
        wide = gap is not None and gap > rules.max_spread
        g["status"] = ("below" if wide else "ok") if g["judged"] else ("too_few" if wide else "ok")
    return out


def confidence_bands(records: list, rules: Rules) -> list:
    edges = [("below 0.70", 0.0, 0.70), ("0.70 to %.2f" % rules.high_conf, 0.70, rules.high_conf),
             ("%.2f or more" % rules.high_conf, rules.high_conf, 1.01)]
    out = []
    for label, lo, hi in edges:
        rs = [r for r in records if r["kind"] != "abstained" and lo <= r["conf"] < hi]
        t = tally(rs)
        t["name"], t["status"] = label, "ok"
        t["mean_conf"] = sum(r["conf"] for r in rs) / len(rs) if rs else None
        out.append(t)
    return out


def score(proposals: list, outcomes: list, rules: Rules) -> dict:
    """Join the two files on case_id and compute every number the checks and the report use."""
    by_outcome = {o["case_id"]: o for o in outcomes}
    records = []
    for p in sorted(proposals, key=lambda x: x["case_id"]):
        o = by_outcome.get(p["case_id"])
        if o is None:
            continue
        kind = judge(p, o)
        records.append({"segment": p["segment"], "week": p["day"] // rules.week_days, "reviewer": o["reviewer"],
                        "human": o["outcome"], "proposed": p["outcome"] or ABSTAINED, "conf": p["conf"], "kind": kind,
                        "risky": kind == "disagree_outcome" and (p["outcome"], o["outcome"]) in rules.risky})
    if not records:
        raise InputError(f"no case_id appears in both files ({len(proposals)} proposals, {len(outcomes)} outcomes); "
                         "check that both cover the same cases")
    total = tally(records)
    humans = Counter(r["human"] for r in records)
    label, count = sorted(humans.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    confusion = {}
    for r in records:
        row = confusion.setdefault(r["proposed"], Counter())
        row[r["human"]] += 1
    by_class = groups(records, "human", rules)
    for g in by_class:
        low = g["coverage"] < rules.min_class_coverage
        g["judged"] = g["n"] >= rules.min_group
        g["status"] = ("below" if low else "ok") if g["judged"] else ("too_few" if low else "ok")
    interval = wilson(total["agree"], total["proposed"]) if total["proposed"] else None
    risky = sum(1 for r in records if r["risky"])
    return {
        "proposals": len(proposals), "outcomes": len(outcomes), "matched": total["n"],
        "pending": len(proposals) - total["n"], "orphans": len(outcomes) - total["n"],
        "proposed": total["proposed"], "abstained": total["n"] - total["proposed"], "agree": total["agree"],
        "kinds": dict(sorted(Counter(r["kind"] for r in records).items())),
        "headline": total["rate"], "interval": interval, "end_to_end": total["agree"] / total["n"],
        "coverage": total["coverage"], "majority_label": label, "majority_share": count / total["n"],
        "lift": total["agree"] / total["n"] - count / total["n"],
        "risky": risky, "risky_rate": risky / total["proposed"] if total["proposed"] else None,
        "by_class": by_class, "by_segment": groups(records, "segment", rules),
        "by_week": groups(records, "week", rules), "by_reviewer": reviewer_groups(records, rules),
        "by_confidence": confidence_bands(records, rules),
        "confusion": {k: dict(sorted(v.items())) for k, v in sorted(confusion.items())},
    }


# ---------------------------------------------------------------- checks
def _check(cid, name, threshold, measured, result, detail="") -> dict:
    return {"id": cid, "name": name, "threshold": threshold, "measured": measured, "result": result, "detail": detail}


def _worst(gs: list, key: str):
    judged = [g for g in gs if g["judged"] and g[key] is not None]
    return min(judged, key=lambda g: (g[key], g["name"])) if judged else None


def evaluate(s: dict, rules: Rules) -> list:
    """The ten checks. Each returns PASS, FAIL or SKIP with a reason; nothing is skipped silently."""
    out = []
    out.append(_check("C01", "sample size (matched cases)", f">= {rules.min_cases}", str(s["matched"]),
                      "PASS" if s["matched"] >= rules.min_cases else "FAIL"))
    out.append(_check("C02", "coverage (proposals made)", ">= " + pct(rules.min_coverage), pct(s["coverage"]),
                      "PASS" if s["coverage"] >= rules.min_coverage else "FAIL"))
    w = _worst(s["by_class"], "coverage")
    if w is None:
        out.append(_check("C03", "coverage in every outcome class", ">= " + pct(rules.min_class_coverage), "n/a", "SKIP",
                          f"no outcome class has {rules.min_group} cases"))
    else:
        out.append(_check("C03", "coverage in every outcome class", ">= " + pct(rules.min_class_coverage), pct(w["coverage"]),
                          "PASS" if w["coverage"] >= rules.min_class_coverage else "FAIL",
                          f"{clean(w['name'])} was proposed on {w['proposed']} of {w['n']} cases"))
    if s["interval"] is None:
        out.append(_check("C04", "agreement, lower end of 95% interval", ">= " + pct(rules.min_lower), "n/a", "SKIP",
                          "the agent made no proposals"))
    else:
        lo = s["interval"][0]
        out.append(_check("C04", "agreement, lower end of 95% interval", ">= " + pct(rules.min_lower), pct(lo),
                          "PASS" if lo >= rules.min_lower else "FAIL", f"first-report rate {pct(s['headline'])}"))
    out.append(_check("C05", "lift over always-%s rule" % clean(s["majority_label"], 24), ">= %.1f pts" % (100 * rules.min_lift),
                      "%.1f pts" % (100 * s["lift"]), "PASS" if s["lift"] >= rules.min_lift else "FAIL",
                      f"{pct(s['end_to_end'])} against {pct(s['majority_share'])}"))
    if not rules.risky:
        out.append(_check("C06", "risky disagreements", "<= " + pct(rules.max_risky), "n/a", "SKIP", "no --risky pairs were given"))
    elif s["risky_rate"] is None:
        out.append(_check("C06", "risky disagreements", "<= " + pct(rules.max_risky), "n/a", "SKIP", "the agent made no proposals"))
    else:
        out.append(_check("C06", "risky disagreements", "<= " + pct(rules.max_risky), pct(s["risky_rate"]),
                          "PASS" if s["risky_rate"] <= rules.max_risky else "FAIL", f"{s['risky']} of {s['proposed']} proposals"))
    for cid, label, key in (("C07", "segment", "by_segment"), ("C08", "week", "by_week")):
        w = _worst(s[key], "rate")
        name = f"weakest {label} (>= {rules.min_group} proposals)"
        if w is None:
            out.append(_check(cid, name, ">= " + pct(rules.group_floor), "n/a", "SKIP", f"no {label} has {rules.min_group} proposals"))
        else:
            bad = [g for g in s[key] if g["status"] == "below"]
            out.append(_check(cid, name, ">= " + pct(rules.group_floor), pct(w["rate"]), "FAIL" if bad else "PASS",
                              "; ".join(f"{label} {clean(g['name'])} {pct(g['rate'])} on {g['proposed']}" for g in bad)))
    hi = s["by_confidence"][-1]
    name = "agreement at confidence >= %.2f" % rules.high_conf
    if hi["proposed"] < rules.min_group:
        out.append(_check("C09", name, ">= " + pct(rules.high_conf), "n/a", "SKIP", f"fewer than {rules.min_group} proposals in the band"))
    else:
        out.append(_check("C09", name, ">= " + pct(rules.high_conf), pct(hi["rate"]),
                          "PASS" if hi["rate"] >= rules.high_conf else "FAIL", f"{hi['agree']} of {hi['proposed']} proposals"))
    judged = [g for g in s["by_reviewer"] if g["judged"] and g["gap"] is not None]
    name = "reviewer gap (agreement vs the rest)"
    if not judged:
        out.append(_check("C10", name, "<= %.1f pts" % (100 * rules.max_spread), "n/a", "SKIP",
                          f"no reviewer has {rules.min_group} proposals and a second reviewer to compare with"))
    else:
        wide = max(judged, key=lambda g: (g["gap"], g["name"]))
        bad = [g for g in judged if g["status"] == "below"]
        out.append(_check("C10", name, "<= %.1f pts" % (100 * rules.max_spread), "%.1f pts" % (100 * wide["gap"]),
                          "FAIL" if bad else "PASS",
                          "; ".join(f"reviewer {clean(g['name'])} {pct(g['rate'])} against {pct(g['rest_rate'])} for the rest" for g in bad)))
    return out


def decide(checks: list) -> str:
    return "HOLD" if any(c["result"] == "FAIL" for c in checks) else "CLEAR"


# ---------------------------------------------------------------- report
def _cell(g: dict, key: str, kind: str) -> str:
    v = g.get(key)
    if kind == "n":
        return str(v)
    if kind == "pts":
        return "n/a" if v is None else "%.1f" % (100 * v)
    return pct(v)


def _table(title: str, gs: list, cols: tuple) -> list:
    lines = [f"  {title}", "    " + " " * 24 + "  ".join(f"{h:>9}" for h, _k, _t in cols)]
    for g in gs:
        cells = "  ".join(f"{_cell(g, k, t):>9}" for _h, k, t in cols)
        lines.append(f"    {clean(g['name'], 24):<24}{cells}  {'' if g['status'] == 'ok' else g['status']}")
    return lines


BASE_COLS = (("cases", "n", "n"), ("proposed", "proposed", "n"), ("agreed", "agree", "n"), ("agreement", "rate", "pct"))


def render(s: dict, checks: list, decision: str, detail: bool = False) -> str:
    lines = [f"shadow-score: {s['matched']} matched cases ({s['pending']} proposals have no outcome yet, "
             f"{s['orphans']} outcomes have no proposal)"]
    lines.append(f"  first-report rate   {pct(s['headline'])}  (agreed on {s['agree']} of {s['proposed']} proposals; "
                 f"{s['abstained']} abstentions dropped)")
    if s["interval"]:
        lines.append(f"  95% interval        {pct(s['interval'][0])} to {pct(s['interval'][1])}")
    lines.append(f"  all matched cases   {pct(s['end_to_end'])}  (abstentions count as misses)")
    lines.append(f"  always {clean(s['majority_label'], 24)}   {pct(s['majority_share'])}  (the most common recorded outcome)")
    if detail:
        lines.append("")
        lines += _table("by recorded outcome", s["by_class"], BASE_COLS + (("coverage", "coverage", "pct"),))
        lines += _table("by segment", s["by_segment"], BASE_COLS)
        lines += _table("by week", s["by_week"], BASE_COLS)
        lines += _table("by reviewer", s["by_reviewer"], BASE_COLS + (("gap, pts", "gap", "pts"),))
        lines += _table("by stated confidence", s["by_confidence"],
                        (("proposed", "proposed", "n"), ("agreed", "agree", "n"), ("agreement", "rate", "pct"),
                         ("mean conf", "mean_conf", "pct")))
    lines.append("")
    w = max(len(c["name"]) for c in checks)
    lines.append(f"  {'id':<4} {'check':<{w}}  {'threshold':>10}  {'measured':>9}  result")
    for c in checks:
        lines.append(f"  {c['id']:<4} {c['name']:<{w}}  {c['threshold']:>10}  {c['measured']:>9}  {c['result']}")
    for c in checks:
        if c["result"] == "FAIL" and c["detail"]:
            lines.append(f"    {c['id']}: {c['detail']}")
        if c["result"] == "SKIP":
            lines.append(f"    {c['id']} skipped: {c['detail']}")
    small = [f"{label} {clean(g['name'])} {pct(g['rate'])} on {g['proposed']}" for label, key in
             (("segment", "by_segment"), ("week", "by_week"), ("reviewer", "by_reviewer")) for g in s[key] if g["status"] == "too_few"]
    if small:
        lines.append("  too few cases to judge, not counted: " + "; ".join(small))
    fails = sum(1 for c in checks if c["result"] == "FAIL")
    skips = sum(1 for c in checks if c["result"] == "SKIP")
    lines.append(f"decision: {decision}  ({fails} of {len(checks)} checks fail, {skips} skipped)")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def run_check(proposals_path: str, outcomes_path: str, rules: Rules, fmt: str, fail_on: str, detail: bool) -> int:
    try:
        proposals = parse_proposals(read_rows(proposals_path, PROPOSAL_COLS), clean(os.path.basename(proposals_path)))
        outcomes = parse_outcomes(read_rows(outcomes_path, OUTCOME_COLS), clean(os.path.basename(outcomes_path)))
        result = score(proposals, outcomes, rules)
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    checks = evaluate(result, rules)
    decision = decide(checks)
    if fmt == "json":
        print(json.dumps({"decision": decision, "checks": checks, "score": result}, indent=1, sort_keys=True))
    else:
        print(render(result, checks, decision, detail))
    return 1 if decision == "HOLD" and fail_on == "hold" else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"shadow-score: error: {clean(message, 200)}", file=sys.stderr)
        raise SystemExit(2)


def _fraction(text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a number from 0 to 1") from None
    if not 0.0 <= v <= 1.0:
        raise argparse.ArgumentTypeError("expected a number from 0 to 1")
    return v


def _count(text: str) -> int:
    try:
        v = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a whole number of 1 or more") from None
    if v < 1:
        raise argparse.ArgumentTypeError("expected a whole number of 1 or more")
    return v


def _high_conf(text: str) -> float:
    v = _fraction(text)
    if v <= 0.70:
        raise argparse.ArgumentTypeError("expected a number above 0.70 and at most 1")
    return v


def _pair(text: str) -> tuple:
    parts = text.split(":")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise argparse.ArgumentTypeError("expected PROPOSED:HUMAN, for example REFUND:DENY")
    return parts[0].strip(), parts[1].strip()


def build_parser() -> argparse.ArgumentParser:
    ap = _Parser(prog="shadow_score")
    ap.add_argument("--demo", action="store_true", help="score the bundled sample (data/proposals.csv, data/outcomes.csv)")
    sub = ap.add_subparsers(dest="cmd", parser_class=_Parser)
    c = sub.add_parser("check", help="score two CSV files")
    c.add_argument("proposals")
    c.add_argument("outcomes")
    c.add_argument("--risky", action="append", type=_pair, default=[], metavar="PROPOSED:HUMAN",
                   help="a proposal/outcome pair that costs more than an ordinary disagreement (repeatable)")
    c.add_argument("--min-cases", type=_count, default=Rules.min_cases)
    c.add_argument("--min-coverage", type=_fraction, default=Rules.min_coverage)
    c.add_argument("--min-class-coverage", type=_fraction, default=Rules.min_class_coverage)
    c.add_argument("--min-lower", type=_fraction, default=Rules.min_lower, help="floor for the lower end of the 95%% interval")
    c.add_argument("--min-lift", type=_fraction, default=Rules.min_lift)
    c.add_argument("--max-risky", type=_fraction, default=Rules.max_risky)
    c.add_argument("--min-group", type=_count, default=Rules.min_group, help="proposals a group needs before it is judged")
    c.add_argument("--group-floor", type=_fraction, default=Rules.group_floor)
    c.add_argument("--high-conf", type=_high_conf, default=Rules.high_conf)
    c.add_argument("--max-spread", type=_fraction, default=Rules.max_spread)
    c.add_argument("--week-days", type=_count, default=Rules.week_days)
    c.add_argument("--format", choices=["text", "json"], default="text")
    c.add_argument("--fail-on", choices=["hold", "never"], default="hold")
    c.add_argument("--detail", action="store_true", help="add the per-group tables")
    return ap


def main(argv=None) -> int:
    ap = build_parser()
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "proposals.csv"), os.path.join(d, "outcomes.csv"),
                         replace(Rules(), risky=DEMO_RISKY), "text", "never", False)
    if a.cmd == "check":
        rules = Rules(min_cases=a.min_cases, min_coverage=a.min_coverage, min_class_coverage=a.min_class_coverage,
                      min_lower=a.min_lower, min_lift=a.min_lift, max_risky=a.max_risky, min_group=a.min_group,
                      group_floor=a.group_floor, high_conf=a.high_conf, max_spread=a.max_spread,
                      week_days=a.week_days, risky=tuple(a.risky))
        return run_check(a.proposals, a.outcomes, rules, a.format, a.fail_on, a.detail)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
