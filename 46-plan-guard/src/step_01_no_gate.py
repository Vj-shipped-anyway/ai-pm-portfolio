"""Step 1 - Status quo: nothing in CI reads the plan.

Eighty-six Terraform plans are applied in turn. `terraform validate` and the plan itself pass on all of
them, because a public bucket or a world-open port is valid Terraform. This step counts what reaches
apply. The data is synthetic (data/_generate.py), and the truth of each plan is the change that was
planted there, not anything a rule decided.

Run (from src/):  python3 step_01_no_gate.py
"""
from collections import Counter

from common import load_plans

plans = load_plans()
truth = Counter(p["truth"] for p in plans)
changes = sum(len(p["plan"]["resource_changes"]) for p in plans)
by_kind = Counter(p["kind"] for p in plans if p["truth"] == "block")

print("STEP 1 - no plan check in CI")
print(f"  plans applied: {len(plans)}   resource changes in them: {changes}")
print(f"  truth: {truth['block']} should be blocked, {truth['review']} need a person to look, {truth['ok']} are harmless")
print(f"  plans the current CI stops: 0 of {len(plans)}")
print(f"  plans that apply a risky resource unchecked: {truth['block']} of {len(plans)}")
print("  risky plans by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
print("  Terraform accepts every one of them. The risk is found by a scanner after apply, or by someone else.")
