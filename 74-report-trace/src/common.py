"""Shared loading for the four step scripts of project 74."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from report_trace import load_adjustments, load_filed, load_loans, load_spec  # noqa: E402

# Planted classes (data/truth_cells.csv). A problem is a cell a reviewer should be told about.
PROBLEM = ("silent_plug", "restated", "row_removed", "late_arrival", "offsetting", "footing_error")
SOURCE_CHANGE = ("restated", "row_removed", "late_arrival", "offsetting")
# The verdict step 4 should print for each class. source_error is wrong in the source, so the best a trace can say is TRACED.
EXPECTED = {"clean": "TRACED", "unreported_field": "TRACED", "new_after_asof": "TRACED", "logged_adjustment": "ADJUSTED",
            "silent_plug": "UNEXPLAINED", "restated": "SOURCE_CHANGED", "row_removed": "SOURCE_CHANGED",
            "late_arrival": "SOURCE_CHANGED", "offsetting": "SOURCE_CHANGED", "source_error": "TRACED",
            "foots": "FOOTS", "footing_error": "DOES_NOT_FOOT"}


def read_rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world() -> dict:
    spec = load_spec(os.path.join(DATA, "report_spec.json"))
    defs = {c["id"]: c for c in spec["cells"]}
    return {"spec": spec, "defs": defs,
            "filed": load_filed(os.path.join(DATA, "report_filed.csv"), defs),
            "loans0": load_loans(os.path.join(DATA, "loans_filed.csv")),
            "loans1": load_loans(os.path.join(DATA, "loans_now.csv")),
            "adjustments": load_adjustments(os.path.join(DATA, "adjustments.csv")),
            "mapping": {r["cell_id"]: r for r in read_rows("mapping_sheet.csv")},
            "truth": {r["cell_id"]: r["truth_class"] for r in read_rows("truth_cells.csv")},
            "truth_rows": read_rows("truth_rows.csv")}


def mapped_rows(loans: dict, m: dict, as_of: str = None) -> list:
    """Rows of a loans table that a mapping-sheet line selects: product, status and a days-past-due range."""
    lo = int(m["dpd_min"])
    hi = int(m["dpd_max"]) if m["dpd_max"] != "" else None
    return [l for _, l in sorted(loans.items())
            if l["product"] == m["product"] and l["status"] == m["status"] and l["dpd"] is not None and l["dpd"] >= lo
            and (hi is None or l["dpd"] <= hi) and (as_of is None or l["booked"] <= as_of)]


def median(xs: list) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
