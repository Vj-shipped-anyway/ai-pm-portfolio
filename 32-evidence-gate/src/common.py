"""Shared loading for the four step scripts of project 32."""
from __future__ import annotations

import csv
import os

from evidence_gate import evaluate, load_files, load_registry, load_tiers, parse_date, parse_record

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

TRUTH_TO_DECISION = {"should_block": "BLOCK", "needs_review": "REVIEW", "fine": "ALLOW"}


def load_world() -> dict:
    """The tier table, registry, repository file listing and as-of date that the gate reads."""
    with open(os.path.join(DATA, "as_of.txt"), encoding="utf-8") as fh:
        as_of = parse_date(fh.read())
    return {"tiers": load_tiers(os.path.join(DATA, "tier_evidence.csv")),
            "registry": load_registry(os.path.join(DATA, "registry.csv")),
            "files": load_files(os.path.join(DATA, "repo_files.txt")), "as_of": as_of}


def load_cases() -> list:
    """The pull requests: the description the gate reads, and the planted truth used only to score."""
    truth = {}
    with open(os.path.join(DATA, "pr_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["pr_id"]] = r
    cases = []
    with open(os.path.join(DATA, "pr_cases.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = truth[r["pr_id"]]
            cases.append({"pr_id": r["pr_id"], "body": r["body"], "use_case": t["use_case_id"], "true_tier": int(t["true_tier"]),
                          "kind": t["defect_kind"], "truth": t["truth_class"],
                          "bad_items": [x for x in t["bad_items"].split(";") if x]})
    return cases


def run_gate(case: dict, world: dict, registry=True, files=True, dates=True) -> dict:
    """Evaluate one pull request with the full gate, or with one input left out (registry, files, dates)."""
    return evaluate(parse_record(case["body"]), world["tiers"], world["registry"] if registry else None,
                    world["files"] if files else None, world["as_of"] if dates else None)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
