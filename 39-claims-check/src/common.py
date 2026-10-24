"""Shared loading and scoring for the four step scripts of project 39."""
from __future__ import annotations

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from claims_check import GREEN, TAGS, check_claims, extract_claims, index_evidence  # noqa: E402


def load_projects() -> list:
    with open(os.path.join(DATA, "projects.json"), encoding="utf-8") as fh:
        return json.load(fh)


def load_truth() -> list:
    """One dict per planted bullet: project_id, line_start, line_end, kind, expected ("ok" or "flag")."""
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["line_start"], r["line_end"] = int(r["line_start"]), int(r["line_end"])
    return rows


def grep_lines(project: dict) -> list:
    """The check in tools/check_repo.py: on each physical line, every digit string after a green circle
    must appear somewhere in the output as a piece of text."""
    haystack = project["evidence"].replace(",", "")
    flagged = []
    for no, line in enumerate(project["readme"].split("\n"), 1):
        if GREEN not in line:
            continue
        for seg in re.findall(GREEN + r"(.*?)(?=" + "|".join(TAGS) + "|$)", line):
            for tok in re.findall(r"\d[\d,]*\.?\d*", seg):
                t = tok.replace(",", "").rstrip(".")
                if len(t.replace(".", "")) >= 2 and t not in ("2025", "2026") and t not in haystack:
                    flagged.append(no)
    return flagged


def grep_on_claims_lines(project: dict) -> list:
    """The same piece-of-text match, but on the claims the tool extracts (wrapped bullets, code spans and links handled)."""
    haystack = project["evidence"].replace(",", "")
    flagged = []
    for c in extract_claims(project["readme"]):
        keys = list(c["key"]) if c["kind"] == "ratio" else [c["key"]]
        if any(len(k.replace(".", "")) >= 2 and k not in haystack for k in keys):
            flagged.append(c["line"])
    return flagged


def tool_lines(project: dict, min_digits: int = 2, pairs: bool = True) -> list:
    evidence = index_evidence([project["evidence"]])
    results = check_claims(extract_claims(project["readme"]), evidence, min_digits, pairs)
    return [r["line"] for r in results if r["status"] == "unsupported"]


def score(projects: list, truth: list, flagger) -> dict:
    """Run flagger(project) -> flagged line numbers. A flagged line counts for the planted bullet that contains it.
    Returns {"flagged": {(project_id, line_start): bool}, "stray": flags outside every planted bullet}."""
    flagged = {(r["project_id"], r["line_start"]): False for r in truth}
    stray = 0
    for p in projects:
        mine = [r for r in truth if r["project_id"] == p["project_id"]]
        for line in flagger(p):
            row = next((r for r in mine if r["line_start"] <= line <= r["line_end"]), None)
            if row is None:
                stray += 1
            else:
                flagged[(row["project_id"], row["line_start"])] = True
    return {"flagged": flagged, "stray": stray}


def tally(truth: list, result: dict) -> dict:
    """caught of unsupported, false alarms of supported (strays included), and the flag count per planted kind."""
    f = result["flagged"]
    bad = [r for r in truth if r["expected"] == "flag"]
    good = [r for r in truth if r["expected"] == "ok"]
    by_kind = {}
    for r in truth:
        k = by_kind.setdefault(r["kind"], {"flagged": 0, "total": 0, "expected": r["expected"]})
        k["total"] += 1
        k["flagged"] += 1 if f[(r["project_id"], r["line_start"])] else 0
    return {"caught": sum(1 for r in bad if f[(r["project_id"], r["line_start"])]), "unsupported": len(bad),
            "false_alarms": sum(1 for r in good if f[(r["project_id"], r["line_start"])]) + result["stray"],
            "supported": len(good), "stray": result["stray"], "by_kind": by_kind}


def misses(t: dict) -> str:
    parts = [f"{k} {v['total'] - v['flagged']}" for k, v in sorted(t["by_kind"].items())
             if v["expected"] == "flag" and v["flagged"] < v["total"]]
    return ", ".join(parts) or "none"


def false_alarms(t: dict) -> str:
    parts = [f"{k} {v['flagged']}" for k, v in sorted(t["by_kind"].items()) if v["expected"] == "ok" and v["flagged"]]
    if t["stray"]:
        parts.append(f"outside any planted bullet {t['stray']}")
    return ", ".join(parts) or "none"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
