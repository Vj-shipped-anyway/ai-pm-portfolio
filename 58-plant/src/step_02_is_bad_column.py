"""Step 2 - The common basic approach: random corruption and one is_bad column.

Same five files as step 1, now with a column that says which rows were corrupted. This is what most
teams do next: score the checker's flags against that column and report recall and precision.

Run (from src/):  python3 step_02_is_bad_column.py
"""
from common import SEEDS, LEVELS, boolean_key, demo_spec, flag_rows, score, sprinkle

spec = demo_spec()
pooled = {lvl: {"found": 0, "positives": 0, "flagged": 0} for lvl in LEVELS}

print("STEP 2 - score against an is_bad column")
for seed in SEEDS:
    made = sprinkle(spec, seed)
    key = boolean_key(made)
    cells = []
    for lvl in LEVELS:
        sc = score(key, len(made["rows"]), set(flag_rows(made["rows"], lvl)))
        for k in pooled[lvl]:
            pooled[lvl][k] += sc[k]
        cells.append(f"{lvl} recall {sc['recall']:.2f} precision {sc['precision']:.2f}")
    print(f"  file {seed}: {len(key)} rows marked is_bad; " + "; ".join(cells))
for lvl in LEVELS:
    p = pooled[lvl]
    print(f"  {lvl}, five files pooled: recall {p['found'] / p['positives']:.2f}, precision {p['found'] / p['flagged']:.2f} ({p['found']} of {p['positives']} marked rows found)")
print("  The tuned rules look better on precision and level on recall. The report ends there.")
