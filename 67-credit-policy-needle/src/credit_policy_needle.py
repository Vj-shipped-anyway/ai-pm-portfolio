#!/usr/bin/env python3
"""credit_policy_needle: checks for an assistant that answers questions from a long credit policy manual.

Two commands, plus a demo on bundled sample data. Standard library only, Python 3.9 or newer.

  audit MANUAL        list the clauses that read as exceptions, and say which of them do not name the rule
                      they change (a search on the rule's own words will not return those)
  score PROBES ANSWERS  score an assistant's answers against exact expected answers, flag the form-by-depth
                      cells that fail, and print PASS or FAIL
  --demo              run both on the bundled example

PROBES is a CSV with the columns probe_id, form, length_pages, depth_pct, expected_answer. ANSWERS is a CSV
with probe_id and answer. Exit codes: 0 PASS, 1 FAIL (the tool found a problem), 2 the input could not be read.
Add --format github for workflow annotations, with every value from the files escaped.

This is a prototype. The audit reads cue words in English; it will miss an exception worded without one and
flag a pointer that is not an exception. Both are measured in step 4 of the project.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")

PAGE_CHARS = 1800
CELL_FLOOR = 0.90    # a form x length x depth cell is flagged below this pass rate
GATE_OVERALL = 0.98  # the whole run must pass at least this share
GATE_SLICE = 0.90    # each form x length slice, and each depth band, must pass at least this share

CUE_RE = re.compile(r"\bexcept\b|\bexception to clause\b|\bnotwithstanding\b|\bdoes not apply\b|\bregister entry\b", re.I)
PROHIBIT_RE = re.compile(r"\bno exception\b|\bnot permitted\b", re.I)
EVIDENCE_RE = re.compile(r"\bclause \d+\.\d+|\$\d|\d+%|\d+ (?:points|months)", re.I)
BLOCK_ID_RE = re.compile(r"^((?:R-)?\d+(?:\.\d+)?)\s")
CLAUSE_REF_RE = re.compile(r"\bclause (\d+\.\d+)(?!\d|\.\d)", re.I)
PROBE_COLUMNS = ("probe_id", "form", "length_pages", "depth_pct", "expected_answer")
ANSWER_COLUMNS = ("probe_id", "answer")


class InputError(Exception):
    """The input could not be read. The command line turns this into exit code 2."""


# ---------------------------------------------------------------------------
# output safety: values from the files are untrusted
# ---------------------------------------------------------------------------
def clean(value: object, limit: int = 80) -> str:
    """One printable line: control characters and line separators become spaces."""
    s = re.sub(r"[\x00-\x1f\x7f-\x9f  ]", " ", str(value))
    return s if len(s) <= limit else s[:limit - 3] + "..."


def gh_data(value: object) -> str:
    """Escape a workflow command message: % then carriage return then newline."""
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def gh_prop(value: object) -> str:
    return gh_data(value).replace(":", "%3A").replace(",", "%2C")


def annotation(level: str, title: str, message: object) -> str:
    return "::%s title=%s::%s" % (level, gh_prop(title), gh_data(str(message)[:300]))


# ---------------------------------------------------------------------------
# reading input
# ---------------------------------------------------------------------------
def read_text(path: str, what: str) -> str:
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            text = fh.read()
    except FileNotFoundError:
        raise InputError("%s not found: %s" % (what, clean(path)))
    except UnicodeDecodeError:
        raise InputError("%s is not UTF-8 text: %s" % (what, clean(path)))
    except OSError as e:
        raise InputError("cannot read %s: %s" % (what, clean(e.strerror or e)))
    if not text.strip():
        raise InputError("%s is empty: %s" % (what, clean(path)))
    return text


def read_rows(path: str, required: tuple, what: str) -> list:
    text = read_text(path, what)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = reader.fieldnames or []
        missing = [c for c in required if c not in header]
        if missing:
            raise InputError("%s is missing column(s): %s" % (what, ", ".join(missing)))
        rows = []
        for n, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise InputError("%s: line %d does not have the same number of fields as the header" % (what, n))
            rows.append({k: v.strip() for k, v in row.items()})
    except csv.Error as e:
        raise InputError("%s is not a readable CSV: %s" % (what, clean(e)))
    if not rows:
        raise InputError("%s has a header and no rows" % what)
    return rows


def load_probes(path: str) -> list:
    rows = read_rows(path, PROBE_COLUMNS, "probes file")
    seen = set()
    for n, r in enumerate(rows, 2):
        for col in ("depth_pct", "length_pages"):
            try:
                r[col] = int(r[col])
            except ValueError:
                raise InputError("probes file: line %d, %s is not a whole number: %s" % (n, col, clean(r[col], 30)))
        if not r["probe_id"] or not r["expected_answer"] or not r["form"]:
            raise InputError("probes file: line %d has an empty probe_id, form or expected_answer" % n)
        if r["probe_id"] in seen:
            raise InputError("probes file: probe_id repeated: %s" % clean(r["probe_id"], 40))
        seen.add(r["probe_id"])
    return rows


def load_answers(path: str) -> dict:
    out = {}
    for r in read_rows(path, ANSWER_COLUMNS, "answers file"):
        if r["probe_id"] in out:
            raise InputError("answers file: probe_id repeated: %s" % clean(r["probe_id"], 40))
        out[r["probe_id"]] = r["answer"]
    return out


# ---------------------------------------------------------------------------
# audit: which clauses read as exceptions
# ---------------------------------------------------------------------------
def capitalized_names(text: str) -> set:
    """Capitalized words of a clause after its number, leaving out the clause's first word."""
    rest = BLOCK_ID_RE.sub("", text, count=1)
    words = re.findall(r"\b[A-Z][a-z]+\b", rest)
    return set(words[1:] if rest[:1].isupper() and words else words)


