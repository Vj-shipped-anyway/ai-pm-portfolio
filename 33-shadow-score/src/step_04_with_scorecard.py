"""Step 4 - The fix: a scorecard with ten checks over the two files.

  1. join on case_id and report what did not join (waiting for an outcome, no proposal)
  2. count abstentions as misses next to the first-report rate, with a 95% interval
  3. compare with a rule that always proposes the most common outcome
  4. split by outcome class, segment, week, reviewer and stated confidence, and judge a group only
     when it has 30 proposals
  5. count the pairs I marked risky
  6. print PASS, FAIL or SKIP for each check and HOLD or CLEAR for the whole

The command line tool (shadow_score.py) runs exactly this code. The thresholds are my assumptions.

KNOWN LIMITS, left in on purpose: a planted problem that sits one point above the floor passes, and
cases where the agent and the person agree and are both wrong are invisible. The script prints both.

Run (from src/):  python3 step_04_with_scorecard.py
Output: a report, plus out/step_04_scorecard.json, out/step_04_groups.csv and out/step_04_planted.csv
"""
import csv
import json
import os

from common import load, joined, planted, score, evaluate, RULES, ensure_out, OUT_DIR
from shadow_score import decide, render

proposals, outcomes = load()
s = score(proposals, outcomes, RULES)
checks = evaluate(s, RULES)
decision = decide(checks)

print("STEP 4 - the scorecard")
print(render(s, checks, decision, detail=True))

GROUPS = {"segment": "by_segment", "week": "by_week", "reviewer": "by_reviewer", "class": "by_class"}
found = []
print("\nplanted problems against what the scorecard flagged")
for p in planted():
    g = next(g for g in s[GROUPS[p["group_type"]]] if g["name"] == p["group"])
    if p["group_type"] == "class":
        seen = f"proposed on {g['proposed']} of {g['n']} cases ({g['coverage']:.1%})"
    else:
        seen = f"{g['rate']:.1%} on {g['proposed']} proposals"
    if p["real"] == "1":
        found.append(g["status"] == "below")
        verdict = "found" if g["status"] == "below" else "MISSED"
        print(f"  {p['problem_id']} {p['group_type']} {p['group']}: {verdict}  ({seen})")
    else:
        verdict = "shown as too few to judge" if g["status"] == "too_few" else "FAILED A CHECK"
        print(f"  {p['problem_id']} {p['group_type']} {p['group']}: look-alike, {verdict}  ({seen})")
looks = [p for p in planted() if p["real"] == "0"]
raised = sum(1 for p in looks if next(g for g in s[GROUPS[p["group_type"]]] if g["name"] == p["group"])["status"] == "below")
print(f"  planted problems found: {sum(found)} of {len(found)}")
print(f"  look-alikes that failed a check: {raised} of {len(looks)}")

missed = [p for p in planted() if p["real"] == "1" and
          next(g for g in s[GROUPS[p["group_type"]]] if g["name"] == p["group"])["status"] != "below"]
both_wrong = sum(1 for r in joined() if r["kind"] == "agree" and r["proposed"] != r["true"])
weak = min((g for g in s["by_class"] if g["judged"]), key=lambda g: g["rate"])
print("known limits")
for p in missed:
    g = next(g for g in s[GROUPS[p["group_type"]]] if g["name"] == p["group"])
    print(f"  {p['group_type']} {p['group']} is a planted problem and passes: {g['rate']:.1%} against a floor of {RULES.group_floor:.1%}")
print(f"  {both_wrong} of {s['agree']} agreements are cases where both the agent and the person are wrong; the scorecard cannot see them")
print(f"  no check holds a floor on agreement per outcome class: {weak['name']} sits at {weak['rate']:.1%} on {weak['proposed']} proposals")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_scorecard.json"), "w", encoding="utf-8") as fh:
    json.dump({"decision": decision, "checks": checks, "score": s,
               "planted_found": sum(found), "planted": len(found), "look_alikes_failed": raised, "look_alikes": len(looks),
               "agreements_both_wrong": both_wrong}, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_groups.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["group_type", "group", "cases", "proposed", "agreed", "rate", "status"])
    for gtype, key in GROUPS.items():
        for g in s[key]:
            w.writerow([gtype, g["name"], g["n"], g["proposed"], g["agree"], "" if g["rate"] is None else "%.4f" % g["rate"], g["status"]])
with open(os.path.join(OUT_DIR, "step_04_planted.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["problem_id", "kind", "group_type", "group", "real", "note"])
    for p in planted():
        w.writerow([p["problem_id"], p["kind"], p["group_type"], p["group"], p["real"], p["note"]])
print("Wrote step_04_scorecard.json, step_04_groups.csv and step_04_planted.csv in src/out/")
