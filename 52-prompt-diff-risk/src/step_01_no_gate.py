"""Step 1 - Status quo: nothing runs when a system prompt changes.

Seventy pull requests each change the system prompt of one synthetic bank-support assistant. The unit
tests pass on all of them, because the tests exercise the code around the prompt, not what the assistant
says. This step merges all of them in turn. The data is synthetic (data/_generate.py): the truth label
of each pull request is the edit that was planted, and the probes that would fail after each edit are
planted too. No model was called, so those failures are simulated.

Run (from src/):  python3 step_01_no_gate.py
"""
from collections import Counter

from common import load_cases, load_world

cases = load_cases()
_catalogue, probes = load_world()
truth = Counter(c["truth"] for c in cases)
regress = [c for c in cases if c["fails"]]
failing = sum(len(c["fails"]) for c in cases)
slices = len({p["slice"] for p in probes})

print("STEP 1 - no gate on prompt changes")
print(f"  prompt pull requests merged: {len(cases)}   probes in the set: {len(probes)} in {slices} slices")
print(f"  truth: {truth['high']} high, {truth['medium']} medium, {truth['low']} low")
print(f"  pull requests that run any probe before merge: 0 of {len(cases)}")
print(f"  pull requests with at least one planted failing probe: {len(regress)} of {len(cases)}")
print(f"  planted failing probes that reach users unseen: {failing}")
print("  The assistant changes behavior in production, or not at all; the first signal is a customer.")
