"""feature_contract: check a delivery of model-input data against a contract before the model scores it.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 feature_contract.py --demo
    python3 feature_contract.py check CONTRACT.json BATCH.csv [--fail-on fail|warn|never] [--format text|github]

BATCH is a .csv file (an empty cell is a null) or a .jsonl file (one JSON object per row, typed).
Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or
malformed input. A decision is FAIL (a field broke its contract), WARN (a column the contract does
not list) or PASS. There is no model in this file: the checks are plain rules.

Contract (JSON):
    {"contract": "name", "version": "1.0.0",
     "unexpected_columns": "allow" | "warn" | "fail",      default "warn"
     "max_bad_rate": 0.02,                                  default 0; share of rows allowed to break
                                                            a type, range or allowed-values rule
     "fields": [{"name": "dti_ratio", "type": "number", "min": 0, "max": 1.5, "unit": "ratio",
                 "max_null_rate": 0.0}, ...]}
Field keys: name, type (string, integer, number, boolean), min and max (inclusive, integer and
number only), allowed (string only), max_null_rate (default 0), unit and description (for the reader).
Unknown keys are rejected, so a typo cannot turn a check into a silent no-op.

Types: integer accepts "12" and "12.0" but not "12.5" or "1e3"; number accepts a plain decimal or an
exponent and rejects nan, inf, thousands separators and padding; boolean is true or false in any case.
Not supported: patterns, formats, cross-field rules, distributions.
"""
from __future__ import annotations

import io
import argparse
import csv
import json
import math
import os
import re
import sys

DECISION_RANK = {"PASS": 0, "WARN": 1, "FAIL": 2}
TYPES = ("string", "integer", "number", "boolean")
POLICIES = ("allow", "warn", "fail")
CONTRACT_KEYS = {"contract", "version", "unexpected_columns", "max_bad_rate", "fields"}
FIELD_KEYS = {"name", "type", "min", "max", "allowed", "max_null_rate", "unit", "description"}
_INT_RE = re.compile(r"-?[0-9]{1,30}(?:\.0{1,10})?")
_NUM_RE = re.compile(r"-?[0-9]{1,30}(?:\.[0-9]{1,30})?(?:[eE][+-]?[0-9]{1,3})?")


# ---------------------------------------------------------------- safe text
def q(value) -> str:
    """A quoted, escaped, shortened form of anything that came from input, safe to put in one log line."""
    s = repr(value)
    return s if len(s) <= 40 else s[:37] + "..."


def safe(name) -> str:
    """A name as it is, unless it holds a control character or is long, then quoted."""
    return name if isinstance(name, str) and name.isprintable() and len(name) <= 60 else q(name)


