"""PolicyNeedle harness: probe loader, four STUB readers, scorer, slicing and the CI-style gate.

Standard library only. Runs on Python 3.9.

READ THIS FIRST: nothing in this file is a model and nothing here calls one.
The four readers are small, deterministic functions (stubs). Each was written
to have one KNOWN fault, so the harness can be checked against faults we know
are there. They stand in for "an assistant that answers from a long manual".
Their output is not observed behavior of any real model.

The reader interface is one function:

    reader(document_text: str, question: str) -> answer_text

Replace a stub with a function of that shape that calls your own assistant,
and the same sweep, slicing and gate run on it.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PAGE_CHARS = 1800            # one synthetic "page" (about 300 words); a repo convention
TRUNCATE_AT = 60_000         # the truncating stub reads this many characters (about 33 pages)
MATCH_NUM, MATCH_DEN = 4, 5  # keyword stubs: a block is a match when it holds 4/5 of the question words

DEPTHS = [0, 25, 50, 75, 100]
LENGTHS = [40, 120, 240]
FORMS = ["plain", "superseded", "exception", "table", "two_section", "distractor"]
FORM_LABEL = {
    "plain": "plain clause",
    "superseded": "superseded clause",
    "exception": "exception in a footnote",
    "table": "table value",
    "two_section": "two-section fact",
    "distractor": "near-duplicate distractor",
}
DEFICIENCY = {
    "plain": ("a", "Position sensitivity"),
    "superseded": ("b", "Superseded clause answered from old version"),
    "exception": ("c", "Exception or negation clause missed"),
    "table": ("d", "Table value wrong"),
    "two_section": ("e", "Two-section synthesis fact missed"),
    "distractor": ("f", "Near-duplicate distractor answered"),
}

# Gate thresholds (CI-style). With 3 probes per cell, one miss flags the cell.
SLICE_FLOOR = 0.90    # a form x length x depth cell is flagged below this pass rate
GATE_OVERALL = 0.98   # overall pass rate must be at least this
GATE_FORM_LENGTH = 0.90   # every form x length slice must be at least this
GATE_DEPTH = 0.90         # every depth band (all forms, all lengths) must be at least this

STOPWORDS = frozenset(
    "what is the for on of a an when because at in to and or by with per how "
    "much many which are does do it its this that".split()
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
VALUE_RE = re.compile(r"\$\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?%|\d+ (?:business |calendar )?days?")
NEGATION_RE = re.compile(r"\b(?:not|no|never|waived|exempt)\b")
Q_VALUE = re.compile(r"^What is the (?P<attr>.+?) for (?P<product>.+?)(?: at Tier (?P<tier>\d))?\?$")
Q_YESNO = re.compile(
    r"^Is the (?P<attr>.+?) on (?P<product>.+?) charged when (?P<event>.+?) because of (?P<reason>\w+)\?$")


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_manuals() -> dict:
    out = {}
    with open(DATA_DIR / "manuals.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            with open(DATA_DIR / row["file"], encoding="utf-8", newline="") as mh:
                out[row["manual_id"]] = mh.read()
    return out


def load_manual_rows() -> list:
    with open(DATA_DIR / "manuals.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_probes() -> list:
    rows = []
    with open(DATA_DIR / "probes.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            for k in ("length_pages", "doc_chars", "depth_pct", "evidence_start", "evidence_end"):
                r[k] = int(r[k])
            r["position_pct"] = float(r["position_pct"])
            rows.append(r)
    return rows


def load_probe_types() -> list:
    with open(DATA_DIR / "probe_types.csv", newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# scoring: normalized exact match
# ---------------------------------------------------------------------------
def normalize(text: str) -> str:
    s = text.strip().lower()
    s = s.replace("$", "").replace(",", "")
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".;: ")
    s = re.sub(r"(\d+)\.00\b", r"\1", s)
    s = s.replace(" percent", "%")
    return s


def score(answer: str, expected: str) -> bool:
    """True when the normalized answer equals the normalized expected answer."""
    return normalize(answer) == normalize(expected)


# ---------------------------------------------------------------------------
# shared parsing helpers for the stubs
# ---------------------------------------------------------------------------
def question_words(question: str) -> frozenset:
    return frozenset(t for t in TOKEN_RE.findall(question.lower()) if t not in STOPWORDS)


@lru_cache(maxsize=16)
def _blocks(doc: str) -> tuple:
    return tuple((b, frozenset(TOKEN_RE.findall(b.lower()))) for b in doc.split("\n\n"))


@lru_cache(maxsize=16)
def _structure(doc: str) -> tuple:
    """(text, lowercase text, inside the amendment register) for every block."""
    items = []
    in_register = False
    for b in doc.split("\n\n"):
        if b.startswith("Appendix A."):
            in_register = True
        items.append((b, b.lower(), in_register))
    return tuple(items)


@lru_cache(maxsize=16)
def _visible(doc: str, limit: int) -> str:
    """The first `limit` characters; a block that the limit cuts in half is dropped."""
    out = []
    pos = 0
    for b in doc.split("\n\n"):
        end = pos + len(b)
        if end > limit:
            break
        out.append(b)
        pos = end + 2
    return "\n\n".join(out)


def candidate_blocks(doc: str, question: str) -> list:
    """Blocks that hold at least 4/5 of the question's content words, in document order."""
    qw = question_words(question)
    return [b for b, toks in _blocks(doc) if MATCH_DEN * len(qw & toks) >= MATCH_NUM * len(qw)]


