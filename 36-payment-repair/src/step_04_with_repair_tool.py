"""Step 4 - The fix: derive from the bank's own tables, gate what changes the payment, refuse the rest, record it.

The tool in payment_repair.py sorts every message into PASS, REPAIRED, HOLD or RETURN:
  AUTO tier       derived from the message or from the bank's own customer record; applied without a person
  APPROVAL tier   derived from a table but it decides where the money goes or what the payment says;
                  applied only with an approval for that exact plan from an active person who holds the
                  reviewer role and did not enter the payment order
  NEVER tier      amount, currency, account numbers, beneficiary name: the message goes back untouched

The approver here is a scripted test double: it approves any plan it is shown. It exercises the
control paths and says nothing about how good a real reviewer is.

KNOWN LIMITS, left in on purpose and printed: a well-formed BIC that belongs to another bank passes;
a directory that still lists a bank's old BIC, and a creditor who lives outside the IBAN country,
produce wrong proposals that a scripted approver approves.

Run (from src/):  python3 step_04_with_repair_tool.py
Output: a report, plus out/step_04_decisions.csv, out/step_04_summary.json and out/step_04_audit.csv
"""
from __future__ import annotations

import csv
import json
import os
import random
from collections import Counter

from common import OUT_DIR, basic_fill, defect_status, ensure_out, load_messages, load_truth, load_world
from payment_repair import (APPROVAL, AUDIT_COLUMNS, LABELS, MSG_ID, REVIEWER_ROLE, RMT, audit_rows, clean, order_initiator,
                            repair_all, write_audit)

messages, world = load_messages(), load_world()
refs = world["refs"]
routes, defects = load_truth()
by_id = {m[MSG_ID]: m for m in messages}
true_value = {(mid, d["path"]): d["true_value"] for mid, ds in defects.items() for d in ds}

# ---- run A: no approvals on file
run_a, _ = repair_all(messages, refs, [])
route_a = {r["msg_id"]: r["route"] for r in run_a}
count_a = Counter(route_a.values())
auto_edits = [(r["msg_id"], e) for r in run_a if r["route"] == "REPAIRED" for e in r["edits"]]
auto_correct = sum(1 for mid, e in auto_edits if true_value.get((mid, e["path"])) == e["new"])
hold = [r for r in run_a if r["route"] == "HOLD"]
returned = [r for r in run_a if r["route"] == "RETURN"]
untouched = sum(1 for r in returned if r["message"] is by_id[r["msg_id"]])
intended = {mid: routes[mid]["intended_route"] for mid in routes}
match = sum(1 for mid in route_a if route_a[mid] == intended[mid])
mismatch = Counter(routes[mid]["recipe"] for mid in route_a if route_a[mid] != intended[mid])
passers = [mid for mid in intended if intended[mid] == "PASS"]
false_alarm = sum(1 for mid in passers if route_a[mid] != "PASS")
unwanted_return = sum(1 for mid in route_a if route_a[mid] == "RETURN" and intended[mid] != "RETURN")
negative_total = Counter(routes[mid]["recipe"] for mid in routes if routes[mid]["hardness"] == "hard_negative")
negatives = Counter(routes[mid]["recipe"] for mid in routes if routes[mid]["hardness"] == "hard_negative" and route_a[mid] == "PASS")

print("STEP 4 - the repair tool: derive, gate, refuse, record")
print(f"RUN A (no approvals on file): {count_a['PASS']} pass, {count_a['REPAIRED']} repaired without a person, "
      f"{count_a['HOLD']} hold for approval, {count_a['RETURN']} return")
print(f"  route matches the planted intent: {match} of {len(messages)}"
      + ("; the rest: " + ", ".join(f"{k} {v}" for k, v in sorted(mismatch.items())) if mismatch else ""))
print(f"  repairs applied without a person: {len(auto_edits)} fields, equal to the true value on {auto_correct}")
print(f"  messages that should pass and did not: {false_alarm} of {len(passers)}; returned although a repair was intended: {unwanted_return}")
print("  hard negatives left alone: " + ", ".join(f"{k} {negatives[k]} of {negative_total[k]}" for k in sorted(negative_total)))
print(f"  returned: {len(returned)} messages, {untouched} of {len(returned)} left untouched (no value written)")


# ---- the approval gate, probed
def reviewers() -> list:
    return sorted(a for a, row in refs["approvers"].items() if row["kind"] == "person" and row["role"] == REVIEWER_ROLE
                  and row["active"] == "yes")


