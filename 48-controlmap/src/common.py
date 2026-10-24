"""Shared loading and scoring for the four step scripts of project 48."""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from controlmap import load_controls, load_obligations, load_terms, parse_date, tokens  # noqa: E402

STOP = frozenset("""about above after again against also been before being between both each every from have into more most must
only other over same should such than that their them then there these they this those through under until what when where
which while will with within without would your""".split())


def read_rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_all() -> dict:
    """The register, the library, the dictionary, the hand-typed column and the planted truth."""
    with open(os.path.join(DATA, "dataset.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    as_of = parse_date(meta["as_of"], "dataset.json")
    obligations = load_obligations(os.path.join(DATA, "obligations.csv"))
    controls = load_controls(os.path.join(DATA, "controls.csv"), as_of)
    claimed = {r["obligation_id"]: [x for x in r["claimed_controls"].split(";") if x] for r in read_rows("obligations.csv")}
    return {
        "meta": meta, "obligations": obligations, "controls": controls, "ctl_by_id": {c["control_id"]: c for c in controls},
        "terms": load_terms(os.path.join(DATA, "terms.csv")), "claimed": claimed,
        "truth_status": {r["obligation_id"]: r["status"] for r in read_rows("truth_status.csv")},
        "truth_pairs": {(r["obligation_id"], r["control_id"]): r["coverage"] for r in read_rows("truth_pairs.csv")},
        "kind": {r["control_id"]: r["kind"] for r in read_rows("control_truth.csv")},
    }


def pct(a: int, b: int) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def content_tokens(text: str) -> set:
    """Words of 4 letters or more that are not on the stop list, with a trailing s removed."""
    out = set()
    for t in tokens(text):
        if len(t) >= 4 and t not in STOP:
            out.add(t[:-1] if t.endswith("s") and len(t) > 4 else t)
    return out


def sheet_links(data: dict, min_shared: int = 2) -> dict:
    """The common basic approach: an obligation links to every control (retired ones too) that shares at least
    `min_shared` content words with it. {obligation_id: [control_id, ...]}"""
    ctl_words = {c["control_id"]: content_tokens(c["name"] + " " + c["description"]) for c in data["controls"]}
    out = {}
    for o in data["obligations"]:
        words = content_tokens(o["statement"])
        out[o["obligation_id"]] = [cid for cid, w in ctl_words.items() if len(words & w) >= min_shared]
    return out


def covered_or_not(linked_ids) -> str:
    """How a reader takes a list: any control listed means covered, none means uncovered."""
    return "COVERED" if linked_ids else "UNCOVERED"


def truth_orphans(data: dict) -> list:
    """Active controls that serve no obligation at all, by the planted truth."""
    serving = {cid for (_oid, cid) in data["truth_pairs"]}
    return [c["control_id"] for c in data["controls"] if c["active"] and c["control_id"] not in serving]


def pair_scores(found: set, data: dict) -> tuple:
    """(true links, links found, true pairs) for a set of (obligation_id, control_id) links."""
    truth = set(data["truth_pairs"])
    return len(found & truth), len(found), len(truth)


def count_by(items) -> dict:
    out = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
