"""Step 2 - The common basic approach: check the header and the column types.

This is the first check a team adds, and the one a dataframe load gives for free. The header must
equal the expected column list, in order, and the type inferred from each column's values must match
the declared type. Nothing else looks at a value. The truth label is known, so this step counts what
it stops, what it passes, and what it blocks for no reason.

Run (from src/):  python3 step_02_header_and_type.py
"""
from collections import Counter

from common import load_batches, load_contracts, basic_check

contracts, batches = load_contracts(), load_batches()
got = {b["batch_id"]: basic_check(contracts[b["feed"]], b["columns"], b["rows"]) for b in batches}
bad = [b for b in batches if b["truth"] == "bad"]
ok = [b for b in batches if b["truth"] == "ok"]
stopped = [b for b in bad if got[b["batch_id"]] == "FAIL"]
passed = [b for b in bad if got[b["batch_id"]] == "PASS"]
false_alarms = [b for b in ok if got[b["batch_id"]] == "FAIL"]
flagged = sum(1 for v in got.values() if v == "FAIL")

print("STEP 2 - header and type check")
print(f"  bad batches stopped: {len(stopped)} of {len(bad)}")
print(f"  harmless batches blocked: {len(false_alarms)} of {len(ok)}")
print(f"  share of blocks that are harmless: {len(false_alarms) / flagged:.1%}")
print("  harmless blocked by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(b['kind'] for b in false_alarms).items())))
print(f"  bad batches that pass: {len(passed)} of {len(bad)}")
print("  passing by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(b['kind'] for b in passed).items())))
print("  A column can keep its name and its type and carry values the model has never seen.")