def row(r, approver, digest=None):
    return {"msg_id": r["msg_id"], "plan_digest": digest or r["digest"], "approver_id": approver, "decision": "approve"}


def good_row(r):
    who = [a for a in reviewers() if a != order_initiator(by_id[r["msg_id"]], refs)]
    return row(r, who[0])


def applied(msgs, rows, ids):
    res, _ = repair_all(msgs, refs, rows)
    return sum(1 for x in res if x["msg_id"] in ids and x["route"] == "REPAIRED")


def role_of(kind_filter):
    return sorted(a for a, v in refs["approvers"].items() if kind_filter(v))


hold_ids = {r["msg_id"] for r in hold}
agent = role_of(lambda v: v["kind"] == "agent")[0]
inactive = role_of(lambda v: v["kind"] == "person" and v["active"] == "no")[0]
initiator_role = role_of(lambda v: v["kind"] == "person" and v["role"] != REVIEWER_ROLE and v["active"] == "yes")
rev_initiated = [r for r in hold if order_initiator(by_id[r["msg_id"]], refs) in reviewers()]
probes = [
    ("no approval on file", [], hold_ids),
    ("approval carries another plan's digest", [row(r, reviewers()[0], hold[(i + 1) % len(hold)]["digest"]) for i, r in enumerate(hold)], hold_ids),
    ("approver is an agent", [row(r, agent) for r in hold], hold_ids),
    ("approver is a person who left the team", [row(r, inactive) for r in hold], hold_ids),
    ("approver is a person without the reviewer role",
     [row(r, [a for a in initiator_role if a != order_initiator(by_id[r["msg_id"]], refs)][0]) for r in hold], hold_ids),
    ("approver entered the payment order", [row(r, order_initiator(by_id[r["msg_id"]], refs)) for r in rev_initiated],
     {r["msg_id"] for r in rev_initiated}),
]
print(f"APPROVAL GATE (scripted approver; {len(hold)} messages hold for approval)")
blocked_total = attempted_total = 0
for label, rows, ids in probes:
    n = len(ids)
    ok = applied(messages, rows, ids)
    blocked_total += n - ok
    attempted_total += n
    print(f"  {label:<48} blocked {n - ok} of {n}")
good = [good_row(r) for r in hold]
changed = [dict(by_id[r["msg_id"]], **{RMT: "edited after the plan was drawn up"}) for r in hold]
ok = applied(changed, good, hold_ids)
blocked_total += len(hold) - ok
attempted_total += len(hold)
print(f"  {'message changed after the plan was drawn up':<48} blocked {len(hold) - ok} of {len(hold)}")
ok = applied(messages, good, hold_ids)
print(f"  {'valid approval for that exact plan':<48} applied {ok} of {len(hold)}")

# ---- run C: the valid approvals are on file
run_c, _ = repair_all(messages, refs, good)
route_c = {r["msg_id"]: r["route"] for r in run_c}
count_c = Counter(route_c.values())
finals = {r["msg_id"]: r["message"] for r in run_c}
replay, unused_replay = repair_all([finals[m[MSG_ID]] for m in messages], refs, good)
replay_changes = sum(len(r["edits"]) for r in replay)
print(f"  same approvals shown again on the repaired messages: {unused_replay['not_needed']} rows ignored as not needed, {replay_changes} further changes")

# ---- values and the answer key
status = defect_status(by_id, finals, defects)
applied_edits = [(r["msg_id"], e) for r in run_c if r["route"] == "REPAIRED" for e in r["edits"]]
wrong_applied = [(mid, e) for mid, e in applied_edits if true_value.get((mid, e["path"])) != e["new"]]
approved_edits = [(mid, e) for mid, e in applied_edits if e["tier"] == APPROVAL]
approved_right = sum(1 for mid, e in approved_edits if true_value.get((mid, e["path"])) == e["new"])
released = {mid for mid in route_c if route_c[mid] in ("PASS", "REPAIRED")}
bad_released = sorted({mid for (mid, p), s in status.items() if s != "correct" and mid in released})
basic_rng = random.Random(2)
basic_finals = {m[MSG_ID]: basic_fill(m, world, basic_rng)[0] for m in messages}
basic_bad = sorted({mid for (mid, p), s in defect_status(by_id, basic_finals, defects).items() if s != "correct"})
print(f"RUN C (valid approvals on file): {count_c['PASS']} pass, {count_c['REPAIRED']} repaired, {count_c['HOLD']} hold, {count_c['RETURN']} return")
print(f"  changes after approval: {len(approved_edits)} fields, equal to the true value on {approved_right}")
print(f"  wrong values applied: {len(wrong_applied)} ("
      + ", ".join(f"{k} {v}" for k, v in sorted(Counter(routes[mid]["recipe"] for mid, _ in wrong_applied).items())) + ")")
