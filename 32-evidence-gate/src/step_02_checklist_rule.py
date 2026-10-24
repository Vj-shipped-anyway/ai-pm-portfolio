"""Step 2 - The common basic approach: require every checkbox in the description to be ticked.

This is what a task-list check does. It finds the checkboxes in the pull request description and fails
the check when one is unticked, or when there is none. It does not know which items the tier requires,
what a ticked box points at, or how old the evidence is. The truth label is known, so this step counts
what it stops and what it lets through.

Run (from src/):  python3 step_02_checklist_rule.py
"""
import re
from collections import Counter

from common import load_cases

BOX = re.compile(r"^\s*[-*+]\s+\[([ xX])\]", re.MULTILINE)


def checklist_passes(body: str) -> bool:
    boxes = BOX.findall(body)
    return bool(boxes) and all(b != " " for b in boxes)


cases = load_cases()
passed = {c["pr_id"]: checklist_passes(c["body"]) for c in cases}
bad = [c for c in cases if c["truth"] == "should_block"]
fine = [c for c in cases if c["truth"] == "fine"]
review = [c for c in cases if c["truth"] == "needs_review"]
slipped = [c for c in bad if passed[c["pr_id"]]]

print("STEP 2 - every checkbox ticked")
print(f"  pull requests that pass the check: {sum(passed.values())} of {len(cases)}")
print(f"  should-block pull requests stopped: {len(bad) - len(slipped)} of {len(bad)}")
print(f"  should-block pull requests that pass: {len(slipped)} of {len(bad)}")
print(f"  fine pull requests stopped: {sum(1 for c in fine if not passed[c['pr_id']])} of {len(fine)}")
print(f"  wrong-tier-label pull requests noticed: 0 of {len(review)} (the rule never reads the tier)")
print("  passed anyway, by planted defect: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in slipped).items())))
print("  A deleted line looks the same whether the item did not apply or the author skipped it, and a ticked box can point at nothing.")
