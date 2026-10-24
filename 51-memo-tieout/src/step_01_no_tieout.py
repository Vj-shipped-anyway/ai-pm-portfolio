"""Step 1 - Status quo: nothing ties the figures in a credit memo to the spread.

Twenty-eight memos each quote 11 figures from a spread. The memo is a markdown file, the spread is a
spreadsheet export, and the only check is a reviewer with the two open side by side. This step counts
what that leaves to a person and what ships when the person misses one. The data is synthetic
(data/_generate.py); the label on each figure comes from how the figure was built (the true value at the
precision shown, or altered on purpose).

Run (from src/):  python3 step_01_no_tieout.py
"""
from collections import Counter

from common import load_memos, load_truth

memos, truth = load_memos(), load_truth()
wrong = [r for r in truth if r["expected"] == "flag"]
with_wrong = {r["memo_id"] for r in wrong}
values = sum(len(m["spread"]["values"]) for m in memos)
kinds = Counter(r["kind"] for r in wrong)

print("step_01_no_tieout.py - no check between a memo and its spread")
print(f"  memos: {len(memos)}   spread values: {values}   figures in the memos: {len(truth)} ({len(wrong)} wrong, {len(truth) - len(wrong)} fine)")
print(f"  figures a reviewer looks up by hand: {len(truth)}")
print(f"  wrong figures the current process stops before sign-off: 0 of {len(wrong)}")
print(f"  memos that carry at least one wrong figure: {len(with_wrong)} of {len(memos)}")
print("  planted wrong figures by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
print("  A wrong figure is found by a reader who happens to look it up, or it is not found.")