print(f"  messages released with a wrong or unusable required value: {len(bad_released)} of {len(released)} released "
      f"(the basic script in step 3: {len(basic_bad)} of {len(messages)})")
print("    " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(routes[mid]["recipe"] for mid in bad_released).items())))

# ---- the record
audit = audit_rows(run_c)
fields_changed = sum(1 for mid in released for k in set(by_id[mid]) | set(finals[mid]) if by_id[mid].get(k) != finals[mid].get(k))
no_source = sum(1 for a in audit if not a[AUDIT_COLUMNS.index("source")])
no_person = sum(1 for a in audit if a[AUDIT_COLUMNS.index("tier")] == APPROVAL and not a[AUDIT_COLUMNS.index("approved_by")])
print(f"AUDIT: {len(audit)} rows for {fields_changed} fields changed; rows without a source: {no_source}; "
      f"approval-tier rows without an approver: {no_person}")

print("KNOWN LIMITS (left in on purpose)")
wrong_pass = [mid for mid in released if routes[mid]["recipe"] == "bic_present_wrong"]
print(f"  1. A well-formed creditor BIC that belongs to another bank passes: {len(wrong_pass)} of "
      f"{sum(1 for mid in routes if routes[mid]['recipe'] == 'bic_present_wrong')} planted. The tool checks presence and shape, not consistency with the IBAN.")
print(f"  2. {len(wrong_applied)} wrong proposals reach the gate and the scripted approver approves them. "
      f"A real reviewer's catch rate is not measured.")
for mid, e in wrong_applied[:3]:
    print(f"       {mid} {LABELS[e['path']]}: proposed {clean(e['new'])}, true value {clean(true_value[(mid, e['path'])])} ({routes[mid]['recipe']})")

# ---- files for the demo
ensure_out()
rows_out = []
res_by_id = {r["msg_id"]: r for r in run_c}
for m in messages:
    mid = m[MSG_ID]
    r = res_by_id[mid]
    st = [status[(mid, d["path"])] for d in defects.get(mid, [])]
    if not st:
        value = "-"
    elif "filled_wrong" in st:
        value = "wrong value applied"
    elif "wrong_untouched" in st:
        value = "wrong value untouched"
    elif r["route"] in ("RETURN", "HOLD"):
        value = "not changed"
    else:
        value = "all correct"
    if r["refusals"]:
        note = "; ".join(f"{LABELS[f['path']] if f['path'] else 'plan'}: {f['reason']}" for f in r["refusals"])
    elif r["edits"]:
        note = "; ".join(f"{LABELS[e['path']]} from {e['source']}" for e in r["edits"])
    else:
        note = ""
    rows_out.append({"msg_id": mid, "recipe": routes[mid]["recipe"], "hardness": routes[mid]["hardness"],
                     "intended_route": intended[mid], "route_before_approval": route_a[mid], "route_after_approval": route_c[mid],
                     "changes": len(r["edits"]) if r["route"] == "REPAIRED" else 0, "value_check": value, "note": clean(note, 160)})
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows_out[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows_out)
write_audit(os.path.join(OUT_DIR, "step_04_audit.csv"), audit)
summary = {"messages": len(messages), "route_match": match, "pass_a": count_a["PASS"], "repaired_a": count_a["REPAIRED"],
           "hold_a": count_a["HOLD"], "return_a": count_a["RETURN"], "auto_fields": len(auto_edits), "auto_correct": auto_correct,
           "probes_attempted": attempted_total, "probes_blocked": blocked_total, "approved_fields": len(approved_edits),
           "approved_correct": approved_right, "wrong_applied": len(wrong_applied), "bad_released": len(bad_released),
           "basic_bad": len(basic_bad), "false_alarm": false_alarm, "audit_rows": len(audit)}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv, step_04_summary.json and step_04_audit.csv in src/out/")
