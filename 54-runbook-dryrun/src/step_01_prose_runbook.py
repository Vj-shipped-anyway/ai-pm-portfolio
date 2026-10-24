"""Step 1 - Status quo: the runbook is a page, and the first test of it is the incident.

Ninety-four drill cases, each one a runbook, a snapshot of system state, a requester and the approvals on
file. Nothing checks any of it before a person starts. The truth file records what a real run would do,
decided when the case was planted (data/_generate.py). This step counts what the on-call person meets.

Run (from src/):  python3 step_01_prose_runbook.py
"""

from __future__ import annotations

from collections import Counter

from common import load_cases

cases = load_cases()
by_truth = Counter(c["truth"] for c in cases)
bad = [c for c in cases if c["truth"] == "BLOCKED"]
real = Counter(c["real_run"] for c in bad)
half_done = [c for c in bad if c["real_run"] in ("stops", "garbled") and c["writes_before"] >= 1]
steps_in = sum(c["problem_index"] - 1 for c in bad) / len(bad)

print("STEP 1 - runbooks followed by hand, nothing checked first")
print(f"  drill cases: {len(cases)} ({by_truth['READY']} complete, {by_truth['WAITING']} park at a gate, {by_truth['BLOCKED']} go wrong)")
print(f"  problems met only while following the runbook: {len(bad)} of {len(cases)}")
print(f"  high-risk change goes ahead with no valid approval: {real['unsafe']}")
print(f"  run stops part-way: {real['stops']}; a command is sent with a parameter never filled in: {real['garbled']}")
print(f"  run stops or garbles after a write step has already gone through: {len(half_done)} of {len(bad)}")
print(f"  steps already done when the first problem shows, on average: {steps_in:.1f}")
print("  The first reader of the runbook is the person on call, during the incident.")