def _is_yes_no(question: str) -> bool:
    return question.lower().startswith("is ")


def _naive_answer(block: str, question: str) -> str:
    """What the two keyword stubs do with the block they picked.

    Yes/no question: "no" if the block contains a negation word, else "yes".
    Value question: the first value token on the line that shares the most words with the question.
    """
    if _is_yes_no(question):
        return "no" if NEGATION_RE.search(block.lower()) else "yes"
    qw = frozenset(w for w in question_words(question) if not w.isdigit())  # numbers do not pick the line
    lines = [ln for ln in block.split("\n") if VALUE_RE.search(ln)]
    if not lines:
        return ""
    best = max(lines, key=lambda ln: len(qw & frozenset(TOKEN_RE.findall(ln.lower()))))
    return VALUE_RE.search(best).group(0)


def _has_phrase(low: str, phrase: str) -> bool:
    """True when `phrase` occurs in `low` as whole words ("alder checking" is not in "alder business checking")."""
    i = low.find(phrase)
    while i != -1:
        j = i + len(phrase)
        before_ok = i == 0 or not low[i - 1].isalnum()
        after_ok = j >= len(low) or not low[j].isalnum()
        if before_ok and after_ok:
            return True
        i = low.find(phrase, i + 1)
    return False


def _fmt_money(x: float) -> str:
    if abs(x - round(x)) < 1e-9:
        return "${:,}".format(int(round(x)))
    return "${:,.2f}".format(x)


# ---------------------------------------------------------------------------
# the four readers. All four are STUBS, not models.
# ---------------------------------------------------------------------------
def full_scan_control(document_text: str, question: str) -> str:
    """STUB (control). Scans every block and follows the rules a careful reader would.

    Amendments in Appendix A govern over the clause they replace. A footnote exception
    applies when its reason matches. A table value is read from the column the question
    names. A discount clause is combined with the standard fee it refers to. A clause for
    a sibling product is not the clause for this product. Written against the synthetic
    wording; it exists to show the probes are answerable and the harness stays quiet.
    """
    items = _structure(document_text)
    m = Q_YESNO.match(question)
    if m:
        attr, prod, reason = m.group("attr").lower(), m.group("product").lower(), m.group("reason").lower()
        has_main = has_exception = False
        for _text, low, _reg in items:
            if attr in low and _has_phrase(low, prod):
                if "not charged when" in low:
                    if reason in low:
                        has_exception = True
                elif "charged when" in low:
                    has_main = True
        if has_exception:
            return "no"
        return "yes" if has_main else ""
    m = Q_VALUE.match(question)
    if not m:
        return ""
    attr, prod, tier = m.group("attr").lower(), m.group("product").lower(), m.group("tier")
    if tier:
        for text, low, _reg in items:
            if low.startswith("table") and attr in low.split("\n", 1)[0]:
                lines = text.split("\n")
                header = [c.strip().lower() for c in lines[1].strip().strip("|").split("|")]
                want = "tier {}".format(tier)
                if want not in header:
                    continue
                col = header.index(want)
                for ln in lines[2:]:
                    cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                    if cells and cells[0].lower() == prod and col < len(cells):
                        return cells[col]
        return ""
    matches = [(t, low, reg) for t, low, reg in items if attr in low and _has_phrase(low, prod)]
    amended = [t for t, _low, reg in matches if reg]
    if amended:
        v = VALUE_RE.search(amended[-1])
        return v.group(0) if v else ""
    discount = [t for t, low, reg in matches if "off the standard" in low]
    if discount:
        pct = re.search(r"(\d+(?:\.\d+)?)%", discount[0])
        base = None
        for t, low, reg in items:
            if not reg and ("the standard " + attr + " is") in low:
                bm = re.search(r"\$(\d[\d,]*(?:\.\d+)?)", t)
                if bm:
                    base = float(bm.group(1).replace(",", ""))
                break
        if pct and base is not None:
            return _fmt_money(base * (100.0 - float(pct.group(1))) / 100.0)
        return ""
    plain = [t for t, _low, reg in matches if not reg]
    if plain:
        v = VALUE_RE.search(plain[0])
        return v.group(0) if v else ""
    return ""


