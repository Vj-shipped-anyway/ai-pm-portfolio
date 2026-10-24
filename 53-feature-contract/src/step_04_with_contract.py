"""Step 4 - The fix: one contract, checked before the model scores the batch.

Per field the contract states a type, a range or allowed values, and the share of nulls it allows.
Per batch it states how many rows may break a range or type rule before the field fails (a tolerance
for isolated bad rows) and what to do with a column it does not list (here: warn). Decision per batch:
FAIL if a field broke its contract, WARN if only an unlisted column appeared, otherwise PASS.
The command-line tool and the GitHub Action in action/ run exactly this code (feature_contract.py).

KNOWN LIMIT, left in on purpose: a change that stays inside the declared type, range and null rate is
not seen. The script prints those batches.

Run (from src/):  python3 step_04_with_contract.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_batches, load_contracts, basic_check, check_batch, decide, ensure_out, OUT_DIR

contracts, batches = load_contracts(), load_batches()
rows = []
for b in batches:
    fs = check_batch(contracts[b["feed"]], b["columns"], b["rows"])
    rows.append({"batch_id": b["batch_id"], "feed": b["feed"], "change_kind": b["kind"], "field": b["field"], "truth": b["truth"],
                 "decision": decide(fs), "findings": "; ".join(f"{f['kind']}:{f['field']}" for f in fs) or "none"})

bad = [r for r in rows if r["truth"] == "bad"]
ok = [r for r in rows if r["truth"] == "ok"]
stopped = sum(1 for r in bad if r["decision"] == "FAIL")
blocked = sum(1 for r in ok if r["decision"] == "FAIL")
warned = sum(1 for r in ok if r["decision"] == "WARN")
correct = stopped + sum(1 for r in ok if r["decision"] != "FAIL")
reads = sum(1 for r in rows if r["decision"] != "PASS")
step2_flags = sum(1 for b in batches if basic_check(contracts[b["feed"]], b["columns"], b["rows"]) == "FAIL")
missed = [r for r in bad if r["decision"] != "FAIL"]

print("STEP 4 - structure and values together, one contract per feed")
print(f"  bad batches stopped: {stopped} of {len(bad)}")
print(f"  harmless batches blocked: {blocked} of {len(ok)}; warned: {warned} of {len(ok)}")
print(f"  decision is right (bad stopped, harmless not blocked): {correct} of {len(rows)}")
print(f"  batches a person has to read: {reads} of {len(rows)} (the step 2 check blocked {step2_flags})")
print(f"  bad batches that still pass: {len(missed)} of {len(bad)} ({', '.join(sorted({r['change_kind'] for r in missed})) or 'none'})")
for r in missed:
    print(f"    {r['batch_id']} {r['feed']} {r['change_kind']} {r['field']}")
by_kind = Counter((r["change_kind"], r["decision"]) for r in rows)
print("  decisions by planted change:")
for kind in sorted({r["change_kind"] for r in rows}):
    print(f"    {kind:<22} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("FAIL", "WARN", "PASS") if by_kind[(kind, d)]))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
summary = {"bad_stopped": stopped, "bad": len(bad), "harmless_blocked": blocked, "harmless_warned": warned, "harmless": len(ok),
           "correct": correct, "batches": len(rows), "to_read": reads, "missed": len(missed), "step2_blocked": step2_flags}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
