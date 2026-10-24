"""Step 2 - The common approach: a cell mapping sheet, re-run against the loan table.

The team documents each leaf cell as a filter on the loan table (data/mapping_sheet.csv: product, days
past due range, status) and writes each total and ratio as a formula. To check a number, a reviewer
re-runs the filter on today's table and compares with the filed value. The sheet says nothing about the
as-of date and nothing about adjustments, which is how these sheets usually read. Planted classes come
from data/truth_cells.csv; the sheet and the re-run never look at them.

Run (from src/):  python3 step_02_mapping_sheet.py
"""
from __future__ import annotations

from collections import Counter

from common import PROBLEM, load_world, mapped_rows, median
from report_trace import apply_formula, cell_order

w = load_world()
leaf = [c["id"] for c in w["spec"]["cells"] if c["kind"] == "leaf"]
values, rows_read, flagged = {}, {}, {}
for cid in leaf:
    rows = mapped_rows(w["loans1"], w["mapping"][cid])
    values[cid], rows_read[cid] = sum(l["balance"] for l in rows), len(rows)
    flagged[cid] = values[cid] != w["filed"][cid]
for cid in cell_order(w["defs"]):
    if w["defs"][cid]["kind"] == "derived":
        values[cid] = apply_formula(w["defs"][cid], values)
        flagged[cid] = values[cid] != w["filed"][cid]

truth = w["truth"]
cls_n = Counter(truth[c] for c in leaf)
cls_flag = Counter(truth[c] for c in leaf if flagged[c])
problems = [c for c in leaf if truth[c] in PROBLEM]
found = sum(1 for c in problems if flagged[c])
benign = [c for c in leaf if flagged[c] and truth[c] not in PROBLEM]
derived = [c for c in w["defs"] if w["defs"][c]["kind"] == "derived"]

print("STEP 2 - cell mapping sheet, re-run against the loan table as it stands now")
print(f"  leaf cells whose re-run equals the filed value: {sum(1 for c in leaf if not flagged[c])} of {len(leaf)}")
print(f"  leaf cells flagged: {sum(flagged[c] for c in leaf)} of {len(leaf)}")
print(f"  planted problems among the leaf cells that the re-run flags: {found} of {len(problems)}")
print(f"  flagged but not a problem: {len(benign)}  ({', '.join(f'{k} {cls_flag[k]}' for k in sorted(cls_flag) if k not in PROBLEM)})")
print(f"  planted problems that pass: {len(problems) - found}  ({', '.join(f'{k} {cls_n[k] - cls_flag[k]}' for k in sorted(cls_n) if k in PROBLEM and cls_n[k] - cls_flag[k])})")
print(f"  rows a reviewer reads to explain one flagged cell: median {median([rows_read[c] for c in leaf if flagged[c]]):g}")
print(f"  columns in the sheet: {', '.join(next(iter(w['mapping'].values())))}; none names a row, an as-of date or an adjustment")
print(f"  derived cells flagged: {sum(flagged[c] for c in derived)} of {len(derived)}  (planted footing errors: {sum(1 for c in derived if truth[c] == 'footing_error')})")
