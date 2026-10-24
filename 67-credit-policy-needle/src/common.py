"""Shared loading and the four stub readers for the step scripts of project 67.

READ THIS FIRST: nothing here is a model and nothing calls one. Each reader is a small deterministic
function, and all but the control have one fault written in on purpose, so the checks in
credit_policy_needle.py can be tried against faults that are known to be there. They are written against
the synthetic wording of data/.
The reader interface is one function: reader(document_text, question) -> answer_text.
"""
from __future__ import annotations

import csv
import os
import re
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from credit_policy_needle import load_probes, read_text  # noqa: E402

TRUNCATE_AT = 60_000   # the truncating reader sees this many characters, about 33 pages (an assumption)
READERS = ("control", "truncating", "base_only", "retrieval")
READER_NOTE = {
    "control": "reads every block, follows clause references, applies an exception only when its condition holds",
    "truncating": "sees only the first 60,000 characters",
    "base_only": "answers from the rule clause and never reads an exception",
    "retrieval": "reads only blocks that hold every word of the product name and the attribute phrase",
}

VAL = r"\$\d{1,3}(?:,\d{3})*|\d+%|\d+ points|\d+ months"
NOUNS = ("a customer relationship", "verified annual income", "an initial payment", "annual business revenue")
COND_RE = re.compile(r"(%s) of at least (%s)" % ("|".join(NOUNS), VAL))
FACT_RE = re.compile(r"(%s) of (%s)" % ("|".join(NOUNS), VAL))
QUESTION_RE = re.compile(r"^What is the (?P<attr>.+?) for (?P<prod>.+?)(?: for an applicant with (?P<facts>.+))?\?$")
DEFAULT_RE = re.compile(r"payment default recorded (\d+) months ago")
CARVE_TAIL = r" does not apply to an applicant with a payment default recorded in the prior (\d+) months"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def num(text: str) -> float:
    return float(re.sub(r"[^\d.]", "", text))


def parse_question(question: str):
    m = QUESTION_RE.match(question)
    if not m:
        return None
    facts = m.group("facts") or ""
    d = DEFAULT_RE.search(facts)
    return {"attr": m.group("attr"), "prod": m.group("prod"),
            "facts": {noun: num(v) for noun, v in FACT_RE.findall(facts)},
            "default": int(d.group(1)) if d else None}


@lru_cache(maxsize=8)
def _blocks(doc: str) -> tuple:
    return tuple(b.strip() for b in doc.split("\n\n") if b.strip())


@lru_cache(maxsize=8)
def _token_sets(doc: str) -> tuple:
    return tuple((b, frozenset(TOKEN_RE.findall(b.lower()))) for b in _blocks(doc))


@lru_cache(maxsize=8)
def _visible(doc: str) -> tuple:
    """Blocks that end inside the first TRUNCATE_AT characters; a block the limit cuts is dropped."""
    out, pos = [], 0
    for raw in doc.split("\n\n"):
        end = pos + len(raw)
        if end > TRUNCATE_AT:
            break
        if raw.strip():
            out.append(raw.strip())
        pos = end + 2
    return tuple(out)


def answer_from(blocks: tuple, q: dict, use_exceptions: bool = True) -> str:
    """The rule value, changed by every exception whose condition the applicant meets and no carve-out cancels."""
    rule = re.compile(r"^(?P<id>\d+\.\d+) The %s for %s is (?P<val>%s)" % (re.escape(q["attr"]), re.escape(q["prod"]), VAL))
    found = next(((m, b) for b in blocks for m in [rule.match(b)] if m), None)
    if found is None:
        return ""
    m, text = found
    value = m.group("val")
    if not use_exceptions:
        return value
    bid = m.group("id")
    exceptions = []   # (block id, new value, condition noun, threshold)
    inline = re.search(r", except that it is (%s)" % VAL, text)
    cond = COND_RE.search(text)
    if inline and cond:
        exceptions.append((bid, inline.group(1), cond.group(1), num(cond.group(2))))
    cites = re.compile(r"clause %s(?!\d|\.\d)" % re.escape(bid))
    for b in blocks:
        if b is text or "does not apply" in b or "clause %s" % bid not in b or not cites.search(b):
            continue
        new, c, head = re.search(r" is (%s)" % VAL, b), COND_RE.search(b), re.match(r"^(\S+) ", b)
        if new and c and head:
            exceptions.append((head.group(1), new.group(1), c.group(1), num(c.group(2))))
    for eid, new_value, noun, threshold in exceptions:
        if q["facts"].get(noun, -1.0) < threshold:
            continue
        carve = re.compile(r"^\S+ Clause %s(?!\d|\.\d)%s" % (re.escape(eid), CARVE_TAIL))
        carved = any(q["default"] is not None and q["default"] < int(c.group(1))
                     for c in (carve.match(b) for b in blocks) if c)
        if not carved:
            value = new_value
    return value


def reader_control(doc: str, question: str) -> str:
    q = parse_question(question)
    return answer_from(_blocks(doc), q) if q else ""


def reader_truncating(doc: str, question: str) -> str:
    q = parse_question(question)
    return answer_from(_visible(doc), q) if q else ""


def reader_base_only(doc: str, question: str) -> str:
    q = parse_question(question)
    return answer_from(_blocks(doc), q, use_exceptions=False) if q else ""


def reader_retrieval(doc: str, question: str) -> str:
    q = parse_question(question)
    if not q:
        return ""
    need = frozenset(TOKEN_RE.findall((q["prod"] + " " + q["attr"]).lower()))
    hits = tuple(b for b, toks in _token_sets(doc) if need <= toks)[:3]
    return answer_from(hits, q)


READER_FUNCS = {"control": reader_control, "truncating": reader_truncating,
                "base_only": reader_base_only, "retrieval": reader_retrieval}


def oracle_fails(reader: str, p: dict) -> bool:
    """Whether a reader should get a probe wrong, worked out from the planted offsets and the fault description alone."""
    if reader == "control":
        return False
    if reader == "base_only":
        return p["variant"] == "applies"
    if reader == "retrieval":
        return (p["form"] in ("crossref", "restated", "register") and p["variant"] == "applies") or p["variant"] == "carved_out"
    base_end = int(p["base_end"])
    exc_end = int(p["exception_end"]) if p["exception_end"] else 0
    carve_end = int(p["carve_end"]) if p["carve_end"] else 0
    if base_end > TRUNCATE_AT:
        return True
    if p["variant"] == "applies":
        return exc_end > TRUNCATE_AT
    if p["variant"] == "carved_out":
        return exc_end <= TRUNCATE_AT < carve_end
    return False


def load_manuals() -> dict:
    out = {}
    for row in _manual_rows():
        out[row["manual_id"]] = read_text(os.path.join(DATA, row["file"]), "manual")
    return out


def _manual_rows() -> list:
    with open(os.path.join(DATA, "manuals.csv"), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_sweep() -> list:
    return load_probes(os.path.join(DATA, "probes.csv"))


def run_reader(name: str, probes: list, manuals: dict) -> dict:
    fn = READER_FUNCS[name]
    return {p["probe_id"]: fn(manuals[p["manual_id"]], p["question"]) for p in probes}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
