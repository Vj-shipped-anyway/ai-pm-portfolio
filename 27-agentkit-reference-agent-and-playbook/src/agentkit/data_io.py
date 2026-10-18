"""Loads the synthetic world from data/*.csv into plain dicts. Standard library only."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _rows(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world(data_dir: Optional[Path] = None) -> Dict:
    d = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    cases = _rows(d / "cases.csv")
    for c in cases:
        c["delivery_no"] = int(c["delivery_no"])
        c["opened_hour"] = int(c["opened_hour"])
    payments = {r["payment_id"]: r for r in _rows(d / "payments.csv")}
    for p in payments.values():
        p["value_hour"] = int(p["value_hour"])
    outcomes = {}
    for r in _rows(d / "human_outcomes.csv"):
        r["touch_minutes"] = float(r["touch_minutes"])
        outcomes[r["case_id"]] = r
    truth = {r["case_id"]: r for r in _rows(d / "case_truth.csv")}
    for t in truth.values():
        t["planted"] = int(t["planted"])
    reason_codes = {r["code"]: r for r in _rows(d / "reason_codes.csv")}
    watchlist = _rows(d / "parties_watchlist.csv")
    faults = _rows(d / "fault_schedule.csv")
    minutes = {r["step"]: {**r, "minutes": float(r["minutes"])} for r in _rows(d / "step_minutes.csv")}
    return {"cases": cases, "payments": payments, "outcomes": outcomes, "truth": truth,
            "reason_codes": reason_codes, "watchlist": watchlist, "faults": faults, "step_minutes": minutes,
            "data_dir": d}
