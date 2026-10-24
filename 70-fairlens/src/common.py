"""Shared loading for the four step scripts of project 70."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from fairlens_pack import DEFAULT_REASON_COLUMNS, Data, Params, run_pack  # noqa: E402,F401

PROXY_COLUMN = "postcode_points"
PROXY_CODE = "R05"
TESTS = ("T1", "T2", "T3", "T4", "T5", "T6")


def load_cases() -> list:
    """The 36 portfolios with their planted truth. Groups come from the explicit `group` column."""
    with open(os.path.join(DATA, "case_truth.csv"), newline="", encoding="utf-8") as fh:
        truth = {r["case_id"]: r for r in csv.DictReader(fh)}
    rows_by = {}
    with open(os.path.join(DATA, "case_scores.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows_by.setdefault(r["case_id"], []).append(r)
    cases = []
    for cid in sorted(truth):
        rows, t = rows_by[cid], truth[cid]
        d = Data(sorted({r["group"] for r in rows}), [r["group"] for r in rows], [float(r["score"]) for r in rows],
                 [int(r["bad_outcome"]) for r in rows], [float(r[PROXY_COLUMN]) for r in rows], PROXY_COLUMN,
                 [tuple(r[c] for c in DEFAULT_REASON_COLUMNS) for r in rows])
        cases.append({"id": cid, "mechanism": t["mechanism"], "planted": t["proxy_planted"] == "1",
                      "predictive": t["proxy_predictive"] == "1", "data": d,
                      "params": Params(cutoff=float(t["cutoff"]), proxy_code=PROXY_CODE)})
    return cases


def run_cases(cases: list) -> dict:
    return {c["id"]: run_pack(c["data"], c["params"]) for c in cases}


def verdicts(pack: dict) -> dict:
    return {t["id"]: t["verdict"] for t in pack["tests"]}


def mechanisms(cases: list) -> list:
    return list(dict.fromkeys(c["mechanism"] for c in cases))


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
