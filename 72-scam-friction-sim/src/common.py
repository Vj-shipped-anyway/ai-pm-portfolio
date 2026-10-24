"""Shared loading for the four step scripts of project 72."""
from __future__ import annotations

import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from scam_friction_sim import (  # noqa: E402,F401
    check_assumptions, fmt_money, fmt_pct, load_assumptions, load_payments, metrics, policy_blanket, policy_none,
    policy_score, risk_score, simulate, tier)

# Planted by the generator and kept out of every rule on purpose; the steps use it to score what the rules miss.
HARD_CASE = "known_payee"
HARD_NEGATIVE = "big_first_time"
BLANKET_MIN_AMOUNT = 500


def load_all() -> tuple:
    """The 12,000 payments with their truth, and the assumptions file."""
    rows = load_payments(os.path.join(DATA, "payments.csv"), os.path.join(DATA, "truth.csv"))
    return rows, load_assumptions(os.path.join(DATA, "assumptions.json"))


def changed(assumptions: dict, **kw) -> dict:
    """A validated copy of the assumptions with some top-level values replaced."""
    out = copy.deepcopy(assumptions)
    out.update(kw)
    return check_assumptions(out)


def scaled_response(assumptions: dict, factor: float) -> dict:
    """A copy with every scam scenario's p_abandon multiplied by factor (capped at 1)."""
    sc = copy.deepcopy(assumptions["scam_scenarios"])
    for spec in sc.values():
        spec["p_abandon"] = min(1.0, spec["p_abandon"] * factor)
    return changed(assumptions, scam_scenarios=sc)


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
