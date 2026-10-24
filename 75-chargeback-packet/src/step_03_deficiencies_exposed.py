"""Step 3 - Where each check fails when used alone.

The checker has three parts, and each is switched on by itself here:
  completeness  the evidence list for the reason code, with either-or items
  clock         the response window, counted in calendar days from the day the dispute was received
  consistency   references, amounts, document dates and the page limit

The truth is known, so each part is scored on the same 100 cases. A packet is "flagged" when the part
returns FIX or LATE. KNOWN LIMIT, left in on purpose: a document with the right label, reference,
date and page count and the wrong content (another case's file, an unreadable scan) passes all three
parts, and step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_cases, evaluate

items = load_cases()
ready = [it for it in items if it["truth"] == "ready"]
defective = [it for it in items if it["truth"] == "defective"]
late = [it for it in items if it["truth"] == "late"]
visible = [it for it in defective if it["visible"]]

print("STEP 3 - each part alone")
flagged_by = {}
for name in ("completeness", "clock", "consistency"):
    rows = evaluate(items, (name,))
    flagged_by[name] = {r["case"]["case_id"] for r in rows if r["result"]["state"] != "READY"}
    got = flagged_by[name]
    print(f"  {name} only")
    print(f"    defective flagged: {sum(1 for it in defective if it['case']['case_id'] in got)} of {len(defective)}"
          f" ({sum(1 for it in visible if it['case']['case_id'] in got)} of {len(visible)} visible in metadata)")
    print(f"    late flagged: {sum(1 for it in late if it['case']['case_id'] in got)} of {len(late)}")
    print(f"    ready packets flagged: {sum(1 for it in ready if it['case']['case_id'] in got)} of {len(ready)}")

any_flag = set().union(*flagged_by.values())
passed = [it for it in items if it["truth"] != "ready" and it["case"]["case_id"] not in any_flag]
print(f"  faulty packets that pass all three parts: {len(passed)} of {len(defective) + len(late)}")
for it in passed:
    print(f"    {it['case']['case_id']} {it['case']['reason_code']} {it['kind']}")
print("  No part covers every planted fault on its own, and none of them opens a file.")
