"""Step 3 - Deficiencies exposed: where the mapping sheet fails, and what the next obvious fix gets wrong.

Seven checks on the same data as step 2. Each prints a count. The last one tries the fix people reach
for next, a comparison of every column of every row against the filing snapshot, and shows what it costs.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from collections import Counter

from common import SOURCE_CHANGE, load_world, mapped_rows, median, read_rows
from report_trace import apply_formula, cell_order

w = load_world()
as_of = w["spec"]["as_of"]
leaf = [c["id"] for c in w["spec"]["cells"] if c["kind"] == "leaf"]
truth, filed = w["truth"], w["filed"]
adj_sum = Counter()
for a in w["adjustments"]:
    adj_sum[a["cell_id"]] += a["amount_cents"]
cause_rows = Counter(r["cell_id"] for r in w["truth_rows"]
                     if r["change_kind"] in ("balance_restated", "row_removed", "late_arrival", "offset_up", "offset_down"))


def rerun(cid, dated):
    return sum(l["balance"] for l in mapped_rows(w["loans1"], w["mapping"][cid], as_of if dated else None))


live = {c: rerun(c, False) != filed[c] for c in leaf}
dated = {c: rerun(c, True) != filed[c] for c in leaf}

print("STEP 3 - where the mapping sheet fails")
only_date = [c for c in leaf if live[c] and not dated[c]]
print(f"  1. no as-of date: {len(only_date)} cells are flagged only because rows booked after {as_of} are in the table")
off = [c for c in leaf if truth[c] == "offsetting"]
print(f"  2. value-only comparison: {sum(1 for c in off if not live[c])} of {len(off)} cells with offsetting changes pass")
chg = [c for c in leaf if truth[c] in SOURCE_CHANGE]
print(f"  3. no row named: {len(chg)} cells have a source change; a reviewer reads a median of "
      f"{median([len(mapped_rows(w['loans1'], w['mapping'][c])) for c in chg]):g} rows per cell to find a cause in a median of {median([cause_rows[c] for c in chg]):g} row(s)")
by_log = [c for c in leaf if live[c] and adj_sum[c] and filed[c] - rerun(c, False) == adj_sum[c]]
by_plug = [c for c in leaf if truth[c] == "silent_plug"]
print(f"  4. adjustments not linked: {len(by_log)} flagged cells differ by exactly a logged adjustment and {len(by_plug)} by an unlogged amount; "
      f"the sheet shows both as a plain mismatch")
values = {c: rerun(c, False) for c in leaf}
derived = [c for c in cell_order(w["defs"]) if w["defs"][c]["kind"] == "derived"]
for c in derived:
    values[c] = apply_formula(w["defs"][c], values)
foot = [c for c in derived if apply_formula(w["defs"][c], filed) != filed[c]]
print(f"  5. totals and ratios: a live re-run flags {sum(1 for c in derived if values[c] != filed[c])} of {len(derived)} derived cells; "
      f"a cross-foot of the filed numbers alone finds {len(foot)} ({', '.join(foot)})")
covered = {l["loan_id"] for c in leaf for l in mapped_rows(w["loans0"], w["mapping"][c], as_of)}
orphans = [l for l in w["loans0"].values() if l["status"] == "open" and l["booked"] <= as_of and l["loan_id"] not in covered]
print(f"  6. blank days past due: {len(orphans)} open loans sit in no cell and no check flags them; the sheet's filters skip them without saying so")

snap0 = {r["loan_id"]: r for r in read_rows("loans_filed.csv")}
snap1 = {r["loan_id"]: r for r in read_rows("loans_now.csv")}
hash_flag = {c: any(snap1.get(l["loan_id"]) != snap0[l["loan_id"]] for l in mapped_rows(w["loans0"], w["mapping"][c], as_of)) for c in leaf}
cnt = Counter(truth[c] for c in leaf)
hit = Counter(truth[c] for c in leaf if hash_flag[c])
print(f"  7. whole-row comparison against the filing snapshot: offsetting found {hit['offsetting']} of {cnt['offsetting']}, "
      f"restated {hit['restated']} of {cnt['restated']}, removed {hit['row_removed']} of {cnt['row_removed']}; "
      f"late arrivals found {hit['late_arrival']} of {cnt['late_arrival']} (rows it never knew), "
      f"and {hit['unreported_field']} of {cnt['unreported_field']} cells flagged for a note nobody reports")
