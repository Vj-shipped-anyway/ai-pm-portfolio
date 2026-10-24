"""Step 2 - The common basic approach: fail when the cost per call rises.

The first thing a team adds is a spend check. Compare the mean cost of a call in this run with the
mean cost in the last run on the main branch, and fail the build when it rises by more than 10%.
(10% is my assumption; it is the usual size of an alert like this, not a figure from a standard.)
The truth is known, so the step counts what the check caught and what it got wrong.

Run (from src/):  python3 step_02_cost_per_call.py
"""
from collections import Counter

from common import load_budget, load_runs, mean_cost_per_call

THRESHOLD = 0.10

budget = load_budget()
baseline, crs = load_runs(budget)
base_call = mean_cost_per_call(baseline)
for c in crs:
    c["ratio"] = mean_cost_per_call(c["items"]) / base_call
    c["fails"] = c["ratio"] > 1 + THRESHOLD
over = [c for c in crs if c["over"]]
within = [c for c in crs if not c["over"]]
missed = [c for c in over if not c["fails"]]
false_alarms = [c for c in within if c["fails"]]
cheaper = [c for c in over if c["ratio"] < 1.0]

print(f"STEP 2 - fail when cost per call rises more than {THRESHOLD:.0%} over the baseline run")
print(f"  baseline cost per call: ${base_call:.5f}")
print(f"  change requests failed: {sum(c['fails'] for c in crs)} of {len(crs)}")
print(f"  over budget and failed: {len(over) - len(missed)} of {len(over)}")
print(f"  over budget and passed: {len(missed)} of {len(over)}")
print(f"  within budget and failed (false alarms): {len(false_alarms)} of {len(within)}")
print(f"  over budget although cost per call fell below the baseline: {len(cheaper)} of {len(over)}")
print("  passed although over budget, by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in missed).items())))
print("  failed although within budget, by planted change: " + (", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in false_alarms).items())) or "none"))
print("  A cost per call cannot tell a model that costs less per call from one that costs less per right answer.")
