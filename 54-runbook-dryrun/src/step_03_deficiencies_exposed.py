"""Step 3 - Where each part fails when used alone.

The dry-run tool has three parts, and each is run here by itself on the same 94 cases:
  lint    defects in the runbook text, with no snapshot and no approvals
  state   the snapshot and the `sets` each step declares, with no lint and no gate
  gate    the approval records against each gated step, with no lint and no snapshot

KNOWN LIMIT, left in on purpose: a runbook that mislabels a step (a write declared as a read) and a
snapshot that goes stale before the run both pass all three parts, and step 4 does not catch them either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""

from __future__ import annotations

from collections import Counter

from common import load_cases, run_case

cases = load_cases()
bad = [c for c in cases if c["truth"] == "BLOCKED"]
fine = [c for c in cases if c["truth"] != "BLOCKED"]


def score(name, part):
    got = {c["case_id"]: run_case(c, (part,))["verdict"] for c in cases}
    caught = [c for c in bad if got[c["case_id"]] == "BLOCKED"]
    wrong = [c for c in fine if got[c["case_id"]] == "BLOCKED"]
    print(f"  {name}")
    print(f"    blocked cases caught: {len(caught)} of {len(bad)}")
    print(f"    clean or waiting cases blocked wrongly: {len(wrong)} of {len(fine)}")
    print("    caught: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in caught).items())))
    return {c["case_id"] for c in caught}


print("STEP 3 - each part alone")
found = score("lint only (no snapshot, no approvals)", "lint")
found |= score("state only (no lint, no gate)", "state")
found |= score("gate only (no lint, no snapshot)", "gate")
missed = [c for c in bad if c["case_id"] not in found]
print(f"  blocked cases caught by at least one part: {len(found)} of {len(bad)}")
print(f"  blocked cases that pass every part: {len(missed)} of {len(bad)}")
print("  by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in missed).items())))
print("  No part sees a step that lies about its effect, or a snapshot that moved after it was taken.")
