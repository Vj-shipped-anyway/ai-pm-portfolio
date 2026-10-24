"""Step 2 - The common basic approach: an issue form and a workflow that reads it with a regex.

The workflow takes the text under each heading, adds up the rubric points on the values as written, and
adds a tier label. It is what most teams would write first. It makes no check against the data catalog
or the vendor registry, treats a missing or unreadable value as 0 points, and always adds a label.

Run (from src/):  python3 step_02_form_and_regex.py
"""
from collections import Counter

from common import load_issues, naive_assess

issues = load_issues()
res = [(i, naive_assess(i["body_v1"])) for i in issues]
hi = [(i, r) for i, r in res if i["ref"] >= 3]
print("STEP 2 - issue form, regex, additive label")
print(f"  tier labels added: {len(res)} of {len(issues)}; needs-info labels added: 0")
print(f"  tier equals the reference tier: {sum(1 for i, r in res if r['tier'] == i['ref'])} of {len(issues)}")
print(f"  tier below the reference: {sum(1 for i, r in res if r['tier'] < i['ref'])}; above: {sum(1 for i, r in res if r['tier'] > i['ref'])}")
print(f"  tier 3-4 issues labeled tier 1-2: {sum(1 for i, r in hi if r['tier'] < 3)} of {len(hi)}")
print(f"  labeled with fewer than 5 of the 5 required inputs read: {sum(1 for i, r in res if r['found'] < 5)} of {len(issues)}")
print("  labeled tier by kind of body: " + ", ".join(f"{k} {n}" for k, n in sorted(Counter(i['kind'] for i, r in res if r['found'] < 5).items())))
print("  The workflow never says it could not read an issue.")
