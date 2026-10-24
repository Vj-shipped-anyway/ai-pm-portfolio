"""Step 2 - The common basic approach: the annual access review.

Once a year the agent's manager gets the list of grants and approves what is on it. The list has no
usage column and nobody opens the call log.

ASSUMPTIONS (modeled):
  R1  a grant with a ticket reference is approved; a grant with none is revoked
  R2  the reviewer does not look at the calls
  R3  one pass a year; this run is that pass

Because the data is synthetic, the script can score the removals against the truth and replay the
calls under what the review left in place.

Run (from src/):  python3 step_02_annual_review.py
"""
from common import load_world, annual_review

w = load_world()
rev = annual_review(w)
needed = w["needed"]
removed = sorted(rev["removed"])
unneeded = {k for k, v in needed.items() if not v["needed"]}
holders = {g["agent_id"] for g in w["grants"]}
agents_untouched = len(holders) - len({a for a, _ in removed})

print("STEP 2 - the annual access review")
print("  assumptions (modeled): R1 approve a grant with a ticket, revoke one without; R2 the call log is not opened; R3 one pass a year")
print(f"  approved: {len(w['grants']) - len(removed)} of {len(w['grants'])} grants")
print(f"  removed: {len(removed)} of {len(w['grants'])} grants, every one for a missing ticket")
print(f"  grants the agent does not need: {len(unneeded)}; removed by the review: {len(unneeded & rev['removed'])} of {len(unneeded)}")
print(f"  grants the agent needs that the review removed: {len(rev['removed'] - unneeded)}")
print(f"  agents whose whole list was approved: {agents_untouched} of {len(holders)}")
for a, s in removed:
    v = needed[(a, s)]
    print(f"    removed {a} {s}: {'needed (' + v['basis'] + ')' if v['needed'] else 'not needed (' + v['basis'] + ')'}")
print(f"  dry run of the {max(c['day'] for c in w['calls'])} days of calls under what the review left in place: "
      f"{rev['denied']} of {len(w['calls'])} calls denied")
print("  The review checks that a ticket exists. It does not check that the access is used.")
