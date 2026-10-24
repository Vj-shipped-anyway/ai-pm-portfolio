"""Step 1 - Status quo: staff each queue to its average workload.

Thirteen synthetic review queues, each with a service target (a share of cases that must start review
within a wait) and a cap on how busy a reviewer may be. The common spreadsheet answer is to divide the work
that arrives in a day by the minutes in a shift and round up. This step does that, then replays the cases
of days 11 to 20 first come first served and counts what the reviewers would have met. The assumptions are
measured on the same ten days, so a miss here is the method's and not a forecast's. The planted truth
(data/queue_truth.csv) is the smallest number of reviewers at the desk that meets both limits on that replay.

Run (from src/):  python3 step_01_average_workload.py
"""
from common import load_world, average_load_seats, score

world = load_world()
seats = {q["queue_id"]: average_load_seats(q) for q in world}
s = score(world, seats)

print("STEP 1 - staff to the average workload")
print(f"  queues: {s['queues']}   cases replayed: {s['cases']}   days replayed: 11 to 20")
print(f"  reviewers at the desk: {s['seats']} chosen, {s['true_seats']} needed (smallest count that meets both limits)")
print(f"  queues that meet the wait target: {s['wait_ok']} of {s['queues']}")
print(f"  queues within the utilization cap: {s['util_ok']} of {s['queues']}")
print(f"  queues that meet both: {s['meets']} of {s['queues']}")
print(f"  queues staffed below the need: {len(s['under'])} of {s['queues']}")
print(f"  cases that waited past their target: {s['late']} of {s['cases']} ({100.0 * s['late'] / s['cases']:.1f}%)")
worst = max(world, key=lambda q: s["results"][q["queue_id"]]["late_share"])
w = s["results"][worst["queue_id"]]
print(f"  worst queue: {worst['queue_id']}, {seats[worst['queue_id']]} reviewers against {worst['true_seats']} needed, "
      f"{100.0 * w['late_share']:.1f}% of cases late against {100.0 * (1 - worst['target_share']):.0f}% allowed")
print("  Average workload leaves no slack for cases that arrive together or take long, so the queue absorbs it.")
