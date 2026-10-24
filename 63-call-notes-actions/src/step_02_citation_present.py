"""Step 2 - The common basic approach: every action must carry a citation.

Two versions of the rule a team adds first:
  presence     the cite_quote field is not empty
  exact match  the quote appears, character for character, somewhere in the note text

Neither looks at which sentence the citation points to, and the exact match treats a model's tidied quote
(curly apostrophe, doubled space, cut short with an ellipsis, lower case) as a fabrication.

Run (from src/):  python3 step_02_citation_present.py
"""
from common import load_world, score, by_cause, fmt

w = load_world()
text = {nid: "\n".join(n["sentences"][k] for k in sorted(n["sentences"])) for nid, n in w["notes"].items()}

presence = {c["cand_id"]: "ACCEPT" if c["cite_quote"].strip() else "REJECT" for c in w["cands"]}
exact = {c["cand_id"]: "ACCEPT" if c["cite_quote"] and c["cite_quote"] in text.get(c["note_id"], "") else "REJECT"
         for c in w["cands"]}

print("step_02_citation_present: require a citation")
for name, d in (("presence of a quote", presence), ("exact quote anywhere in the note", exact)):
    s = score(d, w)
    print(f"  {name}")
    print(f"    ungrounded actions stopped: {s['unsafe_dropped']} of {s['ungrounded']}; still written: {s['unsafe_written']}")
    print(f"    grounded actions wrongly rejected: {s['valid_dropped']} of {s['valid']}")
print(f"  grounded actions the exact match rejects, by planted cause: {fmt(by_cause(exact, w, 'REJECT', True))}")
print(f"  ungrounded actions the exact match lets through, by planted cause: {fmt(by_cause(exact, w, 'ACCEPT', False))}")
print("  A quote that exists is not the same as a sentence that supports the action.")