def audit_text(text: str) -> dict:
    """Flag numbered clauses and register entries that carry an exception cue and a limit or a clause reference.

    A clause that says no exception is allowed is not flagged. An exception worded as a restated limit, with no
    cue word, is not flagged either; that is the known miss.
    """
    if not text.strip():
        raise InputError("manual is empty")
    blocks, pos = [], 0
    for raw in text.split("\n\n"):
        if raw.strip():
            blocks.append((pos, raw.strip()))
        pos += len(raw) + 2
    by_id = {}
    for start, b in blocks:
        m = BLOCK_ID_RE.match(b)
        if m and m.group(1) not in by_id:
            by_id[m.group(1)] = (start, b, capitalized_names(b))
    flagged = []
    for start, b in blocks:
        m = BLOCK_ID_RE.match(b)
        if not m or not CUE_RE.search(b) or not EVIDENCE_RE.search(b) or PROHIBIT_RE.search(b):
            continue
        bid = m.group(1)
        refs = [r for r in CLAUSE_REF_RE.findall(b) if r != bid]
        row = {"id": bid, "cites": "", "relation": "inside", "distance": 0, "excerpt": b[m.end():]}
        if refs:
            row["cites"] = refs[0]
            if refs[0] not in by_id:
                row["relation"] = "missing"
            else:
                ref_start, _ref_text, names = by_id[refs[0]]
                tokens = set(re.findall(r"[A-Za-z]+", b))
                row["relation"] = "named" if names and names <= tokens else "unnamed"
                row["distance"] = abs(start - ref_start)
        flagged.append(row)
    clauses = sum(1 for _s, b in blocks if re.match(r"\d+\.\d+\s", b))
    return {"blocks": len(blocks), "clauses": clauses, "flagged": flagged}


