"""Step 2 - The common basic approach: every sentence must carry a [txn: ...] bracket.

A regular expression is the first check a team writes. It splits the narrative on punctuation followed
by a space and flags every piece that holds no citation bracket. The truth label is known, so this step
counts what the check catches and what it flags by mistake.

Run (from src/):  python3 step_02_bracket_check.py
"""
import re

from common import load_corpus, misses, false_alarms, score, tally
from narrative_trace import CITE

_, narratives, truth = load_corpus()


def chunks(text):
    out, start = [], 0
    for m in re.finditer(r"(?<=[.!?])\s+", text):
        out.append((start, text[start:m.start()]))
        start = m.end()
    if text[start:].strip():
        out.append((start, text[start:]))
    return out


def has_no_bracket(case_id, text):
    return [(start, CITE.search(piece) is None) for start, piece in chunks(text)]


n_chunks = sum(len(chunks(n["text"])) for n in narratives)
flags, stray = score(narratives, truth, has_no_bracket)
t = tally(truth, flags, stray)

print("STEP 2 - flag a piece of text that has no [txn: ...] bracket (split on punctuation plus a space)")
print(f"  pieces examined: {n_chunks} for {t['defects'] + t['fine']} planted sentences")
print(f"  planted defects flagged: {t['caught']} of {t['defects']}")
uncited = t["by_kind"]["uncited"]
print(f"  of those flagged, uncited sentences: {uncited['flagged']} of {uncited['total']}; "
      f"the other {t['caught'] - uncited['flagged']} are defects that were cut in two by a period after Inc. or Ltd.")
print(f"  fine sentences flagged: {t['false_alarms']} of {t['fine']} ({false_alarms(t)})")
print(f"  defects that pass because a bracket is present: {t['defects'] - t['caught']} of {t['defects']} ({misses(t)})")
print("  A bracket that cites a record that does not exist, or the wrong one, counts the same as a good one.")
