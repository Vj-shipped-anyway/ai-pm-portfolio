"""Step 1 - Status quo: the shadow run is reported as one number.

An agent triaged 1,000 card-dispute cases in shadow mode. People recorded their own outcome for
most of them. The report that goes to the steering group says how often the two agree. This step
produces that report the way it is usually produced: join on case_id, drop the cases the agent did
not propose on, count agreements. The data is synthetic (data/_generate.py).

Run (from src/):  python3 step_01_one_number.py
"""
from collections import Counter

from common import load, joined, planted

proposals, outcomes = load()
rows = joined()
proposed = [r for r in rows if r["proposed"]]
agree = sum(1 for r in proposed if r["kind"] == "agree")
disagree = [r for r in proposed if r["kind"] != "agree"]

print("STEP 1 - the shadow run as it is reported today")
print(f"  cases triaged by the agent: {len(proposals)}   outcomes recorded by people: {len(outcomes)}")
print(f"  cases with both: {len(rows)}   proposals still waiting for an outcome: {len(proposals) - len(rows)}"
      f"   outcomes with no proposal: {len(outcomes) - len(rows)}")
print(f"  the agent made no proposal on {len(rows) - len(proposed)} of the {len(rows)}")
print(f"  the report: agreed on {agree} of {len(proposed)} proposals ({agree / len(proposed):.1%})")
print(f"  disagreements a person would have to read to find out why: {len(disagree)}")
kinds = Counter(r["kind"] for r in disagree)
print(f"    different outcome: {kinds['disagree_outcome']}   same outcome, different value: {kinds['disagree_value']}")
print(f"  what the report splits the number by: nothing. The cases fall in "
      f"{len({r['segment'] for r in rows})} segments, {len({r['week'] for r in rows})} weeks, "
      f"{len({r['reviewer'] for r in rows})} reviewers and {len({r['human'] for r in rows})} outcome classes.")
print(f"  planted in the data for later steps: {sum(1 for p in planted() if p['real'] == '1')} problems "
      f"and {sum(1 for p in planted() if p['real'] == '0')} look-alikes that are not problems.")
