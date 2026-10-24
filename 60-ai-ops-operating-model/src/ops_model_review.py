"""ops_model_review: check an AI program's claimed lifecycle stage against the evidence it filed.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 ops_model_review.py --demo
    python3 ops_model_review.py review --checklist C.csv --programs P.csv --evidence E.csv --as-of YYYY-MM-DD
                                       [--program ID] [--window 30|60|90] [--fail-on overclaim|never]
                                       [--format text|github]

Exit status: 0 when no claim is above its evidence (or --fail-on never), 1 when a claim is, 2 for bad input.

Inputs are three CSV files (columns in data/README.md):
    checklist  one row per evidence item: stage, minimum tier, cycle in days, whether someone other than
               the builder must have produced it, and the first-90-days window it falls in
    programs   one row per program: tier, builder, and the stage its owner claims
    evidence   one row per (program, item): artifact reference, who produced it, date

An owed item is OK when a row exists, its reference is not empty or a placeholder, it is not dated after
the review date, it is no older than 1.5 times the item's cycle, and (for items that need it) it was
produced by someone other than the program's builder. A program reaches stage k when every owed item in
stages up to k is OK. The decision compares that stage with the claim: CONFIRMED, OVERCLAIM or UNDERCLAIM.
The tool reads the register, not the artifacts, so a complete-looking row for an empty artifact passes.
There is no model in this file.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys

FRESH_FACTOR = 1.5
PLACEHOLDERS = frozenset(["", "tbd", "n/a", "na", "none", "todo", "-", "?"])
RULES = ("tier", "ref", "future", "fresh", "indep")
WINDOWS = (30, 60, 90)
CHECKLIST_COLUMNS = ["item_id", "stage", "stage_name", "item", "min_tier", "cycle_days", "independent",
                     "day_window"]
PROGRAM_COLUMNS = ["program_id", "program_name", "tier", "builder", "claimed_stage"]
EVIDENCE_COLUMNS = ["program_id", "item_id", "artifact_ref", "produced_by", "date"]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------- loading
def _rows(path: str, columns: list, label: str) -> list:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"{label}: the file is empty")
        absent = [c for c in columns if c not in reader.fieldnames]
        if absent:
            raise ValueError(f"{label}: missing column {', '.join(absent)}")
        rows = []
        for line, r in enumerate(reader, 2):
            if None in r or any(v is None for v in r.values()):
                raise ValueError(f"{label}: line {line} has the wrong number of fields")
            rows.append(r)
    return rows


def _int(value: str, label: str, line: int, field: str, low: int, high: int = 1_000_000) -> int:
    try:
        n = int(value.strip())
    except ValueError:
        raise ValueError(f"{label}: line {line}: {field} must be a whole number, got {value[:30]!r}") from None
    if not low <= n <= high:
        raise ValueError(f"{label}: line {line}: {field} must be between {low} and {high}")
    return n


def parse_date(value: str, label: str) -> datetime.date:
    if not DATE_RE.fullmatch(value.strip()):
        raise ValueError(f"{label}: date must look like 2026-09-30, got {value[:30]!r}")
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError(f"{label}: {value[:30]!r} is not a real date") from None


def load_checklist(path: str) -> list:
    out, seen = [], set()
    for line, r in enumerate(_rows(path, CHECKLIST_COLUMNS, path), 2):
        if not r["item_id"].strip() or r["item_id"] in seen:
            raise ValueError(f"{path}: line {line}: item_id is empty or repeated")
        if r["independent"].strip() not in ("yes", "no"):
            raise ValueError(f"{path}: line {line}: independent must be yes or no")
        seen.add(r["item_id"])
        out.append({"item_id": r["item_id"], "stage": _int(r["stage"], path, line, "stage", 1),
                    "stage_name": r["stage_name"], "item": r["item"], "min_tier": _int(r["min_tier"], path, line, "min_tier", 1),
                    "cycle_days": _int(r["cycle_days"], path, line, "cycle_days", 1),
                    "independent": r["independent"].strip() == "yes",
                    "day_window": _int(r["day_window"], path, line, "day_window", 0)})
    if not out:
        raise ValueError(f"{path}: the checklist has no items")
    return out


def load_programs(path: str, max_stage: int) -> list:
    out, seen = [], set()
    for line, r in enumerate(_rows(path, PROGRAM_COLUMNS, path), 2):
        if not r["program_id"].strip() or r["program_id"] in seen:
            raise ValueError(f"{path}: line {line}: program_id is empty or repeated")
        if not r["builder"].strip():
            raise ValueError(f"{path}: line {line}: builder is empty")
        claimed = _int(r["claimed_stage"], path, line, "claimed_stage", 0)
        if claimed > max_stage:
            raise ValueError(f"{path}: line {line}: claimed_stage {claimed} is above the last stage, {max_stage}")
        seen.add(r["program_id"])
        out.append({"program_id": r["program_id"], "program_name": r["program_name"], "builder": r["builder"].strip(),
                    "tier": _int(r["tier"], path, line, "tier", 1), "claimed_stage": claimed})
    if not out:
        raise ValueError(f"{path}: the file has no programs")
    return out


def load_evidence(path: str, programs: list, checklist: list) -> dict:
    """The register as {(program_id, item_id): row}. A row for an unknown program or item is an error, not a no-op."""
    known_p = {p["program_id"] for p in programs}
    known_i = {i["item_id"] for i in checklist}
    out = {}
    for line, r in enumerate(_rows(path, EVIDENCE_COLUMNS, path), 2):
        if r["program_id"] not in known_p:
            raise ValueError(f"{path}: line {line}: unknown program {r['program_id'][:30]!r}")
        if r["item_id"] not in known_i:
            raise ValueError(f"{path}: line {line}: unknown item {r['item_id'][:30]!r}")
        key = (r["program_id"], r["item_id"])
        if key in out:
            raise ValueError(f"{path}: line {line}: a second row for {r['program_id'][:30]} and {r['item_id'][:30]}")
        out[key] = {"artifact_ref": r["artifact_ref"], "produced_by": r["produced_by"].strip(),
                    "date": parse_date(r["date"], f"{path}: line {line}")}
    return out


# ---------------------------------------------------------------- the rules
def judge(item: dict, row, builder: str, as_of: datetime.date, rules=RULES) -> tuple:
    """(status, detail) for one owed item. `rules` names the checks that run; presence is always checked."""
    if row is None:
        return "MISSING", "no evidence row"
    if "ref" in rules and row["artifact_ref"].strip().lower() in PLACEHOLDERS:
        return "BLANK_REF", "the artifact reference is empty or a placeholder"
    if "future" in rules and row["date"] > as_of:
        return "FUTURE", f"dated {row['date']}, after the review date {as_of}"
    if "fresh" in rules:
        age = (as_of - row["date"]).days
        limit = FRESH_FACTOR * item["cycle_days"]
        if age > limit:
            return "STALE", f"{age} days old, limit {limit:g} days"
    if "indep" in rules and item["independent"] and (not row["produced_by"] or row["produced_by"] == builder):
        who = "no producer is named" if not row["produced_by"] else f"produced by the builder, {row['produced_by']}"
        return "NOT_INDEPENDENT", who
    return "OK", ""


def review_program(program: dict, checklist: list, register: dict, as_of: datetime.date, window=None,
                   rules=RULES) -> dict:
    """Judge every item the program's tier owes, find the stage the evidence reaches, compare it with the claim."""
    items, not_owed = [], 0
    for it in checklist:
        if "tier" in rules and program["tier"] < it["min_tier"]:
            not_owed += 1
            continue
        status, detail = judge(it, register.get((program["program_id"], it["item_id"])), program["builder"], as_of, rules)
        items.append({"item_id": it["item_id"], "item": it["item"], "stage": it["stage"], "stage_name": it["stage_name"],
                      "day_window": it["day_window"], "status": status, "detail": detail})
    reached = 0
    for s in sorted({it["stage"] for it in checklist}):
        if any(r["stage"] == s and r["status"] != "OK" for r in items):
            break
        reached = s
    claimed = program["claimed_stage"]
    decision = "OVERCLAIM" if claimed > reached else "CONFIRMED" if claimed == reached else "UNDERCLAIM"
    out = {"program_id": program["program_id"], "program_name": program["program_name"], "tier": program["tier"],
           "claimed": claimed, "reached": reached, "decision": decision, "items": items, "not_owed": not_owed,
           "gaps": [r for r in items if r["status"] != "OK" and r["stage"] <= claimed]}
    if window is not None:
        inside = [r for r in items if 0 < r["day_window"] <= window]
        out["window"] = {"days": window, "owed": len(inside), "ok": sum(1 for r in inside if r["status"] == "OK"),
                         "open": [r["item_id"] for r in inside if r["status"] != "OK"]}
    return out


