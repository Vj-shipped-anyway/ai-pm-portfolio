"""Step 1 - Status quo: one flat target per case.

A case-management queue gives every dispute one target date: 30 calendar days from the day the case
was logged. It turns red when the case is still open past that date, or was closed after it. This
step reads the planted truth (data/truth.csv) and counts what that single target can and cannot see.

Run (from src/):  python3 step_01_flat_target.py
"""
from __future__ import annotations

import datetime as dt
from collections import Counter

from common import FLAT_TARGET_DAYS, INVESTIGATION, is_missed, load_world

world = load_world()
as_of, truth = world["as_of"], world["truth"]


def flagged(d: dict) -> bool:
    target = d["dates"]["logged_on"] + dt.timedelta(days=FLAT_TARGET_DAYS)
    done = d["dates"]["concluded_on"]
    return done > target if done else as_of > target


flags = {d["dispute_id"]: flagged(d) for d in world["disputes"]}
status = Counter(t["status"] for t in truth.values())
missed = sorted(k for k, t in truth.items() if is_missed(t["status"]))
shown = [k for k in missed if k[1] in INVESTIGATION and flags[k[0]]]
flag_without_miss = sorted(i for i, f in flags.items() if f and not any(k[0] == i for k in missed))
by_clock = {c["clock_id"]: [k for k in missed if k[1] == c["clock_id"]] for c in world["policy"]}

print("STEP 1 - one flat target per case")
print(f"  disputes: {len(world['disputes'])}   clocks that apply: {len(truth)}   read as of {as_of.isoformat()}")
print(f"  planted truth: missed {len(missed)} (late {status['late']}, breached {status['breached']}); "
      f"running {status['running']}; not started {status['not_started']}; on time {status['on_time']}")
print(f"  the queue's target is {FLAT_TARGET_DAYS} calendar days from the day the case was logged")
print(f"  disputes the queue flags past target: {sum(flags.values())} of {len(flags)}")
print(f"  missed clocks the queue shows: {len(shown)} of {len(missed)}")
for cid, ks in by_clock.items():
    seen = sum(1 for k in ks if k in shown)
    print(f"    {cid}: {seen} of {len(ks)} shown")
print(f"  disputes flagged although none of their clocks was missed: {len(flag_without_miss)}")
print("  The target knows one window. It cannot tell an acknowledgement from a final notice.")
