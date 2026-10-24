"""Step 2 - The common basic approach: one agreement rate, a bar and a confusion matrix.

The usual improvement on a bare number is to set a bar before the run and add a confusion matrix.
The bar here is 90% (an assumption of mine, not a standard). The matrix shows which outcome the
agent proposed against which outcome the person recorded.

Run (from src/):  python3 step_02_overall_agreement.py
"""
from common import load, score, RULES

BAR = 0.90
proposals, outcomes = load()
s = score(proposals, outcomes, RULES)
labels = sorted({h for row in s["confusion"].values() for h in row})

print("STEP 2 - one rate, a bar and a confusion matrix")
print(f"  agreement on proposals made: {s['agree']} of {s['proposed']} = {s['headline']:.1%}   bar: {BAR:.0%}")
print(f"  meets the bar: {'yes' if s['headline'] >= BAR else 'no'}")
print("  confusion matrix (rows: what the agent proposed; columns: what the person recorded)")
print("    " + " " * 16 + "".join(f"{h[:12]:>14}" for h in labels))
for prop, row in s["confusion"].items():
    print(f"    {prop[:16]:<16}" + "".join(f"{row.get(h, 0):>14}" for h in labels))
off = sum(n for prop, row in s["confusion"].items() for h, n in row.items() if prop != h and prop != "(abstained)")
print(f"  off-diagonal cells, abstentions left out: {off} cases")
print("  The matrix says which outcomes get confused. It does not say in which segment, in which week, "
      "with which reviewer, or whether the person was the one who was wrong.")
