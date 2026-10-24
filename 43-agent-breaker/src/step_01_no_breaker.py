"""Step 1 - Status quo: no automatic stop. An operator switch exists, and a person reads each agent's failure rate.

Five agents make 7,523 calls over three days. 25 faults were planted: 14 that a breaker should trip on, 7 that
it should not trip on, and 4 that it is expected to miss. The generator knows which calls did harm (the agent
failed, was wrong, or stepped outside its scope because of a fault). The person is a model with assumptions
(data/model_assumptions.csv): a review every 60 minutes, the same 0.50 failure rate as the breaker, a 120 minute
hold, so the manual numbers are modeled, not measured on anyone.

Run (from src/):  python3 step_01_no_breaker.py
"""
from collections import Counter

from common import evaluate, load_all, manual_run, no_stop_run, of_class, tripped

d = load_all()
a = d["assume"]
none = evaluate(d, no_stop_run(d), 0)
man = evaluate(d, manual_run(d), int(a["manual_lookback_min"]))
cls = Counter(f["cls"] for f in d["faults"])
must = of_class(man, "must_trip")
in_time = sum(1 for f in must if f["in_time"])

print("STEP 1 - no automatic stop; a person reads the failure rate every %d min (assumption)" % a["manual_review_interval_min"])
print(f"  agents: {len({e['agent'] for e in d['events']})}   calls: {none['calls']}   planted faults: {len(d['faults'])} "
      f"({cls['must_trip']} must trip, {cls['must_not_trip']} must not trip, {cls['hard_miss']} expected misses)")
print(f"  harmful calls with no stop at all: {none['harm_total']}, every one served")
print(f"  with the person: switch engaged for {tripped(must)} of {len(must)} must-trip faults, {in_time} of them while the fault was still running")
print(f"  with the person: harmful calls served {man['harm_served']} of {man['harm_total']}")
print(f"  with the person: harmless calls sent to the human queue {man['held_harmless']} (the switch stays on {int(a['manual_hold_min'])} min whatever happens)")
print("  In this model the person sees a rate up to an hour late, the switch comes off only when the hold ends, and nothing records why.")
