"""Shared loading for the four step scripts of project 65."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from failover_scorecard import BUNDLED_AS_OF, default_policy, load_drills, load_services, parse_date, score  # noqa: E402,F401

AS_OF = parse_date(BUNDLED_AS_OF)


def _csv(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_all() -> dict:
    """Services, drills and the planted truth, joined on service_id (an explicit field, nothing inferred)."""
    services = load_services(os.path.join(DATA, "services.csv"))
    drills = load_drills(os.path.join(DATA, "drills.csv"))
    truth = {r["service_id"]: r for r in _csv("service_truth.csv")}
    claims = {r["service_id"]: r["failover_plan"] == "yes" for r in _csv("services.csv")}
    return {"services": services, "drills": drills, "truth": truth, "claims": claims,
            "by_id": {s["service_id"]: s for s in services}}


def truth_class(data: dict, service_id: str) -> str:
    return data["truth"][service_id]["truth_class"]


def predicted_class(status: str) -> str:
    """The class a scorecard status asserts: READY means ready, NOT_REQUIRED means accepted, the rest not_ready."""
    return {"READY": "ready", "NOT_REQUIRED": "accepted"}.get(status, "not_ready")


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
