"""Step 3 - Where each gate fails when used alone.

Gates, each built from the checks in call_notes_actions.py:
  citation only         the sentence id exists and the quote is inside that sentence, compared after normalizing
  citation + support    the above, plus: the sentence has a trigger word for the action type and names its
                        subject, the due date and amount match the sentence, and the owner matches who is
                        speaking. No look at whether the sentence is conditional, negated, past or hedged.

The truth is known, so each gate is scored on the same candidates. KNOWN LIMIT, left in on purpose: a quote
that is real, supports the action and agrees with every slot can still be the wrong clause or a softened
commitment. Step 4 does not catch those, and the script prints them there.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_world, check_all, score, by_cause, fmt

w = load_world()


def decisions(checks):
    return {r["cand_id"]: r["decision"] for r in check_all(w["notes"], w["cands"], checks)}


print("step_03_deficiencies_exposed: each gate alone")
cite = decisions(("cite",))
support = decisions(("cite", "support", "slots", "owner"))
for name, d in (("citation only", cite), ("citation + support", support)):
    s = score(d, w)
    print(f"  {name}")
    print(f"    ungrounded stopped (held or dropped): {s['unsafe_held'] + s['unsafe_dropped']} of {s['ungrounded']}; still written: {s['unsafe_written']}")
    print(f"    grounded actions wrongly rejected: {s['valid_dropped']} of {s['valid']}; held for review: {s['valid_held']}")
    print(f"    still written, by planted cause: {fmt(by_cause(d, w, 'ACCEPT', False))}")
print("  Citation alone cannot tell a sentence that carries the action from one that merely exists.")
print("  Support alone reads a conditional, negated, past or hedged sentence as a commitment.")
