"""Step 2 - The common basic approach: add exception questions, with the exception beside the rule.

The next thing a team does is write a few exception questions. The author knows where the exception is, so
it sits in the rule clause or in the clause that follows, and the question is asked once, at mid depth (50%),
in each manual. This step runs that test on the same four stub readers.

Run (from src/):  python3 step_02_exception_beside_rule.py
"""
from common import READERS, load_manuals, load_sweep, run_reader
from credit_policy_needle import score_probes

probes, manuals = load_sweep(), load_manuals()
test = [p for p in probes if p["form"] in ("inline", "adjacent") and p["depth_pct"] == 50]

print("STEP 2 - exception questions with the exception beside the rule, asked at depth 50%")
print(f"  questions: {len(test)} of {len(probes)} in the full sweep   forms: inline, adjacent   manuals: {len(manuals)}")
print(f"  {'reader':<12}{'pass':>10}")
passed = {}
for name in READERS:
    passed[name] = score_probes(test, run_reader(name, probes, manuals))["passed"]
    print(f"  {name:<12}{passed[name]:>6} of {len(test)}")
faulty = [n for n in READERS if n != "control"]
flagged = [n for n in faulty if passed[n] < len(test)]
clean = [n for n in faulty if passed[n] == len(test)]
print(f"  faulty readers flagged: {len(flagged)} of {len(faulty)} ({', '.join(flagged)})")
print(f"  faulty readers that pass: {', '.join(clean) or 'none'}")
print("  The exception was never farther than one clause from the rule, so a reader that cannot reach a far exception looks fine.")
