"""Step 2 - The common basic approach: Erlang C on the mean arrival rate and the mean handling time.

Erlang C is the textbook formula for a queue with identical servers. It takes one arrival rate and one mean
handling time and assumes arrivals come independently and handling times are exponential. This step sizes
each queue as the smallest number of reviewers for which Erlang C meets the queue's wait target and stays
within the utilization cap, then replays days 11 to 20 against that number. The opening batch, where a
queue has one, is averaged into the arrival rate, as a dashboard would.

Run (from src/):  python3 step_02_erlang_c.py
"""
from common import load_world, score
from review_capacity import required_seats

world = load_world()
seats = {q["queue_id"]: required_seats(q, use_variability=False, use_batch=False) for q in world}
s = score(world, seats)

print("STEP 2 - Erlang C on the mean rate")
print(f"  queues that meet both limits on the replay: {s['meets']} of {s['queues']}")
print(f"  matches the true number of reviewers: {s['exact']} of {s['queues']}; within one: {s['within_one']} of {s['queues']}")
print(f"  queues with too few reviewers: {len(s['under'])}; with too many: {len(s['over'])}")
print(f"  reviewers at the desk: {s['seats']} chosen, {s['true_seats']} needed")
print(f"  cases that waited past their target: {s['late']} of {s['cases']} ({100.0 * s['late'] / s['cases']:.1f}%)")
for q in s["under"]:
    r = s["results"][q["queue_id"]]
    print(f"    short: {q['queue_id']} ({q['kind']}) {seats[q['queue_id']]} against {q['true_seats']}, "
          f"{100.0 * r['late_share']:.1f}% late against {100.0 * (1 - q['target_share']):.0f}% allowed")
for q in s["over"]:
    print(f"    spare: {q['queue_id']} ({q['kind']}) {seats[q['queue_id']]} against {q['true_seats']}")
print("  Erlang C is right when arrivals are independent. A batch that lands at open is not independent.")
