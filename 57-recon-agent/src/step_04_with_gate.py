"""Step 4 - The fix: a proposer that shows evidence, a check that re-runs the rules, and an approval gate.

  1. propose: five rules in a fixed order; every match cites the lines, the rule and the facts it rests on
  2. check: the rule is re-run on exactly the lines the match cites; a match that fails is never posted
  3. gate: a match posts on its own only if its rule allows it (ref_exact, at or below the limit, names
     agree); anything else posts only on a recorded approval for exactly that proposal from someone else
  4. report: every line not posted is listed with a reason

The approver here is a script (common.reviewer_double) that reads what is printed with each proposal and
approves unless the counterparty names differ. It stands in for a person and is not a measure of one.

KNOWN LIMITS, left in on purpose and printed: the 6 look-alike invoices one edit apart from a real one are
indistinguishable, in these fields, from the 15 real typos; and the true matches the five rules cannot make
(step 3) stay open.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_matches.csv, out/step_04_unmatched.csv and out/step_04_summary.json
"""
import json
import os
from collections import Counter

from common import (load_data, load_truth, run_agent, score, pair_of, reconcile, ensure_out, OUT_DIR, POSTED)
from recon_agent import write_outputs, load_matches, verify_matches


def kinds(counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "none"


a_rows, b_rows = load_data()
truth = load_truth()
first = reconcile(a_rows, b_rows, [])
need = [q for q in first["proposals"] if q["gate"] == "approval"]
res = run_agent(a_rows, b_rows)
props = res["proposals"]
posted = [q for q in props if q["status"] in POSTED]
auto = [q for q in posted if q["status"] == "posted_auto"]
approved = [q for q in posted if q["status"] == "posted_approved"]
rejected = [q for q in props if q["status"] == "rejected"]
s_all, s_auto, s_app = (score([pair_of(q) for q in grp], truth) for grp in (posted, auto, approved))
rejected_true = sum(1 for q in rejected if pair_of(q) in truth["match"])
unseen = sum(1 for q in posted if q["gate"] == "approval" and not q["approver"])
lines_auto = 2 * len(auto) + sum(len(q["b_ids"]) - 1 for q in auto)
lines_total = len(a_rows) + len(b_rows)
open_by = Counter(o["reason"] for o in res["open"])

print("STEP 4 - proposer, check and approval gate")
print(f"  proposals: {len(props)}; allowed to post on their own: {len(props) - len(need)}; need a person: {len(need)}")
print(f"  posted on their own: {len(auto)}; wrong: {s_auto['wrong']}")
print(f"  posted on approval: {len(approved)} (the scripted approver approved {len(approved)} and rejected {len(rejected)}); wrong: {s_app['wrong']} ({kinds(s_app['wrong_by_kind'])})")
print(f"  of the {len(rejected)} rejections by the scripted approver, right matches: {rejected_true}")
print(f"  posted where the policy needs an approval and none is on record: {unseen}")
print(f"  true matches posted: {s_all['found']} of {s_all['true_pairs']}")
print(f"  open lines: {len(res['open'])} ({kinds(open_by)})")
print(f"  lines a person has to look at: {lines_total - lines_auto} of {lines_total} (step 1: {lines_total})")

# the gate under attack: records that must not post anything
n = len(need)
variants = ["recon-agent", "Recon-Agent", " RECON-AGENT "]
selfs = [{"key": q["key"], "decision": "approve", "approver": variants[i % 3], "note": ""} for i, q in enumerate(need)]
stale = [{"key": q["key"] + "0", "decision": "approve", "approver": "reviewer-1", "note": ""} for q in need]
both = [r for q in need[:10] for r in ({"key": q["key"], "decision": "approve", "approver": "reviewer-1", "note": ""},
                                       {"key": q["key"], "decision": "reject", "approver": "reviewer-2", "note": ""})]
r_self, r_stale, r_both = (reconcile(a_rows, b_rows, recs) for recs in (selfs, stale, both))
print("  approval records the gate refuses:")
print(f"    self-approval by the agent (three spellings): {len(r_self['refused'])} of {n} refused, {sum(1 for q in r_self['proposals'] if q['status'] == 'posted_approved')} posted")
print(f"    approval for a proposal that no longer exists (key altered): {len(r_stale['refused'])} of {n} refused, {sum(1 for q in r_stale['proposals'] if q['status'] == 'posted_approved')} posted")
print(f"    one approve and one reject for the same proposal: {sum(1 for r in r_both['refused'] if r['why'].startswith('conflicting'))} of 10 left pending, {sum(1 for q in r_both['proposals'] if q['status'] == 'posted_approved')} posted")

# the check under tampering: a finished match list edited by hand
ensure_out()
write_outputs(res, OUT_DIR, "step_04_")
rows = load_matches(os.path.join(OUT_DIR, "step_04_matches.csv"))
base = verify_matches(a_rows, b_rows, rows)
failing = {line.split(":")[0] for line in base}
live = [m for m in rows if m["status"] in POSTED]
b_ids_sorted = sorted(b["id"] for b in b_rows)


def swap(m):
    other = next(i for i in b_ids_sorted if i not in m["b_ids"].split("+"))
    return dict(m, b_ids=other)


caught_swap = sum(1 for m in live if m["rule"] != "batch_sum" and verify_matches(a_rows, b_rows, [swap(m)]))
singles = sum(1 for m in live if m["rule"] != "batch_sum")
flips = [m for m in live if m["status"] == "posted_approved"]
caught_flip = sum(1 for m in flips if verify_matches(a_rows, b_rows, [dict(m, status="posted_auto")]))
caught_dup = sum(1 for m in live if verify_matches(a_rows, b_rows, [m, dict(m, match_id="M-9999")]))
print("  the check on a finished match list:")
print(f"    posted matches that re-check against the ledgers: {len(live) - len(failing)} of {len(live)} ({len(base)} problems)")
print(f"    one book line swapped for another: {caught_swap} of {singles} caught")
print(f"    an approved match relabelled as posted on its own: {caught_flip} of {len(flips)} caught")
print(f"    a posted match copied under a second id: {caught_dup} of {len(live)} caught")

proposed = {pair_of(q) for q in props}
left = [(p, k) for p, k in sorted(truth["match"].items()) if p not in proposed and k["kind"] != "twin_payments"]
parked_a = sum(1 for (side, _) in res["parked"] if side == "A")
print(f"  sent to a person as undecidable: {parked_a} bank lines (twin_payments)")
print(f"  KNOWN LIMIT: true matches the five rules never propose: {len(left)} ({kinds(Counter(k['kind'] for _, k in left))}); they sit in the open list")
print(f"  KNOWN LIMIT: the scripted approver approved all {sum(1 for q in props if q['rule'] == 'ref_near' and q['status'] in POSTED)} ref_near proposals, and {s_app['wrong']} of them are distinct invoices one edit away from a real one")

summary = {"bank_lines": len(a_rows), "book_lines": len(b_rows), "proposals": len(props), "need_person": n, "posted_auto": len(auto),
           "posted_approved": len(approved), "rejected": len(rejected), "wrong_auto": s_auto["wrong"], "wrong_approved": s_app["wrong"],
           "rejected_right": rejected_true, "true_found": s_all["found"], "true_matches": s_all["true_pairs"], "open_lines": len(res["open"]),
           "to_read": lines_total - lines_auto, "lines": lines_total, "unseen": unseen, "refused_self": len(r_self["refused"]),
           "refused_stale": len(r_stale["refused"]), "check_problems": len(base), "parked_bank_lines": parked_a,
           "open_by_reason": dict(sorted(open_by.items()))}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_matches.csv, step_04_unmatched.csv and step_04_summary.json in src/out/")
