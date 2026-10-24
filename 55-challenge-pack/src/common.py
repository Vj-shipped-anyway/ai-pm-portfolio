"""Shared loading and scoring for the four step scripts of project 55."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from challenge_pack import (CLASS_ORDER, ITEMS, ITEM_BY_ID, TIERS, add_months, assess, effective_tier,  # noqa: E402,F401
                            group_evidence, plan_items, read_evidence, read_use_cases, same_unit)

AS_OF = dt.date(2026, 10, 1)
DEFECTS = ("missing", "stale", "wrong_version", "not_independent")


def load_world() -> dict:
    """The use cases, the evidence on file and the planted truth. Truth is read here and used only to score."""
    forms = read_use_cases(os.path.join(DATA, "use_cases.csv"))
    by_uc = group_evidence(read_evidence(os.path.join(DATA, "evidence.csv"), AS_OF))
    true_tier, true_vendor, true_class = {}, {}, {}
    with open(os.path.join(DATA, "truth_tier.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            true_tier[r["use_case_id"]] = int(r["true_tier"])
            true_vendor[r["use_case_id"]] = r["true_vendor_model"]
            true_class[r["use_case_id"]] = r["true_data_class"]
    truth = {}
    with open(os.path.join(DATA, "truth_evidence.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth.setdefault(r["use_case_id"], {})[r["item_id"]] = (int(r["owed"]), r["planted_status"])
    return {"forms": forms, "by_uc": by_uc, "true_tier": true_tier, "true_vendor": true_vendor,
            "true_class": true_class, "truth": truth}


def required(world: dict, uid: str) -> set:
    return {i for i, (owed, _s) in world["truth"][uid].items() if owed}


def defects(world: dict, uid: str) -> dict:
    """{item id: planted status} for the required items that carry a visible defect."""
    return {i: s for i, (owed, s) in world["truth"][uid].items() if owed and s in DEFECTS}


def score_requests(world: dict, requested: dict) -> dict:
    """How well a set of requested items per use case matches the items the use case truly owes."""
    need = covered = over = 0
    for f in world["forms"]:
        uid = f["use_case_id"]
        req = required(world, uid)
        need += len(req)
        covered += len(req & requested[uid])
        over += len(requested[uid] - req)
    return {"required": need, "covered": covered, "missed": need - covered, "over": over}


def pct(a: int, b: int) -> str:
    return "%.1f%%" % (100.0 * a / b) if b else "n/a"


def write_json(name: str, obj: dict) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)


def write_csv(name: str, header: list, rows: list) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
