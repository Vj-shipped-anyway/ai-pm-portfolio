"""Step 1 - Status quo: two ledgers, nothing matched.

The bank statement (A) and the cash book (B) for one month are side by side and the totals do not agree.
A person reconciles them by reading both. This step counts what is there and breaks the gap between the
two totals into the pieces the answer key says it is made of. The data is synthetic (data/_generate.py);
the answer key comes from the generator, not from any matching rule.

Run (from src/):  python3 step_01_two_ledgers_unmatched.py
"""
from collections import Counter

from common import load_data, load_truth
from recon_agent import money

a_rows, b_rows = load_data()
truth = load_truth()
links = truth["links"]
status = Counter(k["status"] for k in links)
groups = sum(1 for k in links if k["status"] == "match" and len(k["b"]) > 1)
usd_a = sum(r["cents"] for r in a_rows if r["currency"] == "USD")
usd_b = sum(r["cents"] for r in b_rows if r["currency"] == "USD")
gap = usd_a - usd_b
a_only = sum(r["cents"] for r in a_rows if truth["kind_of"][("A", r["id"])]["status"] == "a_only")
b_only = sum(r["cents"] for r in b_rows if truth["kind_of"][("B", r["id"])]["status"] == "b_only" and r["currency"] == "USD")
fees = sum(r["cents"] - sum(b["cents"] for b in b_rows if b["id"] in truth["kind_of"][("A", r["id"])]["b"])
           for r in a_rows if truth["kind_of"][("A", r["id"])]["kind"] == "fee_netted")
lines = len(a_rows) + len(b_rows)

print("STEP 1 - two ledgers, nothing matched")
print(f"  bank lines: {len(a_rows)}   book lines: {len(b_rows)}   lines to read side by side: {lines}")
print(f"  answer key: {status['match']} true matches ({groups} of them one bank line against several book lines), "
      f"{status['a_only']} bank-only lines, {status['b_only']} book-only lines")
print(f"  USD totals differ by {money(gap)}")
print(f"  the gap is made of: bank-only lines {money(a_only)}, less book-only lines ({money(b_only)}), plus netted fees ({money(fees)}) = {money(a_only - b_only + fees)}")
print("  The total says the books are out. It does not say which of the " + str(lines) + " lines to look at.")
print(f"  modeled: at 1 minute per line, reading every line takes {lines / 60:.1f} hours (the 1 minute is an assumption, not a measurement)")
