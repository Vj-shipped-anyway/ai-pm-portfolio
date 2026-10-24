"""Shared loading and scoring for the four step scripts of project 41."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from narrative_trace import UNTRACED, analyse, load_records  # noqa: E402


def load_corpus() -> tuple:
    """(ledger, narratives, truth). truth maps a case_id to its planted sentences:
    sent_no, start, end (offsets into the narrative), kind and expected ("ok" or "flag")."""
    ledger = load_records(os.path.join(DATA, "transactions.csv"))
    with open(os.path.join(DATA, "narratives.json"), encoding="utf-8") as fh:
        narratives = json.load(fh)
    truth = {}
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for key in ("sent_no", "start", "end"):
                r[key] = int(r[key])
            truth.setdefault(r["case_id"], []).append(r)
    return ledger, narratives, truth


def locate(rows: list, start: int):
    """The planted sentence that holds the character at offset start, or None."""
    return next((r for r in rows if r["start"] <= start < r["end"]), None)


def score(narratives: list, truth: dict, flagger) -> tuple:
    """flagger(case_id, text) returns (start offset, flagged) pairs. A flag counts for the planted sentence that
    holds its start. Returns ({(case_id, sent_no): flagged}, flags outside every planted sentence)."""
    flags = {(r["case_id"], r["sent_no"]): False for rows in truth.values() for r in rows}
    stray = 0
    for n in narratives:
        rows = truth[n["case_id"]]
        for start, flagged in flagger(n["case_id"], n["text"]):
            row = locate(rows, start)
            if row is None:
                stray += 1 if flagged else 0
            elif flagged:
                flags[(row["case_id"], row["sent_no"])] = True
    return flags, stray


def tally(truth: dict, flags: dict, stray: int) -> dict:
    by_kind = {}
    for rows in truth.values():
        for r in rows:
            k = by_kind.setdefault(r["kind"], {"flagged": 0, "total": 0, "expected": r["expected"]})
            k["total"] += 1
            k["flagged"] += 1 if flags[(r["case_id"], r["sent_no"])] else 0
    bad = [v for v in by_kind.values() if v["expected"] == "flag"]
    good = [v for v in by_kind.values() if v["expected"] == "ok"]
    return {"caught": sum(v["flagged"] for v in bad), "defects": sum(v["total"] for v in bad),
            "false_alarms": sum(v["flagged"] for v in good) + stray, "fine": sum(v["total"] for v in good),
            "stray": stray, "by_kind": by_kind}


def tool_flagger(ledger, strict: bool = False, **options):
    """A flagger that runs the tool. strict also flags a sentence that cites a record but states nothing checkable."""
    bad = UNTRACED + (("unchecked",) if strict else ())

    def flagger(case_id, text):
        return [(r["start"], r["status"] in bad) for r in analyse(text, ledger, case_id, **options)]
    return flagger


def false_alarms(t: dict) -> str:
    parts = ["%s %d" % (k, v["flagged"]) for k, v in sorted(t["by_kind"].items()) if v["expected"] == "ok" and v["flagged"]]
    if t["stray"]:
        parts.append("outside any planted sentence %d" % t["stray"])
    return ", ".join(parts) or "none"


def misses(t: dict) -> str:
    parts = ["%s %d" % (k, v["total"] - v["flagged"]) for k, v in sorted(t["by_kind"].items())
             if v["expected"] == "flag" and v["flagged"] < v["total"]]
    return ", ".join(parts) or "none"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
