"""Step 1 - Status quo: the agent's actions are written to a JSON-lines file and nothing checks it later.

The log is built from data/actions.csv. Then 101 planted edits are applied to copies of it, one edit per
copy (data/tamper_plan.csv): 91 that change what the log says, and 10 that change only how it is written
or add events through the real writer. With no integrity check, a reader gets the log as the file says it.
The truth label of each edit comes from the plan, not from any check. The data is synthetic.

Run (from src/):  python3 step_01_no_integrity_check.py
"""
import json

from common import evaluate, tally, build_log, load_plan, apply_op, dumps_event

result = evaluate()
rows = result["rows"]
t_flag, t_all = tally(rows, "none", truth="tampered")
b_flag, b_all = tally(rows, "none", truth="benign")

print("STEP 1 (step_01_no_integrity_check.py) - a JSON-lines log with no integrity check")
print(f"  log: {result['events']} events from {result['params']['cases']} cases")
print(f"  planted edits: {len(rows)} ({t_all} tampered, {b_all} benign)")
print(f"  tampered logs flagged: {t_flag} of {t_all}")
print(f"  benign changes flagged: {b_flag} of {b_all}")

base = [dumps_event(e) for e in build_log()]
edits = [r for r in load_plan() if r["op"] == "edit_value"]
row = next((r for r in edits if json.loads(base[r["seq"] - 1])["kind"] == "approval"), edits[0])
before, after = json.loads(base[row["seq"] - 1]), json.loads(apply_op(base, row)[row["seq"] - 1])
print(f"  example, {row['tamper_id']} (edit_value at event {row['seq']}, kind {before['kind']}, actor {before['actor']}):")
print(f"    written: {json.dumps(before['detail'], sort_keys=True)}")
print(f"    after the edit: {json.dumps(after['detail'], sort_keys=True)}")
print("  Both versions are well-formed events. Nothing in the file says which one is the original.")
