"""Step 4 - The fix: check every instruction against its mandate, keep a ledger, write an audit record.

  1. identity and validity: the mandate exists, belongs to this agent, and is inside its dates and not revoked
  2. the payee by id, with the account the mandate pins, and the currency, rail and category
  3. amount: per-payment limit (reject) and confirmation threshold (hold for a person)
  4. a ledger of what was released: the daily limit, repeated instruction ids, the same payee and amount again
  5. one hash-chained audit record per decision

Decision per instruction: REJECT if anything is outside the mandate, HOLD if it is inside but a person
should look, else RELEASE. The command-line tool runs exactly this code (payment_mandate_check.py).

KNOWN LIMIT, left in on purpose: split payments whose pieces each sit under the confirmation threshold,
and a memo that contradicts the declared category, are released. The script prints them.

Run (from src/):  python3 step_04_with_mandate_check.py
Output: a report, plus out/step_04_decisions.csv, out/step_04_summary.json and out/step_04_audit.jsonl
"""
import copy
import csv
import json
import os
from collections import Counter

from common import (load_case, check_batch, audit_records, verify_audit, score, ensure_out, OUT_DIR,
                    HARD_NEGATIVE, RELEASE, HOLD, REJECT)

mandates, rows, truth = load_case()
results = check_batch(mandates, rows)
got = {r["submission_id"]: r["decision"] for r in results}
s = score(got, truth)
n = Counter(t["truth_decision"] for t in truth.values())
held = sum(1 for sid, d in got.items() if d == HOLD and truth[sid]["truth_decision"] == HOLD)
rejected = sum(1 for sid, d in got.items() if d == REJECT and truth[sid]["truth_decision"] == REJECT)
released = sum(1 for sid, d in got.items() if d == RELEASE and truth[sid]["truth_decision"] == RELEASE)
hard = [sid for sid, t in truth.items() if t["kind"] in HARD_NEGATIVE]
hard_ok = sum(1 for sid in hard if got[sid] == RELEASE)
missed = [sid for sid, d in got.items() if d == RELEASE and truth[sid]["truth_decision"] != RELEASE]
missed_by_kind = Counter(truth[sid]["kind"] for sid in missed)
mandates_per_id = {}
for r in rows:
    mandates_per_id.setdefault(r["instruction_id"], set()).add(r["mandate_id"])
shared_ids = sum(1 for v in mandates_per_id.values() if len(v) > 1)

records = audit_records(results)
ok, msg = verify_audit(records)
tampered = copy.deepcopy(records)
victim = next(i for i in range(len(tampered) // 2, len(tampered)) if tampered[i]["decision"] == REJECT)
tampered[victim]["decision"] = RELEASE
tampered_ok, tampered_msg = verify_audit(tampered)
cut_plain = verify_audit(records[:-1])[1]
cut_head = verify_audit(records[:-1], head=records[-1]["hash"])[1]

print("STEP 4 - mandate check with ledger and audit record")
print(f"  inside the mandate and released: {released} of {n['RELEASE']}")
print(f"  for a person and held: {held} of {n['HOLD']}")
print(f"  outside the mandate and rejected: {rejected} of {n['REJECT']}")
print(f"  legitimate instructions stopped: {s['legit_stopped']} of {n['RELEASE']}")
print(f"  hard negatives released (limits to the cent, last second, hostile memo and others): {hard_ok} of {len(hard)}")
print(f"  instruction_ids that appear on more than one mandate (a check keyed on the id alone would call these duplicates): {shared_ids}")
print(f"  decision matches the planted truth: {s['exact']} of {len(rows)}")
print(f"  still released although they should not be: {len(missed)} of {len(rows)} ({', '.join(f'{k} {v}' for k, v in sorted(missed_by_kind.items()))})")
for sid in missed[:3]:
    print(f"    {sid} {truth[sid]['kind']} group {truth[sid]['group_id']}")
by_kind = Counter((t["kind"], got[sid]) for sid, t in truth.items())
print("  decisions by planted scenario:")
for kind in sorted({t["kind"] for t in truth.values()}):
    print(f"    {kind:<27} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in (RELEASE, HOLD, REJECT) if by_kind[(kind, d)]))
print(f"  audit: {msg}")
print(f"  audit with one decision edited after the fact: {tampered_msg}")
print(f"  audit with the last record cut off, no head recorded: {cut_plain}")
print(f"  audit with the last record cut off, checked against the recorded head: {cut_head}")

rows_out = []
for r in results:
    t = truth[r["submission_id"]]
    rows_out.append({"submission_id": r["submission_id"], "mandate_id": r["mandate_id"], "payee_id": r["payee_id"], "amount": r["amount"],
                     "currency": r["currency"], "received_at": r["received_at"], "kind": t["kind"], "truth": t["truth_decision"],
                     "decision": r["decision"], "reasons": ";".join(x["code"] for x in r["reasons"]) or "none"})
summary = {"instructions": len(rows), "mandates": len(mandates), "released": released, "inside": n["RELEASE"], "held": held,
           "for_person": n["HOLD"], "rejected": rejected, "outside": n["REJECT"], "legit_stopped": s["legit_stopped"],
           "exact_match": s["exact"], "still_released": len(missed), "hard_negatives": len(hard), "hard_negatives_released": hard_ok,
           "audit_records": len(records)}
ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows_out[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows_out)
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
with open(os.path.join(OUT_DIR, "step_04_audit.jsonl"), "w", encoding="utf-8") as fh:
    for rec in records:
        fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")
print("Wrote step_04_decisions.csv, step_04_summary.json and step_04_audit.jsonl in src/out/")
