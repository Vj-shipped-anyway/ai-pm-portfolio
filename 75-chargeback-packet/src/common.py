"""Shared loading for the four step scripts of project 75."""
from __future__ import annotations

import csv
import json
import os
from datetime import date

from chargeback_packet import CHECKS, check_case, load_rules

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

EXPECTED = {"ready": "READY", "defective": "FIX", "late": "LATE"}


def load_as_of() -> date:
    with open(os.path.join(DATA, "as_of.txt"), encoding="utf-8") as fh:
        return date.fromisoformat(fh.read().strip())


def load_cases() -> list:
    """The 100 dispute cases, each with its planted truth: {"case", "kind", "truth", "visible"}."""
    truth = {}
    with open(os.path.join(DATA, "case_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["case_id"]] = r
    with open(os.path.join(DATA, "cases.json"), encoding="utf-8") as fh:
        cases = json.load(fh)
    return [{"case": c, "kind": truth[c["case_id"]]["planted_kind"], "truth": truth[c["case_id"]]["truth_class"],
             "visible": truth[c["case_id"]]["visible_in_metadata"] == "yes"} for c in cases]


def evaluate(items: list, checks=CHECKS) -> list:
    """Run the checker on every item and attach the result as item["result"]."""
    rules, as_of = load_rules(), load_as_of()
    return [dict(it, result=check_case(it["case"], rules, as_of, checks)) for it in items]


def total_cents(items: list) -> int:
    return sum(it["case"]["amount_cents"] for it in items)


def dollars(cents: int) -> str:
    return f"{cents // 100:,}.{cents % 100:02d}"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
