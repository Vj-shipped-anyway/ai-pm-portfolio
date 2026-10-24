"""Step 4 - The fix: agent_breaker.

The breaker adds, to the common one: a critical-failure path, a failure rate over a time window (scored only when
the window holds enough calls), a warn tier, a hold that doubles after a failed probe, three probes to close, an
operator switch that releases into probes, and a hash-chained log that a second run can reproduce line for line.
Parameters are in data/policy.csv; nothing is fitted to this stream, and the sensitivity block shows what moving
two of them does.

KNOWN LIMITS, left in on purpose: silent errors (the agent reports ok and is wrong), a slow burn below the trip
rate, and a low-volume agent whose window never holds enough calls.

Run (from src/):  python3 step_04_with_breaker.py
Output: a report, plus out/step_04_faults.csv, out/step_04_timeline.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from agent_breaker import CLOSED, FORCED_OPEN, OPEN, AuditLog, verify_log
from common import (OUT_DIR, basic_run, breaker_run, ensure_out, evaluate, load_all, manual_run, median_text, no_stop_run,
                    of_class, of_kind, tripped)

d = load_all()
grace = int(d["assume"]["justify_grace_min"])
none = evaluate(d, no_stop_run(d), 0)
man = evaluate(d, manual_run(d), int(d["assume"]["manual_lookback_min"]))
basic = evaluate(d, basic_run(d), grace)
run = breaker_run(d)
ev = evaluate(d, run, grace)
fleet = run["fleet"]
must, blips, hard = of_class(ev, "must_trip"), of_class(ev, "must_not_trip"), of_class(ev, "hard_miss")
avoided = ev["harm_total"] - ev["harm_served"]

print("STEP 4 - agent_breaker: critical path, failure rate, backoff, probes, operator switch, replayable log")
kinds = ", ".join(f"{k.replace('_', ' ')} {tripped(of_kind(ev, k))} of {len(of_kind(ev, k))}"
                  for k in ("scope_violation", "hard_outage", "brownout", "flapping"))
print(f"  must-trip faults tripped: {tripped(must)} of {len(must)} ({kinds})")
print(f"  median minutes from fault start to trip: {median_text([f['minutes_to_trip'] for f in must if f['tripped']])} "
      f"(common breaker: {median_text([f['minutes_to_trip'] for f in of_class(basic, 'must_trip') if f['tripped']])})")
tr = [e for e in fleet.log.events if e["kind"] == "transition"]
rules = Counter(e["data"]["rule"] for e in tr if e["data"]["from"] == CLOSED and e["data"]["to"] == OPEN)
print(f"  trips by rule: critical {rules['critical']}, consecutive {rules['consecutive']}, rate {rules['rate']}")
long_blips = [f["id"] for f in blips if f["tripped"]]
print(f"  must-not-trip faults tripped: {tripped(blips)} of {len(blips)} ({', '.join(long_blips) or 'none'}: "
      f"{'a run of 5 or 6 failures looks like an outage to a count' if long_blips else 'none'})")
print(f"  harmful calls served: no stop {none['harm_served']}, person {man['harm_served']}, common breaker {basic['harm_served']}, "
      f"this breaker {ev['harm_served']} of {ev['harm_total']} ({avoided} avoided, {100.0 * avoided / ev['harm_total']:.1f}%)")
print(f"  harmless calls sent to the human queue: person {man['held_harmless']}, common breaker {basic['held_harmless']}, "
      f"this breaker {ev['held_harmless']}; operator holds on purpose {ev['held_operator']}")
print(f"  harmless calls held per harmful call avoided: common breaker "
      f"{basic['held_harmless'] / (basic['harm_total'] - basic['harm_served']):.2f}, this breaker {ev['held_harmless'] / avoided:.2f}")

noise_probe_fails = sum(1 for e, r in zip(d["events"], run["records"]) if r["state"] == "HALF_OPEN" and e["outcome"] == "fail" and d["truth"][e["case"]][1] == 0)
lag = [f["recovery_lag"] for f in must if f["recovery_lag"] is not None]
still = sum(1 for f in must if f["tripped"] and f["recovery_lag"] is None)
print(f"  recovery: closed a median {median_text(lag)} min after the fault ended; {noise_probe_fails} probe failures were not harm "
      f"(background noise or a short blip); premature closes {ev['premature_closes']}; still held when the data ends {still}")
slow = of_kind(ev, "slow_burn")
warn_t = [e for e in fleet.log.events if e["kind"] == "warn"]
warned_slow = sum(1 for f in slow if any(w["agent"] == f["agent"] and f["start"] <= w["t"] <= f["end"] for w in warn_t))
print(f"  warns: {len(warn_t)}; slow-burn faults that raised a warn: {warned_slow} of {len(slow)}")
rel = [i for i, e in enumerate(tr) if e["data"]["rule"] == "operator_release"]
done = sum(1 for i in rel if next(x for x in tr[i + 1:] if x["agent"] == tr[i]["agent"])["data"]["rule"] == "probes_passed")
print(f"  operator switch: {sum(1 for c in d['controls'] if c['action'] == 'engage')} engaged, {len(rel)} released; "
      f"{done} of {len(rel)} closed only after {d['policy']['probe_calls']} good probe calls")

# ---- the log that proves it
lines = fleet.log.lines()
problems = verify_log(lines, d["policy"])
leaks = sum(1 for e in fleet.log.events if e["kind"] == "call" and e["data"]["route"] == "agent"
            and e["data"]["state"] in (OPEN, FORCED_OPEN))
kinds_n = {k: sum(1 for e in fleet.log.events if e["kind"] == k) for k in ("call", "transition", "warn", "control")}
print(f"  audit log: {len(lines)} events ({kinds_n['call']} calls, {kinds_n['transition']} transitions, {kinds_n['warn']} warns, "
      f"{kinds_n['control']} controls); {'chain intact, replay agrees' if not problems else problems[0]}; calls that reached the agent while open: {leaks}")


def verdict(found):
    return "not detected" if not found else "detected (" + found[0].split(":")[0] + ")"


mid = len(lines) // 2
edit = json.loads(lines[mid])
edit["t"] += 1
edited = lines[:mid] + [json.dumps(edit, sort_keys=True, ensure_ascii=True)] + lines[mid + 1:]
removed = lines[:mid] + lines[mid + 1:]
first_trip = next(i for i, e in enumerate(fleet.log.events) if e["kind"] == "transition" and e["data"]["to"] == OPEN)
forged = AuditLog()
for i, e in enumerate(fleet.log.events):
    if i != first_trip:
        forged.append(e["t"], e["agent"], e["kind"], e["data"])
cut = lines[:-100]
tests = [("edit one field in one line", verify_log(edited, d["policy"]), None),
         ("remove one line", verify_log(removed, d["policy"]), None),
         ("delete the first trip and re-hash every line after it", verify_log(forged.lines(), d["policy"]), None),
         ("cut the last 100 lines", verify_log(cut, d["policy"]), verify_log(cut, d["policy"], head=fleet.log.head))]
print("  tamper tests (without the stored head hash / with it):")
for name, plain, with_head in tests:
    print(f"    {name}: {verdict(plain)}" + (f" / {verdict(with_head)}" if with_head is not None else ""))
without_head = sum(1 for _, p, _ in tests if p)
with_head_n = sum(1 for _, p, h in tests if (h if h is not None else p))
print(f"    detected without the stored head hash: {without_head} of {len(tests)}; with it: {with_head_n} of {len(tests)}")

# ---- known limits
silent = sum(1 for e in d["events"] if e["outcome"] == "ok" and d["truth"][e["case"]][1] == 1)
sf = of_kind(ev, "silent_bad")
print("  KNOWN LIMITS, left in on purpose:")
print(f"    silent errors: {silent} of {ev['harm_total']} harmful calls were reported ok; silent-error faults tripped {tripped(sf)} of {len(sf)}")
print(f"    slow burn at a 0.28 failure rate: tripped {tripped(slow)} of {len(slow)}, harmful calls served {sum(f['harm_served'] for f in slow)} of {sum(f['harm'] for f in slow)}")
agent_calls, peak = {}, {}
for e in d["events"]:
    q = agent_calls.setdefault(e["agent"], [])
    q.append(e["t"])
    while q[0] <= e["t"] - d["policy"]["window_min"]:
        q.pop(0)
    peak[e["agent"]] = max(peak.get(e["agent"], 0), len(q))
low = [f for f in must if f["agent"] == "limit-review"]
print(f"    low-volume agent: limit-review never had more than {peak['limit-review']} calls in a {d['policy']['window_min']} min window "
      f"(the rate is scored from {d['policy']['min_window_calls']}); its must-trip faults tripped {tripped(low)} of {len(low)}")

print("  sensitivity, one change at a time from data/policy.csv:")
for name, values in (("trip_failure_rate", (0.3, 0.4, 0.5, 0.6, 0.7)), ("max_hold_min", (60, 120, 240))):
    for v in values:
        e = evaluate(d, breaker_run(d, dict(d["policy"], **{name: v})), grace)
        m, b = of_class(e, "must_trip"), of_class(e, "must_not_trip")
        print(f"    {name} {v}: must-trip tripped {tripped(m)} of {len(m)}, must-not-trip tripped {tripped(b)} of {len(b)}, "
              f"harmful served {e['harm_served']}, harmless held {e['held_harmless']}")

# ---- what the demo needs
ensure_out()
person_by = {f["id"]: f for f in man["faults"]}
basic_by = {f["id"]: f for f in basic["faults"]}
cols = ["fault_id", "agent", "kind", "truth_class", "start_min", "end_min", "harm_calls", "person_served", "common_served",
        "breaker_served", "common_tripped", "breaker_tripped", "breaker_minutes_to_trip", "breaker_recovery_lag"]
with open(os.path.join(OUT_DIR, "step_04_faults.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(cols)
    for f in ev["faults"]:
        w.writerow([f["id"], f["agent"], f["kind"], f["cls"], f["start"], f["end"], f["harm"], person_by[f["id"]]["harm_served"],
                    basic_by[f["id"]]["harm_served"], f["harm_served"], int(basic_by[f["id"]]["tripped"]), int(f["tripped"]),
                    "" if f["minutes_to_trip"] is None else f["minutes_to_trip"], "" if f["recovery_lag"] is None else f["recovery_lag"]])
last_t = d["events"][-1]["t"]
cur, segs = {}, []
for e in tr:
    state, since = cur.get(e["agent"], (CLOSED, 0))
    if state != CLOSED:
        segs.append((e["agent"], "breaker", state, since, e["t"]))
    cur[e["agent"]] = (e["data"]["to"], e["t"])
for agent, (state, since) in sorted(cur.items()):
    if state != CLOSED:
        segs.append((agent, "breaker", state, since, last_t))
segs += [(f["agent"], "fault", f["kind"], f["start"], f["end"]) for f in d["faults"]]
with open(os.path.join(OUT_DIR, "step_04_timeline.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["agent", "lane", "label", "start_min", "end_min"])
    w.writerows(sorted(segs, key=lambda s: (s[0], s[1], s[3])))
summary = {"minutes": last_t, "calls": ev["calls"], "harm_total": ev["harm_total"], "harm_person": man["harm_served"],
           "harm_common": basic["harm_served"], "harm_breaker": ev["harm_served"], "must_trip": len(must),
           "must_trip_tripped": tripped(must), "must_not_trip": len(blips), "must_not_trip_tripped": tripped(blips),
           "hard_miss": len(hard), "hard_miss_tripped": tripped(hard), "held_harmless_breaker": ev["held_harmless"],
           "held_harmless_common": basic["held_harmless"], "audit_events": len(lines), "tamper_detected_with_head": with_head_n,
           "tamper_tests": len(tests)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_faults.csv, step_04_timeline.csv and step_04_summary.json in src/out/")
