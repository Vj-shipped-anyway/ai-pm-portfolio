"""aigf_checks: check a crosswalk from framework risks to runnable checks. Standard library only.
Python 3.9 or newer.

A crosswalk row says: this check covers that risk, and the line "label: value" in the check's printed
output shows it. This tool reads the row, the risk catalogue, the check registry and the captured
output of each check, and reports what no longer holds. It does not run any check and it does not
read any check's code.

Command line (from src/):
    python3 aigf_checks.py --demo
    python3 aigf_checks.py check RISKS.csv CHECKS.csv CROSSWALK.csv OUTPUTS.json [--fail-on any|never] [--format text|github]
    python3 aigf_checks.py signoff COMMIT_MESSAGE.txt

Exit status: 0 when nothing is found, 1 when a row has a finding (or a commit message has a problem),
2 for input that cannot be read or is malformed.

Files (columns):
    RISKS.csv      risk_id, title, aspects          aspects: what a check must exercise, separated by ;
    CHECKS.csv     check_id, project, command, exercises
    CROSSWALK.csv  row_id, risk_id, check_id, covers (full or partial), claim_label, claim_value, note
    OUTPUTS.json   {check_id: the text the check printed}

Findings: unknown_risk, unknown_check, duplicate_row, no_output, label_missing, stale_value,
aspect_gap, overclaim_wording. Each risk then gets a status: CHECKED (a row whose claim holds and
whose check exercises every aspect), PARTIAL (a row whose claim holds and whose check exercises some),
UNVERIFIED (rows exist and none holds) or GAP (no row).

What it cannot see: the aspects a check declares are taken as written. A check that declares an
aspect it does not exercise passes. The wording rule knows a short list of words.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

OVERCLAIM = re.compile(r"(?<!non-)\bcompliant\b|\bcertified\b|\bcertification\b|\bguarantee[sd]?\b", re.I)
SIGNOFF = re.compile(r"^Signed-off-by: \S.* <[^<>@\s]+@[^<>@\s]+\.[^<>@\s]+>$")
ERROR_KINDS = ("unknown_risk", "unknown_check", "no_output", "label_missing", "stale_value", "aspect_gap")
STATUSES = ("CHECKED", "PARTIAL", "UNVERIFIED", "GAP")


class InputError(ValueError):
    """Input that cannot be read or is malformed. The command line turns it into exit status 2."""


# ---------------------------------------------------------------- reading the printed lines
def norm_label(text: str) -> str:
    return " ".join(text.lower().split())


def norm_value(text: str) -> str:
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return " ".join(text.lower().split()).rstrip(".")


def printed_lines(text: str) -> list:
    """(normalized label, value as printed) for each 'label: value' line of a check's output."""
    out = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        if label.strip() and value.strip():
            out.append((norm_label(label), value.strip()))
    return out


# ---------------------------------------------------------------- the analysis
def split_list(text: str) -> frozenset:
    return frozenset(p.strip() for p in text.split(";") if p.strip())


def _finding(row_id: str, kind: str, detail: str) -> dict:
    return {"row_id": row_id, "kind": kind, "detail": detail}


def analyze(risks: dict, checks: dict, rows: list, outputs: dict) -> dict:
    """Findings per row and a status per risk. risks and checks are {id: record}; rows is a list of dicts."""
    findings, state = [], {}
    first_row, compared = {}, 0
    for row in rows:
        rid, risk, check = row["row_id"], risks.get(row["risk_id"]), checks.get(row["check_id"])
        label = norm_label(row["claim_label"])
        found = []
        if risk is None:
            found.append(("unknown_risk", f"risk {row['risk_id']!r} is not in the risks file"))
        if check is None:
            found.append(("unknown_check", f"check {row['check_id']!r} is not in the checks file"))
        key = (row["risk_id"], row["check_id"], label)
        if key in first_row:
            found.append(("duplicate_row", f"same risk, check and claim label as {first_row[key]}"))
        else:
            first_row[key] = rid
        proof = False
        if check is not None:
            text = outputs.get(row["check_id"])
            if text is None:
                found.append(("no_output", f"no captured output for {row['check_id']}, so the claim was not compared"))
            else:
                match = next((v for lab, v in printed_lines(text) if lab == label), None)
                if match is None:
                    found.append(("label_missing", f"{row['check_id']} prints no line labelled {row['claim_label']!r}"))
                else:
                    compared += 1
                    if norm_value(match) != norm_value(row["claim_value"]):
                        found.append(("stale_value", f"{row['claim_label']!r} claimed {row['claim_value']}, the check prints {match}"))
                    else:
                        proof = True
        coverage = None
        if risk is not None and check is not None:
            missing = sorted(risk["aspects"] - check["exercises"])
            shared = risk["aspects"] & check["exercises"]
            if row["covers"] == "full" and not missing:
                coverage = "full"
            else:
                coverage = "partial" if shared else "none"
            if row["covers"] == "full" and missing:
                found.append(("aspect_gap", f"marked full but {row['check_id']} does not exercise {', '.join(missing)}"))
            elif row["covers"] == "partial" and not shared:
                found.append(("aspect_gap", f"marked partial but {row['check_id']} shares no aspect with {row['risk_id']}"))
        word = OVERCLAIM.search(row["note"])
        if word:
            found.append(("overclaim_wording", f"the note says {word.group()!r}; say 'aligned to' instead"))
        findings.extend(_finding(rid, k, d) for k, d in found)
        state[rid] = {"proof": proof, "coverage": coverage}
    status = {}
    for risk_id in risks:
        mine = [state[r["row_id"]] for r in rows if r["risk_id"] == risk_id]
        if not mine:
            status[risk_id] = "GAP"
        elif any(s["proof"] and s["coverage"] == "full" for s in mine):
            status[risk_id] = "CHECKED"
        elif any(s["proof"] and s["coverage"] == "partial" for s in mine):
            status[risk_id] = "PARTIAL"
        else:
            status[risk_id] = "UNVERIFIED"
    return {"findings": findings, "risk_status": status, "compared": compared}


