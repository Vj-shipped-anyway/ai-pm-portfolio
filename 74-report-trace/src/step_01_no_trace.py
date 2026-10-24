"""Step 1 - Status quo: a filed number with no recorded path back to its source rows.

A reporting job reads a loan table, writes one value per cell, and files the report. The report carries
cell_id and value, nothing else. A reviewer who asks "which loans make up this cell?" has the filed
number and the loan table as it stands today. This step counts what that costs and how often the
reviewer's first guess at the rule reproduces the filed value. The data is synthetic (data/_generate.py).

Run (from src/):  python3 step_01_no_trace.py
"""
from __future__ import annotations

from common import load_world, read_rows, median
from report_trace import build_lineage

w = load_world()
spec, filed_rows = w["spec"], read_rows("report_filed.csv")
leaf = [c for c in spec["cells"] if c["kind"] == "leaf"]
bounds = {b["name"]: b for b in spec["buckets"]}
with_path = sum(1 for r in filed_rows if any(v for k, v in r.items() if k not in ("cell_id", "value")))
lineage = build_lineage(spec, w["loans0"], w["adjustments"], w["filed"])
behind = [len(lineage["cells"][c["id"]]["rows"]) for c in leaf]

hits = 0
for c in leaf:
    b = bounds[c["bucket"]]
    total = sum(l["balance"] for l in w["loans1"].values()
                if l["product"] == c["product"] and l["dpd"] is not None and l["dpd"] >= b["min"] and (b["max"] is None or l["dpd"] <= b["max"]))
    hits += total == w["filed"][c["id"]]

print("STEP 1 - a filed report with no recorded path back")
print(f"  cells in the filed report: {len(filed_rows)} ({len(leaf)} leaf, {len(filed_rows) - len(leaf)} derived)")
print(f"  cells with a recorded path to source rows: {with_path} of {len(filed_rows)}")
print(f"  rows in the loan table a reviewer reads to find the loans behind one cell: {len(w['loans1'])}")
print(f"  rows that actually sit behind a leaf cell: median {median(behind):g}, largest {max(behind)}")
print(f"  first try (product and days past due from the column label, any status): reproduces the filed value on {hits} of {len(leaf)} leaf cells")
print("  The reviewer has to guess the rule, and the table has moved since filing.")
