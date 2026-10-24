"""Step 1 - Status quo: nothing checks the data before the model reads it.

Ninety deliveries of model-input data arrive from three feeds, 100 rows each. Some carry a changed
field the model should not see (a column renamed, a ratio turned into a percent, a null surge). The
pipeline loads every one of them. This step counts what reaches the model. The data is synthetic
(data/_generate.py) and the truth label of each batch is the change that was planted.

Run (from src/):  python3 step_01_no_check.py
"""
from collections import Counter

from common import load_batches

batches = load_batches()
bad = [b for b in batches if b["truth"] == "bad"]
ok = [b for b in batches if b["truth"] == "ok"]
rows_total = sum(len(b["rows"]) for b in bad)
changed_rows = sum(b["changed"] for b in bad)
by_kind = Counter(b["kind"] for b in bad)

print("STEP 1 - no input check before the model")
print(f"  deliveries: {len(batches)} batches of {len(batches[0]['rows'])} rows from {len({b['feed'] for b in batches})} feeds")
print(f"  planted truth: {len(bad)} with a changed field the model should not see, {len(ok)} harmless ({sum(1 for b in ok if b['kind'] == 'unchanged')} unchanged)")
print(f"  batches the pipeline stops: 0 of {len(batches)}")
print(f"  bad batches that reach the model: {len(bad)} of {len(batches)}")
print(f"  rows with a changed value in those batches: {changed_rows} of {rows_total}")
print("  bad batches by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(by_kind.items())))
print("  The model scores every row. The first sign is a score that moved, if anyone looks.")
