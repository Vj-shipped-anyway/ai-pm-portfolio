"""Step 2 - The common basic approach: a pass-rate floor on the probe set.

The first gate a team adds is one number: block the deploy when the mean pass rate over the results it
has falls under a floor. The floor here is 0.90, the pass-rate threshold constant project 04 (EvalForge)
uses; it is an assumption in this project, not a measured threshold. The truth label is known, so this step counts what
the floor stops and what it stops by mistake.

Run (from src/):  python3 step_02_pass_rate_floor.py
"""
import math
from collections import Counter

from common import load_runs

FLOOR = 0.90

_, runs = load_runs()


def floor_decision(run: dict) -> str:
    rate = math.fsum(r["passes"] / r["trials"] for r in run["rows"]) / len(run["rows"])   # exact sum: sum() changed its float rounding in Python 3.12
    return "BLOCK" if rate < FLOOR else "ALLOW"


got = {r["run_id"]: floor_decision(r) for r in runs}
must = [r for r in runs if r["truth"] == "BLOCK"]
rev = [r for r in runs if r["truth"] == "REVIEW"]
fine = [r for r in runs if r["truth"] == "ALLOW"]
caught = [r for r in must if got[r["run_id"]] == "BLOCK"]
false = [r for r in fine if got[r["run_id"]] == "BLOCK"]
blocks = sum(1 for d in got.values() if d == "BLOCK")
missed = Counter(r["kind"] for r in must if got[r["run_id"]] == "ALLOW")

print("STEP 2 - block when the mean pass rate is under 0.90 (step_02_pass_rate_floor.py)")
print(f"  should-block runs stopped: {len(caught)} of {len(must)}")
print(f"  should-review runs stopped: {sum(1 for r in rev if got[r['run_id']] == 'BLOCK')} of {len(rev)}")
print(f"  fine runs stopped: {len(false)} of {len(fine)}")
print(f"  share of stops that are on fine runs: {len(false) / blocks:.1%}")
print("  should-block runs it lets through, by planted event: " + ", ".join(f"{k} {v}" for k, v in sorted(missed.items())))
print("  A floor sees the pass rate and nothing about which model produced it.")
