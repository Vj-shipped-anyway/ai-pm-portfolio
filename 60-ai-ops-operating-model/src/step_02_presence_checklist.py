"""Step 2 - The common basic approach: one flat checklist, ticked when a row exists.

Most teams add a checklist next. Every program gets all 23 items, whatever its tier, and an item counts
as done when the evidence register holds a row for it. This is the review with every check switched off
except presence: no tier, no placeholder test, no date test, no independence test.

Run (from src/):  python3 step_02_presence_checklist.py
"""
from collections import Counter

from common import load_all, review_all

d = load_all()
truth, item_truth = d["truth"], d["item_truth"]
reviews = review_all(d, rules=())
n = len(reviews)
same = sum(1 for r in reviews if r["reached"] == truth[r["program_id"]]["true_stage"])
over_truth = [r for r in reviews if r["claimed"] > truth[r["program_id"]]["true_stage"]]
flagged_true = sum(1 for r in over_truth if r["decision"] == "OVERCLAIM")
flagged_false = [r for r in reviews if r["claimed"] <= truth[r["program_id"]]["true_stage"] and r["decision"] == "OVERCLAIM"]
not_owed_missing = [(r["program_id"], i["item_id"]) for r in reviews for i in r["items"]
                    if i["status"] == "MISSING" and not item_truth[(r["program_id"], i["item_id"])]["owed"]]
accepted = Counter(item_truth[(r["program_id"], i["item_id"])]["state"] for r in reviews for i in r["items"]
                   if i["status"] == "OK" and item_truth[(r["program_id"], i["item_id"])]["owed"]
                   and item_truth[(r["program_id"], i["item_id"])]["state"] != "ok")
tier1 = sum(1 for i in d["checklist"] if i["min_tier"] <= 1)

print("STEP 2 - one flat checklist, ticked when a row exists")
print(f"  items asked of every program: {len(d['checklist'])}; items a tier-1 program owes: {tier1}")
print(f"  stage reached equals the true stage: {same} of {n}")
print(f"  claims above the true stage that it flags: {flagged_true} of {len(over_truth)}")
print(f"  claims at or below the true stage that it flags as overclaims: {len(flagged_false)} of {n - len(over_truth)}")
print(f"  items flagged missing that the program's tier does not owe: {len(not_owed_missing)} "
      f"in {len({p for p, _ in not_owed_missing})} programs")
print("  evidence it accepts that the planted truth rejects, by planted state: "
      + (", ".join(f"{k} {accepted[k]}" for k in sorted(accepted)) or "none"))
print("  A row is not evidence: it passes an empty reference, a date in the future and a stale file,")
print("  and it asks a tier-1 program for the same proof as a tier-4 one.")
