"""Shared loading for the four step scripts of project 40."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from eval_gate import evaluate, load_probes, load_results  # noqa: E402

DECISIONS = ("BLOCK", "REVIEW", "ALLOW")
RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}


def _table(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_runs() -> tuple:
    """The probe file and the 64 candidate deploys, each with its pin, planted truth and result rows."""
    probes = load_probes(os.path.join(DATA, "probes.csv"))
    pins = {r["run_id"]: r["pin"] for r in _table("run_pins.csv")}
    runs = []
    for t in _table("run_truth.csv"):
        rows, _ = load_results(os.path.join(DATA, "runs.csv"), t["run_id"])
        runs.append({"run_id": t["run_id"], "kind": t["planted_kind"], "truth": t["truth_decision"],
                     "pin": pins[t["run_id"]], "rows": rows})
    return probes, runs


def gate(probes: list, run: dict, kinds=None, **limits) -> dict:
    """Evaluate one run. With kinds, only findings of those kinds count toward the decision (one rule at a time)."""
    result = evaluate(probes, run["rows"], run["pin"], **limits)
    if kinds is not None:
        levels = [f["level"] for f in result["findings"] if f["kind"] in kinds]
        result = dict(result, decision=max(levels, key=RANK.__getitem__, default="ALLOW"))
    return result


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
