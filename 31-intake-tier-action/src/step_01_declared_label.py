"""Step 1 - Status quo: the sponsor's declared tier becomes the label.

An intake issue comes in. Someone reads the declared tier on the form and puts it on the issue as a
label. Nothing recomputes it. This step reads the declared tier on each of the 160 synthetic issues and
scores it against the reference tier, which is the written rubric applied to the TRUE attributes of the
use case (data/_generate.py). Every issue is read by a person.

Run (from src/):  python3 step_01_declared_label.py
"""
from collections import Counter

from common import load_issues, naive_field

issues = load_issues()
ref = Counter(i["ref"] for i in issues)
rows = []
for i in issues:
    d = naive_field(i["body_v1"], "Declared tier")
    rows.append((i, int(d) if d in ("1", "2", "3", "4") else None))
labeled = [(i, d) for i, d in rows if d is not None]
hi = [(i, d) for i, d in labeled if i["ref"] >= 3]
print("STEP 1 - the declared tier becomes the label")
print(f"  issues: {len(issues)}   reference tiers: " + ", ".join(f"{t} {ref[t]}" for t in (1, 2, 3, 4)))
print(f"  issues with a readable declared tier: {len(labeled)} of {len(issues)}")
print(f"  declared tier equals the reference tier: {sum(1 for i, d in labeled if d == i['ref'])} of {len(labeled)}")
print(f"  declared below the reference: {sum(1 for i, d in labeled if d < i['ref'])}; above: {sum(1 for i, d in labeled if d > i['ref'])}")
print(f"  tier 3-4 issues declared at tier 1-2: {sum(1 for i, d in hi if d < 3)} of {len(hi)}")
print(f"  issues a person has to read to know the tier: {len(issues)} of {len(issues)}")
print("  The label is the sponsor's own answer, so the use cases most likely to be under-declared are labeled lowest.")
