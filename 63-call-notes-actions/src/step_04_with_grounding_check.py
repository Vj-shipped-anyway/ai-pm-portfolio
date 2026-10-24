"""Step 4 - The fix: one grounding check with five parts.

  1. citation   the sentence id exists and the quote is inside that sentence (normalized)
  2. support    the sentence has a trigger word for the action type and names the subject
  3. slots      the due date and the amount are in the sentence (weekday names and 'tomorrow' are resolved)
  4. owner      the sentence has a first-person commitment for rm, a third-person one for client
  5. modality   no 'if', no negation, no past tense, no hedge word in the cited sentence

Decision per candidate: REJECT when the citation or the support fails, REVIEW when a slot, the owner or the
modality is off, else ACCEPT. The command-line tool runs exactly this code (call_notes_actions.py).

KNOWN LIMIT, left in on purpose: a candidate that takes a date or a document from the other clause of a
two-clause sentence, and a commitment softened in words that are not on the lists ("I will try to", "hold off"),
pass every rule. The script prints them.

Run (from src/):  python3 step_04_with_grounding_check.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import load_world, check_all, score, by_cause, fmt, pct, ensure_out, OUT_DIR

w = load_world()
results = check_all(w["notes"], w["cands"])
decisions = {r["cand_id"]: r["decision"] for r in results}
s = score(decisions, w)
s1 = score({c["cand_id"]: "ACCEPT" for c in w["cands"]}, w)
held = s["valid_held"] + s["unsafe_held"]
missed = [r for r in results if r["decision"] == "ACCEPT" and not w["truth"][r["cand_id"]]["valid"]]

print("step_04_with_grounding_check: citation, support, slots, owner and modality together")
print(f"  ungrounded actions written to the CRM: {s['unsafe_written']} of {s['ungrounded']} ({pct(s['unsafe_written'], s['ungrounded'])}; step 1 wrote {s1['unsafe_written']})")
print(f"  ungrounded actions held for a person: {s['unsafe_held']}; rejected outright: {s['unsafe_dropped']}")
print(f"  grounded actions written: {s['valid_written']} of {s['valid']}; held for review: {s['valid_held']}; rejected: {s['valid_dropped']}")
print(f"  planted actions written correctly without a person: {s['actions_written']} of {s['actions']} (step 1: {s1['actions_written']} of {s['actions']}, with {s1['unsafe_written']} ungrounded ones beside them)")
print(f"  candidates a person reads: {held} of {s['candidates']} (reading every candidate: {s['candidates']})")
print(f"  planted actions the extractor never put out correctly: {s['actions'] - s['actions_proposed']} of {s['actions']} (the check cannot add these)")
print(f"  ungrounded actions that still pass: {len(missed)} of {s['ungrounded']} ({fmt(Counter(w['truth'][r['cand_id']]['defect'] for r in missed))})")
for r in missed:
    print(f"    {r['cand_id']} {r['note_id']} {w['truth'][r['cand_id']]['defect']}")
print(f"  grounded actions held, by planted cause: {fmt(by_cause(decisions, w, 'REVIEW', True))}")
print(f"  grounded actions rejected, by planted cause: {fmt(by_cause(decisions, w, 'REJECT', True))}")
print(f"  share of held candidates that were ungrounded: {pct(s['unsafe_held'], held)}")
by_kind = Counter((w["truth"][r["cand_id"]]["defect"], r["decision"]) for r in results)
print("  decisions by planted cause:")
for kind in sorted({k for k, _ in by_kind}):
    print(f"    {kind:<24} " + ", ".join(f"{d} {by_kind[(kind, d)]}" for d in ("ACCEPT", "REVIEW", "REJECT") if by_kind[(kind, d)]))

rows = [{"cand_id": r["cand_id"], "note_id": r["note_id"], "action_type": r["action_type"], "owner": r["owner"],
         "due": r["due"], "subject": r["subject"], "amount": r["amount"], "cite_sent_id": r["cite_sent_id"],
         "quote": r["cite_quote"], "decision": r["decision"], "reasons": "; ".join(r["reasons"]),
         "planted": w["truth"][r["cand_id"]]["defect"], "grounded": int(w["truth"][r["cand_id"]]["valid"])} for r in results]
ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    wr = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    wr.writeheader()
    wr.writerows(rows)
summary = {"candidates": s["candidates"], "grounded": s["valid"], "ungrounded": s["ungrounded"],
           "ungrounded_written": s["unsafe_written"], "ungrounded_held": s["unsafe_held"],
           "ungrounded_rejected": s["unsafe_dropped"], "grounded_written": s["valid_written"],
           "grounded_held": s["valid_held"], "grounded_rejected": s["valid_dropped"],
           "actions": s["actions"], "actions_written": s["actions_written"], "to_read": held}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
