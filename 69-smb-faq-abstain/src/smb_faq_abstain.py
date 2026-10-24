"""smb_faq_abstain: decide whether a drafted answer to a small-business FAQ question may be served, or
whether the customer should be handed to a banker. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 smb_faq_abstain.py --demo
    python3 smb_faq_abstain.py check --kb KB.csv --question TEXT --draft TEXT [--min-grounded 1.0]
    python3 smb_faq_abstain.py batch --kb KB.csv --pairs PAIRS.csv [--min-grounded 1.0]

Exit status. check: 0 when the draft may be served, 1 when it is held back, 2 for bad or malformed input.
batch: 0 when every row was decided, 2 for bad or malformed input.

There is no model in this file. The gate reads a question, a drafted answer and a small knowledge base
(columns fact_id, product, excluded_states, text) and applies plain rules in this order:
  handoff    the draft already hands the customer to a banker
  scope      the question asks for advice or a decision, which an FAQ source cannot ground
  source     no passage covers enough of the question
  ambiguity  the question fits passages from more than one product equally well
  grounding  every number, citation, yes or no, and named state in the draft must be supported by
             the best passage (or, for numbers, by the question itself)
A draft with nothing checkable in it is held back as unverifiable. The rules do not read units or
meaning: a number that is in the passage but answers a different question passes.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from typing import NamedTuple

SOURCE_MIN = 0.5        # assumption: share of the question's weighted words a passage must cover
AMBIG_MARGIN = 0.05     # assumption: passages this close to the best one count as equally good
ALL_GATES = frozenset({"scope", "source", "ambiguity", "grounding"})

STOP = frozenset(
    "a an the is are was were be to of in on for and or do does did can could will would should i my me you your we our "
    "it its this that with at by as from what when how much many there any have has get about business".split())
STATES = frozenset(
    "alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois "
    "indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri "
    "montana nebraska nevada new-hampshire new-jersey new-mexico new-york north-carolina north-dakota ohio oklahoma "
    "oregon pennsylvania rhode-island south-carolina south-dakota tennessee texas utah vermont virginia washington "
    "west-virginia wisconsin wyoming".split())
_STATE_WORDS = frozenset(w for s in STATES for w in s.split("-"))
_STATE_RE = re.compile(r"\b(" + "|".join(sorted((s.replace("-", " ") for s in STATES), key=len, reverse=True)) + r")\b")
YESNO_FIRST = frozenset("is are does do can will has have did could would".split())
NEGATIVE = frozenset("no not none never without cannot unavailable".split())
_SCOPE_RE = re.compile(r"\bshould i\b|\bapproved\b|\btax(?:es)?\b|\blegal(?:ly)?\b|\blawyer\b|\bqualify\b")
_HANDOFF_RE = re.compile(r"\blet me (?:connect|get)\b|\bi (?:don't|do not|can't|cannot)\b")
_CITE_RE = re.compile(r"\b(?:Act|Regulation|Section|CFR|Statute)\b|§")
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z]+")


class Fact(NamedTuple):
    fact_id: str
    product: str
    excluded: frozenset
    text: str
    tokens: frozenset
    numbers: frozenset
    negative: bool


# ---------------------------------------------------------------- text helpers
def norm_number(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def numbers_in(text: str) -> frozenset:
    return frozenset(norm_number(m) for m in _NUM_RE.findall(text))


def content_tokens(text: str) -> frozenset:
    """Lower-case words with a light plural strip. Stop words, one-letter words, numbers and state names are dropped."""
    out = set()
    for w in _WORD_RE.findall(text.lower()):
        if w in STOP or len(w) < 2 or w in _STATE_WORDS:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return frozenset(out)


def is_negative(text: str) -> bool:
    words = re.findall(r"[a-z']+", text.lower())
    return any(w in NEGATIVE or w.endswith("n't") for w in words)


def states_in(text: str) -> frozenset:
    return frozenset(m.replace(" ", "-") for m in _STATE_RE.findall(text.lower()))


def clean(text, limit: int = 300) -> str:
    """One printable line: control characters and line breaks are shown as escapes, so input cannot start a new log line."""
    out = []
    for ch in str(text):
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch.isprintable():
            out.append(ch)
        else:
            out.append("\\u{%x}" % ord(ch))
    s = "".join(out)
    return s if len(s) <= limit else s[:limit] + "..."


# ---------------------------------------------------------------- loading
def _read_csv(path: str, required: tuple, label: str) -> list:
    """Rows of a CSV as dicts. Raises ValueError with a one-line message for anything that is not a complete table."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, strict=True)
            if not reader.fieldnames:
                raise ValueError(f"{label}: the file is empty")
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise ValueError(f"{label}: missing column {missing[0]!r}")
            rows = []
            for i, row in enumerate(reader, start=2):
                if None in row or None in row.values():
                    raise ValueError(f"{label}: row {i} is truncated or has extra fields")
                rows.append(row)
    except csv.Error as e:
        raise ValueError(f"{label}: not a valid CSV table ({e})") from None
    except UnicodeDecodeError:
        raise ValueError(f"{label}: not UTF-8 text") from None
    if not rows:
        raise ValueError(f"{label}: the file has a header and no rows")
    return rows


