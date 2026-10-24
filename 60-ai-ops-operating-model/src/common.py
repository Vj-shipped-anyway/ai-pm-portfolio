"""Shared loading for the four step scripts of project 60."""
from __future__ import annotations

import csv
import os

from ops_model_review import (RULES, load_checklist, load_evidence, load_programs, parse_date,  # noqa: F401
                              review_program)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")
DEFECTS = ("absent", "lapsed", "blank_ref", "future", "self_signed", "hollow")


def load_all() -> dict:
    """Checklist, programs, evidence register and review date from data/, plus the planted truth."""
    checklist = load_checklist(os.path.join(DATA, "checklist.csv"))
    programs = load_programs(os.path.join(DATA, "programs.csv"), max(i["stage"] for i in checklist))
    register = load_evidence(os.path.join(DATA, "evidence.csv"), programs, checklist)
    with open(os.path.join(DATA, "as_of.txt"), encoding="utf-8") as fh:
        as_of = parse_date(fh.read().strip(), "as_of.txt")
    with open(os.path.join(DATA, "program_truth.csv"), newline="", encoding="utf-8") as fh:
        truth = {r["program_id"]: {"reach": int(r["reach"]), "true_stage": int(r["true_stage"]),
                                   "window90_ok": r["window90_ok"] == "1"} for r in csv.DictReader(fh)}
    with open(os.path.join(DATA, "item_truth.csv"), newline="", encoding="utf-8") as fh:
        items = {(r["program_id"], r["item_id"]): {"owed": r["owed"] == "1", "state": r["planted_state"]}
                 for r in csv.DictReader(fh)}
    return {"checklist": checklist, "programs": programs, "register": register, "as_of": as_of,
            "truth": truth, "item_truth": items}


def review_all(d: dict, rules=RULES, window=None) -> list:
    return [review_program(p, d["checklist"], d["register"], d["as_of"], window, rules) for p in d["programs"]]


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def item_outcomes(d: dict, reviews: list) -> dict:
    """Score the item judgments of a review against the planted states, owed items only.

    caught[state] = [items the review rejected, items planted in that state]; false_alarms are planted-ok
    items the review rejected; passed[state] lists (program, item) the review called OK that were planted
    defective."""
    caught = {s: [0, 0] for s in DEFECTS}
    false_alarms, passed = [], {s: [] for s in DEFECTS}
    for r in reviews:
        for i in r["items"]:
            t = d["item_truth"][(r["program_id"], i["item_id"])]
            if not t["owed"]:
                continue
            if t["state"] == "ok":
                if i["status"] != "OK":
                    false_alarms.append((r["program_id"], i["item_id"], i["status"]))
                continue
            caught[t["state"]][1] += 1
            if i["status"] == "OK":
                passed[t["state"]].append((r["program_id"], i["item_id"]))
            else:
                caught[t["state"]][0] += 1
    return {"caught": caught, "false_alarms": false_alarms, "passed": passed}


def stage_above_truth(d: dict, reviews: list) -> list:
    """Programs where the review reaches a higher stage than the planted truth, with the planted states that let it through."""
    out = []
    for r in reviews:
        true_stage = d["truth"][r["program_id"]]["true_stage"]
        if r["reached"] <= true_stage:
            continue
        causes = sorted((d["item_truth"][(r["program_id"], i["item_id"])]["state"], i["item_id"]) for i in r["items"]
                        if i["stage"] <= r["reached"] and i["status"] == "OK"
                        and d["item_truth"][(r["program_id"], i["item_id"])]["state"] != "ok")
        out.append({"program_id": r["program_id"], "reached": r["reached"], "true_stage": true_stage, "causes": causes})
    return out
