"""Step 2 - The common basic approach: look up each bank line by amount and date.

For every bank line, take the nearest unused book line with the same amount inside the date window and
post it as matched. It is what a spreadsheet lookup does, and what many first scripts do. No currency,
reference or name is read, and the only record kept of why two lines were paired is that the amount and
the date fit.

Run (from src/):  python3 step_02_amount_and_date_lookup.py
"""
from common import load_data, load_truth, amount_date_lookup, score, DEFAULT_PARAMS

a_rows, b_rows = load_data()
truth = load_truth()
pairs = amount_date_lookup(a_rows, b_rows, DEFAULT_PARAMS.window)
s = score(pairs, truth)
a_by, b_by = {r["id"]: r for r in a_rows}, {r["id"]: r for r in b_rows}
ref_differ = [p for p in pairs if a_by[p[0][0]]["ref_key"] and b_by[p[1][0]]["ref_key"] and a_by[p[0][0]]["ref_key"] != b_by[p[1][0]]["ref_key"]]
ref_differ_wrong = sum(1 for p in ref_differ if p not in truth["match"])
other_currency = sum(1 for (a,), (b,) in pairs if a_by[a]["currency"] != b_by[b]["currency"])

print("STEP 2 - lookup on amount and date (window 3 days)")
print(f"  matches posted: {s['posted']} of {len(a_rows)} bank lines")
print(f"  correct against the answer key: {s['correct']}; wrong: {s['wrong']}")
print(f"  true matches found: {s['found']} of {s['true_pairs']}")
print(f"  matches that record a reason a reviewer can check beyond amount and date: 0 of {s['posted']}")
print(f"  posted although both lines carry a reference and the references differ: {len(ref_differ)} ({ref_differ_wrong} wrong, {len(ref_differ) - ref_differ_wrong} right: a typo in a reference is not proof of a different invoice)")
print(f"  posted across two currencies: {other_currency}")
print(f"  bank lines left unmatched: {len(a_rows) - s['posted']}; book lines left unmatched: {len(b_rows) - s['posted']}")
print("  The ledgers look closer to agreeing. Nobody can tell which of the " + str(s["posted"]) + " matches are the " + str(s["wrong"]) + " wrong ones.")
