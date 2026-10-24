"""Step 4 - The fix: business-day clocks that start at first contact and follow the events.

The tool in dispute_clock.py does three things the step 2 countdown does not:
  1. counts business days, skipping weekends and the holiday file, and leaves calendar windows alone
  2. starts each clock at the date its policy row names (first contact; for the final notice, the
     conclusion, so that clock has not started while the investigation is open)
  3. lets the earliest of several events satisfy a clock (the credit decision is met by a provisional
     credit or by finishing the investigation, whichever comes first)

KNOWN LIMIT, left in on purpose: a paused investigation (the bank waited for the customer) is still
read as running the whole time, and a dispute recorded as extended is given the longer window even
when it never applied. The script prints both sets.

Run (from src/):  python3 step_04_business_day_clocks.py
Output: a report, plus out/step_04_clocks.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os

import dispute_clock as dc
from common import OUT_DIR, ensure_out, is_missed, load_world, pct

SOON_DAYS = 5
world = load_world()
truth, as_of = world["truth"], world["as_of"]
results = dc.evaluate_all(world["disputes"], world["policy"], world["holidays"], as_of)
by_id = {d["dispute_id"]: d for d in world["disputes"]}
rows = []
for r in results:
    t = truth[(r["dispute_id"], r["clock_id"])]
    rows.append({"dispute_id": r["dispute_id"], "dispute_type": r["dispute_type"],
                 "window_class": by_id[r["dispute_id"]]["window_class"], "clock_id": r["clock_id"],
                 "clock_name": r["clock_name"], "unit": r["unit"], "start": r["start"].isoformat() if r["start"] else "",
                 "due": r["due"].isoformat() if r["due"] else "", "sent": r["sent"].isoformat() if r["sent"] else "",
                 "status": r["status"], "days": "" if r["days"] is None else r["days"], "planted_status": t["status"],
                 "hard_case": "|".join(t["tags"]), "match": "yes" if r["status"] == t["status"] else "no"})

right = sum(1 for r in rows if r["match"] == "yes")
total_missed = sum(1 for t in truth.values() if is_missed(t["status"]))
found = sum(1 for r in rows if is_missed(r["status"]) and is_missed(r["planted_status"]))
false_alarms = [r for r in rows if is_missed(r["status"]) and not is_missed(r["planted_status"])]
silent = [r for r in rows if is_missed(r["planted_status"]) and not is_missed(r["status"])]
soon = dc.due_soon(results, as_of, SOON_DAYS)
with_miss = sorted({r["dispute_id"] for r in rows if is_missed(r["status"])})

print("STEP 4 - business days, first-contact start, event-driven anchors")
print(f"  statuses that match the planted truth: {right} of {len(rows)} ({pct(right, len(rows))})")
print(f"  missed clocks found: {found} of {total_missed}; missed clocks the tool calls fine: {len(silent)}")
print(f"  called missed, truth says not: {len(false_alarms)}")
print("  hard cases, statuses right / clocks of that kind:")
for tag, label in (("boundary", "event on the due day"), ("holiday", "business-day window across a holiday"),
                   ("logged_late", "logged after first contact"), ("pause", "paused investigation"),
                   ("misrecorded", "extended class recorded, never applied")):
    kind = [r for r in rows if tag in r["hard_case"].split("|")]
    print(f"    {label:<40} {sum(1 for r in kind if r['match'] == 'yes')} / {len(kind)}")
paused = [r for r in false_alarms if "pause" in r["hard_case"].split("|")]
print(f"  KNOWN LIMIT: {len(false_alarms)} false alarms ({len(paused)} on paused investigations): "
      + (", ".join(f"{r['dispute_id']} {r['clock_id']}" for r in false_alarms) or "none"))
print("  ALSO, the tool trusts the recorded window class: missed clocks it calls fine: "
      + (", ".join(f"{r['dispute_id']} {r['clock_id']}" for r in silent) or "none"))
print(f"  disputes with at least one missed clock: {len(with_miss)} of {len(world['disputes'])}")
print(f"  running clocks due within {SOON_DAYS} days of the as-of date: {len(soon)} on {len({r['dispute_id'] for r in soon})} disputes")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_clocks.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"as_of": as_of.isoformat(), "disputes": len(world["disputes"]), "clocks": len(rows), "right": right,
           "missed_found": found, "missed_truth": total_missed, "false_alarms": len(false_alarms),
           "disputes_with_miss": len(with_miss), "due_soon": len(soon), "due_soon_days": SOON_DAYS}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_clocks.csv and step_04_summary.json in src/out/")
