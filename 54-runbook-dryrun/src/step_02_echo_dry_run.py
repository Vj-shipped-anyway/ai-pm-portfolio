"""Step 2 - The common basic approach: a dry-run flag that prints every command.

Most scripts get a `--dry-run` that fills in the parameters and prints what would run. A person reads the
plan. This step does exactly that for all 94 cases and counts what a reader could see in the printed text:
a placeholder left unfilled is visible, nothing else is. Approval gates print as a line of text.

Run (from src/):  python3 step_02_echo_dry_run.py
"""

from __future__ import annotations

from common import load_cases, render

cases = load_cases()


def plan(c) -> list:
    params = dict(c["rb"]["params"])
    params.update(c["params"])
    return [render(st["run"], params) for st in c["rb"]["steps"]]


def visible(c) -> bool:
    return any("{{" in line for line in plan(c))


bad = [c for c in cases if c["truth"] == "BLOCKED"]
fine = [c for c in cases if c["truth"] != "BLOCKED"]
seen = [c for c in bad if visible(c)]
approvals = [c for c in bad if c["group"] == "approval"]

print("STEP 2 - a dry run that prints every command")
print(f"  plans printed: {len(cases)} of {len(cases)}; exit status 0 on {len(cases)}")
print(f"  problems a reader can see in the printed plan: {len(seen)} of {len(bad)} (an unfilled {{{{name}}}})")
print(f"  plans that look fine though a real run goes wrong: {len(bad) - len(seen)} of {len(bad)}")
print(f"  invalid approvals noticed: {sum(1 for c in approvals if visible(c))} of {len(approvals)}")
print(f"  false alarms: {sum(1 for c in fine if visible(c))} of {len(fine)}")
print("  The plan shows what would run. It does not say whether the state allows it or whether anyone may approve it.")
