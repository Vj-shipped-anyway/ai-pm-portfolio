"""Shared loading, the basic approach and scoring for the four step scripts of project 56."""
from __future__ import annotations

import csv
import os
from collections import Counter

from aigf_checks import STATUSES, analyze, load_checks, load_crosswalk, load_outputs, load_risks

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

KIND_ORDER = ["stale_value", "label_missing", "unknown_check", "unknown_risk", "overclaim", "no_output", "duplicate",
              "wording_claim", "wording_paraphrase", "false_declaration"]
HARD_NEGATIVES = ["ok_reformatted", "ok_negated_word", "ok_partial"]


def load_all() -> dict:
    """The catalogue, the registry, the crosswalk, the captured outputs and the planted truth."""
    def p(name):
        return os.path.join(DATA, name)

    with open(p("row_truth.csv"), newline="", encoding="utf-8") as fh:
        row_truth = {r["row_id"]: r for r in csv.DictReader(fh)}
    with open(p("risk_truth.csv"), newline="", encoding="utf-8") as fh:
        risk_truth = {r["risk_id"]: r["status"] for r in csv.DictReader(fh)}
    return {"risks": load_risks(p("risks.csv")), "checks": load_checks(p("checks.csv")),
            "rows": load_crosswalk(p("crosswalk.csv")), "outputs": load_outputs(p("check_outputs.json")),
            "row_truth": row_truth, "risk_truth": risk_truth}


def basic_flags(d: dict) -> dict:
    """The common basic approach, as a script: a row is flagged when its risk or check id does not
    resolve, or when its claimed value is not found anywhere in the check's output. A row whose
    check has no output file is skipped, which is what a grep loop over missing files does."""
    flags = {}
    for row in d["rows"]:
        kind = None
        if row["risk_id"] not in d["risks"]:
            kind = "unknown_risk"
        elif row["check_id"] not in d["checks"]:
            kind = "unknown_check"
        elif row["check_id"] in d["outputs"] and row["claim_value"] not in d["outputs"][row["check_id"]]:
            kind = "stale_value"
        flags[row["row_id"]] = {kind} if kind else set()
    return flags


def basic_status(d: dict, flags: dict) -> dict:
    """Risk status from the basic approach: an unflagged row counts as shown, at the coverage the row states."""
    out = {}
    for risk_id in d["risks"]:
        mine = [r for r in d["rows"] if r["risk_id"] == risk_id]
        ok = [r for r in mine if not flags[r["row_id"]]]
        if not mine:
            out[risk_id] = "GAP"
        elif any(r["covers"] == "full" for r in ok):
            out[risk_id] = "CHECKED"
        elif ok:
            out[risk_id] = "PARTIAL"
        else:
            out[risk_id] = "UNVERIFIED"
    return out


def tool_flags(d: dict) -> tuple:
    """The finding kinds per row from aigf_checks, and the full result."""
    result = analyze(d["risks"], d["checks"], d["rows"], d["outputs"])
    flags = {r["row_id"]: set() for r in d["rows"]}
    for f in result["findings"]:
        flags[f["row_id"]].add(f["kind"])
    return flags, result


def score(d: dict, flags: dict) -> dict:
    """Score row flags against the planted truth."""
    truth = d["row_truth"]
    defective = [r for r, t in truth.items() if t["defective"] == "yes"]
    clean = [r for r, t in truth.items() if t["defective"] == "no"]
    by_kind = {}
    for kind in KIND_ORDER + ["ok", "ok_reformatted", "ok_negated_word", "ok_partial"]:
        ids = [r for r, t in truth.items() if t["kind"] == kind]
        by_kind[kind] = (sum(1 for r in ids if flags[r]), len(ids))
    return {"rows": len(truth), "defective": len(defective), "clean": len(clean),
            "found": sum(1 for r in defective if flags[r]),
            "right_kind": sum(1 for r in defective if truth[r]["expected_finding"] in flags[r]),
            "false_alarms": sum(1 for r in clean if flags[r]),
            "flagged": sum(1 for r in truth if flags[r]), "by_kind": by_kind}


def status_right(d: dict, status: dict) -> int:
    return sum(1 for r, s in status.items() if d["risk_truth"][r] == s)


def status_counts(status: dict) -> str:
    c = Counter(status.values())
    return ", ".join(f"{s} {c[s]}" for s in STATUSES)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
