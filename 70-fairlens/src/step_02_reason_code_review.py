"""Step 2 - The common basic approach: review the decline reasons.

A validator who has no fairness test pack looks at the adverse-action reasons. This step runs
that review as test T5 on its own: declined applicants with nearly equal scores are matched
across groups, and the portfolio is flagged when their top reason differs more often than it
does between two applicants of the reference group. The review sees whether the reasons are
consistent. It does not look at what the points do.

Run (from src/):  python3 step_02_reason_code_review.py
"""
from collections import Counter

from common import load_cases, run_cases, mechanisms

cases = load_cases()
packs = run_cases(cases)
t5 = {c["id"]: packs[c["id"]]["tests"][4] for c in cases}
planted = [c for c in cases if c["planted"]]
others = [c for c in cases if not c["planted"]]

print("STEP 2 - reason-code review alone (T5)")
cnt = Counter(t5[c["id"]]["verdict"] for c in planted)
print(f"  planted proxy ({len(planted)}): PASS {cnt['PASS']}, REVIEW {cnt['REVIEW']}, FAIL {cnt['FAIL']}")
cnt = Counter(t5[c["id"]]["verdict"] for c in others)
thin = sum(1 for c in others if t5[c["id"]]["excess"] is None)
print(f"  no planted proxy ({len(others)}): PASS {cnt['PASS']}, REVIEW {cnt['REVIEW']}, FAIL {cnt['FAIL']} (REVIEW for too few matched pairs: {thin})")
print("  by mechanism (PASS / flagged):")
for m in mechanisms(cases):
    vs = [t5[c["id"]]["verdict"] for c in cases if c["mechanism"] == m]
    print(f"    {m:<20} {sum(1 for v in vs if v == 'PASS')} / {sum(1 for v in vs if v != 'PASS')}")
ex = [c for c in planted if packs[c["id"]]["gs"]["min_air"] < 0.80 and t5[c["id"]]["verdict"] == "PASS"]
print(f"  planted proxies with the reason review passed and the lowest AIR under 0.80: {len(ex)} of {len(planted)}")
print("  The reasons are consistent across groups because every group is scored by the same points.")