def render_audit(name: str, res: dict, fmt: str = "text", show: int = 8) -> list:
    flagged = res["flagged"]
    count = defaultdict(int)
    for f in flagged:
        count[f["relation"]] += 1
    risky = [f for f in flagged if f["relation"] in ("unnamed", "missing")]
    if fmt == "github":
        lines = [annotation("warning", "exception not named",
                            "%s cites clause %s, %.1f pages away, and does not name its rule: %s" % (
                                f["id"], f["cites"], f["distance"] / PAGE_CHARS, f["excerpt"][:100])) for f in risky[:10]]
        lines.append(annotation("notice", "audit", "%d exception clauses flagged in %d clauses, %d do not name their rule" % (
            len(flagged), res["clauses"], len(risky))))
        return lines
    lines = ["manual: %s   blocks: %d   clauses: %d" % (clean(name), res["blocks"], res["clauses"]),
             "exception clauses flagged: %d" % len(flagged)]
    if not flagged:
        lines.append("  none found. Either the manual has no exceptions, or they are worded without a cue word "
                     "(for example a restated limit). Do not read this as a clean bill.")
        return lines
    lines += ["  inside the rule clause: %d" % count["inside"],
              "  cite a clause and name its rule: %d" % count["named"],
              "  cite a clause and do not name its rule: %d" % count["unnamed"],
              "  cite a clause that is not in the manual: %d" % count["missing"]]
    if risky:
        lines.append("not named, so a search on the rule's own words will not return them:")
        for f in risky[:show]:
            lines.append("  %s cites %s, %.1f pages away: %s" % (clean(f["id"], 20), clean(f["cites"], 20),
                                                               f["distance"] / PAGE_CHARS, clean(f["excerpt"], 70)))
        if len(risky) > show:
            lines.append("  ... and %d more" % (len(risky) - show))
    return lines


# ---------------------------------------------------------------------------
# score: exact match, cells, gate
# ---------------------------------------------------------------------------
def normalize(text: str) -> str:
    s = text.strip().lower().replace("$", "").replace(",", "")
    s = re.sub(r"\s+", " ", s).rstrip(".;: ")
    return s.replace(" percent", "%")


def score_probes(probes: list, answers: dict) -> dict:
    ids = {p["probe_id"] for p in probes}
    answered = sum(1 for i in ids if i in answers)
    if answered == 0:
        raise InputError("none of the %d probe ids appears in the answers file; check that it is the right file" % len(ids))
    cells, by_form, by_depth, by_slice = (defaultdict(lambda: [0, 0]) for _ in range(4))
    passed = 0
    for p in probes:
        ok = p["probe_id"] in answers and normalize(answers[p["probe_id"]]) == normalize(p["expected_answer"])
        passed += ok
        for table, key in ((cells, (p["form"], p["length_pages"], p["depth_pct"])), (by_form, p["form"]),
                           (by_depth, p["depth_pct"]), (by_slice, (p["form"], p["length_pages"]))):
            table[key][0] += ok
            table[key][1] += 1
    flagged = sorted(k for k, (a, b) in cells.items() if a / b < CELL_FLOOR)
    return {"total": len(probes), "answered": answered, "unknown_answers": len([a for a in answers if a not in ids]),
            "passed": passed, "cells": dict(cells), "by_form": dict(by_form), "by_depth": dict(by_depth),
            "by_slice": dict(by_slice), "flagged": flagged}


def gate(res: dict) -> tuple:
    """('PASS' or 'FAIL', reasons)."""
    reasons = []
    overall = res["passed"] / res["total"]
    if overall < GATE_OVERALL:
        reasons.append("overall pass %.1f%% is below %.1f%%" % (100 * overall, 100 * GATE_OVERALL))
    for (form, length), (a, b) in sorted(res["by_slice"].items()):
        if a / b < GATE_SLICE:
            reasons.append("form %s at %d pages passes %d of %d" % (clean(form, 30), length, a, b))
    for depth, (a, b) in sorted(res["by_depth"].items()):
        if a / b < GATE_SLICE:
            reasons.append("depth %d%% passes %d of %d" % (depth, a, b))
    return ("FAIL" if reasons else "PASS"), reasons


