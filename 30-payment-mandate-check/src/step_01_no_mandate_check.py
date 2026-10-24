"""Step 1 - Status quo: the agent's credential is the only control.

The agent signs in with a service account that is allowed to submit payments, and the gateway releases
what it submits. Nothing compares an instruction with what the customer actually delegated. This step
replays the 475 synthetic instructions through that gateway and counts what goes out. The data is
synthetic (data/_generate.py); the truth of each instruction is the scenario that produced it.

Run (from src/):  python3 step_01_no_mandate_check.py
"""
from collections import Counter
from decimal import Decimal

from common import load_case, parse_amount

mandates, rows, truth = load_case()
by_truth = Counter(truth[r["submission_id"]]["truth_decision"] for r in rows)
forbidden = [r for r in rows if truth[r["submission_id"]]["truth_decision"] == "REJECT"]
usd = sum((parse_amount(r["amount"]) or Decimal(0) for r in forbidden if r["currency"] == "USD"), Decimal(0))

print("STEP 1 - no mandate check")
print(f"  instructions received: {len(rows)} on {len(mandates)} mandates")
print(f"  planted truth: {by_truth['RELEASE']} inside the mandate, {by_truth['HOLD']} for a person to look at, {by_truth['REJECT']} outside it")
print(f"  instructions released by the gateway: {len(rows)} of {len(rows)}")
print(f"  released although the mandate forbids them: {len(forbidden)} of {len(rows)}")
print(f"  released although a person should have seen them: {by_truth['HOLD']} of {len(rows)}")
print(f"  USD value of the forbidden ones that parse as an amount: {usd:,.2f}")
print("  The customer finds out from a statement, or never.")
