"""A small mapping used by the unit tests, so a test shows the whole rule it checks."""
import csv
import json
import os

import _bootstrap  # noqa: F401
import iso20022_map_check as tool

LEGACY = [
    {"field": "NM", "max_len": "10", "kind": "text", "codes": ""},
    {"field": "AMT", "max_len": "12", "kind": "amount", "codes": ""},
    {"field": "DT", "max_len": "8", "kind": "date", "codes": ""},
    {"field": "CD", "max_len": "1", "kind": "code", "codes": "A|B"},
    {"field": "L1", "max_len": "5", "kind": "text", "codes": ""},
    {"field": "L2", "max_len": "5", "kind": "text", "codes": ""},
    {"field": "NOTE", "max_len": "5", "kind": "text", "codes": ""},
]
ISO = [
    {"path": "Nm", "max_len": "10", "kind": "text", "mandatory": "N", "codes": ""},
    {"path": "Amt", "max_len": "19", "kind": "decimal", "mandatory": "Y", "codes": ""},
    {"path": "Dt", "max_len": "10", "kind": "date", "mandatory": "Y", "codes": ""},
    {"path": "Code", "max_len": "4", "kind": "code", "mandatory": "N", "codes": "AAAA|BBBB"},
    {"path": "Text", "max_len": "11", "kind": "text", "mandatory": "N", "codes": ""},
    {"path": "Ref", "max_len": "8", "kind": "text", "mandatory": "Y", "codes": ""},
]
MAPPING = [
    {"row_id": "R1", "legacy_fields": "NM", "iso_path": "Nm", "transform": "copy", "param": ""},
    {"row_id": "R2", "legacy_fields": "AMT", "iso_path": "Amt", "transform": "amount_implied2", "param": ""},
    {"row_id": "R3", "legacy_fields": "DT", "iso_path": "Dt", "transform": "date_yyyymmdd", "param": ""},
    {"row_id": "R4", "legacy_fields": "CD", "iso_path": "Code", "transform": "code_table", "param": "cd"},
    {"row_id": "R5", "legacy_fields": "L1|L2", "iso_path": "Text", "transform": "join_lines", "param": " "},
    {"row_id": "R6", "legacy_fields": "", "iso_path": "Ref", "transform": "const", "param": "NOREF"},
    {"row_id": "R7", "legacy_fields": "NOTE", "iso_path": "", "transform": "drop", "param": ""},
]
TABLES = {"cd": {"A": "AAAA", "B": "BBBB"}}
GOOD_SOURCE = {"NM": "ACME      ", "AMT": "000000125050", "DT": "20261024", "CD": "A", "L1": "AB   ", "L2": "CD   ", "NOTE": "x    "}
GOOD_TARGET = {"Nm": "ACME", "Amt": "1250.50", "Dt": "2026-10-24", "Code": "AAAA", "Text": "AB CD", "Ref": "NOREF"}


def rows(base, **changes):
    """A copy of a row list with one row replaced: rows(MAPPING, R1={...})."""
    return [dict(r, **changes.get(r.get("row_id") or r.get("field") or r.get("path"), {})) for r in base]


def bundle(legacy=None, iso=None, mapping=None, tables=None):
    return tool.build_bundle(LEGACY if legacy is None else legacy, ISO if iso is None else iso,
                             MAPPING if mapping is None else mapping, TABLES if tables is None else tables)


def write_dir(directory, legacy=None, iso=None, mapping=None, tables=None):
    for name, data in (("legacy_fields.csv", LEGACY if legacy is None else legacy), ("iso_elements.csv", ISO if iso is None else iso),
                       ("mapping.csv", MAPPING if mapping is None else mapping)):
        with open(os.path.join(directory, name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    with open(os.path.join(directory, "code_tables.json"), "w", encoding="utf-8") as fh:
        json.dump(TABLES if tables is None else tables, fh)
