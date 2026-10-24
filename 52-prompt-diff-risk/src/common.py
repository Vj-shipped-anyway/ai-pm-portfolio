"""Shared loading for the four step scripts of project 52."""
import csv
import os

from prompt_diff_risk import analyse, load_catalogue, load_probes

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

TRUTH_TO_DECISION = {"high": "BLOCK", "medium": "REVIEW", "low": "ALLOW"}


def load_cases() -> list:
    """The 70 prompt pull requests with their planted truth."""
    truth = {}
    with open(os.path.join(DATA, "pr_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["pr_id"]] = r
    cases = []
    with open(os.path.join(DATA, "pr_cases.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = truth[r["pr_id"]]
            cases.append({"pr_id": r["pr_id"], "assistant": r["assistant"], "old": r["old_prompt"], "new": r["new_prompt"],
                          "kind": t["change_kind"], "truth": t["truth_class"], "item": t["changed_item"],
                          "slices": [s for s in t["truth_slices"].split(";") if s],
                          "fails": [p for p in t["failing_probes"].split(";") if p]})
    return cases


def load_world() -> tuple:
    """(tool catalogue, probe set) from data/."""
    return load_catalogue(os.path.join(DATA, "tools.json")), load_probes(os.path.join(DATA, "probes.csv"))


def analyse_all(cases, catalogue, probes) -> dict:
    """{pr_id: analysis} with the full classifier."""
    return {c["pr_id"]: analyse(c["old"], c["new"], catalogue, probes) for c in cases}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
