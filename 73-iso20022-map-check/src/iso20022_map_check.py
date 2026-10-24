"""iso20022_map_check: test a field mapping between a legacy payment format and ISO 20022 for gaps and
truncation. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 iso20022_map_check.py --demo
    python3 iso20022_map_check.py check DIR [--pairs PAIRS.json]
    python3 iso20022_map_check.py probe DIR

DIR holds four files: legacy_fields.csv, iso_elements.csv, mapping.csv and code_tables.json.
PAIRS.json is {"pairs": [{"pair_id": "...", "source": {legacy tag: value}, "target": {ISO path: value}}]}:
the legacy message and the ISO message your converter produced from it, as flat path-to-value maps.

Exit status: 0 when nothing at error level was found, 1 when something was, 2 for bad or malformed input.
The demo always exits 0 so it can be shown in a README.

What it checks
  The mapping alone: a legacy field with no row, a mandatory ISO element no row fills, a legacy code
  with no table entry, a field that cannot fit its target (capacity), and the reverse (a warning).
  Each pair: every populated source value is carried to the ISO element the mapping names, without
  being dropped, cut short or changed; elements the mapping cannot explain; ISO schema basics.
  The probe command prints legacy messages with every field filled to its limit, so a converter that
  cuts early shows itself. Values are never printed; only field names, counts and lengths are.
Trailing and leading spaces are ignored on both sides; amounts are compared as numbers.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import product

TRANSFORMS = ("copy", "join_lines", "amount_implied2", "date_yyyymmdd", "code_table", "const", "drop")
LEGACY_KINDS = ("text", "digits", "amount", "date", "code")
ISO_KINDS = ("text", "decimal", "date", "code")
WARNING_KINDS = ("reverse_exposure",)
MAX_COMBOS = 64
DIGITS = "0123456789" * 40
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "..", "data")


class InputError(ValueError):
    """Bad or malformed input; the command line turns it into exit status 2."""


def safe(text) -> str:
    """Make text from input safe to print: control characters and escape sequences become visible."""
    return "".join(c if c.isprintable() else "\\u%04x" % ord(c) for c in str(text))


def finding(kind: str, subject: str, detail: str) -> dict:
    return {"kind": kind, "subject": subject, "detail": detail,
            "severity": "warning" if kind in WARNING_KINDS else "error"}


# ---------------------------------------------------------------- loading
def _read_csv(path: str, columns: tuple) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None or [c for c in columns if c not in reader.fieldnames]:
                raise InputError(f"{safe(path)}: expected the columns {', '.join(columns)}")
            # param is kept as written: a single space is a valid separator for join_lines
            rows = [{c: (r.get(c) or "") if c == "param" else (r.get(c) or "").strip() for c in columns} for r in reader]
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{safe(path)}: {safe(e)}") from None
    if not rows:
        raise InputError(f"{safe(path)}: no rows")
    return rows


def _size(value: str, label: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise InputError(f"{label}: max_len {safe(value)!r} is not a whole number") from None
    if n < 1:
        raise InputError(f"{label}: max_len must be at least 1")
    return n


def _codes(value: str) -> list:
    return [c for c in value.split("|") if c]


def build_bundle(legacy_rows: list, iso_rows: list, mapping_rows: list, tables) -> dict:
    """Validate the four inputs and return one bundle. Every problem raises InputError."""
    legacy, iso = {}, {}
    for r in legacy_rows:
        name = r["field"]
        label = f"legacy_fields {safe(name)!r}"
        if not name or name in legacy:
            raise InputError(f"legacy_fields: field name {safe(name)!r} is empty or appears twice")
        if r["kind"] not in LEGACY_KINDS:
            raise InputError(f"{label}: kind must be one of {', '.join(LEGACY_KINDS)}")
        codes = _codes(r["codes"])
        if r["kind"] == "code" and not codes:
            raise InputError(f"{label}: a code field must list its codes")
        legacy[name] = {"max_len": _size(r["max_len"], label), "kind": r["kind"], "codes": codes}
    for r in iso_rows:
        path = r["path"]
        label = f"iso_elements {safe(path)!r}"
        if not path or path in iso:
            raise InputError(f"iso_elements: path {safe(path)!r} is empty or appears twice")
        if r["kind"] not in ISO_KINDS or r["mandatory"] not in ("Y", "N"):
            raise InputError(f"{label}: kind must be one of {', '.join(ISO_KINDS)} and mandatory must be Y or N")
        codes = _codes(r["codes"])
        if r["kind"] == "code" and not codes:
            raise InputError(f"{label}: a code element must list its codes")
        iso[path] = {"max_len": _size(r["max_len"], label), "kind": r["kind"], "mandatory": r["mandatory"] == "Y", "codes": codes}
    if not isinstance(tables, dict) or any(
            not isinstance(t, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in t.items())
            for t in tables.values()):
        raise InputError("code_tables.json: expected an object of tables, each mapping legacy code to ISO code as strings")
    rows, seen_ids, seen_paths = [], set(), set()
    for r in mapping_rows:
        rid, transform = r["row_id"], r["transform"]
        param = r["param"] if transform == "join_lines" else r["param"].strip()
        label = f"mapping row {safe(rid)!r}"
        if not rid or rid in seen_ids:
            raise InputError(f"mapping: row id {safe(rid)!r} is empty or appears twice")
        seen_ids.add(rid)
        if transform not in TRANSFORMS:
            raise InputError(f"{label}: transform must be one of {', '.join(TRANSFORMS)}")
        fields = [f for f in r["legacy_fields"].split("|") if f]
        for f in fields:
            if f not in legacy:
                raise InputError(f"{label}: unknown legacy field {safe(f)!r}")
        wanted = {"join_lines": "2 or more", "const": "no", "drop": "1 or more"}.get(transform, "exactly 1")
        count_ok = {"join_lines": len(fields) >= 2, "const": not fields, "drop": len(fields) >= 1}.get(transform, len(fields) == 1)
        if not count_ok:
            raise InputError(f"{label}: {transform} needs {wanted} legacy fields")
        path = r["iso_path"]
        if transform == "drop":
            if path:
                raise InputError(f"{label}: a drop row must not name an ISO element")
        else:
            if path not in iso:
                raise InputError(f"{label}: unknown ISO element {safe(path)!r}")
            if path in seen_paths:
                raise InputError(f"{label}: ISO element {safe(path)!r} is written by two rows")
            seen_paths.add(path)
        if transform == "code_table" and param not in tables:
            raise InputError(f"{label}: code table {safe(param)!r} is not in code_tables.json")
        if transform == "const" and not param:
            raise InputError(f"{label}: a const row needs a value in param")
        rows.append({"row_id": rid, "fields": fields, "iso_path": path, "transform": transform, "param": param})
    if not rows:
        raise InputError("mapping: no rows")
    return {"legacy": legacy, "iso": iso, "rows": rows, "tables": tables}


def load_bundle(directory: str) -> dict:
    legacy = _read_csv(os.path.join(directory, "legacy_fields.csv"), ("field", "max_len", "kind", "codes"))
    iso = _read_csv(os.path.join(directory, "iso_elements.csv"), ("path", "max_len", "kind", "mandatory", "codes"))
    mapping = _read_csv(os.path.join(directory, "mapping.csv"), ("row_id", "legacy_fields", "iso_path", "transform", "param"))
    path = os.path.join(directory, "code_tables.json")
    try:
        with open(path, encoding="utf-8") as fh:
            tables = json.load(fh)
    except (OSError, ValueError, RecursionError) as e:
        raise InputError(f"{safe(path)}: {safe(e)}") from None
    return build_bundle(legacy, iso, mapping, tables)


def load_pairs(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError, RecursionError) as e:
        raise InputError(f"{safe(path)}: {safe(e)}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("pairs"), list):
        raise InputError(f"{safe(path)}: expected an object with a list under 'pairs'")
    if not doc["pairs"]:
        raise InputError(f"{safe(path)}: the pairs list is empty, so nothing can be checked")
    for i, p in enumerate(doc["pairs"]):
        ok = isinstance(p, dict) and isinstance(p.get("pair_id"), str)
        for side in ("source", "target"):
            m = p.get(side) if ok else None
            ok = ok and isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in m.items())
        if not ok:
            raise InputError(f"{safe(path)}: pair {i + 1} needs a string pair_id and string-to-string 'source' and 'target' objects")
    return doc["pairs"]


# ---------------------------------------------------------------- the mapping on its own
def capacity(row: dict, legacy: dict) -> int:
    """Characters a copy or join_lines row can carry out of the legacy format."""
    sizes = [legacy[f]["max_len"] for f in row["fields"]]
    return sum(sizes) + len(row["param"]) * (len(sizes) - 1) if row["transform"] == "join_lines" else sizes[0]


def check_mapping(bundle: dict) -> list:
    legacy, iso, rows, tables = bundle["legacy"], bundle["iso"], bundle["rows"], bundle["tables"]
    out = []
    used = {f for r in rows for f in r["fields"]}
    for name in legacy:
        if name not in used:
            out.append(finding("legacy_unmapped", name, "no mapping row, so a populated value is dropped"))
    produced = {r["iso_path"] for r in rows if r["transform"] != "drop"}
    for path, spec in iso.items():
        if spec["mandatory"] and path not in produced:
            out.append(finding("iso_mandatory_unsourced", path, "mandatory element with no mapping row and no constant"))
    for r in rows:
        if r["transform"] == "code_table":
            name = r["fields"][0]
            for code in legacy[name]["codes"]:
                if code not in tables[r["param"]]:
                    out.append(finding("code_not_covered", f"{name}={code}", f"legacy code has no entry in table {r['param']}"))
        if r["transform"] in ("copy", "join_lines"):
            cap, limit = capacity(r, legacy), iso[r["iso_path"]]["max_len"]
            names = "+".join(r["fields"])
            if cap > limit:
                out.append(finding("capacity_overflow", r["iso_path"], f"{names} can hold {cap} characters, the element takes {limit}"))
            elif cap < limit:
                out.append(finding("reverse_exposure", r["iso_path"], f"element takes {limit} characters, {names} holds {cap}"))
    return out


# ---------------------------------------------------------------- one pair
def expected_target(source: dict, bundle: dict):
    """What the ISO message should hold if the mapping were applied without loss.
    Returns (expected {path: str or Decimal}, issues [(kind, subject, detail)], explained paths)."""
    legacy, tables = bundle["legacy"], bundle["tables"]
    expected, issues, explained, mapped = {}, [], set(), set()
    for row in bundle["rows"]:
        mapped.update(row["fields"])
        t, path = row["transform"], row["iso_path"]
        if t == "drop":
            continue
        if t == "const":
            expected[path] = row["param"]
            continue
        field = row["fields"][0]
        vals = [source.get(f, "").strip() for f in row["fields"]]
        if t == "copy":
            value = vals[0]
        elif t == "join_lines":
            value = row["param"].join(v for v in vals if v)
        elif t == "amount_implied2":
            value = None
            if vals[0] and not (vals[0].isascii() and vals[0].isdigit()):
                issues.append(("source_invalid", field, "amount is not all digits"))
                explained.add(path)
            elif vals[0]:
                value = Decimal(vals[0]).scaleb(-2)
        elif t == "date_yyyymmdd":
            value = None
            if vals[0]:
                try:
                    if len(vals[0]) != 8 or not (vals[0].isascii() and vals[0].isdigit()):
                        raise ValueError
                    value = datetime.strptime(vals[0], "%Y%m%d").date().isoformat()
                except ValueError:
                    issues.append(("source_invalid", field, "date is not a valid YYYYMMDD"))
                    explained.add(path)
        else:
            value = None
            if vals[0]:
                value = tables[row["param"]].get(vals[0])
                if value is None:
                    issues.append(("code_unmapped", f"{field}={vals[0]}", f"legacy code has no entry in table {row['param']}"))
                    explained.add(path)
        if value is not None and value != "":
            expected[path] = value
    for name, value in source.items():
        if name not in legacy:
            issues.append(("unknown_source_field", name, "not in legacy_fields.csv, so it cannot be checked"))
        elif name not in mapped and value.strip():
            issues.append(("unmapped_lost", name, "populated, but no mapping row carries it"))
    return expected, issues, explained


def compare(expected: dict, target: dict) -> list:
    out = []
    for path, want in expected.items():
        got = target.get(path, "").strip()
        if not got:
            out.append(("dropped", path, "the element is absent or empty"))
        elif isinstance(want, Decimal):
            try:
                same = Decimal(got) == want
            except InvalidOperation:
                same = False
            if not same:
                out.append(("altered", path, "the amount differs"))
        elif got != want:
            if len(got) < len(want) and want.startswith(got):
                out.append(("truncated", path, f"kept {len(got)} of {len(want)} characters"))
            else:
                at = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
                out.append(("altered", path, f"differs from character {at + 1}"))
    return out


def schema_issues(target: dict, bundle: dict) -> list:
    out = []
    for path, spec in bundle["iso"].items():
        value = target.get(path, "").strip()
        if not value:
            if spec["mandatory"]:
                out.append(("schema_missing_mandatory", path, "mandatory element is absent or empty"))
            continue
        if len(value) > spec["max_len"]:
            out.append(("schema_over_length", path, f"{len(value)} characters, the element takes {spec['max_len']}"))
        elif spec["kind"] == "date":
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                out.append(("schema_bad_value", path, "not a valid YYYY-MM-DD date"))
        elif spec["kind"] == "decimal":
            try:
                ok = Decimal(value).is_finite()
            except InvalidOperation:
                ok = False
            if not ok:
                out.append(("schema_bad_value", path, "not a decimal number"))
        elif spec["kind"] == "code" and value not in spec["codes"]:
            out.append(("schema_bad_value", path, "not one of the allowed codes"))
    return out


def check_pair(source: dict, target: dict, bundle: dict, schema: bool = True) -> list:
    """All findings for one (source, target) pair. schema=False skips the ISO schema basics."""
    expected, issues, explained = expected_target(source, bundle)
    found = issues + compare(expected, target)
    produced = {r["iso_path"] for r in bundle["rows"] if r["transform"] != "drop"}
    for path, value in sorted(target.items()):
        if value.strip() and path not in expected and path not in explained:
            why = "the source field is blank" if path in produced else "no mapping row writes this element"
            found.append(("untraced", path, f"a value is present but {why}"))
    if schema:
        found += schema_issues(target, bundle)
    return [finding(k, s, d) for k, s, d in found]


# ---------------------------------------------------------------- coverage and probes
def coverage(sources: list, bundle: dict) -> dict:
    """What the messages never exercised: mapping rows with a blank source, code values and code combinations."""
    legacy = bundle["legacy"]
    blank = [r["row_id"] for r in bundle["rows"] if r["fields"] and r["transform"] != "drop"
             and all(not s.get(f, "").strip() for s in sources for f in r["fields"])]
    code_fields = [f for f, spec in legacy.items() if spec["kind"] == "code"]
    codes_unseen = []
    for f in code_fields:
        seen = {s.get(f, "").strip() for s in sources}
        codes_unseen += [f"{f}={c}" for c in legacy[f]["codes"] if c not in seen]
    combos = None
    total = 1
    for f in code_fields:
        total *= len(legacy[f]["codes"])
    if len(code_fields) >= 2 and total <= MAX_COMBOS:
        seen = {tuple(s.get(f, "").strip() for f in code_fields) for s in sources}
        missing = [c for c in product(*[legacy[f]["codes"] for f in code_fields]) if c not in seen]
        combos = {"fields": code_fields, "missing": len(missing), "total": total,
                  "examples": ", ".join("/".join(c) for c in missing[:6])}
    return {"blank_rows": blank, "codes_unseen": codes_unseen, "combos": combos}


def _probe_value(idx: int, spec: dict, k: int) -> str:
    size = spec["max_len"]
    if spec["kind"] == "code":
        return spec["codes"][k % len(spec["codes"])]
    if spec["kind"] == "amount":
        return "123456789012"[:size]
    if spec["kind"] == "date":
        return "20261231"[:size]
    return DIGITS[idx % 10: idx % 10 + size]


def probe_messages(bundle: dict) -> list:
    """Legacy messages with every field at its limit; probe k uses code k of each coded field."""
    legacy = bundle["legacy"]
    n = max([len(s["codes"]) for s in legacy.values() if s["kind"] == "code"] + [1])
    return [{"pair_id": f"P{k + 1}",
             "source": {name: _probe_value(i, spec, k).ljust(spec["max_len"]) for i, (name, spec) in enumerate(legacy.items())}}
            for k in range(n)]


# ---------------------------------------------------------------- output
def _group(pair_findings: list) -> list:
    groups = {}
    for pair_id, f in pair_findings:
        g = groups.setdefault((f["kind"], f["subject"]), {"n": 0, "first": pair_id, "detail": f["detail"], "severity": f["severity"]})
        g["n"] += 1
    return [(k, s, g) for (k, s), g in sorted(groups.items())]


def render(bundle: dict, static: list, pair_count: int, pair_findings: list, cov) -> str:
    rows = bundle["rows"]
    dropped = [f for r in rows if r["transform"] == "drop" for f in r["fields"]]
    lines = [f"mapping: {len(rows)} rows | {len(bundle['legacy'])} legacy fields | {len(bundle['iso'])} ISO elements"
             + (f" | {len(dropped)} dropped on purpose ({safe(', '.join(dropped))})" if dropped else "")]
    for f in (x for x in static if x["severity"] == "error"):
        lines.append(f"  [error  ] {f['kind']:<24} {safe(f['subject']):<24} {safe(f['detail'])}")
    warn = [x for x in static if x["severity"] == "warning"]
    if warn:
        lines.append(f"  [warning] {warn[0]['kind']:<24} {len(warn)} rows{'':<18} the ISO element takes more than the legacy field holds, "
                     f"e.g. {safe(warn[0]['subject'])}: {safe(warn[0]['detail'])}")
    n_static = sum(1 for x in static if x["severity"] == "error")
    n_pair = len(pair_findings)
    if pair_count is None:
        lines.append("pairs: none given (--pairs), so only the mapping was checked")
    else:
        lines.append(f"pairs: {pair_count} checked" + ("" if pair_findings else ", no findings"))
        for kind, subject, g in _group(pair_findings):
            lines.append(f"  [{g['severity']:<7}] {kind:<24} {safe(subject):<24} {g['n']} of {pair_count} pairs"
                         f" (first {safe(g['first'])}): {safe(g['detail'])}")
        if cov is not None:
            if cov["blank_rows"]:
                lines.append(f"coverage: mapping rows whose source is blank in every pair: {safe(', '.join(cov['blank_rows']))}")
            if cov["codes_unseen"]:
                lines.append(f"coverage: code values never seen: {safe(', '.join(cov['codes_unseen']))}")
            c = cov["combos"]
            if c and c["missing"]:
                lines.append(f"coverage: code combinations ({safe(', '.join(c['fields']))}) never seen: {c['missing']} of {c['total']} "
                             f"({safe(c['examples'])})")
            if not (cov["blank_rows"] or cov["codes_unseen"] or (c and c["missing"])):
                lines.append("coverage: every mapping row, code value and code combination appears in at least one pair")
    lines.append(f"decision: {'FAIL' if n_static or n_pair else 'PASS'} ({n_static} mapping errors, {n_pair} pair findings)")
    return "\n".join(lines)


def run_check(directory: str, pairs_path, demo: bool = False) -> int:
    bundle = load_bundle(directory)
    pairs = load_pairs(pairs_path) if pairs_path else None
    static = check_mapping(bundle)
    pair_findings = []
    for p in pairs or []:
        pair_findings += [(p["pair_id"], f) for f in check_pair(p["source"], p["target"], bundle)]
    cov = coverage([p["source"] for p in pairs], bundle) if pairs else None
    print(render(bundle, static, len(pairs) if pairs else None, pair_findings, cov))
    errors = any(x["severity"] == "error" for x in static) or bool(pair_findings)
    return 0 if demo or not errors else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="iso20022_map_check")
    ap.add_argument("--demo", action="store_true", help="check the bundled mapping and three bundled message pairs")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check a mapping, and message pairs when given")
    c.add_argument("dir")
    c.add_argument("--pairs", help="JSON file of source and target message pairs")
    p = sub.add_parser("probe", help="print legacy messages with every field at its limit")
    p.add_argument("dir")
    a = ap.parse_args(argv)
    try:
        if a.demo:
            return run_check(DEMO_DIR, os.path.join(DEMO_DIR, "example_pairs.json"), demo=True)
        if a.cmd == "check":
            return run_check(a.dir, a.pairs)
        if a.cmd == "probe":
            print(json.dumps({"probes": probe_messages(load_bundle(a.dir))}, indent=1))
            return 0
    except InputError as e:
        print(f"input error: {safe(e)}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