# ---------------------------------------------------------------- loading
def read_rows(path: str, required: tuple, label: str, optional: tuple = ()) -> list:
    """(line number, {column: stripped text}) for each CSV row. Raises InputError on a missing column or field."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{label}: {path} is empty")
            absent = [c for c in required if c not in reader.fieldnames]
            if absent:
                raise InputError(f"{label}: {path} has no column {', '.join(absent)}")
            raw = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{label}: cannot read {path}: {e}") from None
    out = []
    for n, r in enumerate(raw, 2):
        rec = {}
        for col in required:
            if r.get(col) is None:
                raise InputError(f"{label} line {n}: missing field {col!r}, the file may be truncated")
            rec[col] = r[col].strip()
        for col in optional:
            rec[col] = (r.get(col) or "").strip()
        out.append((n, rec))
    return out


def load_risks(path: str) -> dict:
    out = {}
    for n, r in read_rows(path, ("risk_id", "title", "aspects"), "risks"):
        aspects = split_list(r["aspects"])
        if not r["risk_id"]:
            raise InputError(f"risks line {n}: empty risk_id")
        if r["risk_id"] in out:
            raise InputError(f"risks line {n}: duplicate risk_id {r['risk_id']!r}")
        if not aspects:
            raise InputError(f"risks line {n}: risk {r['risk_id']!r} lists no aspects")
        out[r["risk_id"]] = {"risk_id": r["risk_id"], "title": r["title"], "aspects": aspects}
    if not out:
        raise InputError("risks: the file has no rows")
    return out


def load_checks(path: str) -> dict:
    out = {}
    for n, r in read_rows(path, ("check_id", "project", "command", "exercises"), "checks"):
        if not r["check_id"]:
            raise InputError(f"checks line {n}: empty check_id")
        if r["check_id"] in out:
            raise InputError(f"checks line {n}: duplicate check_id {r['check_id']!r}")
        out[r["check_id"]] = {"check_id": r["check_id"], "project": r["project"], "command": r["command"],
                              "exercises": split_list(r["exercises"])}
    if not out:
        raise InputError("checks: the file has no rows")
    return out


def load_crosswalk(path: str) -> list:
    rows, seen = [], set()
    cols = ("row_id", "risk_id", "check_id", "covers", "claim_label", "claim_value")
    for n, r in read_rows(path, cols, "crosswalk", optional=("note",)):
        if not r["row_id"]:
            raise InputError(f"crosswalk line {n}: empty row_id")
        if r["row_id"] in seen:
            raise InputError(f"crosswalk line {n}: duplicate row_id {r['row_id']!r}")
        if r["covers"] not in ("full", "partial"):
            raise InputError(f"crosswalk line {n}: covers must be full or partial, got {r['covers']!r}")
        if not r["claim_label"] or not r["claim_value"]:
            raise InputError(f"crosswalk line {n}: claim_label and claim_value must not be empty")
        seen.add(r["row_id"])
        rows.append(r)
    if not rows:
        raise InputError("crosswalk: the file has no rows, so there is nothing to check")
    return rows


def load_outputs(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        raise InputError(f"outputs: cannot read {path}: {e}") from None
    if not isinstance(data, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in data.items()):
        raise InputError("outputs: expected a JSON object of check_id to the text the check printed")
    return data


# ---------------------------------------------------------------- output
def one_line(text, limit: int = 110) -> str:
    """Printable text on one line, so a value read from a file cannot start a new output line."""
    s = "".join(ch if ch.isprintable() else " " for ch in str(text))
    return s if len(s) <= limit else s[:limit - 3] + "..."


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so file text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render(risks: dict, checks: dict, rows: list, result: dict, fmt: str) -> str:
    by_id = {r["row_id"]: r for r in rows}
    findings, n_rows = result["findings"], len({f["row_id"] for f in result["findings"]})
    lines = []
    if fmt == "github":
        for f in findings:
            row = by_id[f["row_id"]]
            level = "error" if f["kind"] in ERROR_KINDS else "warning"
            lines.append(f"::{level} title=aigf-checks {f['kind']}::"
                         + escape_annotation(f"{row['row_id']} {row['risk_id']} -> {row['check_id']}: {f['detail']}"))
        lines.append(f"::notice title=aigf-checks::{len(findings)} findings in {n_rows} of {len(rows)} rows; "
                     f"claims compared: {result['compared']}")
        return "\n".join(lines)
    lines.append(f"crosswalk: {len(rows)} rows, {len(risks)} risks, {len(checks)} checks; claims compared: {result['compared']}")
    if rows and not result["compared"]:
        lines.append("  no row's claim could be compared with a printed line, so no number was verified")
    for f in findings:
        row = by_id[f["row_id"]]
        lines.append(f"  {one_line(row['row_id'], 24)}  {one_line(row['risk_id'], 12)} -> {one_line(row['check_id'], 12)}  "
                     f"{f['kind']:<17} {one_line(f['detail'])}")
    if not findings:
        lines.append("  no findings")
    lines.append("risk status: " + ", ".join(f"{one_line(r, 20)} {s}" for r, s in result["risk_status"].items()))
    lines.append(f"result: {len(findings)} findings in {n_rows} of {len(rows)} rows")
    return "\n".join(lines)


def run_check(paths: tuple, fail_on: str, fmt: str) -> int:
    try:
        risks, checks = load_risks(paths[0]), load_checks(paths[1])
        rows, outputs = load_crosswalk(paths[2]), load_outputs(paths[3])
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    result = analyze(risks, checks, rows, outputs)
    print(render(risks, checks, rows, result, fmt))
    return 1 if result["findings"] and fail_on == "any" else 0


# ---------------------------------------------------------------- commit message sign-off
def commit_problems(text: str) -> list:
    """Problems with a commit message against the contribution rules: a sign-off line and a short subject."""
    lines = text.splitlines()
    problems = []
    if not lines or not lines[0].strip():
        problems.append("the subject line is empty")
    elif len(lines[0]) > 72:
        problems.append(f"the subject line is {len(lines[0])} characters; the limit is 72")
    trailers = [(n, ln) for n, ln in enumerate(lines, 1) if ln.startswith("Signed-off-by:")]
    if not trailers:
        problems.append("no Signed-off-by line; add one with git commit -s")
    problems.extend(f"line {n}: the sign-off is not in the form 'Signed-off-by: Name <email>'"
                    for n, ln in trailers if not SIGNOFF.match(ln))
    return problems


def run_signoff(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"input error: cannot read {path}: {e}", file=sys.stderr)
        return 2
    if not text.strip():
        print(f"input error: {path} is empty", file=sys.stderr)
        return 2
    problems = commit_problems(text)
    print("\n".join(f"  {p}" for p in problems) if problems else "commit message: sign-off and subject line ok")
    return 1 if problems else 0


# ---------------------------------------------------------------- command line
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aigf_checks")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check a crosswalk against the risks, the checks and their printed output")
    for name in ("risks", "checks", "crosswalk", "outputs"):
        c.add_argument(name)
    c.add_argument("--fail-on", choices=["any", "never"], default="any")
    c.add_argument("--format", choices=["text", "github"], default="text")
    s = sub.add_parser("signoff", help="check a commit message for a Signed-off-by line and a short subject")
    s.add_argument("message")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        names = ("example_risks.csv", "example_checks.csv", "example_crosswalk.csv", "example_outputs.json")
        return run_check(tuple(os.path.join(d, n) for n in names), "never", "text")
    if a.cmd == "check":
        return run_check((a.risks, a.checks, a.crosswalk, a.outputs), a.fail_on, a.format)
    if a.cmd == "signoff":
        return run_signoff(a.message)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
