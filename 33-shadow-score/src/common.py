"""Shared loading for the four step scripts of project 33."""
import csv
import os
import sys
from dataclasses import replace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from shadow_score import (DEMO_RISKY, OUTCOME_COLS, PROPOSAL_COLS, Rules, evaluate, judge,  # noqa: E402,F401
                          parse_outcomes, parse_proposals, read_rows, score)

RULES = replace(Rules(), risky=DEMO_RISKY)


def load() -> tuple:
    """The parsed proposals and outcomes the scorecard reads."""
    proposals = parse_proposals(read_rows(os.path.join(DATA, "proposals.csv"), PROPOSAL_COLS), "proposals.csv")
    outcomes = parse_outcomes(read_rows(os.path.join(DATA, "outcomes.csv"), OUTCOME_COLS), "outcomes.csv")
    return proposals, outcomes


def _read(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def planted() -> list:
    """The generator's list of planted problems and hard negatives. The scorecard never reads it."""
    return _read("planted_problems.csv")


def joined() -> list:
    """Matched cases with the generator's truth attached, for the steps that explain a result."""
    proposals, outcomes = load()
    truth = {r["case_id"]: r for r in _read("case_truth.csv")}
    out_by_id = {o["case_id"]: o for o in outcomes}
    rows = []
    for p in sorted(proposals, key=lambda x: x["case_id"]):
        o = out_by_id.get(p["case_id"])
        if o is None:
            continue
        rows.append({"case_id": p["case_id"], "segment": p["segment"], "week": p["day"] // RULES.week_days,
                     "reviewer": o["reviewer"], "proposed": p["outcome"], "human": o["outcome"],
                     "kind": judge(p, o), "true": truth[p["case_id"]]["true_outcome"],
                     "planted": truth[p["case_id"]]["planted"]})
    return rows


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
