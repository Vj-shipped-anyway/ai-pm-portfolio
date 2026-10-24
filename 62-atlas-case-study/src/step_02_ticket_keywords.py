"""Step 2 - The common approach: write the case study from the ticket.

A person (or a script that stands in for one) reads the on-call note, looks for the words that point at a
technique, pastes the note in as the summary and uses the matching sentence as the procedure step. No
trace is read. The keyword table is in common.py. The leak check looks for the strings that were
planted in each ticket (an identifier in one of three forms, a first name) in the text of the draft.

Run (from src/):  python3 step_02_ticket_keywords.py
"""
from common import load_runs, keyword_draft

runs = load_runs()
drafts = []
for r in runs:
    techs, steps = keyword_draft(r["ticket"])
    if techs:
        drafts.append((r, techs, [r["ticket"]] + steps))

worthy = [r for r in runs if r["worthy"]]
harmless = [r for r in runs if not r["worthy"]]
found = sum(1 for d in drafts if d[0]["worthy"])
false = sum(1 for d in drafts if not d[0]["worthy"])
exact = sum(1 for d in drafts if d[1] == d[0]["truth"])
leaky = sum(1 for d in drafts if any(p in " ".join(d[2]) for p in d[0]["planted"]))
n_steps = sum(len(d[1]) for d in drafts)

print("STEP 2 - a draft written from the ticket's words")
print(f"  drafts written: {len(drafts)} of {len(runs)} runs")
print(f"  failures drafted: {found} of {len(worthy)}")
print(f"  harmless runs drafted as case studies: {false} of {len(harmless)}")
print(f"  drafts whose techniques equal the planted set: {exact} of {len(drafts)}")
print(f"  drafts that carry a planted identifier or name: {leaky} of {len(drafts)}")
print(f"  procedure steps that point at a call in the trace: 0 of {n_steps}")
