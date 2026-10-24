"""Step 1 - Status quo: the invoice arrives by account, and the account's owner pays.

One month of a cloud bill for a fictional bank (data/_generate.py). Finance has no tag policy that
anyone enforces, so chargeback is the account view: each dedicated account's bill goes to the
cost center that account belongs to, and the shared accounts go to a central pool nobody owns.
This step scores that against the planted owner of every line and prints how tagged the bill is.

Run (from src/):  python3 step_01_no_allocation.py
"""
from common import load_world, compliance_summary, fmt_usd, pct

w = load_world()
bill, accounts, truth = w["bill"], w["accounts"], w["truth"]
total = sum(b["usd"] for b in bill)
dedicated = [b for b in bill if not accounts[b["account_id"]]["shared"]]
shared = [b for b in bill if accounts[b["account_id"]]["shared"]]
right = sum(b["usd"] for b in dedicated if accounts[b["account_id"]]["default"] == truth[b["line_id"]]["cc"])
wrong = sum(b["usd"] for b in dedicated) - right
pool = sum(b["usd"] for b in shared)
comp = compliance_summary(bill, w["policy"], w["registry"])

print("STEP 1 - chargeback by account, no tag policy enforced")
print(f"  billing lines: {len(bill)}   accounts: {len(accounts)}   net spend: {fmt_usd(total)}")
print(f"  dedicated accounts: {fmt_usd(sum(b['usd'] for b in dedicated))}   shared accounts: {fmt_usd(pool)} ({pct(pool, total)} of spend, no owner)")
print(f"  charged to the planted owner: {fmt_usd(right)} ({pct(right, total)} of net spend)")
print(f"  charged to another team's cost center: {fmt_usd(wrong)} ({pct(wrong, total)})")
print(f"  parked in the central pool: {fmt_usd(pool)} ({pct(pool, total)})")
print(f"  lines that carry every required tag, written exactly: {comp['strict']} of {comp['lines']} ({pct(comp['strict_usd'], comp['usd'])} of their dollars)")
print("  A team that asks what its application costs gets a number for the whole account, or none.")
