"""Step 1 - Status quo: the deploy pipeline does not look at which snapshot answered.

Sixty-four candidate deploys each ran the 30-probe set before shipping. The pipeline ships on a green
unit-test run and nobody compares the snapshot id in the responses with the one the team pinned. This
step does not gate anything; it measures what would have gone out. The data is synthetic
(data/_generate.py), and the truth label of each run is the event that was planted, not an output of
the gate.

Run (from src/):  python3 step_01_no_gate.py
"""
from collections import Counter

from common import load_runs, gate

probes, runs = load_runs()
results = {r["run_id"]: gate(probes, r) for r in runs}
truth = Counter(r["truth"] for r in runs)
off_pin = [r for r in runs if results[r["run_id"]]["off_pin"]]
partial = [r for r in off_pin if results[r["run_id"]]["off_pin"] < results[r["run_id"]]["scored"]]
dropped = [r for r in runs if results[r["run_id"]]["drop"] > 0.05]
short = [r for r in runs if results[r["run_id"]]["scored"] < results[r["run_id"]]["probes"]]

print("STEP 1 - no check on the served snapshot (step_01_no_gate.py)")
print(f"  candidate deploys: {len(runs)}   probes per run: {len(probes)}")
print(f"  planted truth: {truth['BLOCK']} should be blocked, {truth['REVIEW']} should be reviewed, {truth['ALLOW']} are fine")
print(f"  deploys the current pipeline stops: 0 of {len(runs)}")
print(f"  deploys where some probe was served by an id other than the pin: {len(off_pin)} of {len(runs)}")
print(f"    of those, partial rollouts that reached only some probes: {len(partial)}")
print(f"  deploys whose mean pass rate is more than 5 points under the baseline: {len(dropped)} of {len(runs)}")
print(f"  deploys whose results file is short of probes: {len(short)} of {len(runs)}")
print("  The team learns about a swapped snapshot from a complaint, or from nothing.")
