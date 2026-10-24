"""eval_gate: decide whether a model deploy may go ahead, from a probe file and the results of running it.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 eval_gate.py --demo
    python3 eval_gate.py check PROBES.csv RESULTS.csv --pin SNAPSHOT [--run-id ID] [--fail-on block|review|never]
                                                      [--format text|github]

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or malformed input.
The decision is BLOCK, REVIEW or ALLOW. There is no model call in this file: the gate is plain rules.

Probe file (CSV)    probe_id, severity (high, med or low), baseline_rate (0 to 1). Other columns are ignored.
Results file (CSV)  probe_id, passes, trials, served_model, and optionally run_id. served_model is the snapshot id
                    the vendor's response reported for that probe. Compared to --pin as an exact string.

Rules, in order:
  snapshot_changed   any probe served by an id other than the pin                       BLOCK
  unscored_probes    a probe in the probe file has no result                            BLOCK if any is high severity, else REVIEW
  overall_drop       mean pass rate fell below the mean baseline by more than 5 points  BLOCK; more than 3 points: REVIEW
  probe_collapse     a high-severity probe fell 50 points or more below its baseline    BLOCK
The thresholds are assumptions (see the README), not values from a standard.
"""
from __future__ import annotations

import math
import argparse
import csv
import json
import os
import re
import sys

REVIEW_DROP = 0.03
BLOCK_DROP = 0.05
COLLAPSE_DROP = 0.5
SEVERITIES = ("high", "med", "low")
DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


