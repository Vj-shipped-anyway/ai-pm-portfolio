"""Step 4 - The fix: row-level lineage captured at filing, checked against the source today.

For every leaf cell the lineage stores the rule, the source rows behind it (with the fields the rule reads)
and the logged adjustments. The check then asks, per cell: is the filed value explained by those rows plus
the log; did a row change, vanish or turn up that fits the rule and was never in the cell; do the totals and
ratios foot the filed numbers; which open loans are in no cell. A note edited on a loan is not in the rule's
read set and does not count. The command-line tool report_trace.py runs exactly this code.

KNOWN LIMIT, left in on purpose: a source row that is wrong but plausible (a days-past-due value that the
servicing system recorded badly) traces cleanly. Lineage shows where a number came from, not whether the
row was right. The script prints those cells.

Run (from src/):  python3 step_04_with_lineage.py
Output: a report, plus out/step_04_cells.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os

from common import EXPECTED, OUT_DIR, PROBLEM, SOURCE_CHANGE, ensure_out, load_world, mapped_rows
from report_trace import build_lineage, change_lines, evaluate

w = load_world()
lineage = build_lineage(w["spec"], w["loans0"], w["adjustments"], w["filed"])
ev = evaluate(lineage, w["loans1"])
cells, truth, order = ev["cells"], w["truth"], lineage["order"]
s = ev["summary"]

problems = [c for c in order if truth[c] in PROBLEM]
found = [c for c in problems if cells[c]["flags"]]
benign = [c for c in order if truth[c] not in PROBLEM and truth[c] != "source_error"]
false_alarms = [c for c in benign if cells[c]["flags"]]
exact = [c for c in benign + problems if cells[c]["verdict"] == EXPECTED[truth[c]]]
truth_ids = {}
for r in w["truth_rows"]:
    truth_ids.setdefault(r["cell_id"], set()).add(r["loan_id"])
chg = [c for c in order if truth[c] in SOURCE_CHANGE]
named = {c: {x for x, _ in cells[c]["changed"]} | set(cells[c]["missing"]) | set(cells[c]["added"]) for c in chg}
named_ok = [c for c in chg if named[c] == truth_ids[c]]
step2_rows = sum(len(mapped_rows(w["loans1"], w["mapping"][c])) for c in chg)
orphan_ids = {r[0] for r in lineage["orphans"]}
planted_orphans = truth_ids.get("", set())
known = [c for c in order if truth[c] == "source_error"]
detail = {r["loan_id"]: r["detail"] for r in w["truth_rows"] if r["change_kind"] == "source_error"}

print("STEP 4 - row-level lineage captured at filing, checked against the source today")
print(f"  leaf cells: {s['traced']} traced, {s['adjusted']} adjusted (explained by the log), {s['unexplained']} unexplained, {s['source_changed']} with source changes")
print(f"  derived cells: {s['foot']} foot, {s['do_not_foot']} do not")
print(f"  planted problems found: {len(found)} of {len(problems)}")
print(f"  false alarms among the {len(benign)} cells with nothing wrong or only explained: {len(false_alarms)}")
print(f"  verdict matches the planted class: {len(exact)} of {len(benign) + len(problems)}")
print(f"  cells with a source change where the rows named are exactly the rows planted: {len(named_ok)} of {len(chg)}")
print(f"  rows a reviewer reads for those {len(chg)} cells: {sum(len(v) for v in named.values())} named, against {step2_rows} with the mapping sheet")
print(f"  hard negatives that stay quiet: {sum(1 for c in order if truth[c] == 'new_after_asof' and not cells[c]['flags'])} of "
      f"{sum(1 for c in order if truth[c] == 'new_after_asof')} cells with rows booked after the as-of date, "
      f"{sum(1 for c in order if truth[c] == 'unreported_field' and not cells[c]['flags'])} of "
      f"{sum(1 for c in order if truth[c] == 'unreported_field')} cells where only a note changed")
print(f"  open loans in no cell: {len(orphan_ids)} found, {len(planted_orphans)} planted, {len(orphan_ids & planted_orphans)} match")
print(f"  KNOWN LIMIT: {sum(1 for c in known if cells[c]['verdict'] == 'TRACED')} of {len(known)} cells holding a wrong source row verify as TRACED")
for c in known:
    ids = sorted(truth_ids[c])
    print(f"    {c}: {ids[0]} {detail[ids[0]]}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_cells.csv"), "w", newline="", encoding="utf-8") as fh:
    out = csv.writer(fh, lineterminator="\n")
    out.writerow(["cell_id", "kind", "label", "unit", "truth", "verdict", "filed", "rows", "rows_sum", "adjusted", "residual", "named"])
    for c in order:
        r, cell = cells[c], lineage["cells"][c]
        out.writerow([c, r["kind"], cell["label"], "bps" if cell.get("op") == "ratio_bps" else "usd", truth[c], r["verdict"], r["filed"], r["rows"],
                      r.get("rows_sum", ""), r.get("adjusted", ""), r.get("residual", ""),
                      " | ".join(change_lines(r)) if r["kind"] == "leaf" else f"expected {r['expected']}" if r["flags"] else ""])
summary = {"cells": s["cells"], "leaf": s["leaf"], "derived": s["derived"], "problems": len(problems), "found": len(found),
           "benign": len(benign), "false_alarms": len(false_alarms), "exact": len(exact), "exact_of": len(benign) + len(problems),
           "named_ok": len(named_ok), "source_change_cells": len(chg), "orphans": len(orphan_ids), "known_limit_cells": len(known),
           "traced": s["traced"], "adjusted": s["adjusted"], "unexplained": s["unexplained"], "source_changed": s["source_changed"],
           "foot": s["foot"], "do_not_foot": s["do_not_foot"]}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_cells.csv and step_04_summary.json in src/out/")
