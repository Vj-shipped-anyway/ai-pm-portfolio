"""Step 3 - Where each version fails.

  A. the lookup on amount and date (step 2)
  B. the rule ladder with every proposal posted at once, no approval gate (the proposer of step 4 alone)

Both are scored on the same ledgers against the answer key. KNOWN LIMIT, left in on purpose: true matches
the five rules cannot make (a split deposit with no batch id, a date gap beyond the window, a reference with
two wrong characters, a name abbreviation the table does not know) stay open in step 4 as well. The script
prints them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_data, load_truth, amount_date_lookup, score, pair_of, reconcile, DEFAULT_PARAMS


def kinds(counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "none"


a_rows, b_rows = load_data()
truth = load_truth()
print("STEP 3 - where each version fails")

lookup = score(amount_date_lookup(a_rows, b_rows, DEFAULT_PARAMS.window), truth)
print("  A. lookup on amount and date")
print(f"    wrong matches posted: {lookup['wrong']} ({kinds(lookup['wrong_by_kind'])})")
print(f"    true matches it cannot make, by planted kind: {kinds(Counter(k['kind'] for _, k in lookup['missed']))}")

res = reconcile(a_rows, b_rows, [])
props = res["proposals"]
ladder = score([pair_of(q) for q in props], truth)
needs_person = [q for q in props if q["gate"] == "approval"]
needs_person_wrong = sum(1 for q in needs_person if pair_of(q) not in truth["match"])
parked_a = sum(1 for (side, _) in res["parked"] if side == "A")
print("  B. rule ladder, every proposal posted at once")
print(f"    matches posted: {ladder['posted']}; wrong: {ladder['wrong']} ({kinds(ladder['wrong_by_kind'])})")
print(f"    matches the policy says a person must see: {len(needs_person)}, posted with nobody looking; {needs_person_wrong} of them wrong")
print(f"    bank lines parked because two book lines fit equally well: {parked_a}")
print(f"    true matches found: {ladder['found']} of {ladder['true_pairs']}")

left = [(p, k) for p, k in ladder["missed"] if k["kind"] != "twin_payments"]
print(f"  KNOWN LIMIT: {len(left)} true matches have no proposal and are not parked ({kinds(Counter(k['kind'] for _, k in left))})")
for (a_ids, b_ids), k in left:
    if k["kind"] == "split_no_batch":
        print(f"    split deposit, no batch id on the book lines: {a_ids[0]} = {' + '.join(b_ids)}")