# ---------------------------------------------------------------- output
def one_line(text) -> str:
    """Control characters become spaces, so a value from the files cannot start a line of its own in a log."""
    return "".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in str(text))


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so file text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def render_text(rv: dict, last_stage: int, register_rows: int) -> str:
    lines = [one_line(f"program: {rv['program_id']} ({rv['program_name']})   tier {rv['tier']}   claimed stage {rv['claimed']}")]
    for g in rv["gaps"]:
        lines.append(one_line(f"  stage {g['stage']} {g['stage_name']:<16} {g['item_id']} {g['item']}: {g['status']}"
                              + (f"  {g['detail']}" if g["detail"] else "")))
    if register_rows == 0:
        lines.append("  no evidence rows for this program, so every owed item is MISSING")
    w = rv.get("window")
    if w:
        lines.append(f"first {w['days']} days: {w['ok']} of {w['owed']} owed items evidenced"
                     + (f"; open: {', '.join(one_line(x) for x in w['open'])}" if w["open"] else ""))
    lines.append(f"evidence reaches stage {rv['reached']} of {last_stage}")
    lines.append(f"decision: {rv['decision']} (claimed {rv['claimed']})")
    return "\n".join(lines)


def render_github(rv: dict) -> str:
    lines = []
    for g in rv["gaps"]:
        lines.append("::warning title=ops-model-review::" + escape_annotation(
            f"{rv['program_id']} {g['item_id']} {g['item']}: {g['status']}" + (f" ({g['detail']})" if g["detail"] else "")))
    level = "error" if rv["decision"] == "OVERCLAIM" else "notice"
    lines.append(f"::{level} title=ops-model-review::" + escape_annotation(
        f"{rv['program_id']} ({rv['program_name']}): {rv['decision']}; claimed stage {rv['claimed']}, evidence reaches {rv['reached']}"))
    return "\n".join(lines)


