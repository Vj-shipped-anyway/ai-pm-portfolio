"""Step 4 - The fix: lint, state and gate together, with a hold at every approval gate.

The tool (runbook_dryrun.py) renders every command, evaluates each precondition against a copy of the
snapshot, applies the `sets` each step declares, and checks each approval record against the exact
rendering it is about to bless. Verdict per case: BLOCKED when anything is wrong, WAITING when only an
approval is missing, READY otherwise. Nothing is executed.

KNOWN LIMIT, left in on purpose: the tool trusts what the runbook says about itself. A write labeled as a
read, and a snapshot that went stale before the run, are READY here. The script prints those cases. It also
blocks three clean cases whose snapshot holds a number as text, because it will not guess.

Run (from src/):  python3 step_04_with_dryrun.py
Output: a report, plus out/step_04_cases.csv, out/step_04_summary.json and out/step_04_demo_plan.txt
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
from collections import Counter

import runbook_dryrun
from common import load_cases, run_case, ensure_out, OUT_DIR

cases = load_cases()
rows = []
for c in cases:
    res = run_case(c)
    errors = [f for f in res["findings"] if f["severity"] == "error"]
    warns = [f for f in res["findings"] if f["severity"] == "warning"]
    rows.append({"case_id": c["case_id"], "kind": c["kind"], "group": c["group"], "truth": c["truth"], "verdict": res["verdict"],
                 "first_error": f"{errors[0]['kind']}:{errors[0]['step']}" if errors else "none",
                 "warnings": ";".join(f["kind"] for f in warns) or "none"})

bad = [r for r in rows if r["truth"] == "BLOCKED"]
waiting = [r for r in rows if r["truth"] == "WAITING"]
fine = [r for r in rows if r["truth"] != "BLOCKED"]
hard_neg = [r for r in rows if r["group"] == "hard_negative"]
caught = [r for r in bad if r["verdict"] == "BLOCKED"]
wrong = [r for r in fine if r["verdict"] == "BLOCKED"]
missed = [r for r in bad if r["verdict"] != "BLOCKED"]
exact = sum(1 for r in rows if r["verdict"] == r["truth"])
planted_warn = [c["case_id"] for c in cases if c["expect_warning"]]
warned = [r for r in rows if r["warnings"] != "none"]
warned_right = [r for r in warned if r["case_id"] in planted_warn]

print("STEP 4 - lint, state and gate together")
print(f"  blocked cases caught: {len(caught)} of {len(bad)}")
print(f"  clean or waiting cases blocked wrongly: {len(wrong)} of {len(fine)} ({', '.join(sorted({r['kind'] for r in wrong})) or 'none'})")
print(f"  hard negatives that pass: {len(hard_neg) - sum(1 for r in hard_neg if r['verdict'] == 'BLOCKED')} of {len(hard_neg)}")
print(f"  waiting cases held at the gate: {sum(1 for r in waiting if r['verdict'] == 'WAITING')} of {len(waiting)}")
print(f"  missing rollback warned: {len(warned_right)} of {len(planted_warn)}; warnings on any other case: {len(warned) - len(warned_right)}")
print(f"  verdict matches the planted truth: {exact} of {len(rows)}")
print(f"  blocked cases that still pass: {len(missed)} of {len(bad)} ({', '.join(sorted({r['kind'] for r in missed})) or 'none'})")
for r in missed:
    print(f"    {r['case_id']} {r['kind']} -> {r['verdict']}")
by_kind = Counter((r["kind"], r["verdict"]) for r in rows)
print("  verdicts by planted change:")
for kind in sorted({r["kind"] for r in rows}):
    print(f"    {kind:<27} " + ", ".join(f"{v} {by_kind[(kind, v)]}" for v in ("BLOCKED", "WAITING", "READY") if by_kind[(kind, v)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_cases.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"blocked_caught": len(caught), "blocked": len(bad), "false_alarms": len(wrong), "clean_or_waiting": len(fine),
           "exact_match": exact, "cases": len(rows), "missed": len(missed), "waiting_held": len(waiting)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    runbook_dryrun.main(["--demo"])
with open(os.path.join(OUT_DIR, "step_04_demo_plan.txt"), "w", encoding="utf-8") as fh:
    fh.write(buf.getvalue())
print("Wrote step_04_cases.csv, step_04_summary.json and step_04_demo_plan.txt in src/out/")
