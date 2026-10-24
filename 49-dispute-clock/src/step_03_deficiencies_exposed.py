"""Step 3 - Where the countdown goes wrong, and what is left after the fixes.

Two things differ between step 2 and the tool: business-day arithmetic (weekends and the holiday file
are skipped, as the policy says) and the start date (first contact, not the day the case was logged).
This step switches each one on alone, then both, and scores the statuses against the planted truth.

KNOWN LIMIT, left in on purpose: with both fixes on, a few statuses still differ. Most are disputes where
the bank paused the investigation to wait for the customer (info_requested_on to info_received_on); the
tool does not read the pause. The rest are disputes recorded as extended where the longer window never
applied; the tool trusts the recorded class. Step 4 fixes neither.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from collections import Counter

from common import disagreements, is_missed, load_world, stand_in_statuses

world = load_world()
truth = world["truth"]
variants = [("step 2 method", False, "logged_on"), ("business days only", True, "logged_on"),
            ("first-contact start only", False, "first_contact_on"), ("both fixes", True, "first_contact_on")]

print("STEP 3 - which fix removes which error")
results = {}
for name, business_days, start_field in variants:
    results[name] = stand_in_statuses(world, business_days, start_field)
    print(f"  {name}: {len(disagreements(results[name], world))} wrong of {len(truth)}")

base = results["step 2 method"]
print("  step 2 errors on each kind of planted hard case (wrong / clocks of that kind):")
for tag in ("boundary", "holiday", "logged_late", "pause", "misrecorded"):
    keys = sorted(k for k, t in truth.items() if tag in t["tags"])
    wrong = [k for k in keys if base[k] != truth[k]["status"]]
    print(f"    {tag:<12} {len(wrong)} / {len(keys)}")

left = disagreements(results["both fixes"], world)
final = results["both fixes"]
false_alarm = [k for k in left if is_missed(final[k]) and not is_missed(truth[k]["status"])]
silent = [k for k in left if is_missed(truth[k]["status"]) and not is_missed(final[k])]
print(f"  KNOWN LIMIT: with both fixes, {len(left)} statuses still differ from the planted truth")
print(f"    called missed, plan says not: {len(false_alarm)} "
      f"({sum(1 for k in false_alarm if 'pause' in truth[k]['tags'])} on paused investigations)")
print(f"    missed clocks called fine: {len(silent)} "
      f"({sum(1 for k in silent if 'misrecorded' in truth[k]['tags'])} on a wrongly recorded window class)")
kinds = Counter((final[k], truth[k]["status"]) for k in left)
for (got, want), n in sorted(kinds.items()):
    print(f"    tool says {got}, plan says {want}: {n}")
print("    " + ", ".join(f"{k[0]} {k[1]}" for k in left))
print("  A clock cannot tell that the bank was waiting for the customer, or that a window was recorded wrong, from dates alone.")