def run_review(checklist_path, programs_path, evidence_path, as_of_text, program_id, window, fail_on, fmt) -> int:
    try:
        as_of = parse_date(as_of_text, "--as-of")
        checklist = load_checklist(checklist_path)
        last_stage = max(i["stage"] for i in checklist)
        programs = load_programs(programs_path, last_stage)
        register = load_evidence(evidence_path, programs, checklist)
        if program_id is not None:
            programs = [p for p in programs if p["program_id"] == program_id]
            if not programs:
                raise ValueError(f"no program {program_id[:30]!r} in {programs_path}")
    except (OSError, ValueError, csv.Error) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    reviews, blocks = [], []
    for p in programs:
        rv = review_program(p, checklist, register, as_of, window)
        reviews.append(rv)
        rows = sum(1 for (pid, _item) in register if pid == p["program_id"])
        blocks.append(render_github(rv) if fmt == "github" else render_text(rv, last_stage, rows))
    print("\n".join(blocks))
    if len(reviews) > 1 and fmt == "text":
        n = {d: sum(1 for r in reviews if r["decision"] == d) for d in ("CONFIRMED", "OVERCLAIM", "UNDERCLAIM")}
        print(f"programs: {len(reviews)}   confirmed {n['CONFIRMED']}   overclaim {n['OVERCLAIM']}   underclaim {n['UNDERCLAIM']}")
    over = any(r["decision"] == "OVERCLAIM" for r in reviews)
    return 1 if over and fail_on == "overclaim" else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ops_model_review")
    ap.add_argument("--demo", action="store_true", help="review the bundled example program (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("review", help="compare claimed stages with the evidence register")
    r.add_argument("--checklist", required=True)
    r.add_argument("--programs", required=True)
    r.add_argument("--evidence", required=True)
    r.add_argument("--as-of", required=True, help="review date, YYYY-MM-DD; the clock is never read")
    r.add_argument("--program", help="review one program id")
    r.add_argument("--window", type=int, choices=WINDOWS, help="also count items due in the first N days")
    r.add_argument("--fail-on", choices=["overclaim", "never"], default="overclaim")
    r.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        try:
            with open(os.path.join(d, "as_of.txt"), encoding="utf-8") as fh:
                as_of = fh.read().strip()
        except OSError as e:
            print(f"input error: {e}", file=sys.stderr)
            return 2
        return run_review(os.path.join(d, "checklist.csv"), os.path.join(d, "example_programs.csv"),
                          os.path.join(d, "example_evidence.csv"), as_of, None, 90, "never", "text")
    if a.cmd == "review":
        return run_review(a.checklist, a.programs, a.evidence, a.as_of, a.program, a.window, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
