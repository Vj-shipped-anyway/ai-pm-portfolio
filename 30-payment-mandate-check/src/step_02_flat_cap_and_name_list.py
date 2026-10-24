"""Step 2 - The common basic approach: one flat cap and a list of approved payee names.

A platform team's first control is a single per-payment cap for every agent and an approved-vendor list
matched on the payee's name. It does not know which customer delegated what, when the delegation ends,
what a customer already spent today, or whether this is the same instruction again.
Assumption (yellow in the README): the cap is 1,000.00, read as the same number in any currency.

Run (from src/):  python3 step_02_flat_cap_and_name_list.py
"""
from collections import Counter
from decimal import Decimal

from common import load_case, approved_payee_names, parse_amount, score, RELEASE, REJECT

FLAT_CAP = Decimal("1000.00")

mandates, rows, truth = load_case()
names = approved_payee_names()


def gate(row) -> str:
    amt = parse_amount(row["amount"])
    return RELEASE if amt is not None and 0 < amt <= FLAT_CAP and row["payee_name"] in names else REJECT


decisions = {r["submission_id"]: gate(r) for r in rows}
s = score(decisions, truth)
n = Counter(t["truth_decision"] for t in truth.values())
leaked = Counter(truth[sid]["kind"] for sid, d in decisions.items() if d == RELEASE and truth[sid]["truth_decision"] != "RELEASE")

print("STEP 2 - flat cap and approved payee names")
print(f"  rule: release when the amount is at most {FLAT_CAP} and the payee name is on a list of {len(names)} approved names")
print(f"  forbidden instructions released: {s['bad_released']} of {n['REJECT']}")
print(f"  instructions that needed a person, released: {s['person_released']} of {n['HOLD']} (this gateway has no hold path)")
print(f"  legitimate instructions stopped: {s['legit_stopped']} of {n['RELEASE']}")
print(f"  decisions that match the planted truth: {s['exact']} of {len(rows)}")
print("  what got through, by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(leaked.items())))
look = [sid for sid, t in truth.items() if t["kind"] == "payee_lookalike"]
other = [sid for sid, t in truth.items() if t["kind"] == "payee_other_mandate"]
print(f"  look-alike payees (same name, other payee_id) released: {sum(decisions[x] == RELEASE for x in look)} of {len(look)}")
print(f"  payees from another customer's mandate released: {sum(decisions[x] == RELEASE for x in other)} of {len(other)}")
print("  A name is not an identity, and a flat cap is not anyone's mandate.")
