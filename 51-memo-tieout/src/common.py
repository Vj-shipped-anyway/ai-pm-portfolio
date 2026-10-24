"""Shared loading and scoring for the four step scripts of project 51."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from memo_tieout import FLAGGED, METRICS, build_spread, check_memo, parse_figures, ties  # noqa: E402


def load_memos() -> list:
    """The 28 memos: {memo_id, borrower, text, spread}. Spread rows are grouped by the memo_id column."""
    rows = {}
    with open(os.path.join(DATA, "spreads.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.setdefault(r["memo_id"], []).append(r)
    with open(os.path.join(DATA, "memos.json"), encoding="utf-8") as fh:
        memos = json.load(fh)
    return [{"memo_id": m["memo_id"], "borrower": m["borrower"], "text": m["memo"], "spread": build_spread(rows[m["memo_id"]])}
            for m in memos]


def load_truth() -> list:
    """One dict per planted figure: memo_id, line, col, kind, expected ("ok" or "flag"), text."""
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["line"], r["col"] = int(r["line"]), int(r["col"])
    return rows


def key(r: dict) -> tuple:
    return (r["memo_id"], r["line"], r["col"])


# ---------------------------------------------------------------- the checks the steps compare
def anywhere_flags(memo: dict) -> list:
    """The common basic check: read every figure with a $, % or x and look for it among the values in the spread file,
    at the precision the memo shows. It ignores the marks. Percent and multiple figures are never values in the file."""
    values = list(memo["spread"]["values"].values())
    out = []
    for no, line in enumerate(memo["text"].split("\n"), 1):
        for fig in parse_figures(line):
            if fig["kind"] != "money" or not any(ties(fig, v) for v in values):
                out.append((no, fig["start"] + 1))
    return out


def tool_flags(memo: dict, tolerance=None, keep=None) -> list:
    """Positions memo_tieout flags; keep(result, memo) narrows which flags count."""
    out = []
    for r in check_memo(memo["text"], memo["spread"], tolerance):
        if r["status"] in FLAGGED and (keep is None or keep(r, memo)):
            out.append((r["line"], r["col"]))
    return out


def names_a_formula(r: dict, memo: dict) -> bool:
    name = r["tag"].split("/")[0]
    return name in METRICS and name not in memo["spread"]["lines"]


# ---------------------------------------------------------------- scoring
def score(memos: list, truth: list, flagger) -> dict:
    """Run flagger(memo) -> [(line, col)]. Returns {"flagged": {key: bool}, "stray": flags that match no planted figure}."""
    flagged = {key(r): False for r in truth}
    stray = 0
    for m in memos:
        for line, col in flagger(m):
            k = (m["memo_id"], line, col)
            if k in flagged:
                flagged[k] = True
            else:
                stray += 1
    return {"flagged": flagged, "stray": stray}


def tally(truth: list, result: dict) -> dict:
    """caught of the wrong figures, false alarms of the fine ones (strays included), and the flag count per planted kind."""
    f = result["flagged"]
    bad = [r for r in truth if r["expected"] == "flag"]
    good = [r for r in truth if r["expected"] == "ok"]
    by_kind = {}
    for r in truth:
        k = by_kind.setdefault(r["kind"], {"flagged": 0, "total": 0, "expected": r["expected"]})
        k["total"] += 1
        k["flagged"] += 1 if f[key(r)] else 0
    return {"caught": sum(1 for r in bad if f[key(r)]), "wrong": len(bad),
            "false_alarms": sum(1 for r in good if f[key(r)]) + result["stray"], "fine": len(good),
            "stray": result["stray"], "by_kind": by_kind}


def passed(t: dict) -> str:
    """Wrong kinds the check let through, with counts."""
    parts = [f"{k} {v['total'] - v['flagged']}" for k, v in sorted(t["by_kind"].items())
             if v["expected"] == "flag" and v["flagged"] < v["total"]]
    return ", ".join(parts) or "none"


def alarms(t: dict) -> str:
    """Fine kinds the check flagged, with counts."""
    parts = [f"{k} {v['flagged']}" for k, v in sorted(t["by_kind"].items()) if v["expected"] == "ok" and v["flagged"]]
    if t["stray"]:
        parts.append(f"outside any planted figure {t['stray']}")
    return ", ".join(parts) or "none"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
