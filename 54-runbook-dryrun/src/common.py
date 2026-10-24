"""Shared loading for the four step scripts of project 54."""

from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from runbook_dryrun import dry_run, load_runbook, render  # noqa: E402,F401


def load_cases() -> list:
    """The drill cases with their planted truth. Each case carries its parsed runbook."""
    truth = {}
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["case_id"]] = r
    cases = []
    with open(os.path.join(DATA, "cases.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = truth[r["case_id"]]
            cases.append({"case_id": r["case_id"], "requester": r["requester"], "params": json.loads(r["params_json"]),
                          "world": json.loads(r["world_json"]), "approvals": json.loads(r["approvals_json"]),
                          "rb": load_runbook(r["runbook_yaml"]), "kind": t["case_kind"], "group": t["case_group"], "truth": t["truth_verdict"],
                          "real_run": t["real_run"], "problem_index": int(t["problem_index"]),
                          "writes_before": int(t["writes_before"]), "expect_warning": t["expect_warning"] == "yes"})
    return cases


def run_case(c: dict, checks: tuple = ("lint", "state", "gate")) -> dict:
    return dry_run(c["rb"], c["world"], c["params"], c["approvals"], c["requester"], checks)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
