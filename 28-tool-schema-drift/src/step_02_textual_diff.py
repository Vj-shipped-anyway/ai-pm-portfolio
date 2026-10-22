"""Step 2 - The common basic approach: flag every change in the schema file.

A text diff on the schema file is the first thing a team adds. Every pull request that touches a
schema is flagged, and a person reads each one. The truth label is known, so this step counts how
many of those reads were needed.

Run (from src/):  python3 step_02_textual_diff.py
"""
from common import load_cases
from collections import Counter

cases = load_cases()
flagged = [c for c in cases if c["old_text"] != c["new_text"]]
by_truth = Counter(c["truth"] for c in flagged)
needless = len(flagged) - by_truth["breaking"] - by_truth["behavior_risk"]
cosmetic = [c for c in cases if c["kind"] in ("reword", "version_only")]

print("STEP 2 - flag every textual change")
print(f"  pull requests flagged: {len(flagged)} of {len(cases)}")
print(f"  of those, breaking: {by_truth['breaking']}, behavior-risk: {by_truth['behavior_risk']}, harmless: {needless}")
print(f"  share of flags that are harmless: {needless / len(flagged):.1%}")
print(f"  cosmetic changes alone (rewording, version bump): {len(cosmetic)} of {len(cases)}")
print("  Nothing separates a rename that breaks every call from a comment that was reworded.")
