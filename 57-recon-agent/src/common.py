"""Shared loading, scoring and stand-ins for the four step scripts of project 57."""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from recon_agent import DEFAULT_PARAMS, POSTED, load_ledger, names_agree, reconcile  # noqa: E402,F401


def load_data() -> tuple:
    return load_ledger(os.path.join(DATA, "ledger_a.csv"), "A"), load_ledger(os.path.join(DATA, "ledger_b.csv"), "B")


def load_truth() -> dict:
    """The answer key: {'links': [...], 'match': {(a_ids, b_ids): link}, 'kind_of': {(side, id): link}}."""
    links = []
    with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            links.append({"kind": r["kind"], "status": r["truth_status"],
                          "a": tuple(x for x in r["a_ids"].split("+") if x), "b": tuple(x for x in r["b_ids"].split("+") if x)})
    match = {(k["a"], k["b"]): k for k in links if k["status"] == "match"}
    kind_of = {}
    for k in links:
        for i in k["a"]:
            kind_of[("A", i)] = k
        for i in k["b"]:
            kind_of[("B", i)] = k
    return {"links": links, "match": match, "kind_of": kind_of}


def pair_of(q: dict) -> tuple:
    return tuple(sorted(q["a_ids"])), tuple(sorted(q["b_ids"]))


def score(pairs: list, truth: dict) -> dict:
    """Compare posted (a_ids, b_ids) pairs with the answer key."""
    wrong = [p for p in pairs if p not in truth["match"]]
    found = {p for p in pairs if p in truth["match"]}
    return {"posted": len(pairs), "correct": len(found), "wrong": len(wrong),
            "wrong_by_kind": Counter(truth["kind_of"][("A", p[0][0])]["kind"] for p in wrong),
            "found": len(found), "true_pairs": len(truth["match"]),
            "missed": [(p, k) for p, k in sorted(truth["match"].items()) if p not in found]}


def amount_date_lookup(a_rows: list, b_rows: list, window: int) -> list:
    """The common first build: for each bank line take the nearest unused book line with the same amount
    inside the date window. No currency, reference or name is read. Returns posted (a_ids, b_ids) pairs."""
    free = list(b_rows)
    pairs = []
    for a in sorted(a_rows, key=lambda r: r["id"]):
        near = [b for b in free if b["cents"] == a["cents"] and abs((a["date"] - b["date"]).days) <= window]
        if near:
            b = min(near, key=lambda r: (abs((a["date"] - r["date"]).days), r["id"]))
            free.remove(b)
            pairs.append(((a["id"],), (b["id"],)))
    return pairs


def reviewer_double(proposals: list) -> list:
    """A script standing in for a person. It reads what is printed with each proposal and approves unless the
    counterparty names differ. It never opens the invoice. It is not a measure of people."""
    return [{"key": q["key"], "decision": "approve" if names_agree(q["a"], q["bs"]) else "reject",
             "approver": "reviewer-double", "note": "scripted stand-in"}
            for q in proposals if q["gate"] == "approval"]


def run_agent(a_rows: list, b_rows: list) -> dict:
    """The full agent as step 4 describes it: propose, then let the scripted reviewer answer, then gate."""
    first = reconcile(a_rows, b_rows, [])
    return reconcile(a_rows, b_rows, reviewer_double(first["proposals"]))


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
