"""Step 3 - Where the gate fails when a part is taken away, and what it still cannot see.

The parser is the same in every row. Each row removes one input from the full gate:
  no registry      the tier is whatever the author declares
  no file listing  a reference is accepted without checking that the file is in the repository
  no dates         evidence is accepted at any age, including a date in the future
  parser only      all three removed: the record is read, and ticked boxes need only a reference text
The truth is known, so each row is scored on the same pull requests. KNOWN LIMIT, left in on
purpose: a reference to a real file that holds another use case's evidence, and a registry that holds a
use case too low, are not caught by the full gate either. The last lines print them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_cases, load_world, run_gate

cases, world = load_cases(), load_world()
bad = [c for c in cases if c["truth"] == "should_block"]
fine = [c for c in cases if c["truth"] == "fine"]


def score(name: str, **parts) -> None:
    got = {c["pr_id"]: run_gate(c, world, **parts)["decision"] for c in cases}
    slipped = [c for c in bad if got[c["pr_id"]] != "BLOCK"]
    print(f"  {name}")
    print(f"    should-block pull requests blocked: {len(bad) - len(slipped)} of {len(bad)}")
    print(f"    fine pull requests blocked: {sum(1 for c in fine if got[c['pr_id']] == 'BLOCK')} of {len(fine)}")
    print("    not blocked, by planted defect: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c["kind"] for c in slipped).items())))


print("STEP 3 - the gate with one input removed")
score("without the registry", registry=False)
score("without the file listing", files=False)
score("without the dates", dates=False)
score("parser only", registry=False, files=False, dates=False)
full = {c["pr_id"]: run_gate(c, world) for c in cases}
allowed = [c for c in bad if full[c["pr_id"]]["decision"] == "ALLOW"]
to_review = [c for c in bad if full[c["pr_id"]]["decision"] == "REVIEW"]
print(f"  KNOWN LIMIT - should-block pull requests the full gate allows: {len(allowed)} of {len(bad)}")
for kind, n in sorted(Counter(c["kind"] for c in allowed).items()):
    print(f"    {kind} {n}: " + ", ".join(c["pr_id"] for c in allowed if c["kind"] == kind))
print(f"  should-block pull requests the full gate only sends to review: {len(to_review)} of {len(bad)} ({', '.join(sorted({c['kind'] for c in to_review}))})")
print("  The file listing proves a file is there, not what it says. The registry is only as current as its owner keeps it.")
