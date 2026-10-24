"""Step 4 - The fix: the strict chain check in audit_chain.py plus an anchor taken at event 200.

The check reads each line strictly (a duplicate key, a field outside the hash, an unknown event kind,
NaN or an out-of-range number are problems), verifies sequence, links and hashes, and compares event 200
with the hash recorded in an anchor kept outside the log. The anchor is what catches a log cut back to an
earlier point and a rewrite that recomputes every hash. Same 101 planted edits as steps 1 to 3.

KNOWN LIMIT, left in on purpose: nothing written after the anchor is covered by it. A rewrite of the open
tail, a cut that keeps all of the anchored events, a forged append, and an edit to the last event with its own
hash recomputed all pass. They are printed below.

Run (from src/):  python3 step_04_chain_and_anchor.py
Output: a report, plus out/step_04_results.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import evaluate, tally, ops_in, ensure_out, OUT_DIR

result = evaluate()
rows, anchor = result["rows"], result["anchor"]
t_flag, t_all = tally(rows, "anchored", truth="tampered")
b_flag, b_all = tally(rows, "anchored", truth="benign")
a_flag, a_all = tally(rows, "anchored", truth="tampered", region="anchored")
o_flag, o_all = tally(rows, "anchored", truth="tampered", region="open")

print("STEP 4 (step_04_chain_and_anchor.py) - strict chain check plus an anchor at event %d" % anchor["seq"])
print(f"  tampered logs flagged: {t_flag} of {t_all}")
print(f"    edit touches event {anchor['seq']} or earlier: {a_flag} of {a_all}")
print(f"    edit only touches the open tail after it: {o_flag} of {o_all}")
print(f"  benign changes flagged: {b_flag} of {b_all}")
print("  first problem reported, among the flagged:")
for code, n in sorted(Counter(r["first_problem"] for r in rows if r["truth"] == "tampered" and r["anchored"]).items()):
    print(f"    {code:<20} {n}")
print("  by planted edit (open tail rows are counted separately):")
for op in ops_in(rows, "tampered"):
    for region in ("anchored", "open"):
        f, n = tally(rows, "anchored", op=op, region=region)
        if n:
            print(f"    {op:<14} {region:<9} flagged {f} of {n}")
missed = [r for r in rows if r["truth"] == "tampered" and not r["anchored"]]
print(f"  KNOWN LIMIT, passes the check: {len(missed)} of {t_all}, all in the open tail")
for op, n in sorted(Counter(r["op"] for r in missed).items()):
    print(f"    {op:<14} {n}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["tamper_id", "op", "region", "truth", "none", "records", "chain", "anchored", "first_problem"])
    for r in rows:
        w.writerow([r["tamper_id"], r["op"], r["region"], r["truth"]] + ["flagged" if r[k] else "passed" for k in ("none", "records", "chain", "anchored")] + [r["first_problem"]])
summary = {"events": result["events"], "anchor_seq": anchor["seq"], "planted": len(rows), "tampered": t_all, "benign": b_all,
           "flagged": {k: tally(rows, k, truth="tampered")[0] for k in ("none", "records", "chain", "anchored")},
           "false_alarms": {k: tally(rows, k, truth="benign")[0] for k in ("none", "records", "chain", "anchored")},
           "anchored_region": [a_flag, a_all], "open_tail": [o_flag, o_all]}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_results.csv and step_04_summary.json in src/out/")