def truncating_reader(document_text: str, question: str) -> str:
    """STUB. Reads only the first 60,000 characters, then answers as the control does.

    Known fault: anything past the limit is never seen. A fact deep in a long manual
    gets no answer; an amendment in Appendix A is never read, so the old version is
    returned. Its only fault is position.
    """
    return full_scan_control(_visible(document_text, TRUNCATE_AT), question)


def first_match_reader(document_text: str, question: str) -> str:
    """STUB. Returns the answer from the FIRST block that matches the question's keywords.

    Known fault: it never looks past the first match. It answers from the original
    clause when an amendment replaces it, from the main clause when a footnote carves
    out an exception, from the first value in a table row (the first column, whatever
    tier was asked), from a single clause when the fact needs two, and from whichever
    sibling-product clause comes first.
    """
    for block in candidate_blocks(document_text, question):
        return _naive_answer(block, question)
    return ""


def last_match_reader(document_text: str, question: str) -> str:
    """STUB. Returns the answer from the LAST block that matches the question's keywords.

    Known fault: it prefers the most recent match. That happens to be right for an
    amendment and for a footnote exception that applies, and wrong when the footnote
    does not cover the case, for the first value in a table row, for a single clause
    when the fact needs two, and for whichever sibling-product clause comes last.
    """
    cands = candidate_blocks(document_text, question)
    if cands:
        return _naive_answer(cands[-1], question)
    return ""


READERS = [
    {"key": "truncating", "label": "Truncating reader (stub)", "short": "truncating", "fn": truncating_reader,
     "fault": "Reads only the first {:,} characters.".format(TRUNCATE_AT),
     "fault_short": "reads only the first {:,} characters".format(TRUNCATE_AT)},
    {"key": "first_match", "label": "Keyword-window reader (stub)", "short": "first-match", "fn": first_match_reader,
     "fault": "Answers from the first matching window and never looks further.",
     "fault_short": "answers from the first matching window"},
    {"key": "last_match", "label": "Recency reader (stub)", "short": "last-match", "fn": last_match_reader,
     "fault": "Answers from the last matching window.",
     "fault_short": "answers from the last matching window"},
    {"key": "control", "label": "Full-scan control (stub)", "short": "control", "fn": full_scan_control,
     "fault": "None by design. Handles amendments, footnotes, tables, two clauses and siblings.",
     "fault_short": "none by design"},
]
READER_KEYS = [r["key"] for r in READERS]
READER_BY_KEY = {r["key"]: r for r in READERS}


# ---------------------------------------------------------------------------
# the known-fault oracle: written from the stub design, never from reader output
# ---------------------------------------------------------------------------
def designed_to_fail(reader_key: str, probe: dict) -> bool:
    """True when the stub was written to get this probe wrong.

    This is the 'known fault' the harness is validated against. It reads only the
    probe's static spec (form, expected answer, where the evidence sits).
    """
    form = probe["form"]
    if reader_key == "control":
        return False
    if reader_key == "truncating":
        return probe["evidence_end"] > TRUNCATE_AT
    if reader_key == "first_match":
        if form in ("superseded", "table", "two_section", "distractor"):
            return True
        if form == "exception":
            return probe["expected_answer"] == "no"
        return False
    if reader_key == "last_match":
        if form in ("table", "two_section", "distractor"):
            return True
        if form == "exception":
            return probe["expected_answer"] == "yes"
        return False
    raise KeyError(reader_key)


# ---------------------------------------------------------------------------
# running probes
# ---------------------------------------------------------------------------
def diagnose(passed: bool, answer: str, probe: dict) -> str:
    """Name the kind of wrong answer: the designed trap, no answer, or something else."""
    if passed:
        return "ok"
    if not answer.strip():
        return "no_answer"
    traps = {normalize(t) for t in probe["trap_answers"].split("|") if t}
    if normalize(answer) in traps:
        return probe["trap_label"]
    return "other_wrong"


def run_probe(reader_fn, probe: dict, manuals: dict) -> dict:
    answer = reader_fn(manuals[probe["manual_id"]], probe["question"])
    ok = score(answer, probe["expected_answer"])
    return {
        "probe_id": probe["probe_id"], "probe_set": probe["probe_set"], "form": probe["form"],
        "length": probe["length_pages"], "depth": probe["depth_pct"], "position_pct": probe["position_pct"],
        "answer": answer, "expected": probe["expected_answer"], "passed": ok,
        "diagnosis": diagnose(ok, answer, probe),
    }


