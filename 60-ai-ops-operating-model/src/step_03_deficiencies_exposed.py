"""Step 3 - What each check adds, and what none of them sees.

The review has five checks: a tier-aware list of what is owed, a placeholder test on the artifact
reference, a future-date test, a freshness test (no older than 1.5 times the item's cycle) and an
independence test (someone other than the builder produced it). This step switches them off one at a
time and scores the stage each program reaches against the planted truth, then looks at what the full
set still lets through.

KNOWN LIMIT, left in on purpose: the review reads the register, not the artifacts. A row for an artifact
that does not show what the checklist names (planted state hollow) passes every check, and so does
lapsed evidence that sits inside the 1.5 times grace. Step 4 does not close either gap.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import RULES, load_all, review_all, item_outcomes, stage_above_truth

NAMES = {"tier": "tier-aware owed list", "ref": "placeholder reference test", "future": "future-date test",
         "fresh": "freshness, 1.5 x cycle", "indep": "independence from the builder"}

d = load_all()
n = len(d["programs"])


def score(rules) -> tuple:
    """(programs whose stage equals the truth, planted-defective owed items the run accepts)"""
    rv = review_all(d, rules)
    accepted = sum(len(v) for v in item_outcomes(d, rv)["passed"].values())
    return sum(1 for r in rv if r["reached"] == d["truth"][r["program_id"]]["true_stage"]), accepted


full, full_accepted = score(RULES)
print("STEP 3 - each check alone, and what none of them sees")
print(f"  all five checks: stage reached equals the true stage in {full} of {n}; defective items accepted: {full_accepted}")
print("  switch one check off (stage match; defective items accepted):")
for rule in RULES:
    m, acc = score(tuple(x for x in RULES if x != rule))
    print(f"    without {NAMES[rule]:<31} {m} of {n}; {acc}")
reviews = review_all(d, RULES)
out = item_outcomes(d, reviews)
print("  planted defects among owed items that the full review rejects:")
for state, (got, total) in out["caught"].items():
    print(f"    {state:<12} {got} of {total}")
print(f"  planted-ok items the full review rejects: {len(out['false_alarms'])} "
      f"({', '.join(sorted({s for _, _, s in out['false_alarms']})) or 'none'}; evidence from a cycle that ran late)")
above = stage_above_truth(d, reviews)
print(f"  KNOWN LIMIT - programs where the review reaches a higher stage than the truth: {len(above)} of {n}")
for a in above:
    print(f"    {a['program_id']} review {a['reached']}, truth {a['true_stage']}: "
          + ", ".join(f"{s} {i}" for s, i in a["causes"]))
print("  Hollow artifacts and lapsed evidence inside the grace pass every check.")
