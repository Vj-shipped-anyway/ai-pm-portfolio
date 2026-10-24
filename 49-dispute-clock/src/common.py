"""Shared loading and the stand-in methods for the four step scripts of project 49."""
from __future__ import annotations

import csv
import os

import dispute_clock as dc

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

DATE_COLUMNS = ["first_contact_on", "logged_on", "acknowledged_on", "provisional_credit_on", "concluded_on",
                "final_notice_on", "info_requested_on", "info_received_on"]
INVESTIGATION = ("DC3", "DC4")      # the two investigation clocks: the only ones a flat 30-day target can speak to
FLAT_TARGET_DAYS = 30


def load_world() -> dict:
    """Policy, holidays, disputes (every date column parsed), the as-of date and the planted truth."""
    with open(os.path.join(DATA, "as_of.txt"), encoding="utf-8") as fh:
        as_of = dc.parse_date(fh.read(), "as_of.txt")
    truth = {}
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            tags = tuple(t for t in r["hard_case"].split("|") if t)
            truth[(r["dispute_id"], r["clock_id"])] = {"status": r["planted_status"], "tags": tags}
    return {"as_of": as_of, "policy": dc.load_policy(os.path.join(DATA, "policy.csv")),
            "holidays": dc.load_holidays(os.path.join(DATA, "holidays.csv")),
            "disputes": dc.load_disputes(os.path.join(DATA, "disputes.csv"), DATE_COLUMNS), "truth": truth}


def applicable(world: dict):
    """Every (dispute, clock) pair a clock applies to, in file order."""
    return [(d, c) for d in world["disputes"] for c in world["policy"] if dc.applies(d, c["applies_to"])]


def stand_in_statuses(world: dict, business_days: bool, start_field: str) -> dict:
    """The statuses of a simpler method, keyed by (dispute_id, clock_id).

    business_days  count business days as the policy says, or treat every window as calendar days
    start_field    the date column a first-contact clock starts from: first_contact_on or logged_on
    """
    out = {}
    for d, c in applicable(world):
        anchor = start_field if c["anchor"] == "first_contact_on" else c["anchor"]
        start = d["dates"][anchor]
        if start is None:
            out[(d["dispute_id"], c["clock_id"])] = "not_started"
            continue
        unit = c["unit"] if business_days else "calendar"
        due = dc.add_days(start, c["window"], unit, world["holidays"])
        out[(d["dispute_id"], c["clock_id"])] = dc.status_of(due, dc.sent_date(d, c), world["as_of"])
    return out


def tool_statuses(world: dict) -> dict:
    results = dc.evaluate_all(world["disputes"], world["policy"], world["holidays"], world["as_of"])
    return {(r["dispute_id"], r["clock_id"]): r["status"] for r in results}


def disagreements(got: dict, world: dict) -> list:
    """Keys where a method's status differs from the planted truth, sorted."""
    return sorted(k for k, v in got.items() if v != world["truth"][k]["status"])


def is_missed(status: str) -> bool:
    return status in ("late", "breached")


def pct(a: int, b: int) -> str:
    return f"{a / b:.1%}"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
