"""Step 2 - The common basic approaches: read every prompt change, or run every probe on every change.

A. Flag every pull request that touches the prompt file and have a person read the diff. A text diff
   flags anything that differs, so every pull request is flagged.
B. Run the full probe set on every pull request. Nothing is missed, and the cost is the whole set each time.
The truth label is known, so this step counts how many of those reads and runs were needed.

Run (from src/):  python3 step_02_basic_approach.py
"""
from collections import Counter

from common import load_cases, load_world

cases = load_cases()
_catalogue, probes = load_world()
flagged = [c for c in cases if c["old"] != c["new"]]
by_truth = Counter(c["truth"] for c in flagged)
regress = [c for c in cases if c["fails"]]
full_runs = len(cases) * len(probes)
wasted = by_truth["low"] * len(probes)

print("STEP 2 - the common basic approaches")
print("  A. a person reads every prompt change")
print(f"     pull requests flagged: {len(flagged)} of {len(cases)}")
print(f"     of those, high: {by_truth['high']}, medium: {by_truth['medium']}, harmless: {by_truth['low']}")
print(f"     share of flags that are harmless: {by_truth['low'] / len(flagged):.1%}")
print("  B. run the full probe set on every prompt change")
print(f"     pull requests with a planted failing probe that the run catches: {len(regress)} of {len(regress)}")
print(f"     probes run: {full_runs} ({len(cases)} pull requests x {len(probes)} probes)")
print(f"     probes run on harmless pull requests: {wasted}")
print("  A puts a read on every pull request and B pays for the whole set on every change. Neither says which probes matter for this change.")
