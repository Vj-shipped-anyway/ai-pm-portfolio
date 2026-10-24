"""Step 4 - The fix: one gate with four rules.

  1. snapshot_changed   a probe was served by an id other than the pin
  2. unscored_probes    a probe in the probe file has no result
  3. overall_drop       the mean pass rate is under the baseline by more than 3 points (review) or 5 (block)
  4. probe_collapse     a high-severity probe is 50 points or more under its baseline

Decision per run: BLOCK if any rule says block, REVIEW if one says review, else ALLOW. The command-line
tool and the GitHub Action in action/ run exactly this code (eval_gate.py). Moving the pin is how a team
says it has read the vendor's notice.

KNOWN LIMIT, left in on purpose: a change of about two points behind an unchanged id is allowed. The
script prints those runs.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_runs, gate, ensure_out, OUT_DIR, DECISIONS

probes, runs = load_runs()
rows = []
for r in runs:
    g = gate(probes, r)
    rows.append({"run_id": r["run_id"], "planted_kind": r["kind"], "truth": r["truth"], "decision": g["decision"],
                 "pin": r["pin"], "served": " ".join(g["served"]), "off_pin": g["off_pin"], "scored": g["scored"],
                 "pass_rate": f"{g['pass_rate']:.2f}", "baseline": f"{g['baseline']:.2f}",
                 "drop_points": f"{g['drop'] * 100:.1f}", "findings": "; ".join(f"{f['kind']}:{f['probe']}" if f["probe"] else f["kind"] for f in g["findings"]) or "none"})

must = [r for r in rows if r["truth"] == "BLOCK"]
rev = [r for r in rows if r["truth"] == "REVIEW"]
fine = [r for r in rows if r["truth"] == "ALLOW"]
blocked = sum(1 for r in must if r["decision"] == "BLOCK")
flagged = sum(1 for r in rev if r["decision"] != "ALLOW")
false_block = sum(1 for r in fine if r["decision"] == "BLOCK")
false_review = sum(1 for r in fine if r["decision"] == "REVIEW")
exact = sum(1 for r in rows if r["decision"] == r["truth"])
missed = [r for r in rows if r["truth"] != "ALLOW" and r["decision"] == "ALLOW"]

print("STEP 4 - snapshot pin, coverage, drop and collapse together (step_04_with_gate.py)")
print(f"  should-block runs stopped: {blocked} of {len(must)}")
print(f"  should-review runs flagged: {flagged} of {len(rev)}")
print(f"  fine runs blocked: {false_block} of {len(fine)}; sent to review: {false_review} of {len(fine)}")
print(f"  decision matches the planted truth: {exact} of {len(rows)}")
print(f"  should-block or should-review runs that still pass: {len(missed)} of {len(must) + len(rev)}")
for r in missed:
    print(f"    {r['run_id']} {r['planted_kind']} (mean pass rate {r['pass_rate']} against {r['baseline']})")
by_kind = Counter((r["planted_kind"], r["decision"]) for r in rows)
print("  decisions by planted event:")
for kind in sorted({r["planted_kind"] for r in rows}):
    print(f"    {kind:<24} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in DECISIONS if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"should_block_stopped": blocked, "should_block": len(must), "should_review_flagged": flagged, "should_review": len(rev),
           "fine_blocked": false_block, "fine_review": false_review, "fine": len(fine), "exact_match": exact, "runs": len(rows),
           "missed": len(missed)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