# ---------------------------------------------------------------- loading
def _read_rows(path: str, required: list, label: str) -> list:
    """Rows of a CSV as dicts. Raises ValueError for an empty, header-only or truncated file."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames
            rows = list(reader)
    except csv.Error as e:
        raise ValueError(f"{label}: not readable as CSV ({e})")
    if not header:
        raise ValueError(f"{label}: the file is empty")
    missing = [c for c in required if c not in header]
    if missing:
        raise ValueError(f"{label}: missing column {', '.join(missing)}")
    if not rows:
        raise ValueError(f"{label}: header only, no rows")
    for n, row in enumerate(rows, 2):
        if None in row or any(row.get(c) is None for c in required):
            raise ValueError(f"{label} line {n}: wrong number of fields (truncated or unquoted comma)")
    return rows


def _rate(label: str, n: int, field: str, text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise ValueError(f"{label} line {n}: {field} {text!r} is not a number")
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"{label} line {n}: {field} {text!r} is outside 0 to 1")
    return v


def _count(label: str, n: int, field: str, text: str) -> int:
    if not re.fullmatch(r"[0-9]+", text.strip()):
        raise ValueError(f"{label} line {n}: {field} {text!r} is not a whole number")
    return int(text)


def load_probes(path: str) -> list:
    """The probe file as a list of {probe_id, severity, baseline_rate}."""
    label = "probe file"
    out, seen = [], set()
    for n, r in enumerate(_read_rows(path, ["probe_id", "severity", "baseline_rate"], label), 2):
        pid = r["probe_id"].strip()
        if not pid:
            raise ValueError(f"{label} line {n}: probe_id is empty")
        if pid in seen:
            raise ValueError(f"{label} line {n}: probe_id {pid!r} appears twice")
        seen.add(pid)
        sev = r["severity"].strip()
        if sev not in SEVERITIES:
            raise ValueError(f"{label} line {n}: severity {sev!r} is not one of high, med, low")
        out.append({"probe_id": pid, "severity": sev, "baseline_rate": _rate(label, n, "baseline_rate", r["baseline_rate"])})
    return out


def load_results(path: str, run_id: str | None = None) -> tuple:
    """The results of one run as (rows, run label). A file that holds several runs needs run_id."""
    label = "results file"
    raw = list(enumerate(_read_rows(path, ["probe_id", "passes", "trials", "served_model"], label), 2))
    has_run = "run_id" in raw[0][1]
    if run_id is not None and not has_run:
        raise ValueError(f"{label}: --run-id was given but the file has no run_id column")
    if has_run:
        ids = sorted({r["run_id"] for _, r in raw})
        if run_id is None and len(ids) > 1:
            raise ValueError(f"{label}: holds {len(ids)} runs; pass --run-id ({ids[0]!r} is the first)")
        if run_id is not None:
            raw = [(n, r) for n, r in raw if r["run_id"] == run_id]
            if not raw:
                raise ValueError(f"{label}: no rows for run id {run_id!r}")
    out, seen = [], set()
    for n, r in raw:
        pid = r["probe_id"].strip()
        if pid in seen:
            raise ValueError(f"{label} line {n}: probe_id {pid!r} appears twice in one run")
        seen.add(pid)
        passes, trials = _count(label, n, "passes", r["passes"]), _count(label, n, "trials", r["trials"])
        if trials < 1 or passes > trials:
            raise ValueError(f"{label} line {n}: passes {passes} out of trials {trials} is not possible")
        model = r["served_model"].strip()
        if not model:
            raise ValueError(f"{label} line {n}: served_model is empty")
        out.append({"probe_id": pid, "passes": passes, "trials": trials, "served_model": model})
    return out, (run_id or (raw[0][1]["run_id"] if has_run else "single run"))


# ---------------------------------------------------------------- the gate
def _finding(kind: str, level: str, probe: str, message: str) -> dict:
    return {"kind": kind, "level": level, "probe": probe, "message": message}


def evaluate(probes: list, rows: list, pin: str, review_drop: float = REVIEW_DROP, block_drop: float = BLOCK_DROP,
             collapse_drop: float = COLLAPSE_DROP) -> dict:
    """Apply the four rules to one run. Raises ValueError when the inputs cannot be compared."""
    if not pin:
        raise ValueError("the pin is empty; name the snapshot id the deploy is supposed to use")
    if not (0 < review_drop <= block_drop <= 1 and 0 < collapse_drop <= 1):
        raise ValueError("thresholds must satisfy 0 < review-drop <= block-drop <= 1 and 0 < collapse-drop <= 1")
    by_id = {p["probe_id"]: p for p in probes}
    scored = [r for r in rows if r["probe_id"] in by_id]
    if not scored:
        raise ValueError("no result row names a probe in the probe file; check that these are the right two files")
    scored_ids = {r["probe_id"] for r in scored}
    findings, notes = [], []

    off = {}
    for r in scored:
        if r["served_model"] != pin:
            off.setdefault(r["served_model"], []).append(r["probe_id"])
    for model in sorted(off):
        findings.append(_finding("snapshot_changed", "BLOCK", "",
                                 f"{len(off[model])} of {len(scored)} probes were served by {model}, not the pinned {pin}. "
                                 f"Read the vendor's notice and re-run before moving the pin."))

    missing = sorted(i for i in by_id if i not in scored_ids)
    if missing:
        high = [i for i in missing if by_id[i]["severity"] == "high"]
        shown = ", ".join(missing[:5]) + (f" and {len(missing) - 5} more" if len(missing) > 5 else "")
        findings.append(_finding("unscored_probes", "BLOCK" if high else "REVIEW", "",
                                 f"{len(missing)} of {len(by_id)} probes have no result ({shown}); {len(high)} of them high severity."))

    rates = {r["probe_id"]: r["passes"] / r["trials"] for r in scored}
    current = math.fsum(rates.values()) / len(rates)   # exact sum: sum() changed its float rounding in Python 3.12
    baseline = math.fsum(by_id[i]["baseline_rate"] for i in rates) / len(rates)
    drop = round(baseline - current, 4)
    if drop > review_drop:
        findings.append(_finding("overall_drop", "BLOCK" if drop > block_drop else "REVIEW", "",
                                 f"mean pass rate {current:.2f} is {drop * 100:.1f} points below the baseline {baseline:.2f} "
                                 f"(review above {review_drop * 100:.1f}, block above {block_drop * 100:.1f})."))

    for pid in sorted(rates):
        p = by_id[pid]
        if p["severity"] == "high" and round(p["baseline_rate"] - rates[pid], 4) >= collapse_drop:
            findings.append(_finding("probe_collapse", "BLOCK", pid,
                                     f"high-severity probe {pid} fell from {p['baseline_rate']:.2f} to {rates[pid]:.2f}."))

    ignored = len(rows) - len(scored)
    if ignored:
        notes.append(f"{ignored} result rows name a probe that is not in the probe file and were ignored.")
    decision = max((f["level"] for f in findings), key=DECISION_RANK.__getitem__, default="ALLOW")
    return {"decision": decision, "findings": findings, "notes": notes, "pass_rate": current, "baseline": baseline,
            "drop": drop, "scored": len(scored), "probes": len(by_id), "off_pin": sum(len(v) for v in off.values()),
            "served": sorted({r["served_model"] for r in scored})}


# ---------------------------------------------------------------- output
def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def safe(text) -> str:
    """One line of printable text: control characters become escapes, so a value cannot add a line to a log."""
    return json.dumps(str(text), ensure_ascii=False)[1:-1]


def render(result: dict, pin: str, label: str, fmt: str) -> str:
    lines = []
    summary = (f"pass rate {result['pass_rate']:.2f} against a baseline of {result['baseline']:.2f} "
               f"({(0.0 - result['drop']) * 100:+.1f} points)")
    if fmt == "github":
        for f in result["findings"]:
            level = "error" if f["level"] == "BLOCK" else "warning"
            lines.append(f"::{level} title=eval-gate {f['kind']}::" + escape_annotation(f["message"]))
        for n in result["notes"]:
            lines.append("::notice title=eval-gate::" + escape_annotation(n))
        lines.append(f"::notice title=eval-gate::decision {result['decision']}; {summary}")
        return "\n".join(lines)
    lines.append(f"run: {safe(label)}   pin {safe(pin)}   {result['scored']} of {result['probes']} probes scored")
    lines.append(summary)
    for f in result["findings"]:
        lines.append(f"  [{f['level']:<6}] {f['kind']:<16} {safe(f['message'])}")
    if not result["findings"]:
        lines.append("  no finding")
    lines.extend("  note: " + safe(n) for n in result["notes"])
    lines.append(f"decision: {result['decision']}")
    return "\n".join(lines)


def run_check(probes_path, results_path, pin, run_id, fail_on, fmt, **limits) -> int:
    try:
        probes = load_probes(probes_path)
        rows, label = load_results(results_path, run_id)
        result = evaluate(probes, rows, pin, **limits)
    except (OSError, ValueError) as e:
        print(f"input error: {safe(e)}", file=sys.stderr)
        return 2
    print(render(result, pin, label, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[result["decision"]] >= DECISION_RANK[fail_on.upper()] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_gate")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/probes.csv, data/example_results.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="gate one run of the probe set")
    c.add_argument("probes")
    c.add_argument("results")
    c.add_argument("--pin", required=True, help="the snapshot id this deploy is meant to use")
    c.add_argument("--run-id", default=None, help="which run to read when the results file holds several")
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    c.add_argument("--review-drop", type=float, default=REVIEW_DROP)
    c.add_argument("--block-drop", type=float, default=BLOCK_DROP)
    c.add_argument("--collapse-drop", type=float, default=COLLAPSE_DROP)
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "probes.csv"), os.path.join(d, "example_results.csv"),
                         "vendor-balanced-4-20260214", None, "never", "text")
    if a.cmd == "check":
        return run_check(a.probes, a.results, a.pin, a.run_id, a.fail_on, a.format,
                         review_drop=a.review_drop, block_drop=a.block_drop, collapse_drop=a.collapse_drop)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
