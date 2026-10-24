"""Step 4 - The fix: one check with three parts.

  1. the evidence list for the reason code, with either-or items
  2. the response clock: days left for a draft, on time or late for a sent packet
  3. consistency: every document names this order, post-purchase documents are not dated before the
     purchase, no document is dated after the check date, the order record covers the disputed amount,
     and the packet stays inside the page limit

Decision per packet: LATE if the window has closed, FIX if anything is wrong while the clock is still
running, else READY. The command-line tool runs exactly this code (chargeback_packet.py).

KNOWN LIMIT, left in on purpose: a document with the right label and the wrong content passes. The
script prints those packets.

Run (from src/):  python3 step_04_with_check.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_cases, evaluate, ensure_out, OUT_DIR, EXPECTED

rows = evaluate(load_cases())
ready = [r for r in rows if r["truth"] == "ready"]
defective = [r for r in rows if r["truth"] == "defective"]
late = [r for r in rows if r["truth"] == "late"]
visible = [r for r in defective if r["visible"]]
hidden = [r for r in defective if not r["visible"]]
caught = [r for r in visible if r["result"]["state"] == "FIX"]
late_caught = [r for r in late if r["result"]["state"] == "LATE"]
false_alarm = [r for r in ready if r["result"]["state"] != "READY"]
exact = sum(1 for r in rows if r["result"]["state"] == EXPECTED[r["truth"]])
opened = sum(1 for r in rows if r["result"]["state"] != "READY")
fix_drafts = [r for r in rows if r["result"]["state"] == "FIX" and not r["result"]["submitted"]]
urgent = [r for r in fix_drafts if r["result"]["days_left"] <= 3]

print("STEP 4 - evidence list, clock and consistency together")
print(f"  defective with a visible fault sent to FIX: {len(caught)} of {len(visible)}")
print(f"  late packets marked LATE: {len(late_caught)} of {len(late)}")
print(f"  ready packets flagged by mistake: {len(false_alarm)} of {len(ready)}")
print(f"  decision matches the planted truth: {exact} of {len(rows)}")
print(f"  packets a person has to open: {opened} of {len(rows)}")
print(f"  drafts to fix with 3 or fewer days left: {len(urgent)} of {len(fix_drafts)}")
print("  hard negatives that stayed READY:")
for kind, label in (("ready_alt_branch", "second option of an either-or item"), ("ready_partial", "partial dispute, order total above the disputed amount"),
                    ("ready_on_deadline", "sent on the last day"), ("ready_draft", "draft with the window still open"),
                    ("ready_extra_doc", "extra document that is on no list")):
    group = [r for r in ready if r["kind"] == kind]
    print(f"    {kind:<18} {sum(1 for r in group if r['result']['state'] == 'READY')} of {len(group)}  {label}")
due_today = [r for r in ready if r["kind"] == "ready_draft" and r["result"]["days_left"] == 0]
print(f"  drafts due today that stayed READY: {sum(1 for r in due_today if r['result']['state'] == 'READY')} of {len(due_today)}")
print(f"  KNOWN LIMIT - defective packets with a wrong file that still pass: {sum(1 for r in hidden if r['result']['state'] == 'READY')} of {len(hidden)}")
for r in hidden:
    print(f"    {r['case']['case_id']} {r['case']['reason_code']} {r['kind']} -> {r['result']['state']}")
by_kind = Counter((r["kind"], r["result"]["state"]) for r in rows)
print("  decisions by planted case:")
for kind in sorted({r["kind"] for r in rows}):
    print(f"    {kind:<22} " + ", ".join(f"{s} {by_kind[(kind, s)]}" for s in ("READY", "FIX", "LATE") if by_kind[(kind, s)]))

ensure_out()
fields = ["case_id", "reason_code", "amount", "planted_kind", "truth", "state", "days_left", "sent", "problems"]
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(fields)
    for r in rows:
        res = r["result"]
        w.writerow([res["case_id"], res["reason_code"], "%d.%02d" % divmod(res["amount_cents"], 100), r["kind"], r["truth"], res["state"],
                    res["days_left"], res["submitted"] or "draft", "; ".join(sorted({p["kind"] for p in res["problems"]})) or "none"])
summary = {"cases": len(rows), "ready": len(ready), "defective": len(defective), "late": len(late), "visible_defective": len(visible),
           "caught": len(caught), "late_caught": len(late_caught), "false_alarms": len(false_alarm), "exact_match": exact,
           "to_open": opened, "urgent_fix": len(urgent), "fix_drafts": len(fix_drafts), "hidden": len(hidden),
           "hidden_passing": sum(1 for r in hidden if r["result"]["state"] == "READY")}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
