"""Step 1 - Status quo: nothing in CI looks at what a correct answer costs.

Forty change requests (a new prompt, a model swap, a retrieval tweak) each come with an eval run of
236 items. The eval gate, if there is one, looks at accuracy. Nobody looks at the money until the
invoice. This step merges all forty and counts how many would have gone over the budget file. The
truth comes from the parameters that generated each run (data/_generate.py), not from the gate, and
the data is synthetic.

Run (from src/):  python3 step_01_no_gate.py
"""
from collections import Counter

from common import load_budget, load_runs

budget = load_budget()
baseline, crs = load_runs(budget)
over = [c for c in crs if c["over"]]
within = [c for c in crs if not c["over"]]
whole_run = [c for c in over if "overall" in c["true_scopes"]]
slice_only = [c for c in over if "overall" not in c["true_scopes"]]
worst = max(over, key=lambda c: c["true_worst"])

print("STEP 1 - no cost gate in CI")
print(f"  change requests merged: {len(crs)}   eval items per run: {len(baseline)}")
print(f"  truth, from the generating parameters: {len(over)} over budget, {len(within)} within budget")
print(f"  change requests the current CI stops: 0 of {len(crs)}")
print(f"  over budget on the whole run: {len(whole_run)} of {len(over)}; over only inside one slice: {len(slice_only)} of {len(over)}")
print(f"  worst: {worst['cr_id']} ({worst['kind']}) at {worst['true_worst']:.2f}x its ceiling")
print("  over budget by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in over).items())))
print("  The overspend shows up on the next invoice, after the merge.")
