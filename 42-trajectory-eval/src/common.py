"""Shared loading for the four step scripts of project 42."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from trajectory_eval import load_runs, load_tasks  # noqa: E402

# Planted profiles, by the explicit profile field in runs_truth.csv.
HARD_NEGATIVES = ("reorder_independent", "alt_tool", "harmless_reads", "retry_after_error", "unlisted_alias")


def load_all() -> tuple:
    """(tasks by id, runs). Each run carries its planted profile and truth_class ("pass" or "fail")."""
    tasks = load_tasks(os.path.join(DATA, "tasks.json"))
    runs = load_runs(os.path.join(DATA, "runs.csv"))
    truth = {}
    with open(os.path.join(DATA, "runs_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["run_id"]] = r
    for run in runs:
        run["profile"] = truth[run["run_id"]]["profile"]
        run["truth"] = truth[run["run_id"]]["truth_class"]
    return tasks, runs


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
