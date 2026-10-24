"""Step 3 - Where the common breaker fails, and the one limit that stays.

Five deficiencies of "N failures in a row, fixed hold, one probe", each measured on the same stream, then the
known limit. KNOWN LIMIT, left in on purpose: an agent that reports ok and is wrong is invisible to a breaker
that reads outcomes. Step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import re

from common import basic_run, evaluate, load_all, median_text, of_class, of_kind, tripped

d = load_all()
grace = int(d["assume"]["justify_grace_min"])
run = basic_run(d)
ev = evaluate(d, run, grace)


def served(faults):
    return sum(f["harm_served"] for f in faults), sum(f["harm"] for f in faults)


print("STEP 3 - what the common breaker gets wrong")
scope = of_kind(ev, "scope_violation")
print(f"  1. No critical path: a call outside the agent's scope is one failure, not five. Scope-violation faults tripped: "
      f"{tripped(scope)} of {len(scope)}; harmful calls served in them {served(scope)[0]} of {served(scope)[1]}")
shaped = of_kind(ev, "brownout") + of_kind(ev, "flapping")
print(f"  2. No failure rate: a brownout or flapping must string 5 failures together before it is seen. Tripped {tripped(shaped)} of {len(shaped)}, "
      f"median {median_text([f['minutes_to_trip'] for f in shaped if f['tripped']])} min after the start; "
      f"harmful calls served in them {served(shaped)[0]} of {served(shaped)[1]}")
print(f"  3. One probe closes too early: {len(run['closes'])} closes, {ev['premature_closes']} followed by a new trip within "
      f"{int(d['assume']['premature_close_window_min'])} min")
print("  4. The one knob trades one error for another (failures in a row needed to trip):")
for k in (3, 5, 8):
    e = evaluate(d, basic_run(d, consecutive=k), grace)
    m, b = of_class(e, "must_trip"), of_class(e, "must_not_trip")
    print(f"       k={k}: must-trip tripped {tripped(m)} of {len(m)}, must-not-trip tripped {tripped(b)} of {len(b)}, "
          f"harmless calls held {e['held_harmless']}")
rows = sorted([(t, a, "OPEN") for a, t in run["trips"]] + [(t, a, "CLOSED") for a, t in run["closes"]])
plain = [f"t={t} {a} {s}" for t, a, s in rows]
edited = [plain[0].replace("OPEN", "CLOSED")] + plain[1:]
dropped = plain[:5] + plain[6:]
cut = plain[:-5]
well_formed = sum(all(re.fullmatch(r"t=\d+ \S+ (OPEN|CLOSED)", x) for x in log) for log in (edited, dropped, cut))
print(f"  5. A plain log can be rewritten: {len(plain)} lines of state changes, no reason on any of them. After editing a line, "
      f"dropping a line, or cutting the tail, {well_formed} of 3 logs are still well formed and nothing can say they changed")
silent = sum(1 for e in d["events"] if e["outcome"] == "ok" and d["truth"][e["case"]][1] == 1)
sf = of_kind(ev, "silent_bad")
print("  KNOWN LIMIT, left in on purpose:")
print(f"    {silent} of {ev['harm_total']} harmful calls were reported ok by the agent. Silent-error faults tripped: "
      f"{tripped(sf)} of {len(sf)}. Step 4 does not change this.")
