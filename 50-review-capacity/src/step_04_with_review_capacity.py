"""Step 4 - The fix: the tool's sizing, with variability and the opening batch both in.

Per queue the tool raises the number of reviewers until the modeled late share is within the target and
utilization is within the cap (review_capacity.py, the same code `size` runs). The result is scored against the
planted truth in three ways:
  1. assumptions measured on the replayed days (isolates the method; this is what steps 1 to 3 used)
  2. hard negatives: queues that look risky on paper and should not be over-staffed
  3. assumptions measured on days 1 to 10 and replayed on days 11 to 20 (what a planner has in practice)

KNOWN LIMITS, left in on purpose: a bursty queue is still one reviewer short (step 3 shows the
measurement), and a change in volume after the history was taken (payment_limit_exceptions) is invisible to
any method that is fitted on the history. The script prints both.

Run (from src/):  python3 step_04_with_review_capacity.py
Output: a report, plus out/step_04_queues.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import load_world, average_load_seats, score, ensure_out, OUT_DIR, PAST
from review_capacity import required_seats

world = load_world()
past_world = load_world(PAST)
seats = {q["queue_id"]: required_seats(q) for q in world}
erlang = {q["queue_id"]: required_seats(q, use_variability=False, use_batch=False) for q in world}
s = score(world, seats)
e = score(world, erlang)

print("STEP 4 - the tool, assumptions measured on the replayed days")
print(f"  matches the true number of reviewers: {s['exact']} of {s['queues']}; within one: {s['within_one']} of {s['queues']}")
print(f"  queues with too few reviewers: {len(s['under'])}; with too many: {len(s['over'])}")
print(f"  queues that meet both limits on the replay: {s['meets']} of {s['queues']} (Erlang C {e['meets']})")
print(f"  reviewers at the desk: {s['seats']} chosen, {s['true_seats']} needed (Erlang C {e['seats']})")
print(f"  cases that waited past their target: {s['late']} of {s['cases']} ({100.0 * s['late'] / s['cases']:.1f}%; Erlang C {100.0 * e['late'] / e['cases']:.1f}%)")
opening = [q for q in world if q["kind"] == "opening_batch"]
print(f"  opening-batch queues: tool {', '.join(str(seats[q['queue_id']]) for q in opening)} reviewers, "
      f"Erlang C {', '.join(str(erlang[q['queue_id']]) for q in opening)}, needed {', '.join(str(q['true_seats']) for q in opening)}")
negatives = [q for q in world if q["kind"] == "hard_negative"]
spared = [q for q in negatives if seats[q["queue_id"]] <= q["true_seats"]]
detail = ", ".join("%s %d against %d" % (q["queue_id"], seats[q["queue_id"]], q["true_seats"]) for q in negatives)
print(f"  hard negatives not over-staffed: {len(spared)} of {len(negatives)} ({detail})")
print("  queues still wrong:")
for q in s["under"] + s["over"]:
    r = s["results"][q["queue_id"]]
    word = "short" if q in s["under"] else "spare"
    print(f"    {word}: {q['queue_id']} ({q['kind']}) {seats[q['queue_id']]} against {q['true_seats']}, "
          f"{100.0 * r['late_share']:.1f}% late against {100.0 * (1 - q['target_share']):.0f}% allowed")

forecast = {q["queue_id"]: required_seats(q) for q in past_world}
f = score(world, forecast)
print("  assumptions measured on days 1 to 10, replayed on days 11 to 20")
print(f"    matches the true number: {f['exact']} of {f['queues']}; within one: {f['within_one']} of {f['queues']}; "
      f"too few: {len(f['under'])}; too many: {len(f['over'])}")
print(f"    queues that meet both limits on the replay: {f['meets']} of {f['queues']}")
drift = next(q for q in past_world if q["kind"] == "drift")
now = next(q for q in world if q["kind"] == "drift")
print(f"    KNOWN LIMIT {drift['queue_id']}: {drift['arrivals_per_hour']:.2f} live cases an hour on days 1 to 10, "
      f"{now['arrivals_per_hour']:.2f} on days 11 to 20; the tool says {forecast[drift['queue_id']]} reviewers, {now['true_seats']} were needed")
print(f"    short after the forecast: {', '.join(q['queue_id'] for q in f['under']) or 'none'}")

rows = []
for q in world:
    k = q["queue_id"]
    verdict = "exact" if seats[k] == q["true_seats"] else "short" if seats[k] < q["true_seats"] else "spare"
    rows.append({"queue_id": k, "kind": q["kind"], "true_seats": q["true_seats"], "average_load_seats": average_load_seats(q),
                 "erlang_c_seats": erlang[k], "tool_seats": seats[k], "forecast_seats": forecast[k],
                 "tool_late_pct": f"{100.0 * s['results'][k]['late_share']:.1f}", "erlang_late_pct": f"{100.0 * e['results'][k]['late_share']:.1f}",
                 "target_late_pct": f"{100.0 * (1 - q['target_share']):.0f}", "verdict": verdict})
summary = {"queues": s["queues"], "exact": s["exact"], "within_one": s["within_one"], "short": len(s["under"]), "spare": len(s["over"]),
           "meets": s["meets"], "erlang_meets": e["meets"], "seats": s["seats"], "true_seats": s["true_seats"], "erlang_seats": e["seats"],
           "forecast_exact": f["exact"], "forecast_short": len(f["under"]),
           "late_pct": round(100.0 * s["late"] / s["cases"], 1), "erlang_late_pct": round(100.0 * e["late"] / e["cases"], 1)}
ensure_out()
with open(os.path.join(OUT_DIR, "step_04_queues.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_queues.csv and step_04_summary.json in src/out/")
