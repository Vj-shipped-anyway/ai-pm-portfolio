"""Step 2 - The common basic approach: a countdown per clock, in calendar days, from the logged date.

A team that outgrows the flat target adds one due date per step: acknowledgement, credit, investigation,
final notice, each with its own window from the policy file. The quick version counts every window in
calendar days and starts the count on the day the case was logged. It uses the same policy file and
the same dates as the tool in step 4; only the counting differs.

Run (from src/):  python3 step_02_calendar_countdown.py
"""
from __future__ import annotations

from collections import Counter

from common import disagreements, is_missed, load_world, pct, stand_in_statuses

world = load_world()
truth = world["truth"]
got = stand_in_statuses(world, business_days=False, start_field="logged_on")
wrong = disagreements(got, world)
false_alarm = [k for k in wrong if is_missed(got[k]) and not is_missed(truth[k]["status"])]
missed_clock = [k for k in wrong if is_missed(truth[k]["status"]) and not is_missed(got[k])]
seen = sum(1 for k, t in truth.items() if is_missed(t["status"]) and is_missed(got[k]))
total_missed = sum(1 for t in truth.values() if is_missed(t["status"]))

print("STEP 2 - calendar-day countdown from the logged date")
print(f"  statuses that match the planted truth: {len(truth) - len(wrong)} of {len(truth)} ({pct(len(truth) - len(wrong), len(truth))})")
print(f"  missed clocks found: {seen} of {total_missed}")
print(f"  called missed, truth says not: {len(false_alarm)}")
print(f"  called fine or not due, truth says missed: {len(missed_clock)}")
by_clock = Counter(k[1] for k in wrong)
print("  wrong statuses by clock: " + ", ".join(f"{c['clock_id']} {by_clock[c['clock_id']]}" for c in world["policy"]))
print("  The countdown runs, but it counts days the policy does not count and starts on a day the policy does not name.")