def load_kb(path: str) -> list:
    rows = _read_csv(path, ("fact_id", "product", "excluded_states", "text"), "knowledge base")
    kb, seen = [], set()
    for i, r in enumerate(rows, start=2):
        for col in ("fact_id", "product", "text"):
            if not r[col].strip():
                raise ValueError(f"knowledge base: row {i} has an empty {col}")
        if r["fact_id"] in seen:
            raise ValueError(f"knowledge base: duplicate fact_id {r['fact_id']!r}")
        seen.add(r["fact_id"])
        excluded = frozenset(s.strip().lower().replace(" ", "-") for s in r["excluded_states"].split(";") if s.strip())
        bad = sorted(excluded - STATES)
        if bad:
            raise ValueError(f"knowledge base: row {i} lists {bad[0]!r}, which is not a state name")
        kb.append(Fact(r["fact_id"], r["product"], excluded, r["text"], content_tokens(r["product"] + " " + r["text"]),
                       numbers_in(r["text"]), is_negative(r["text"])))
    return kb


def load_pairs(path: str) -> list:
    rows = _read_csv(path, ("query_id", "question", "draft"), "pairs file")
    return [{"query_id": r["query_id"], "question": r["question"], "draft": r["draft"]} for r in rows]


# ---------------------------------------------------------------- retrieval
def retrieve(question: str, kb: list) -> list:
    """(coverage, fact) pairs, best first. Coverage is the share of the question's idf-weighted words found in the passage."""
    q = content_tokens(question)
    if not q or not kb:
        return []

    def weight(t):
        df = sum(1 for f in kb if t in f.tokens)
        return math.log(1 + len(kb) / (df if df else 0.5))

    w = {t: weight(t) for t in q}
    total = sum(w.values())
    scored = [(sum(w[t] for t in q if t in f.tokens) / total, f) for f in kb]
    scored.sort(key=lambda x: (-round(x[0], 9), x[1].fact_id))
    return scored


# ---------------------------------------------------------------- grounding
def check_claims(question: str, draft: str, fact) -> tuple:
    """Returns (supported, total, problems) for the checkable claims in a draft against one passage (or None)."""
    problems, total = [], 0
    for n in sorted(numbers_in(draft) - numbers_in(question)):
        total += 1
        if fact is None or n not in fact.numbers:
            problems.append(f"number {n} is not in the source")
    for c in sorted(set(_CITE_RE.findall(draft)) - set(_CITE_RE.findall(question))):
        total += 1
        if fact is None or c not in _CITE_RE.findall(fact.text):
            problems.append(f"citation {c!r} is not in the source")
    first = re.findall(r"[a-z]+", question.lower())[:1]
    if first and first[0] in YESNO_FIRST:
        total += 1
        if fact is None or is_negative(draft) != fact.negative:
            problems.append("yes or no disagrees with the source")
    if fact is not None:
        for s in sorted(states_in(question) & fact.excluded):
            total += 1
            if not is_negative(draft):
                problems.append(f"the source excludes {s.replace('-', ' ')} and the draft does not")
    return total - len(problems), total, problems


