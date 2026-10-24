"""Shared loading and the plain header-and-type check for the four step scripts of project 53."""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from feature_contract import check_batch, decide, parse_value  # noqa: E402,F401

VALUE_KINDS = ("null_rate", "below_min", "above_max", "not_allowed")
STRUCTURE_KINDS = ("missing_field", "type_mismatch", "unexpected_column")


def load_contracts() -> dict:
    """{feed name: contract} from data/contract_*.json."""
    out = {}
    for path in sorted(glob.glob(os.path.join(DATA, "contract_*.json"))):
        with open(path, encoding="utf-8") as fh:
            c = json.load(fh)
        out[c["contract"]] = c
    return out


def load_batches() -> list:
    """The 90 deliveries with their planted truth, in batch order."""
    truth = {}
    with open(os.path.join(DATA, "batch_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["batch_id"]] = r
    batches = []
    with open(os.path.join(DATA, "batches.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            b = json.loads(line)
            t = truth[b["batch_id"]]
            b.update(kind=t["change_kind"], truth=t["truth_class"], field=t["changed_field"], changed=int(t["rows_changed"]))
            batches.append(b)
    return batches


def decision_from(findings: list, kinds: tuple) -> str:
    """The decision when only findings of the given kinds are looked at."""
    return decide([f for f in findings if f["kind"] in kinds])


def inferred_dtype(values: list):
    """What a dataframe reader would call the column: integer, number, boolean, string, or None when every cell is empty."""
    cells = [v for v in values if v != ""]
    if not cells:
        return None
    if all(re.fullmatch(r"-?[0-9]+", v) for v in cells):
        return "integer"
    if all(parse_value(v, "number")[0] for v in cells):
        return "number"
    if all(v.lower() in ("true", "false") for v in cells):
        return "boolean"
    return "string"


def basic_check(contract: dict, columns: list, rows: list) -> str:
    """The header-and-type check most teams start with: the header equals the expected column list, and each
    column's inferred type matches the declared one. FAIL or PASS, nothing in between."""
    if list(columns) != [f["name"] for f in contract["fields"]]:
        return "FAIL"
    for i, spec in enumerate(contract["fields"]):
        seen = inferred_dtype([r[i] for r in rows])
        accepted = {"integer": ("integer",), "number": ("integer", "number"), "boolean": ("boolean",), "string": ("string",)}[spec["type"]]
        if seen is not None and seen not in accepted:
            return "FAIL"
    return "PASS"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
