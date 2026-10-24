"""Step 3 - Where the basic script breaks, scored against the answer key.

The same script as step 2, run on the same 500 messages. The answer key holds the true value of
every field the generator damaged, so each fill can be scored: correct, written wrong, left
unusable. KNOWN LIMIT, left in on purpose: twelve messages carry a well-formed BIC that belongs to a
different bank. The script does not see them, and neither does the tool in step 4.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

import random
from collections import Counter

from common import basic_fill, defect_status, load_messages, load_truth, load_world
from payment_repair import AUTO, CCY, CDTR_BIC, CDTR_NM, LABELS, MSG_ID, POLICY, REQUIRED, UETR

messages, world = load_messages(), load_world()
routes, defects = load_truth()
rng = random.Random(2)
final, wrote = {}, {}
for m in messages:
    final[m[MSG_ID]], wrote[m[MSG_ID]] = basic_fill(m, world, rng)
by_id = {m[MSG_ID]: m for m in messages}

status = defect_status(by_id, final, defects)
wrong_by_field, wrong_by_recipe = Counter(), Counter()
for (mid, path), s in status.items():
    if s == "filled_wrong":
        wrong_by_field[path] += 1
        wrong_by_recipe[routes[mid]["recipe"]] += 1
tally = Counter(status.values())
total = len(status)

print("STEP 3 - the basic script, scored against the answer key")
print("(a) What it wrote")
print(f"    planted defective fields: {total}")
print(f"    ended correct: {tally['correct']}   written wrong: {tally['filled_wrong']}   left unusable: {tally['left_unusable']}   "
      f"present and wrong, untouched: {tally['wrong_untouched']}")
print("    written wrong, by field: " + ", ".join(f"{LABELS[p]} {n}" for p, n in sorted(wrong_by_field.items(), key=lambda x: LABELS[x[0]])))
print("    written wrong, by planted recipe: " + ", ".join(f"{k} {v}" for k, v in sorted(wrong_by_recipe.items())))

print("(b) It fills where no table can prove the value")
for p in (CCY, CDTR_NM):
    filled = [(mid, p) for mid in wrote if p in wrote[mid]]
    ok = sum(1 for k in filled if status.get(k) == "correct")
    print(f"    {LABELS[p]}: filled on {len(filled)} messages, right on {ok}, wrong on {len(filled) - ok}")
invented = [mid for mid in wrote if UETR in wrote[mid] and routes[mid]["recipe"] == "uetr_missing_no_order"]
print(f"    UETR with no payment order: invented on {len(invented)} messages, right on "
      f"{sum(1 for mid in invented if status.get((mid, UETR)) == 'correct')}")

garbage = sorted({mid for (mid, p), s in status.items() if s == "left_unusable" and (final[mid].get(p) or "") != ""})
absent = sum(1 for mid in final if any((final[mid].get(p) or "") == "" for p in REQUIRED))
print("(c) It releases messages that are not complete")
print(f"    text that is not a usable value (placeholder, spaces, malformed) released as if complete: {len(garbage)} messages")
print(f"    required field still absent or empty at release: {absent} messages")

opt = sum(1 for mid in wrote for p in wrote[mid] if p not in REQUIRED)
print("(d) It completes optional fields nobody supplied")
print(f"    optional fields written: {opt} (purpose OTHR, remittance NOTPROVIDED)")

behind_person = sum(1 for mid in wrote for p in wrote[mid] if p in REQUIRED and POLICY[p] != AUTO)
changed = sum(1 for mid in wrote for p in wrote[mid] if p in REQUIRED)
print("(e) No second person")
print(f"    changes to fields the policy puts behind a person: {behind_person} of {changed}; the script has no approval step")

print("(f) No record")
print(f"    fields changed: {changed + opt}; the script keeps no record of source or approver")

bad_msgs = sorted({mid for (mid, p), s in status.items() if s != "correct"})
print("(g) Result")
print(f"    messages released with a wrong or unusable required value: {len(bad_msgs)} of {len(messages)}")
known = [mid for mid in defects if routes[mid]["recipe"] == "bic_present_wrong"]
print(f"KNOWN LIMIT: {len(known)} messages carry a well-formed creditor BIC that belongs to a different bank. "
      f"The script leaves all {sum(1 for mid in known if status[(mid, CDTR_BIC)] == 'wrong_untouched')} untouched; step 4 does too.")
print("The basic script does the lookups and mishandles everything around them. The product is the refusal, the gate and the record.")
