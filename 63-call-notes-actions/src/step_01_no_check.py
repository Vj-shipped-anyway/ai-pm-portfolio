"""Step 1 - Status quo: whatever the extractor proposes is written to the CRM.

A stub extractor reads 120 synthetic call notes and proposes actions, each with a cited sentence. Nothing
looks at the citation. This step writes every candidate and counts, against the planted truth, how many
were never in the note. The truth comes from data/_generate.py, which built each sentence knowing whether
it commits anyone to anything.

Run (from src/):  python3 step_01_no_check.py
"""
from common import load_world, score, by_cause, fmt, pct

w = load_world()
decisions = {c["cand_id"]: "ACCEPT" for c in w["cands"]}
s = score(decisions, w)
sentences = sum(len(n["sentences"]) for n in w["notes"].values())

print("step_01_no_check: extractor output written straight to the CRM")
print(f"  notes: {len(w['notes'])}   sentences: {sentences}   actions the notes commit to: {s['actions']}")
print(f"  sentences by planted role: {fmt(w['roles'])}")
print(f"  candidate actions proposed: {s['candidates']} ({s['valid']} grounded, {s['ungrounded']} not)")
print(f"  ungrounded actions written to the CRM: {s['unsafe_written']} of {s['candidates']} ({pct(s['unsafe_written'], s['candidates'])})")
print(f"  ungrounded, by planted cause: {fmt(by_cause(decisions, w, 'ACCEPT', False))}")
print(f"  planted actions that reach the CRM correctly: {s['actions_written']} of {s['actions']}")
print("  A person finds out when a client is chased for a document already sent, or never.")
