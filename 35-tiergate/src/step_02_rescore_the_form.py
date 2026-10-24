"""Step 2 - The common basic approach: re-add the rubric points on the form as written.

A reviewer, or a spreadsheet formula, takes the six answers on the form and applies the rubric. That
removes the sponsor's own shading of the result. It still trusts every answer on the form, and a blank
or 'unsure' customer-facing answer scores 0.

Run (from src/):  python3 step_02_rescore_the_form.py
"""
from __future__ import annotations

from common import form_as_written_tier, load_cases, metrics, pct

cases = load_cases()
declared = {c["use_case_id"]: c["self_declared_tier"] for c in cases}
rescored = {c["use_case_id"]: form_as_written_tier(c) for c in cases}
before, after = metrics(cases, declared), metrics(cases, rescored)
shaded = sum(1 for c in cases if declared[c["use_case_id"]] != rescored[c["use_case_id"]])
fixed = sum(1 for c in cases if declared[c["use_case_id"]] != c["reference_tier"] == rescored[c["use_case_id"]])
broken = sum(1 for c in cases if declared[c["use_case_id"]] == c["reference_tier"] != rescored[c["use_case_id"]])

print("STEP 2 - re-add the rubric points on the form as written")
print(f"  declared tier differs from the points on the form: {shaded} of {after['n']}")
print(f"  recomputed tier equals the reference: {after['exact']} of {after['n']} ({pct(after['exact'], after['n'])}); "
      f"declared was {before['exact']}")
print(f"  below the reference: {after['under']}; above: {after['over']}")
print(f"  tier 3-4 forms recomputed at tier 3-4: {after['full_caught']} of {after['full']} "
      f"({pct(after['full_caught'], after['full'])}); declared was {before['full_caught']}")
print(f"  forms this fixes: {fixed}; forms it makes wrong that the declared tier had right: {broken}")
print("  Every answer on the form is still taken as true.")
