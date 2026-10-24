"""Shared loading for the four step scripts of project 30."""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from payment_mandate_check import (ALL_GROUPS, HOLD, REJECT, RELEASE, audit_records, check_batch,  # noqa: E402,F401
                                   load_instructions, load_mandates, parse_amount, verify_audit)

# Kinds the data generator planted on purpose to test the rules; see data/README.md.
HARD_NEGATIVE = ("at_confirm_threshold", "at_per_payment_limit", "at_daily_cap", "recurring_gap", "first_second",
                 "last_second", "before_revocation", "hostile_memo")
KNOWN_LIMIT = ("split_below_confirm", "memo_contradicts_category")


def load_case():
    """(mandates, instructions, truth) where truth maps submission_id to {kind, truth_decision, group_id}."""
    mandates = load_mandates(os.path.join(DATA, "mandates.json"))
    rows = load_instructions(os.path.join(DATA, "instructions.csv"))
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        truth = {r["submission_id"]: r for r in csv.DictReader(fh)}
    return mandates, rows, truth


def approved_payee_names() -> set:
    """Every payee name on any mandate: the platform-wide approved-vendor list a name-matching gate would hold."""
    with open(os.path.join(DATA, "mandates.json"), encoding="utf-8") as fh:
        return {p["name"] for m in json.load(fh) for p in m["payees"]}


def score(decisions, truth):
    """decisions: {submission_id: decision}. Counts against the planted truth."""
    out = {"exact": 0, "bad_released": 0, "person_released": 0, "legit_stopped": 0, "legit_held": 0, "legit_rejected": 0}
    for sid, d in decisions.items():
        t = truth[sid]["truth_decision"]
        out["exact"] += d == t
        out["bad_released"] += t == REJECT and d == RELEASE
        out["person_released"] += t == HOLD and d == RELEASE
        out["legit_held"] += t == RELEASE and d == HOLD
        out["legit_rejected"] += t == RELEASE and d == REJECT
    out["legit_stopped"] = out["legit_held"] + out["legit_rejected"]
    return out


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
