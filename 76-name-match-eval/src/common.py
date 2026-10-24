"""Shared loading for the four step scripts of project 76."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from name_match_eval import (  # noqa: E402,F401
    FINE, GRID, by_kind_at, evaluate, false_alerts_per_true_hit, format_sweep, highest_threshold_with_recall_at_least,
    load_all, lowest_threshold_with_false_rate_at_most, make_matcher, metrics_at, pct)

TARGET_RECALL = 0.85          # assumption: the recall a screening team asks for
TARGET_FALSE_ALERT = 0.10     # assumption: the share of clear names a team can afford to review
BASE_RATE = 1 / 10000         # assumption: real matches among all customers


def load():
    """(entries, customers, truth) for the full synthetic set."""
    return load_all(os.path.join(DATA, "watchlist.csv"), os.path.join(DATA, "customers.csv"), os.path.join(DATA, "truth.csv"))


def records_for(kind: str, data) -> list:
    entries, customers, truth = data
    return evaluate(make_matcher(kind, [e["name"] for e in entries]), entries, customers, truth)


def kinds_of(records: list) -> tuple:
    """(sorted match kinds, sorted clear kinds) as planted."""
    m = sorted({r["kind"] for r in records if r["truth"] == "match"})
    c = sorted({r["kind"] for r in records if r["truth"] == "clear"})
    return m, c


def modeled_line(m: dict) -> str:
    """The base-rate model for one operating point. Modeled, not measured: BASE_RATE is an assumption."""
    n = false_alerts_per_true_hit(m["false_alerts"] / m["clear"], m["caught"] / m["matches"], BASE_RATE)
    return "about %s false alerts for each true hit" % ("{:,}".format(int(round(n))) if n is not None else "n/a")


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