def render_score(res: dict, decision: str, reasons: list, fmt: str = "text", brief: bool = False, show: int = 10) -> list:
    flagged = res["flagged"]
    if fmt == "github":
        lines = [annotation("error", "cell flagged", "%s at %d pages, depth %d%%: %d of %d pass" % (
            f[0], f[1], f[2], res["cells"][f][0], res["cells"][f][1])) for f in flagged[:show]]
        lines.append(annotation("notice", "gate", "%s: %d of %d probes pass, %d of %d cells flagged" % (
            decision, res["passed"], res["total"], len(flagged), len(res["cells"]))))
        return lines
    lines = []
    if not brief:
        lines.append("probes: %d   answered: %d   not answered: %d   answers for unknown probes: %d" % (
            res["total"], res["answered"], res["total"] - res["answered"], res["unknown_answers"]))
    lines.append("pass: %d of %d probes (%.1f%%), %d of %d cells below %d%%" % (
        res["passed"], res["total"], 100 * res["passed"] / res["total"], len(flagged), len(res["cells"]), round(100 * CELL_FLOOR)))
    if not brief:
        lines.append("by form: " + ", ".join("%s %d of %d" % (clean(k, 30), a, b) for k, (a, b) in sorted(res["by_form"].items())))
        lines.append("by depth: " + ", ".join("%d%% %d of %d" % (k, a, b) for k, (a, b) in sorted(res["by_depth"].items())))
    for f in flagged[:show]:
        a, b = res["cells"][f]
        lines.append("  %s %d pages depth %d%%: %d of %d" % (clean(f[0], 30), f[1], f[2], a, b))
    if len(flagged) > show:
        lines.append("  ... and %d more flagged cells" % (len(flagged) - show))
    lines.append("gate: %s" % decision + ("" if not reasons else " (%s%s)" % (
        reasons[0], "" if len(reasons) == 1 else "; %d more" % (len(reasons) - 1))))
    return lines


# ---------------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------------
class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message)


def build_parser() -> Parser:
    p = Parser(prog="credit_policy_needle.py", description="Exception-clause checks for a credit policy assistant.")
    p.add_argument("--demo", action="store_true", help="run on the bundled example")
    sub = p.add_subparsers(dest="cmd")
    a = sub.add_parser("audit", help="list clauses that read as exceptions")
    a.add_argument("manual")
    a.add_argument("--format", choices=("text", "github"), default="text")
    s = sub.add_parser("score", help="score answers against expected answers")
    s.add_argument("probes")
    s.add_argument("answers")
    s.add_argument("--format", choices=("text", "github"), default="text")
    s.add_argument("--fail-on", choices=("fail", "never"), default="fail")
    return p


def run_demo() -> int:
    manual = os.path.join(DATA, "example_manual.txt")
    res = audit_text(read_text(manual, "example manual"))
    risky = sum(1 for f in res["flagged"] if f["relation"] in ("unnamed", "missing"))
    print("audit  example_manual.txt: %d exception clauses flagged among %d clauses; %d cite a clause without naming its rule" % (
        len(res["flagged"]), res["clauses"], risky))
    probes = load_probes(os.path.join(DATA, "example_probes.csv"))
    answers = load_answers(os.path.join(DATA, "example_answers.csv"))
    sc = score_probes(probes, answers)
    decision, reasons = gate(sc)
    print("score  example_answers.csv: %d of %d probes pass" % (sc["passed"], sc["total"]))
    for line in render_score(sc, decision, reasons, brief=True)[1:]:
        print(line)
    return 0


def main(argv: list) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.demo:
            return run_demo()
        if args.cmd == "audit":
            res = audit_text(read_text(args.manual, "manual"))
            print("\n".join(render_audit(os.path.basename(args.manual), res, args.format)))
            return 0
        if args.cmd == "score":
            res = score_probes(load_probes(args.probes), load_answers(args.answers))
            decision, reasons = gate(res)
            print("\n".join(render_score(res, decision, reasons, args.format)))
            return 1 if decision == "FAIL" and args.fail_on == "fail" else 0
        raise InputError("give a command (audit or score) or --demo")
    except InputError as e:
        print("credit_policy_needle: %s" % clean(e, 300), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