def evaluate(question: str, draft: str, kb: list, min_grounded: float = 1.0, gates=ALL_GATES) -> dict:
    """Decide one draft. `gates` names the checks that run; the handoff check always does."""
    def out(decision, reason, detail, fact=None, supported=0, total=0):
        return {"decision": decision, "reason": reason, "detail": detail, "fact_id": fact.fact_id if fact else "",
                "supported": supported, "total": total}

    if _HANDOFF_RE.search(draft.lower()):
        return out("ABSTAIN", "handoff", "the draft already hands the customer to a banker")
    if "scope" in gates:
        m = _SCOPE_RE.search(question.lower())
        if m:
            return out("ABSTAIN", "out_of_scope", f"the question asks for advice or a decision (cue: {m.group(0)!r})")
    ranked = retrieve(question, kb)
    top = ranked[0][1] if ranked and ranked[0][0] > 0 else None
    best = ranked[0][0] if ranked else 0.0
    if "source" in gates and (top is None or best < SOURCE_MIN):
        return out("ABSTAIN", "no_source", f"no passage covers the question (best coverage {best:.2f}, minimum {SOURCE_MIN:.2f})")
    if "ambiguity" in gates and top is not None:
        near = sorted({f.product for s, f in ranked if best - s < AMBIG_MARGIN})
        if len(near) > 1:
            return out("ABSTAIN", "ambiguous", "the question fits more than one product equally well: " + ", ".join(near), top)
    if "grounding" in gates:
        supported, total, problems = check_claims(question, draft, top)
        if total == 0:
            return out("ABSTAIN", "unverifiable", "the draft has no number, citation, yes or no, or state to check", top)
        if supported / total < min_grounded:
            where = f" (source {top.fact_id})" if top else " (no source passage)"
            return out("ABSTAIN", "ungrounded", "; ".join(problems) + where, top, supported, total)
        return out("SERVE", "grounded", f"{supported} of {total} claims supported by {top.fact_id}", top, supported, total)
    return out("SERVE", "not_checked", "no grounding check ran", top)


# ---------------------------------------------------------------- command line
def render(question: str, draft: str, result: dict) -> str:
    detail = clean(result["detail"])
    return (f"question: {clean(question)}\ndraft:    {clean(draft)}\n"
            f"decision: {result['decision']} ({result['reason']}) {detail}")


def run_check(kb_path, question, draft, min_grounded) -> int:
    try:
        if not question.strip() or not draft.strip():
            raise ValueError("the question and the draft must not be empty")
        kb = load_kb(kb_path)
    except (OSError, ValueError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    result = evaluate(question, draft, kb, min_grounded)
    print(render(question, draft, result))
    return 0 if result["decision"] == "SERVE" else 1


def run_batch(kb_path, pairs_path, min_grounded) -> int:
    try:
        kb = load_kb(kb_path)
        pairs = load_pairs(pairs_path)
    except (OSError, ValueError) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    served = 0
    for p in pairs:
        r = evaluate(p["question"], p["draft"], kb, min_grounded)
        served += r["decision"] == "SERVE"
        print(f"{clean(p['query_id'], 40)}  {r['decision']:<7} {r['reason']:<12} {clean(r['detail'])}")
    print(f"served {served} of {len(pairs)}, held back {len(pairs) - served}")
    return 0


def run_demo() -> int:
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    kb = load_kb(os.path.join(data, "kb.csv"))
    qid = "Q08"
    question = next(r for r in _read_csv(os.path.join(data, "queries.csv"), ("query_id", "question"), "queries") if r["query_id"] == qid)["question"]
    draft = next(r for r in _read_csv(os.path.join(data, "drafts.csv"), ("query_id", "draft"), "drafts") if r["query_id"] == qid)["draft"]
    print(render(question, draft, evaluate(question, draft, kb)))
    return 0


def _fraction(s: str) -> float:
    v = float(s)
    if not 0 < v <= 1:
        raise argparse.ArgumentTypeError("must be above 0 and at most 1")
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="smb_faq_abstain")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/kb.csv, one drafted answer)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="decide one drafted answer")
    c.add_argument("--kb", required=True)
    c.add_argument("--question", required=True)
    c.add_argument("--draft", required=True)
    c.add_argument("--min-grounded", type=_fraction, default=1.0)
    b = sub.add_parser("batch", help="decide every row of a CSV with columns query_id, question, draft")
    b.add_argument("--kb", required=True)
    b.add_argument("--pairs", required=True)
    b.add_argument("--min-grounded", type=_fraction, default=1.0)
    a = ap.parse_args(argv)
    if a.demo:
        return run_demo()
    if a.cmd == "check":
        return run_check(a.kb, a.question, a.draft, a.min_grounded)
    if a.cmd == "batch":
        return run_batch(a.kb, a.pairs, a.min_grounded)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
