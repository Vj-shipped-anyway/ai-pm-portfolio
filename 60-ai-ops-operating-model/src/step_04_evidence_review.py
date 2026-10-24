"""Step 4 - The fix: an evidence review with five checks, run on every program.

Each program's owed items come from its tier. Each item is judged on the register row: present, a real
reference, not dated in the future, no older than 1.5 times its cycle, and produced by someone other than
the builder where the checklist says so. The program reaches the last stage whose owed items, and those of
every earlier stage, are all OK. The decision compares that stage with the owner's claim:
CONFIRMED, OVERCLAIM or UNDERCLAIM. The command-line tool runs exactly this code (ops_model_review.py).

KNOWN LIMIT, left in on purpose: the overclaims it passes. Each has a hollow artifact or lapsed evidence
inside the grace, which the register cannot show. The script prints them.

Run (from src/):  python3 step_04_evidence_review.py
Output: a report, plus out/step_04_programs.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import RULES, OUT_DIR, ensure_out, load_all, review_all, item_outcomes, stage_above_truth

d = load_all()
truth = d["truth"]
reviews = review_all(d, RULES, window=90)
n = len(reviews)
same = sum(1 for r in reviews if r["reached"] == truth[r["program_id"]]["true_stage"])
over_truth = [r for r in reviews if r["claimed"] > truth[r["program_id"]]["true_stage"]]
caught = [r for r in over_truth if r["decision"] == "OVERCLAIM"]
passed = [r for r in over_truth if r["decision"] != "OVERCLAIM"]
false_over = [r for r in reviews if r["claimed"] <= truth[r["program_id"]]["true_stage"] and r["decision"] == "OVERCLAIM"]
w_review = sum(1 for r in reviews if r["window"]["ok"] == r["window"]["owed"])
w_truth = sum(1 for t in truth.values() if t["window90_ok"])
owed_items = sum(len(r["items"]) for r in reviews)
not_owed = sum(r["not_owed"] for r in reviews)
out = item_outcomes(d, reviews)
decisions = Counter(r["decision"] for r in reviews)
above = {a["program_id"]: a for a in stage_above_truth(d, reviews)}

print("STEP 4 - the evidence review")
print(f"  stage reached equals the true stage: {same} of {n}")
print(f"  review stage above the truth: {len(above)} of {n}; below the truth: {sum(1 for r in reviews if r['reached'] < truth[r['program_id']]['true_stage'])} of {n}")
print(f"  claims above the true stage: {len(over_truth)} of {n}; the review flags {len(caught)} of them")
print(f"  claims flagged as overclaims that were not: {len(false_over)} of {n - len(over_truth)}")
print(f"  decisions: CONFIRMED {decisions['CONFIRMED']}, OVERCLAIM {decisions['OVERCLAIM']}, UNDERCLAIM {decisions['UNDERCLAIM']}")
print(f"  items judged: {owed_items} owed, {not_owed} not owed at the program's tier and left alone")
print("  planted defects among owed items that the review rejects: "
      + ", ".join(f"{s} {g} of {t}" for s, (g, t) in out["caught"].items()))
print(f"  first 90 days, every owed item evidenced: review {w_review} of {n}, planted truth {w_truth} of {n}")
print(f"  overclaims that still pass: {len(passed)} of {len(over_truth)}")
for r in passed:
    a = above.get(r["program_id"])
    why = ", ".join(f"{s} {i}" for s, i in a["causes"]) if a else "the review stops short of the truth for another reason"
    print(f"    {r['program_id']} claimed {r['claimed']}, review {r['reached']}, truth {truth[r['program_id']]['true_stage']}: {why}")
print(f"  planted-ok items the review rejects: {len(out['false_alarms'])} (all STALE: evidence from a cycle that ran late)")

ensure_out()
rows = []
for r in reviews:
    t = truth[r["program_id"]]
    rows.append({"program_id": r["program_id"], "program_name": r["program_name"], "tier": r["tier"], "claimed": r["claimed"],
                 "reviewed": r["reached"], "truth": t["true_stage"], "decision": r["decision"],
                 "gaps": "; ".join(f"{g['item_id']} {g['status']}" for g in r["gaps"]) or "none"})
with open(os.path.join(OUT_DIR, "step_04_programs.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"programs": n, "stage_matches": same, "overclaims": len(over_truth), "overclaims_flagged": len(caught),
           "overclaims_passed": len(passed), "false_overclaims": len(false_over), "confirmed": decisions["CONFIRMED"],
           "window_review": w_review, "window_truth": w_truth, "items_owed": owed_items}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_programs.csv and step_04_summary.json in src/out/")
