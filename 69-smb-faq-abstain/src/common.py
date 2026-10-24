"""Shared loading and scoring for the four step scripts of project 69."""
from __future__ import annotations

import csv
import os
from collections import Counter

from smb_faq_abstain import evaluate, load_kb

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")


def _rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_kb_default() -> list:
    return load_kb(os.path.join(DATA, "kb.csv"))


def load_cases() -> list:
    """The 30 questions with the stored draft and the planted truth for each."""
    drafts = {r["query_id"]: r["draft"] for r in _rows("drafts.csv")}
    truth = {r["query_id"]: r for r in _rows("truth.csv")}
    cases = []
    for q in _rows("queries.csv"):
        t = truth[q["query_id"]]
        cases.append({"qid": q["query_id"], "topic": q["topic"], "q_class": q["q_class"], "question": q["question"],
                      "correct": q["correct_answer"], "draft": drafts[q["query_id"]], "fact_id": t["fact_id"],
                      "mode": t["draft_mode"], "draft_ok": t["draft_ok"] == "yes", "should_serve": t["should_serve"] == "yes",
                      "hard_case": t["hard_case"]})
    return cases


def run_cases(cases: list, kb: list, **options) -> list:
    return [evaluate(c["question"], c["draft"], kb, **options) for c in cases]


def outcome(case: dict, result: dict) -> str:
    """served_ok, served_wrong, caught (a wrong draft held back), false_abstain (a correct draft held back) or declined."""
    if result["decision"] == "SERVE":
        return "served_ok" if case["should_serve"] else "served_wrong"
    if case["mode"] == "decline":
        return "declined"
    return "false_abstain" if case["should_serve"] else "caught"


def tally(cases: list, results: list) -> Counter:
    return Counter(outcome(c, r) for c, r in zip(cases, results))


def by_class(cases: list, results: list, which: str) -> str:
    n = Counter(c["q_class"] for c, r in zip(cases, results) if outcome(c, r) == which)
    return ", ".join(f"{k} {v}" for k, v in sorted(n.items())) or "none"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
