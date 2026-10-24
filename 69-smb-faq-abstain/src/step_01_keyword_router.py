"""Step 1 - Status quo: a keyword router in front of the FAQ pages.

Before any model drafts an answer, a router reads the question, looks for a keyword and either returns one
canned passage from the knowledge base, points the customer to a page, or hands them to a banker. It never
states anything it was not given, so the cost is not wrong answers but how little it answers. A canned
passage is scored right when it is the passage that answers the question (the fact_id in data/truth.csv).

Run (from src/):  python3 step_01_keyword_router.py
"""
from __future__ import annotations

import re

from common import load_cases

ROUTES = [  # keywords, kind, target
    (("support", "phone", "chat", "hours"), "passage", "F12"),
    (("document", "documents", "open"), "passage", "F11"),
    (("fee", "fees", "cost", "costs", "charge"), "page", "/fees"),
    (("rate", "rates", "apy", "apr", "interest", "pay", "pays"), "page", "/rates"),
    (("loan", "loans", "credit", "line", "borrow"), "page", "/lending"),
]


def route(question: str) -> tuple:
    words = set(re.findall(r"[a-z]+", question.lower()))
    for keywords, kind, target in ROUTES:
        if words & set(keywords):
            return kind, target
    return "banker", ""


def main() -> None:
    cases = load_cases()
    routed = [(c, *route(c["question"])) for c in cases]
    passages = [(c, t) for c, kind, t in routed if kind == "passage"]
    right = [c for c, t in passages if t == c["fact_id"]]
    wrong = [c for c, t in passages if t != c["fact_id"]]
    pages = [c for c, kind, _t in routed if kind == "page"]
    bankers = [c for c, kind, _t in routed if kind == "banker"]
    has_answer = [c for c in cases if c["fact_id"]]
    print("STEP 1 - a keyword router in front of the FAQ pages")
    print(f"  returned a canned passage: {len(passages)} of {len(cases)} ({len(right)} the right passage, {len(wrong)} the wrong one)")
    print(f"  pointed to a fees, rates or lending page: {len(pages)} of {len(cases)}")
    print(f"  handed to a banker: {len(bankers)} of {len(cases)}")
    print(f"  questions the knowledge base can answer: {len(has_answer)}; the router answered {len(right)} of them")
    for c in wrong:
        print(f"  wrong passage: {c['qid']} {c['question']}")
    print("  The router invents nothing, but it answers few questions and a keyword can send one to the wrong passage.")


if __name__ == "__main__":
    main()
