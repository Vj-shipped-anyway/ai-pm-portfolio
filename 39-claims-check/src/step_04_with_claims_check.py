"""Step 4 - The fix: claims-check with its default settings.

  1. claims are the numbers after a green circle, read per paragraph or list item
     (wrapped bullets joined; fenced blocks, code spans, links and URLs skipped)
  2. a number must be printed as a whole number: 12 is not 112, and 40 is not 40.3
  3. "a of b" must be printed as a pair, "a of b" or "a/b", on one line
  4. numbers of one digit are skipped and counted

The command line and the GitHub Action in action/ run exactly this code (claims_check.py).

KNOWN LIMIT, left in on purpose: a wrong number that equals another number the scripts print passes
(coincidence), and so does a wrong single-digit number (single_digit). The script prints both.

Run (from src/):  python3 step_04_with_claims_check.py
Output: a report, plus out/step_04_results.csv, out/step_04_summary.json and out/demo_run.txt
"""
import contextlib
import csv
import io
import json
import os

import claims_check
from common import OUT_DIR, ensure_out, false_alarms, grep_lines, load_projects, load_truth, misses, score, tally, tool_lines

projects, truth = load_projects(), load_truth()
tool = score(projects, truth, tool_lines)
grep = score(projects, truth, grep_lines)
t = tally(truth, tool)
g = tally(truth, grep)
reads = t["caught"] + t["false_alarms"]
skipped = sum(1 for p in projects for r in claims_check.check_claims(
    claims_check.extract_claims(p["readme"]), claims_check.index_evidence([p["evidence"]])) if r["status"] == "skipped")

print("step_04_with_claims_check.py - whole numbers, pairs, single digits skipped")
print(f"  unsupported bullets caught: {t['caught']} of {t['unsupported']} (step 2 caught {g['caught']})")
print(f"  fine bullets flagged by mistake: {t['false_alarms']} of {t['supported']} (step 2 flagged {g['false_alarms']})")
print(f"  flags outside every planted bullet: {t['stray']}")
print(f"  bullets a person has to open: {reads} of {len(truth)}; real problems among them: {t['caught']} of {reads}")
print(f"  still missed, by planted kind: {misses(t)}")
print(f"  false alarms, by planted kind: {false_alarms(t)}")
print(f"  numbers skipped for having one digit: {skipped}")
print("  flagged / bullets, by planted kind:")
for k, v in sorted(t["by_kind"].items()):
    print(f"    {k:<16} {v['flagged']:>2} / {v['total']:<3} {'should be flagged' if v['expected'] == 'flag' else 'should pass'}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_results.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["project_id", "line_start", "kind", "expected", "claims_check", "grep"])
    for r in truth:
        key = (r["project_id"], r["line_start"])
        w.writerow([r["project_id"], r["line_start"], r["kind"], r["expected"],
                    "flag" if tool["flagged"][key] else "pass", "flag" if grep["flagged"][key] else "pass"])
summary = {"caught": t["caught"], "unsupported": t["unsupported"], "false_alarms": t["false_alarms"], "supported": t["supported"],
           "grep_caught": g["caught"], "grep_false_alarms": g["false_alarms"], "bullets": len(truth), "to_open": reads,
           "projects": len(projects), "skipped": skipped}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    claims_check.main(["--demo"])
with open(os.path.join(OUT_DIR, "demo_run.txt"), "w", encoding="utf-8") as fh:
    fh.write(buf.getvalue())
print("Wrote step_04_results.csv, step_04_summary.json and demo_run.txt in src/out/")
