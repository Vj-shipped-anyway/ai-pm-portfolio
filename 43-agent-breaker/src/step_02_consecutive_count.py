"""Step 2 - The common basic approach: count failures in a row, open for a fixed time, let one probe through.

Per agent (the agent is a field in the data). Trip after 5 failures in a row, hold 30 minutes, then let the next
call through as a single probe; close if it succeeds, open for another 30 minutes if it fails. No window, no
critical failures, no growing hold, no log beyond the state in memory. The 5 and the 30 are the same numbers the
step 4 breaker starts from (data/policy.csv), so the comparison is about the rules, not the settings.

Run (from src/):  python3 step_02_consecutive_count.py
"""
from common import basic_run, evaluate, load_all, median_text, of_class, tripped

d = load_all()
ev = evaluate(d, basic_run(d), int(d["assume"]["justify_grace_min"]))
must, blips = of_class(ev, "must_trip"), of_class(ev, "must_not_trip")
ttt = [f["minutes_to_trip"] for f in must if f["tripped"]]

print("STEP 2 - 5 failures in a row, a fixed 30 min hold, one probe")
print(f"  trips: {ev['trips']}   must-trip faults tripped: {tripped(must)} of {len(must)}   must-not-trip faults tripped: {tripped(blips)} of {len(blips)}")
print(f"  harmful calls served: {ev['harm_served']} of {ev['harm_total']} ({ev['harm_total'] - ev['harm_served']} avoided)")
print(f"  harmless calls sent to the human queue: {ev['held_harmless']}")
print(f"  median minutes from fault start to trip, on the faults it tripped: {median_text(ttt)}")
print("  Better than a person on a schedule. It still misses faults that fail in a different shape; step 3 lists them.")
