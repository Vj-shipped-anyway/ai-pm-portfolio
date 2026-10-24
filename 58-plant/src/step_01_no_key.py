"""Step 1 - Status quo: bad data is added by hand and nothing records what was added.

Five test files for a ledger checker. Each is built the way test data usually is: clean rows, then a
loop that corrupts some of them at random. The corruption is not written down, so there is no answer
key. The checker (naive and tuned rule sets, src/_ledger_rules.py) runs on each file and flags rows.

Without a key, a flag count is all there is. This step prints it, and the number of rows a person
would have to read to find out which flags are right.

Run (from src/):  python3 step_01_no_key.py
"""
from common import SEEDS, LEVELS, demo_spec, flag_rows, sprinkle

spec = demo_spec()
files = {seed: sprinkle(spec, seed)["rows"] for seed in SEEDS}   # the is_bad column is dropped, as it is when mess is added by hand
counts = {lvl: [len(flag_rows(files[s], lvl)) for s in SEEDS] for lvl in LEVELS}

print("STEP 1 - the checker runs on data with no answer key")
for i, seed in enumerate(SEEDS):
    print(f"  file {seed}: {len(files[seed])} rows, naive flags {counts['naive'][i]}, tuned flags {counts['tuned'][i]}")
for lvl in LEVELS:
    print(f"  {lvl}: {min(counts[lvl])} to {max(counts[lvl])} flags per file, {sum(counts[lvl])} across the five files")
print(f"  flags that are correct: unknown. Rows to read by hand to find out: {sum(counts['naive'])} (naive) or {sum(counts['tuned'])} (tuned)")
print("  The tuned rules flag fewer rows than the naive ones. Whether that is better cannot be read from a count.")
