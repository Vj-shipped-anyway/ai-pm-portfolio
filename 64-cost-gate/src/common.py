"""Shared loading for the four step scripts of project 64."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from cost_gate import evaluate, parse_budget, parse_rows  # noqa: E402,F401


def load_budget() -> dict:
    with open(os.path.join(DATA, "budget.json"), encoding="utf-8") as fh:
        return parse_budget(json.load(fh))


def load_runs(budget: dict) -> tuple:
    """(baseline items, [change request dicts]). Runs are grouped by the cr_id field; each carries its planted truth."""
    raw = {}
    with open(os.path.join(DATA, "eval_runs.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            raw.setdefault(r["cr_id"], []).append(r)
    baseline = parse_rows(raw["BASE"], budget["prices"])
    crs = []
    with open(os.path.join(DATA, "cr_truth.csv"), newline="", encoding="utf-8") as fh:
        for t in csv.DictReader(fh):
            crs.append({"cr_id": t["cr_id"], "kind": t["change_kind"], "over": t["truth_class"] == "over_budget",
                        "true_worst": float(t["true_worst_ratio"]), "true_scopes": t["true_scopes_over"].split(";"),
                        "items": parse_rows(raw[t["cr_id"]], budget["prices"])})
    return baseline, crs


def mean_cost_per_call(items: list) -> float:
    return sum(it["cost"] for it in items) / len(items)


def scope_of(report: dict, name: str) -> dict:
    return next(s for s in report["scopes"] if s["scope"] == name)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
