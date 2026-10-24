"""report_trace: trace a number in a filed report back to the source rows behind it. Standard library only.
Python 3.9 or newer.

Command line (from src/):
    python3 report_trace.py --demo
    python3 report_trace.py build  --source LOANS.csv --spec SPEC.json --filed FILED.csv --out LINEAGE.json [--adjustments ADJ.csv]
    python3 report_trace.py verify --lineage LINEAGE.json --source LOANS_NOW.csv [--format text|github]
    python3 report_trace.py trace  --lineage LINEAGE.json --cell CELL_ID [--source LOANS_NOW.csv]

build    reads the source rows as they stood at filing, applies the cell rules in the spec, and writes a lineage
         file: for every cell the rule, the source rows behind it (with the fields the rule reads), the logged
         adjustments, and the filed value. In a real reporting job this capture would sit inside the job; here
         it is a reference implementation of the aggregation.
verify   checks every cell against the lineage and a current copy of the source: is the filed value explained by
         its rows plus logged adjustments, did a row change or vanish, did a row that fits the rule appear that
         the filing never saw, do the totals and ratios foot, and which open loans are in no cell at all.
trace    prints the path from one cell to its rows.

Exit status: 0 when nothing needs a person, 1 when the tool found a problem, 2 for bad or malformed input.
There is no model in this file. A cell can be traced and still be wrong: lineage shows where a number came from,
not whether the source row was right.

Spec shape: {"as_of", "status", "products", "buckets": [{"name", "min", "max"}], "cells": [...]}.
A leaf cell names a product and a bucket. A derived cell is {"op": "sum", "inputs": [...]} or
{"op": "ratio_bps", "numerator": [...], "denominator": [...]}; structure comes from these fields, never from cell names.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys

FORMAT = "report-trace-lineage/1"
LOAN_COLUMNS = ("loan_id", "product", "status", "booked_date", "days_past_due", "balance_cents")
ADJ_COLUMNS = ("adj_id", "cell_id", "amount_cents", "reason")
FILED_COLUMNS = ("cell_id", "value")
READ_SET = ("product", "status", "booked", "dpd", "balance")   # the loan fields a cell rule reads, in lineage-row order
FIELD_NAME = {"product": "product", "status": "status", "booked": "booked_date", "dpd": "days_past_due", "balance": "balance_cents"}
SHOWN = 3
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class InputError(Exception):
    """Bad or inconsistent input. The command line reports it on one line and exits 2."""


# ---------------------------------------------------------------- small helpers
def one_line(text) -> str:
    """Make untrusted text safe for a log line: control and separator characters become visible escapes."""
    return "".join(ch if ch.isprintable() else ("\\u%04x" % ord(ch) if ord(ch) < 0x10000 else "\\U%08x" % ord(ch))
                   for ch in str(text))


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so source text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def money(cents: int) -> str:
    c = abs(cents)
    return f"{'-' if cents < 0 else ''}{c // 100:,}.{c % 100:02d}"


def ratio_bps(num: int, den: int) -> int:
    """num / den in basis points, rounded half away from zero; 0 when the denominator is 0."""
    if den == 0:
        return 0
    q = (abs(num) * 20000 + abs(den)) // (2 * abs(den))
    return -q if (num < 0) != (den < 0) else q


def _expect(ok, message: str) -> None:
    if not ok:
        raise InputError(message)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _whole(text: str, what: str) -> int:
    _expect(re.fullmatch(r"-?[0-9]+", text.strip()) is not None, f"{what}: {text!r} is not a whole number")
    return int(text.strip())


def _date(text, what: str) -> str:
    t = text.strip() if isinstance(text, str) else ""
    ok = re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", t) is not None
    if ok:
        try:
            datetime.date.fromisoformat(t)
        except ValueError:
            ok = False
    _expect(ok, f"{what}: {text!r} is not a date like 2026-06-30")
    return t


def _field(row: dict, col: str, label: str, n: int) -> str:
    v = row.get(col)
    _expect(isinstance(v, str), f"{label} row {n}: no value for {col} (short or truncated row)")
    return v


# ---------------------------------------------------------------- loading
def read_csv(path: str, required, label: str) -> list:
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames
            rows = list(reader) if header else []
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{label}: cannot read {path}: {e}") from None
    _expect(header, f"{label}: {path} is empty")
    missing = [c for c in required if c not in header]
    _expect(not missing, f"{label}: {path} lacks column(s) {', '.join(missing)}")
    return rows


def load_json(path: str, label: str):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError, RecursionError) as e:
        raise InputError(f"{label}: cannot read {path}: {e}") from None


def load_loans(path: str, label: str = "source") -> dict:
    """{loan_id: loan} from a CSV with the columns in LOAN_COLUMNS; any other column is ignored."""
    rows = read_csv(path, LOAN_COLUMNS, label)
    _expect(rows, f"{label}: {path} has a header and no rows")
    loans = {}
    for n, r in enumerate(rows, 2):
        where = f"{label} row {n}"
        lid = _field(r, "loan_id", label, n).strip()
        _expect(lid, f"{where}: empty loan_id")
        _expect(lid not in loans, f"{where}: loan_id {lid!r} appears twice")
        dpd_text = _field(r, "days_past_due", label, n).strip()
        dpd = _whole(dpd_text, f"{where}: days_past_due") if dpd_text else None
        _expect(dpd is None or dpd >= 0, f"{where}: days_past_due is negative")
        loan = {"loan_id": lid, "product": _field(r, "product", label, n).strip(), "status": _field(r, "status", label, n).strip(),
                "booked": _date(_field(r, "booked_date", label, n), f"{where}: booked_date"), "dpd": dpd,
                "balance": _whole(_field(r, "balance_cents", label, n), f"{where}: balance_cents")}
        _expect(loan["product"] and loan["status"], f"{where}: empty product or status")
        loans[lid] = loan
    return loans


def load_adjustments(path: str) -> list:
    rows = read_csv(path, ADJ_COLUMNS, "adjustments")
    seen, out = set(), []
    for n, r in enumerate(rows, 2):
        adj_id = _field(r, "adj_id", "adjustments", n).strip()
        _expect(adj_id, f"adjustments row {n}: empty adj_id")
        _expect(adj_id not in seen, f"adjustments row {n}: adj_id {adj_id!r} appears twice")
        seen.add(adj_id)
        out.append({"adj_id": adj_id, "cell_id": _field(r, "cell_id", "adjustments", n).strip(),
                    "amount_cents": _whole(_field(r, "amount_cents", "adjustments", n), f"adjustments row {n}: amount_cents"),
                    "reason": _field(r, "reason", "adjustments", n)})
    return out


def cell_inputs(cell: dict) -> list:
    return list(cell["inputs"]) if cell["op"] == "sum" else list(cell["numerator"]) + list(cell["denominator"])


def cell_order(defs: dict) -> list:
    """Cell ids with every input ahead of the cells built from it. Raises InputError on an unknown input or a cycle."""
    order, state = [], {}
    for root in defs:
        stack = [(root, False)]
        while stack:
            cid, done = stack.pop()
            if done:
                state[cid] = 2
                order.append(cid)
                continue
            if state.get(cid) == 2:
                continue
            _expect(state.get(cid) != 1, f"cell {cid!r} depends on itself")
            state[cid] = 1
            stack.append((cid, True))
            if defs[cid]["kind"] == "derived":
                for i in cell_inputs(defs[cid]):
                    _expect(i in defs, f"cell {cid!r} uses {i!r}, which is not a cell")
                    if state.get(i) != 2:
                        stack.append((i, False))
    return order


def _id_list(v, what: str) -> None:
    _expect(isinstance(v, list) and v and all(isinstance(i, str) for i in v), f"{what} must be a non-empty list of cell ids")


def check_derived(cid: str, c: dict) -> None:
    _expect(c.get("op") in ("sum", "ratio_bps"), f"cell {cid!r}: op must be sum or ratio_bps")
    if c["op"] == "sum":
        _id_list(c.get("inputs"), f"cell {cid!r}: inputs")
    else:
        _id_list(c.get("numerator"), f"cell {cid!r}: numerator")
        _id_list(c.get("denominator"), f"cell {cid!r}: denominator")


def load_spec(path: str) -> dict:
    spec = load_json(path, "spec")
    _expect(isinstance(spec, dict), "spec: expected a JSON object")
    spec["as_of"] = _date(spec.get("as_of"), "spec as_of")
    spec.setdefault("status", "open")
    _expect(isinstance(spec["status"], str) and spec["status"], "spec: status must be a non-empty string")
    products = spec.get("products")
    _expect(isinstance(products, list) and products and all(isinstance(p, str) and p for p in products)
            and len(set(products)) == len(products), "spec: products must be a list of distinct non-empty strings")
    buckets = spec.get("buckets")
    _expect(isinstance(buckets, list) and buckets, "spec: buckets must be a non-empty list")
    names = set()
    for b in buckets:
        _expect(isinstance(b, dict) and isinstance(b.get("name"), str) and b["name"] and b["name"] not in names
                and _is_int(b.get("min")) and b["min"] >= 0 and "max" in b and (b["max"] is None or (_is_int(b["max"]) and b["max"] >= b["min"])),
                "spec: each bucket needs a distinct name, an integer min and a max that is an integer or null")
        names.add(b["name"])
    ranges = sorted(buckets, key=lambda b: b["min"])
    for prev, cur in zip(ranges, ranges[1:]):
        _expect(prev["max"] is not None and cur["min"] > prev["max"], f"spec: buckets {prev['name']!r} and {cur['name']!r} overlap")
    cells = spec.get("cells")
    _expect(isinstance(cells, list) and cells, "spec: cells must be a non-empty list")
    ids, pairs = set(), set()
    for c in cells:
        _expect(isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] and c["id"] not in ids, "spec: each cell needs a distinct id")
        ids.add(c["id"])
        _expect(c.get("label", "") is None or isinstance(c.get("label", ""), str), f"spec: label of {c['id']!r} must be text")
        _expect(c.get("kind") in ("leaf", "derived"), f"spec: cell {c['id']!r} needs kind leaf or derived")
        if c["kind"] == "leaf":
            _expect(isinstance(c.get("product"), str) and c["product"] in products and isinstance(c.get("bucket"), str) and c["bucket"] in names,
                    f"spec: leaf {c['id']!r} names an unknown product or bucket")
            _expect((c["product"], c["bucket"]) not in pairs, f"spec: leaf {c['id']!r} repeats a product and bucket")
            pairs.add((c["product"], c["bucket"]))
        else:
            check_derived(c["id"], c)
    cell_order({c["id"]: c for c in cells})
    return spec


def load_filed(path: str, defs: dict) -> dict:
    rows = read_csv(path, FILED_COLUMNS, "filed report")
    filed = {}
    for n, r in enumerate(rows, 2):
        cid = _field(r, "cell_id", "filed report", n).strip()
        _expect(cid in defs, f"filed report row {n}: cell {cid!r} is not in the spec")
        _expect(cid not in filed, f"filed report row {n}: cell {cid!r} appears twice")
        filed[cid] = _whole(_field(r, "value", "filed report", n), f"filed report row {n}: value")
    absent = [c for c in defs if c not in filed]
    _expect(not absent, f"filed report has no value for {len(absent)} spec cell(s), first {absent[:1]}")
    return filed


# ---------------------------------------------------------------- build
def row_matches(rule: dict, loan: dict) -> bool:
    d = loan["dpd"]
    return (loan["product"] == rule["product"] and loan["status"] == rule["status"] and loan["booked"] <= rule["as_of"]
            and d is not None and d >= rule["min"] and (rule["max"] is None or d <= rule["max"]))


def row_of(loan: dict) -> list:
    return [loan["loan_id"], loan["product"], loan["status"], loan["booked"], loan["dpd"], loan["balance"]]


def build_lineage(spec: dict, loans: dict, adjustments: list, filed: dict) -> dict:
    buckets = {b["name"]: b for b in spec["buckets"]}
    rules, by_product = {}, {}
    for c in spec["cells"]:
        if c["kind"] == "leaf":
            b = buckets[c["bucket"]]
            rules[c["id"]] = {"product": c["product"], "bucket": b["name"], "min": b["min"], "max": b["max"],
                              "status": spec["status"], "as_of": spec["as_of"]}
            by_product.setdefault(c["product"], []).append(c["id"])
    rows = {cid: [] for cid in rules}
    orphans = []
    for lid in sorted(loans):
        loan = loans[lid]
        if loan["status"] != spec["status"] or loan["booked"] > spec["as_of"]:
            continue
        hit = next((cid for cid in by_product.get(loan["product"], []) if row_matches(rules[cid], loan)), None)
        if hit is None:
            orphans.append(row_of(loan))
        else:
            rows[hit].append(row_of(loan))
    _expect(any(rows.values()), "no source row matches any leaf cell in the spec (check as_of, status and product names)")
    defs = {c["id"]: c for c in spec["cells"]}
    logged = {cid: [] for cid in rules}
    unmatched = []
    for a in adjustments:
        if a["cell_id"] in rules:
            logged[a["cell_id"]].append({"adj_id": a["adj_id"], "amount_cents": a["amount_cents"], "reason": a["reason"]})
        else:
            unmatched.append(dict(a, why="targets a derived cell" if a["cell_id"] in defs else "targets no cell in the spec"))
    cells = {}
    for c in spec["cells"]:
        entry = {"kind": c["kind"], "label": c.get("label") or c["id"], "filed": filed[c["id"]]}
        if c["kind"] == "leaf":
            entry.update(rule=rules[c["id"]], rows=rows[c["id"]], adjustments=logged[c["id"]])
        else:
            entry["op"] = c["op"]
            for k in ("inputs", "numerator", "denominator"):
                if k in c:
                    entry[k] = list(c[k])
        cells[c["id"]] = entry
    return {"format": FORMAT, "as_of": spec["as_of"], "order": [c["id"] for c in spec["cells"]], "cells": cells,
            "orphans": orphans, "unmatched_adjustments": unmatched}


def write_lineage(lineage: dict, path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(lineage, fh, indent=1, sort_keys=True)
            fh.write("\n")
    except OSError as e:
        raise InputError(f"cannot write {path}: {e}") from None


def _check_row(row, where: str) -> None:
    _expect(isinstance(row, list) and len(row) == 6 and all(isinstance(x, str) for x in row[:4])
            and (row[4] is None or _is_int(row[4])) and _is_int(row[5]), f"lineage: {where} has a malformed source row")


def load_lineage(path: str) -> dict:
    lin = load_json(path, "lineage")
    _expect(isinstance(lin, dict) and lin.get("format") == FORMAT, f"lineage: {path} is not a {FORMAT} file")
    order, cells = lin.get("order"), lin.get("cells")
    _expect(isinstance(order, list) and isinstance(cells, dict) and order and len(set(map(str, order))) == len(order) == len(cells)
            and all(isinstance(i, str) and i in cells for i in order), "lineage: order and cells disagree")
    _date(lin.get("as_of"), "lineage as_of")
    for cid, c in cells.items():
        _expect(isinstance(c, dict) and c.get("kind") in ("leaf", "derived") and _is_int(c.get("filed"))
                and isinstance(c.get("label"), str), f"lineage: cell {cid!r} is malformed")
        if c["kind"] == "leaf":
            r = c.get("rule")
            _expect(isinstance(r, dict) and isinstance(r.get("product"), str) and isinstance(r.get("bucket"), str)
                    and _is_int(r.get("min")) and "max" in r and (r["max"] is None or _is_int(r["max"])) and isinstance(r.get("status"), str)
                    and isinstance(r.get("as_of"), str), f"lineage: cell {cid!r} has a malformed rule")
            _expect(isinstance(c.get("rows"), list), f"lineage: cell {cid!r} has no rows list")
            for row in c["rows"]:
                _check_row(row, f"cell {cid!r}")
            adj = c.get("adjustments")
            _expect(isinstance(adj, list) and all(isinstance(a, dict) and isinstance(a.get("adj_id"), str) and _is_int(a.get("amount_cents"))
                                                  and isinstance(a.get("reason"), str) for a in adj), f"lineage: cell {cid!r} has malformed adjustments")
        else:
            check_derived(cid, c)
    _expect(isinstance(lin.get("orphans"), list), "lineage: orphans must be a list")
    for row in lin["orphans"]:
        _check_row(row, "orphans")
    um = lin.get("unmatched_adjustments")
    _expect(isinstance(um, list) and all(isinstance(a, dict) and isinstance(a.get("adj_id"), str) and isinstance(a.get("why"), str)
                                         and isinstance(a.get("cell_id"), str) and _is_int(a.get("amount_cents")) for a in um),
            "lineage: unmatched_adjustments is malformed")
    cell_order(cells)
    return lin


# ---------------------------------------------------------------- verify
def apply_formula(cell: dict, values: dict) -> int:
    if cell["op"] == "sum":
        return sum(values[i] for i in cell["inputs"])
    return ratio_bps(sum(values[i] for i in cell["numerator"]), sum(values[i] for i in cell["denominator"]))


def evaluate(lineage: dict, current: dict = None) -> dict:
    """Judge every cell. current is {loan_id: loan} (as load_loans returns) or None to skip the source comparison."""
    cells = lineage["cells"]
    known = {r[0] for c in cells.values() if c["kind"] == "leaf" for r in c["rows"]} | {r[0] for r in lineage["orphans"]}
    by_product = {}
    for lid in sorted(current or {}):
        by_product.setdefault(current[lid]["product"], []).append(current[lid])
    res = {}
    for cid in lineage["order"]:
        c = cells[cid]
        if c["kind"] != "leaf":
            continue
        rows_sum = sum(r[5] for r in c["rows"])
        adj_sum = sum(a["amount_cents"] for a in c["adjustments"])
        residual = c["filed"] - rows_sum - adj_sum
        changed, missing, added, moved_in = [], [], [], []
        if current is not None:
            own = {r[0] for r in c["rows"]}
            for r in c["rows"]:
                cur = current.get(r[0])
                if cur is None:
                    missing.append(r[0])
                    continue
                diffs = [(FIELD_NAME[k], old, cur[k]) for k, old in zip(READ_SET, r[1:]) if cur[k] != old]
                if diffs:
                    changed.append((r[0], diffs))
            for loan in by_product.get(c["rule"]["product"], []):
                if loan["loan_id"] not in own and row_matches(c["rule"], loan):
                    (moved_in if loan["loan_id"] in known else added).append(loan["loan_id"])
        flags = (["UNEXPLAINED"] if residual else []) + (["SOURCE_CHANGED"] if changed or missing or added else [])
        res[cid] = {"kind": "leaf", "flags": flags, "verdict": "+".join(flags) or ("ADJUSTED" if c["adjustments"] else "TRACED"),
                    "filed": c["filed"], "rows": len(c["rows"]), "rows_sum": rows_sum, "adjusted": adj_sum, "residual": residual,
                    "changed": changed, "missing": missing, "added": added, "moved_in": moved_in}
    filed_values = {cid: c["filed"] for cid, c in cells.items()}
    under = {}
    for cid in cell_order(cells):
        c = cells[cid]
        if c["kind"] == "leaf":
            under[cid] = frozenset([cid])
            continue
        under[cid] = frozenset().union(*(under[i] for i in cell_inputs(c)))
        expected = apply_formula(c, filed_values)
        flags = ["DOES_NOT_FOOT"] if expected != c["filed"] else []
        res[cid] = {"kind": "derived", "flags": flags, "verdict": flags[0] if flags else "FOOTS", "filed": c["filed"], "expected": expected,
                    "leaves": sorted(under[cid]), "rows": sum(res[i]["rows"] for i in under[cid]),
                    "leaf_problems": sum(1 for i in under[cid] if res[i]["flags"])}
    leaf = [r for r in res.values() if r["kind"] == "leaf"]
    der = [r for r in res.values() if r["kind"] == "derived"]
    summary = {"cells": len(res), "leaf": len(leaf), "derived": len(der),
               "traced": sum(1 for r in leaf if r["verdict"] == "TRACED"), "adjusted": sum(1 for r in leaf if r["verdict"] == "ADJUSTED"),
               "unexplained": sum(1 for r in leaf if "UNEXPLAINED" in r["flags"]),
               "source_changed": sum(1 for r in leaf if "SOURCE_CHANGED" in r["flags"]),
               "foot": sum(1 for r in der if not r["flags"]), "do_not_foot": sum(1 for r in der if r["flags"]),
               "orphans": len(lineage["orphans"]), "unmatched_adjustments": len(lineage["unmatched_adjustments"]),
               "needs_person": sum(1 for r in res.values() if r["flags"]), "source_compared": current is not None}
    return {"cells": res, "summary": summary}


# ---------------------------------------------------------------- output
def fmt_value(cell: dict, v: int) -> str:
    return f"{v} bps" if cell["kind"] == "derived" and cell["op"] == "ratio_bps" else money(v)


def change_lines(r: dict) -> list:
    out = []
    for x, diffs in r["changed"]:
        out.append(x + " " + ", ".join("%s %s -> %s" % d for d in diffs))
    out += [f"{x} is no longer in the source" for x in r["missing"]]
    out += [f"{x} fits the rule now and was not in the cell at filing" for x in r["added"]]
    return out


def describe(lineage: dict, r: dict, cid: str) -> str:
    cell = lineage["cells"][cid]
    parts = []
    if "UNEXPLAINED" in r["flags"]:
        parts.append(f"{money(r['residual'])} of the filed value is in no source row and no logged adjustment")
    if "SOURCE_CHANGED" in r["flags"]:
        lines = change_lines(r)
        more = f" and {len(lines) - SHOWN} more" if len(lines) > SHOWN else ""
        parts.append("source changed since filing: " + "; ".join(lines[:SHOWN]) + more)
    if "DOES_NOT_FOOT" in r["flags"]:
        parts.append(f"filed {fmt_value(cell, r['filed'])} but its inputs give {fmt_value(cell, r['expected'])}")
    return "; ".join(parts)


def summary_line(s: dict) -> str:
    return (f"{s['cells']} cells: {s['leaf']} leaf ({s['traced']} traced, {s['adjusted']} adjusted, {s['unexplained']} unexplained, "
            f"{s['source_changed']} with source changes), {s['derived']} derived ({s['foot']} foot, {s['do_not_foot']} do not)")


def render_verify(lineage: dict, ev: dict, fmt: str) -> str:
    s = ev["summary"]
    flagged = [cid for cid in lineage["order"] if ev["cells"][cid]["flags"]]
    tail = (f"{s['needs_person']} cells need a person; open loans in no cell: {s['orphans']}; "
            f"logged adjustments that match no leaf cell: {s['unmatched_adjustments']}")
    if fmt == "github":
        lines = []
        for cid in flagged:
            lines.append("::error::" + escape_annotation(cid + ": " + describe(lineage, ev["cells"][cid], cid)))
        if s["orphans"]:
            lines.append("::warning::" + escape_annotation(f"{s['orphans']} open loans are in no cell, first {lineage['orphans'][0][0]}"))
        for a in lineage["unmatched_adjustments"]:
            lines.append("::warning::" + escape_annotation(f"adjustment {a['adj_id']} {a['why']}: {a['cell_id']}"))
        lines.append("::notice::" + escape_annotation(summary_line(s) + "; " + tail))
        return "\n".join(lines)
    lines = [summary_line(s)]
    if not s["source_compared"]:
        lines.append("source not compared")
    for cid in flagged:
        r = ev["cells"][cid]
        lines.append(f"  {one_line(cid):<20} {r['verdict']:<24} {one_line(describe(lineage, r, cid))}")
    for a in lineage["unmatched_adjustments"]:
        lines.append(f"  adjustment {one_line(a['adj_id'])} {a['why']}: {one_line(a['cell_id'])}")
    if s["orphans"]:
        lines.append(f"  open loans in no cell: {s['orphans']}, first {one_line(lineage['orphans'][0][0])}")
    lines.append("result: " + (tail if s["needs_person"] or s["orphans"] or s["unmatched_adjustments"] else "nothing needs a person"))
    return "\n".join(lines)


def render_trace(lineage: dict, ev: dict, cid: str) -> str:
    cell, r = lineage["cells"][cid], ev["cells"][cid]
    out = [f"cell {one_line(cid)}   {one_line(cell['label'])}   {cell['kind']}   filed {fmt_value(cell, cell['filed'])}"]
    if cell["kind"] == "leaf":
        rule = cell["rule"]
        top = "no upper limit" if rule["max"] is None else f"to {rule['max']}"
        out.append(f"  rule: product {one_line(rule['product'])}, status {one_line(rule['status'])}, booked on or before {rule['as_of']}, "
                   f"days past due {rule['min']} {top}")
        out.append(f"  source rows at filing: {r['rows']}, sum {money(r['rows_sum'])}" + ("   (no loan matched this rule)" if not r["rows"] else ""))
        out.append(f"  logged adjustments: {len(cell['adjustments'])}, sum {money(r['adjusted'])}")
        out += [f"    {one_line(a['adj_id'])}  {money(a['amount_cents'])}  {one_line(a['reason'])}" for a in cell["adjustments"]]
        out.append(f"  unexplained amount: {money(r['residual'])}")
        if ev["summary"]["source_compared"]:
            lines = change_lines(r)
            out.append(f"  against the current source: {len(lines)} difference(s)" if lines else "  against the current source: every row is unchanged")
            out += [f"    {one_line(x)}" for x in lines[:SHOWN * 3]]
            if len(lines) > SHOWN * 3:
                out.append(f"    and {len(lines) - SHOWN * 3} more")
            if r["moved_in"]:
                out.append(f"  {len(r['moved_in'])} row(s) fit the rule now but were in another cell at filing; the filed value is unaffected")
        else:
            out.append("  source not compared (give --source)")
    else:
        names = cell["inputs"] if cell["op"] == "sum" else cell["numerator"] + ["/"] + cell["denominator"]
        shown = ", ".join(one_line(n) for n in names[:6]) + (", ..." if len(names) > 6 else "")
        out.append(f"  formula: {cell['op']} of {shown}")
        out.append(f"  the filed inputs give {fmt_value(cell, r['expected'])}: " + ("it foots" if not r["flags"] else "it does not foot"))
        out.append(f"  beneath it: {len(r['leaves'])} leaf cells, {r['rows']} source rows; {r['leaf_problems']} of those cells need a person")
    out.append(f"  verdict: {r['verdict']}")
    return "\n".join(out)


# ---------------------------------------------------------------- command line
def run_build(a) -> int:
    spec = load_spec(a.spec)
    defs = {c["id"]: c for c in spec["cells"]}
    lineage = build_lineage(spec, load_loans(a.source), load_adjustments(a.adjustments) if a.adjustments else [], load_filed(a.filed, defs))
    write_lineage(lineage, a.out)
    leaf = [c for c in lineage["cells"].values() if c["kind"] == "leaf"]
    empty = [cid for cid in lineage["order"] if lineage["cells"][cid]["kind"] == "leaf" and not lineage["cells"][cid]["rows"]]
    print(f"lineage for {len(lineage['cells'])} cells from {sum(len(c['rows']) for c in leaf)} source rows; "
          f"{len(empty)} leaf cells have no rows; {len(lineage['orphans'])} open loans are in no cell; "
          f"{len(lineage['unmatched_adjustments'])} adjustments match no leaf cell")
    print(f"wrote {one_line(a.out)}")
    return 0


def run_verify(a) -> int:
    lineage = load_lineage(a.lineage)
    current = load_loans(a.source, "current source")
    ev = evaluate(lineage, current)
    print(render_verify(lineage, ev, a.format))
    s = ev["summary"]
    if not any(r[0] in current for c in lineage["cells"].values() if c["kind"] == "leaf" for r in c["rows"]):
        print("note: none of the lineage rows is in this source; is it the right file?", file=sys.stderr)
    return 1 if s["needs_person"] or s["orphans"] or s["unmatched_adjustments"] else 0


def run_trace(a) -> int:
    lineage = load_lineage(a.lineage)
    _expect(a.cell in lineage["cells"], f"no cell {a.cell!r} in the lineage")
    ev = evaluate(lineage, load_loans(a.source, "current source") if a.source else None)
    print(render_trace(lineage, ev, a.cell))
    return 0


def run_demo() -> int:
    d = DATA_DIR
    spec = load_spec(os.path.join(d, "example_report_spec.json"))
    defs = {c["id"]: c for c in spec["cells"]}
    lineage = build_lineage(spec, load_loans(os.path.join(d, "example_loans_filed.csv")),
                            load_adjustments(os.path.join(d, "example_adjustments.csv")),
                            load_filed(os.path.join(d, "example_report_filed.csv"), defs))
    ev = evaluate(lineage, load_loans(os.path.join(d, "example_loans_now.csv")))
    print(render_verify(lineage, ev, "text"))
    first = next((cid for cid in lineage["order"] if "SOURCE_CHANGED" in ev["cells"][cid]["flags"]), None)
    if first:
        print(render_trace(lineage, ev, first))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="report_trace")
    ap.add_argument("--demo", action="store_true", help="run on the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="capture lineage from the source as it stood at filing")
    b.add_argument("--source", required=True)
    b.add_argument("--spec", required=True)
    b.add_argument("--filed", required=True)
    b.add_argument("--adjustments")
    b.add_argument("--out", required=True)
    v = sub.add_parser("verify", help="check every cell against the lineage and a current copy of the source")
    v.add_argument("--lineage", required=True)
    v.add_argument("--source", required=True)
    v.add_argument("--format", choices=["text", "github"], default="text")
    t = sub.add_parser("trace", help="print the path from one cell to its source rows")
    t.add_argument("--lineage", required=True)
    t.add_argument("--cell", required=True)
    t.add_argument("--source")
    a = ap.parse_args(argv)
    try:
        if a.demo:
            return run_demo()
        if a.cmd:
            return {"build": run_build, "verify": run_verify, "trace": run_trace}[a.cmd](a)
    except InputError as e:
        print("input error: " + one_line(e), file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
