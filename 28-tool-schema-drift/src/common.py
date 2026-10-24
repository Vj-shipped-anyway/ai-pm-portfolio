"""Shared loading for the four step scripts of project 28."""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from tool_schema_drift import diff_schemas, decide, replay, load_calls, strict_validate  # noqa: E402,F401

TRUTH_TO_DECISION = {"breaking": "BLOCK", "behavior_risk": "REVIEW", "non_breaking": "ALLOW"}


def load_cases() -> list:
    """The 67 pull requests with their planted truth."""
    truth = {}
    with open(os.path.join(DATA, "pr_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["pr_id"]] = r
    cases = []
    with open(os.path.join(DATA, "pr_cases.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = truth[r["pr_id"]]
            cases.append({"pr_id": r["pr_id"], "tool": r["tool"], "old_text": r["old_schema_json"], "new_text": r["new_schema_json"],
                          "old": json.loads(r["old_schema_json"]), "new": json.loads(r["new_schema_json"]),
                          "kind": t["change_kind"], "truth": t["truth_class"], "param": t["changed_param"]})
    return cases


def calls_by_tool() -> dict:
    out = {}
    for c in load_calls(os.path.join(DATA, "recorded_calls.csv")):
        out.setdefault(c["tool"], []).append(c)
    return out


def replay_counts(cases, calls) -> dict:
    """{pr_id: number of recorded calls for that tool that fail on the PR's new schema}"""
    return {c["pr_id"]: len(replay(c["new"], calls.get(c["tool"], []))) for c in cases}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
