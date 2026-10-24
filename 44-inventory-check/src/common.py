"""Shared loading for the four step scripts of project 44."""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from inventory_check import check, decide, is_blank, load_inventory, load_usage, parse_date, parse_tier, REQUIRED  # noqa: E402,F401


def load_world() -> tuple:
    """(as_of, records, usage) from the committed data files."""
    with open(os.path.join(DATA, "as_of.txt"), encoding="utf-8") as fh:
        as_of = parse_date(fh.read().strip())
    return as_of, load_inventory(os.path.join(DATA, "inventory.json")), load_usage(os.path.join(DATA, "usage.csv"), as_of)


def load_truth() -> dict:
    """{system_id: {case_kind, truth_class, detail}} - the case each record was built as."""
    with open(os.path.join(DATA, "inventory_truth.csv"), newline="", encoding="utf-8") as fh:
        return {r["system_id"]: r for r in csv.DictReader(fh)}


def load_shadows() -> list:
    """The systems that call a model without a usable inventory record, with how they hide."""
    with open(os.path.join(DATA, "shadow_truth.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["calls"] = int(r["calls"])
    return rows


def flagged_ids(findings: list) -> set:
    return {f["system_id"] for f in findings}


def split_truth(truth: dict) -> tuple:
    """(defective ids, clean ids), each sorted."""
    return (sorted(k for k, v in truth.items() if v["truth_class"] == "defective"),
            sorted(k for k, v in truth.items() if v["truth_class"] == "clean"))


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def case_counts(truth: dict, flagged: set, truth_class: str) -> list:
    """[(case kind, flagged, total)] for the records of one truth class, sorted by case kind."""
    totals, hit = {}, {}
    for sid, t in truth.items():
        if t["truth_class"] == truth_class:
            totals[t["case_kind"]] = totals.get(t["case_kind"], 0) + 1
            hit[t["case_kind"]] = hit.get(t["case_kind"], 0) + (1 if sid in flagged else 0)
    return [(k, hit[k], totals[k]) for k in sorted(totals)]


def blank_cell_flags(rec: dict, as_of, review_days: int = 365) -> list:
    """Why the common spreadsheet check (step 2) would flag this row; an empty list means it passes."""
    why = [f for f in REQUIRED if rec.get(f) is None or str(rec.get(f)).strip() == ""]
    d = parse_date(rec.get("last_reviewed"))
    if d is not None and (as_of - d).days > review_days:
        why.append("last_reviewed")
    return why
