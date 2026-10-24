"""Step 1 - Status quo: nothing ties the numbers in a README to the output of its scripts.

Forty small projects each have a README with green-circle bullets and scripts that print numbers.
The tests pass and the scripts run, so CI is green whatever the README says. This step counts what
that lets through. The data is synthetic (data/_generate.py); the label on each bullet comes from how
the bullet was built (copied from the output, or altered on purpose).

Run (from src/):  python3 step_01_no_check.py
"""
from collections import Counter

from common import extract_claims, load_projects, load_truth

projects, truth = load_projects(), load_truth()
bad = [r for r in truth if r["expected"] == "flag"]
numbers = sum(len(extract_claims(p["readme"])) for p in projects)
kinds = Counter(r["kind"] for r in bad)

print("step_01_no_check.py - no check between README numbers and script output")
print(f"  projects: {len(projects)}   green bullets: {len(truth)} ({len(bad)} cite a number no script prints, {len(truth) - len(bad)} are fine)")
print(f"  numbers after a green circle a reviewer would compare by hand: {numbers}")
print(f"  bullets the current CI stops: 0 of {len(bad)}")
print("  planted wrong bullets by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
print("  A reader finds out when someone reruns a script and the number has moved, or never.")