def escape_annotation(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so input cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- values
def _is_null(v) -> bool:
    return v is None or v == ""


def _is_number(v) -> bool:
    if isinstance(v, bool):
        return False
    return isinstance(v, int) or (isinstance(v, float) and math.isfinite(v))


def parse_value(raw, typ: str, typed: bool = False):
    """(True, value) when raw is a valid value of the type, else (False, None).
    typed False: raw is the text of a CSV cell. typed True: raw is a JSON value, and a string is only a string."""
    if not typed:
        if typ == "string":
            return True, raw
        if typ == "integer":
            return (True, int(raw.split(".")[0])) if _INT_RE.fullmatch(raw) else (False, None)
        if typ == "number":
            if _NUM_RE.fullmatch(raw):
                x = float(raw)
                return (True, x) if math.isfinite(x) else (False, None)
            return False, None
        return (True, raw.lower() == "true") if raw.lower() in ("true", "false") else (False, None)
    if typ == "string":
        return (True, raw) if isinstance(raw, str) else (False, None)
    if typ == "boolean":
        return (True, raw) if isinstance(raw, bool) else (False, None)
    if not _is_number(raw):
        return False, None
    if typ == "integer":
        return (True, int(raw)) if isinstance(raw, int) or raw.is_integer() else (False, None)
    return True, raw


def _exceeds(count: int, total: int, rate: float) -> bool:
    """count/total is above rate, compared after rounding so 29/100 against 0.29 is not a float accident."""
    return round(count / total - rate, 12) > 0


def _pct(count: int, total: int) -> str:
    return f"{100 * count / total:.1f}%"


# ---------------------------------------------------------------- the checks
def _finding(kind, field, level, count, rows, reason) -> dict:
    return {"kind": kind, "field": field, "level": level, "count": count, "rows": rows, "reason": reason}


def _check_field(spec: dict, values: list, tolerance: float, typed: bool) -> list:
    n, name, typ = len(values), spec["name"], spec["type"]
    out = []
    nulls = sum(1 for v in values if _is_null(v))
    allowed_nulls = spec.get("max_null_rate", 0.0)
    if _exceeds(nulls, n, allowed_nulls):
        out.append(_finding("null_rate", name, "fail", nulls, n,
                            f"{nulls} of {n} values ({_pct(nulls, n)}) are null; allowed {100 * allowed_nulls:.1f}%"))
    lo, hi, allowed = spec.get("min"), spec.get("max"), spec.get("allowed")
    counts = {"type_mismatch": 0, "below_min": 0, "above_max": 0, "not_allowed": 0}
    first = {}
    for v in values:
        if _is_null(v):
            continue
        ok, x = parse_value(v, typ, typed)
        kind = None
        if not ok:
            kind = "type_mismatch"
        elif lo is not None and x < lo:
            kind = "below_min"
        elif hi is not None and x > hi:
            kind = "above_max"
        elif allowed is not None and x not in allowed:
            kind = "not_allowed"
        if kind:
            counts[kind] += 1
            first.setdefault(kind, v)
    what = {"type_mismatch": f"do not parse as {typ}", "below_min": f"are below the minimum {lo}",
            "above_max": f"are above the maximum {hi}", "not_allowed": "are not in the allowed list"}
    for kind in ("type_mismatch", "below_min", "above_max", "not_allowed"):
        c = counts[kind]
        if c and _exceeds(c, n, tolerance):
            out.append(_finding(kind, name, "fail", c, n,
                                f"{c} of {n} values ({_pct(c, n)}) {what[kind]}; first seen {q(first[kind])}; allowed {100 * tolerance:.1f}%"))
    return out


def check_batch(contract: dict, columns: list, rows: list, typed: bool = False) -> list:
    """Findings for one delivery. columns is the header; rows are lists aligned to it (CSV text, or JSON values when typed).
    The contract must have passed check_contract_shape."""
    n = len(rows)
    if not n:
        raise ValueError("no rows, so nothing can be checked")
    tolerance = contract.get("max_bad_rate", 0.0)
    index = {c: i for i, c in enumerate(columns)}
    listed = {f["name"] for f in contract["fields"]}
    findings = []
    for spec in contract["fields"]:
        if spec["name"] not in index:
            findings.append(_finding("missing_field", spec["name"], "fail", n, n, "the contract lists this column and the batch has none"))
            continue
        i = index[spec["name"]]
        findings.extend(_check_field(spec, [r[i] for r in rows], tolerance, typed))
    policy = contract.get("unexpected_columns", "warn")
    if policy != "allow":
        for c in columns:
            if c not in listed:
                findings.append(_finding("unexpected_column", c, "warn" if policy == "warn" else "fail", 0, n,
                                         "the batch has this column and the contract does not list it"))
    return findings


def decide(findings: list) -> str:
    levels = {f["level"] for f in findings}
    return "FAIL" if "fail" in levels else "WARN" if "warn" in levels else "PASS"


# ---------------------------------------------------------------- loading and input checks
def check_contract_shape(c, label: str) -> None:
    """Raise ValueError with a one-line message when the contract is malformed, so bad input exits 2."""
    if not isinstance(c, dict):
        raise ValueError(f"{label}: expected a JSON object, got {type(c).__name__}")
    for k in sorted(set(c) - CONTRACT_KEYS):
        raise ValueError(f"{label}: unknown key {q(k)}")
    if c.get("unexpected_columns", "warn") not in POLICIES:
        raise ValueError(f"{label}: unexpected_columns must be one of {', '.join(POLICIES)}")
    rate = c.get("max_bad_rate", 0.0)
    if not _is_number(rate) or not 0 <= rate <= 1:
        raise ValueError(f"{label}: max_bad_rate must be a number from 0 to 1")
    fields = c.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError(f"{label}: fields must be a non-empty list")
    seen = set()
    for f in fields:
        if not isinstance(f, dict) or not isinstance(f.get("name"), str) or not f["name"]:
            raise ValueError(f"{label}: every field needs a non-empty string name")
        name = f["name"]
        if name in seen:
            raise ValueError(f"{label}: field {q(name)} is listed twice")
        seen.add(name)
        for k in sorted(set(f) - FIELD_KEYS):
            raise ValueError(f"{label}: field {q(name)} has unknown key {q(k)}")
        typ = f.get("type")
        if typ not in TYPES:
            raise ValueError(f"{label}: field {q(name)} type must be one of {', '.join(TYPES)}")
        for k in ("min", "max"):
            if k in f and (typ not in ("integer", "number") or not _is_number(f[k])):
                raise ValueError(f"{label}: field {q(name)} {k} must be a number on an integer or number field")
        if "min" in f and "max" in f and f["min"] > f["max"]:
            raise ValueError(f"{label}: field {q(name)} min is above max")
        if "allowed" in f:
            a = f["allowed"]
            if typ != "string" or not isinstance(a, list) or not a or not all(isinstance(x, str) for x in a):
                raise ValueError(f"{label}: field {q(name)} allowed must be a non-empty list of strings on a string field")
        nulls = f.get("max_null_rate", 0.0)
        if not _is_number(nulls) or not 0 <= nulls <= 1:
            raise ValueError(f"{label}: field {q(name)} max_null_rate must be a number from 0 to 1")


def load_contract(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as fh:
        c = json.load(fh)
    check_contract_shape(c, os.path.basename(path))
    return c


def _open_csv(path: str, label: str):
    """Open a CSV as text. A NUL byte is refused here because csv.reader refused it only before Python 3.11."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        text = fh.read()
    if "\x00" in text:
        raise ValueError(f"{label}: contains a NUL byte")
    return io.StringIO(text, newline="")


def read_batch(path: str):
    """Return (columns, rows, typed) from a .csv or .jsonl file. Raises ValueError for anything that is not a clean table."""
    label = os.path.basename(path)
    typed = path.endswith(".jsonl")
    if path.endswith(".csv"):
        try:
            with _open_csv(path, label) as fh:
                table = [r for r in csv.reader(fh) if r]
        except csv.Error as e:
            raise ValueError(f"{label}: not readable as CSV ({e})")
        if not table:
            raise ValueError(f"{label}: the file is empty")
        columns, rows = table[0], table[1:]
        for i, r in enumerate(rows, 1):
            if len(r) != len(columns):
                raise ValueError(f"{label}: data row {i} has {len(r)} values and the header has {len(columns)}")
    elif typed:
        objs = []
        with open(path, encoding="utf-8-sig") as fh:
            for i, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError as e:
                    raise ValueError(f"{label}: line {i} is not valid JSON ({e})")
                if not isinstance(obj, dict):
                    raise ValueError(f"{label}: line {i} is {type(obj).__name__}, expected a JSON object")
                objs.append(obj)
        columns = list(dict.fromkeys(k for o in objs for k in o))
        rows = [[o.get(c) for c in columns] for o in objs]
    else:
        raise ValueError(f"{label}: expected a .csv or .jsonl file")
    if len(set(columns)) != len(columns):
        raise ValueError(f"{label}: the header repeats a column name")
    if not rows:
        raise ValueError(f"{label}: no data rows, so nothing can be checked")
    return columns, rows, typed


# ---------------------------------------------------------------- command line
def render(contract, columns, nrows, findings, decision, fmt) -> str:
    name, version = safe(contract.get("contract", "?")), safe(contract.get("version", "?"))
    if fmt == "github":
        lines = []
        for f in findings:
            level = "error" if f["level"] == "fail" else "warning"
            lines.append(f"::{level} title=feature-contract {f['kind']}::" + escape_annotation(f"{safe(f['field'])}: {f['reason']}"))
        lines.append(f"::notice title=feature-contract::" + escape_annotation(f"{name}: decision {decision}; {nrows} rows checked"))
        return "\n".join(lines)
    lines = [f"contract: {name} {version}   batch: {nrows} rows, {len(columns)} columns"]
    for f in findings:
        lines.append(f"  [{f['level'].upper():<4}] {f['kind']:<17} {safe(f['field']):<20} {f['reason']}")
    if not findings:
        lines.append("  no violations")
    lines.append(f"decision: {decision}")
    return "\n".join(lines)


def run_check(contract_path, batch_path, fail_on, fmt) -> int:
    try:
        contract = load_contract(contract_path)
        columns, rows, typed = read_batch(batch_path)
    except (OSError, ValueError, RecursionError) as e:
        print("input error: " + str(e).replace("\r", " ").replace("\n", " "), file=sys.stderr)
        return 2
    findings = check_batch(contract, columns, rows, typed)
    decision = decide(findings)
    print(render(contract, columns, len(rows), findings, decision, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[decision] >= DECISION_RANK[{"fail": "FAIL", "warn": "WARN"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="feature_contract")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_batch.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one batch against a contract")
    c.add_argument("contract")
    c.add_argument("batch")
    c.add_argument("--fail-on", choices=["fail", "warn", "never"], default="fail")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "contract_credit_triage.json"), os.path.join(d, "example_batch.csv"), "never", "text")
    if a.cmd == "check":
        return run_check(a.contract, a.batch, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
