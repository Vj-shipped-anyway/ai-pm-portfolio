"""Shared loading and scoring for the four step scripts of project 71."""
import csv
import os

from tag_chargeback import (allocate, summarize, compliance_summary, load_accounts, load_bill,  # noqa: F401
                            line_compliance, load_cost_centers, load_policy, fmt_usd, pct, plain_usd, EXTRAS)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")


def load_world() -> dict:
    """The billing export, the registry, the account map, the policy, and the planted truth per line."""
    registry = load_cost_centers(os.path.join(DATA, "cost_centers.csv"))
    truth = {}
    with open(os.path.join(DATA, "billing_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            truth[r["line_id"]] = {"cc": r["true_cost_center"], "defect": r["defect_kind"], "compliant": r["compliant"]}
    return {"bill": load_bill(os.path.join(DATA, "billing_export.csv")),
            "policy": load_policy(os.path.join(DATA, "policy.json")),
            "registry": registry,
            "accounts": load_accounts(os.path.join(DATA, "accounts.csv"), registry),
            "truth": truth}


def outcome(result: dict, true_cc: str) -> str:
    """correct, wrong or left for one allocated line, judged against the planted owner."""
    if result["rule"] == "zero_cost":
        return "correct"          # nothing to charge, so nothing can land on the wrong team
    if result["rule"] == "unallocated":
        return "left"
    if true_cc == "SHARED":
        return "correct" if result["rule"] == "shared_split" else "wrong"
    if result["rule"] == "shared_split":
        return "wrong"
    return "correct" if result["cost_center"] == true_cc else "wrong"


def score(bill: list, results: list, truth: dict) -> dict:
    """Micros of spend that landed on the planted owner (correct), on someone else (wrong) or nowhere (left),
    in total, by planted defect kind, and the wrong spend by rule."""
    out = {"correct": 0, "wrong": 0, "left": 0, "by_defect": {}, "wrong_by_rule": {}}
    for line, r in zip(bill, results):
        t = truth[line["line_id"]]
        o = outcome(r, t["cc"])
        out[o] += r["usd"]
        d = out["by_defect"].setdefault(t["defect"], {"lines": 0, "usd": 0, "correct": 0, "wrong": 0, "left": 0,
                                                         "n_correct": 0, "n_wrong": 0, "n_left": 0})
        d["lines"] += 1
        d["usd"] += r["usd"]
        d[o] += r["usd"]
        d["n_" + o] += 1
        if o == "wrong":
            out["wrong_by_rule"][r["rule"]] = out["wrong_by_rule"].get(r["rule"], 0) + r["usd"]
    return out


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
