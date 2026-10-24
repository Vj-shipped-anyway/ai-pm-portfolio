"""Step 4 - The fix: memo_tieout with its default settings.

  1. a figure is a number with a $, % or x; years, counts and section numbers are not
  2. a mark spread:line/period ties the figure to one line and one period of the spread
  3. a ratio or margin is recomputed from the spread by a formula in memo_tieout.py
  4. the figure must equal the spread value rounded to the decimals the memo shows, with no tolerance
  5. a figure with no mark is reported as untied; a term:name mark sets a proposed term aside, counted

The command line in src/memo_tieout.py runs exactly this code.

KNOWN LIMIT, left in on purpose: a number that agrees with its mark passes even when the sentence around it
names another line (prose_tag_mismatch), and a figure written in words or with a USD prefix is never read
(unparsed_form). The script prints each one.

Run (from src/):  python3 step_04_with_memo_tieout.py
Output: a report, plus out/step_04_results.csv, out/step_04_summary.json and out/demo_run.txt
"""
import contextlib
import csv
import io
import json
import os
from collections import Counter

import memo_tieout
from common import OUT_DIR, alarms, anywhere_flags, ensure_out, key, load_memos, load_truth, passed, score, tally, tool_flags

memos, truth = load_memos(), load_truth()
tool = score(memos, truth, tool_flags)
basic = score(memos, truth, anywhere_flags)
t, g = tally(truth, tool), tally(truth, basic)
opened = t["caught"] + t["false_alarms"]

by_memo, statuses = {}, Counter()
for m in memos:
    for r in memo_tieout.check_memo(m["text"], m["spread"]):
        by_memo[(m["memo_id"], r["line"], r["col"])] = r
        statuses[r["status"]] += 1
missed = [r for r in truth if r["expected"] == "flag" and not tool["flagged"][key(r)]]

print("step_04_with_memo_tieout.py - marks, formulas, shown precision, unmarked figures flagged")
print(f"  wrong figures caught: {t['caught']} of {t['wrong']} (step 2 caught {g['caught']})")
print(f"  fine figures flagged by mistake: {t['false_alarms']} of {t['fine']} (step 2 flagged {g['false_alarms']})")
print(f"  flags outside every planted figure: {t['stray']}")
print(f"  figures a person has to open: {opened} of {len(truth)} (step 2: {g['caught'] + g['false_alarms']}); real problems among them: {t['caught']} of {opened}")
print(f"  memos that still carry a wrong figure after the check: {len({r['memo_id'] for r in missed})} of {len(memos)} (step 1: {len({r['memo_id'] for r in truth if r['expected'] == 'flag'})})")
print(f"  by status: {statuses['tied']} tie, {statuses['mismatch']} do not tie, {statuses['unresolved']} unresolved, {statuses['untied']} untied, {statuses['term']} set aside as terms")
print(f"  still missed, by planted kind: {passed(t)}")
print(f"  false alarms, by planted kind: {alarms(t)}")
for r in missed:
    print(f"    {r['memo_id']} line {r['line']:<3} {r['kind']:<19} {r['text']}")
print("  flagged / figures, by planted kind:")
for kind, v in sorted(t["by_kind"].items()):
    print(f"    {kind:<19} {v['flagged']:>2} / {v['total']:<3} {'should be flagged' if v['expected'] == 'flag' else 'should pass'}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["memo_id", "line", "col", "kind", "expected", "text", "status", "step_02", "why"])
    for r in truth:
        res = by_memo.get(key(r))
        w.writerow([r["memo_id"], r["line"], r["col"], r["kind"], r["expected"], r["text"],
                    res["status"] if res else "not read", "flag" if basic["flagged"][key(r)] else "pass",
                    res["why"] if res else "written in a form the reader does not parse"])
summary = {"caught": t["caught"], "wrong": t["wrong"], "false_alarms": t["false_alarms"], "fine": t["fine"],
           "step_02_caught": g["caught"], "step_02_false_alarms": g["false_alarms"], "figures": len(truth),
           "to_open": opened, "memos": len(memos), "missed": len(missed)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    memo_tieout.main(["--demo"])
with open(os.path.join(OUT_DIR, "demo_run.txt"), "w", encoding="utf-8") as fh:
    fh.write(buf.getvalue())
print("Wrote step_04_results.csv, step_04_summary.json and demo_run.txt in src/out/")
