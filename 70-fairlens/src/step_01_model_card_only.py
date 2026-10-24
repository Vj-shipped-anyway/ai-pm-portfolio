"""Step 1 - Status quo: the model card reports accuracy and approval, and nothing by group.

Thirty-six synthetic scorecard portfolios, each scored at its own policy cutoff. The truth is
what the generator planted (data/_generate.py): 14 portfolios carry a proxy, 22 do not. This
step prints what the model card shows for them, and how much of it separates the two sets.

Run (from src/):  python3 step_01_model_card_only.py
"""
from common import load_cases, run_cases, mechanisms

cases = load_cases()
packs = run_cases(cases)
planted = [c for c in cases if c["planted"]]


def mean(xs):
    return sum(xs) / len(xs)


print("STEP 1 - model card only")
sizes = [len(c["data"].scores) for c in cases]
print(f"  portfolios: {len(cases)}   planted proxy: {len(planted)}   no planted proxy: {len(cases) - len(planted)}")
print(f"  applicants per portfolio: {min(sizes)} to {max(sizes)} ({sum(sizes):,} in all)")
print("  mechanism            portfolios  mean accuracy  mean approval")
for m in mechanisms(cases):
    ps = [packs[c["id"]]["gs"] for c in cases if c["mechanism"] == m]
    print(f"  {m:<20} {len(ps):>10}  {100 * mean([g['accuracy'] for g in ps]):>12.1f}%  {100 * mean([g['approval_rate'] for g in ps]):>12.1f}%")
acc_p = mean([packs[c["id"]]["gs"]["accuracy"] for c in planted])
acc_n = mean([packs[c["id"]]["gs"]["accuracy"] for c in cases if not c["planted"]])
print(f"  mean accuracy, planted proxy: {100 * acc_p:.1f}%   no planted proxy: {100 * acc_n:.1f}%   gap {100 * abs(acc_p - acc_n):.1f} points")
below = [c for c in cases if packs[c["id"]]["gs"]["min_air"] < 0.80]
print(f"  portfolios whose lowest group approves under 0.80 of the reference rate: {len(below)} of {len(cases)}")
print("  fairness tests the card runs: 0 of 6. Accuracy alone does not say which portfolios carry a proxy or which group pays for it.")