def sweep(probes: list, manuals: dict, reader_keys=None) -> list:
    """Run every probe through every named reader. Returns one row per (reader, probe)."""
    rows = []
    for key in (reader_keys or READER_KEYS):
        fn = READER_BY_KEY[key]["fn"]
        for p in probes:
            row = run_probe(fn, p, manuals)
            row["reader"] = key
            row["designed_fail"] = designed_to_fail(key, p)
            rows.append(row)
    return rows


def long_probes(probes: list) -> list:
    return [p for p in probes if p["probe_set"] == "long_sweep"]


def short_probes(probes: list) -> list:
    return [p for p in probes if p["probe_set"] == "short_spot"]


# ---------------------------------------------------------------------------
# slicing, flags, localization, gate
# ---------------------------------------------------------------------------
def cell_counts(rows: list) -> dict:
    """{(reader, form, length, depth): [passed, n]}"""
    cells = defaultdict(lambda: [0, 0])
    for r in rows:
        c = cells[(r["reader"], r["form"], r["length"], r["depth"])]
        c[0] += 1 if r["passed"] else 0
        c[1] += 1
    return dict(cells)


def flagged_cells(cells: dict, reader_key: str, floor: float = SLICE_FLOOR) -> set:
    return {(f, l, d) for (rk, f, l, d), (p, n) in cells.items() if rk == reader_key and p / float(n) < floor}


def known_fault_cells(probes: list, reader_key: str) -> set:
    return {(p["form"], p["length_pages"], p["depth_pct"]) for p in probes if designed_to_fail(reader_key, p)}


def describe_depths(failing: list) -> str:
    """Plain-text summary of which depths fail: none, all, depth >= X, or a list."""
    failing = sorted(failing)
    if not failing:
        return "none"
    if failing == DEPTHS:
        return "all depths"
    if failing == [d for d in DEPTHS if d >= failing[0]]:
        return "depth {} and deeper".format(failing[0])
    return "depths " + ", ".join(str(d) for d in failing)


def localize(cells: dict, reader_key: str, form: str, length: int) -> str:
    failing = [d for d in DEPTHS
               if cells[(reader_key, form, length, d)][0] / float(cells[(reader_key, form, length, d)][1]) < SLICE_FLOOR]
    return describe_depths(failing)


def gate(rows: list) -> dict:
    """CI-style gate on one reader's rows (all lengths, or one length if the rows are filtered).

    PASS needs: overall pass rate >= 98%, every form x length slice >= 90%, every depth band >= 90%.
    """
    n = len(rows)
    overall = sum(1 for r in rows if r["passed"]) / float(n)
    by_slice = defaultdict(lambda: [0, 0])
    by_depth = defaultdict(lambda: [0, 0])
    for r in rows:
        s = by_slice[(r["form"], r["length"])]
        s[0] += 1 if r["passed"] else 0
        s[1] += 1
        d = by_depth[r["depth"]]
        d[0] += 1 if r["passed"] else 0
        d[1] += 1
    bad_slices = sorted(k for k, (p, c) in by_slice.items() if p / float(c) < GATE_FORM_LENGTH)
    bad_depths = sorted(k for k, (p, c) in by_depth.items() if p / float(c) < GATE_DEPTH)
    broken = []
    if overall < GATE_OVERALL:
        broken.append("overall pass rate {:.1f}% is below {:.0f}%".format(100 * overall, 100 * GATE_OVERALL))
    if bad_slices:
        broken.append("{} of {} form-by-length slices are below {:.0f}%".format(
            len(bad_slices), len(by_slice), 100 * GATE_FORM_LENGTH))
    if bad_depths:
        broken.append("{} of {} depth bands are below {:.0f}%".format(
            len(bad_depths), len(by_depth), 100 * GATE_DEPTH))
    return {"verdict": "FAIL" if broken else "PASS", "overall": overall, "broken": broken,
            "bad_slices": bad_slices, "bad_depths": bad_depths, "n": n}


def audit_probes(probes: list, manuals: dict) -> dict:
    """Probe-set audit: the keyword rule must find exactly the blocks each form is built around."""
    expected = {"plain": 1, "superseded": 2, "exception": 2, "table": 1, "two_section": 1, "distractor": 3}
    bad = []
    for p in probes:
        found = len(candidate_blocks(manuals[p["manual_id"]], p["question"]))
        if found != expected[p["form"]]:
            bad.append((p["probe_id"], found, expected[p["form"]]))
    return {"checked": len(probes), "ambiguous": bad}


def fault_signature(rows: list, reader_key: str, form: str) -> Counter:
    return Counter(r["diagnosis"] for r in rows if r["reader"] == reader_key and r["form"] == form and not r["passed"])
