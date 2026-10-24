"""Step 1 - Status quo: the tier the sponsor wrote on the form is the tier the form gets.

Two hundred intake forms arrive. Each carries a self-declared tier, and that tier decides how deep the
review goes: tier 3 and 4 get the full review, tier 1 and 2 a light one (my assumption for this
prototype). The reference tier is the written rubric applied to the TRUE inputs, which the generator
knows and the tool never sees (data/_generate.py). This step scores the declared tier against it.

Run (from src/):  python3 step_01_declared_tier.py
"""
from __future__ import annotations

from collections import Counter

from common import FULL_REVIEW_TIER, load_cases, metrics, pct

cases = load_cases()
declared = {c["use_case_id"]: c["self_declared_tier"] for c in cases}
m = metrics(cases, declared)
by_ref = Counter(c["reference_tier"] for c in cases)
light = [c for c in cases if c["reference_tier"] >= FULL_REVIEW_TIER and c["self_declared_tier"] < FULL_REVIEW_TIER]

print("STEP 1 - the declared tier is taken as given")
print(f"  intake forms: {m['n']}   reference tiers 1/2/3/4: " + " / ".join(str(by_ref[t]) for t in (1, 2, 3, 4)))
print(f"  declared tier equals the reference: {m['exact']} of {m['n']} ({pct(m['exact'], m['n'])})")
print(f"  declared below the reference: {m['under']}; above: {m['over']}")
print(f"  tier 3-4 forms by the reference: {m['full']}; declared at tier 3-4 and sent to full review: "
      f"{m['full_caught']} of {m['full']} ({pct(m['full_caught'], m['full'])})")
print(f"  tier 3-4 forms that get the light review: {len(light)}")
print("  Nobody recomputes the tier, so the form is the only evidence anyone looks at.")
