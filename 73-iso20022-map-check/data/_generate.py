"""Generate the synthetic data for project 73: a legacy payment format, a simplified ISO 20022
credit-transfer element list, a field mapping that has gaps planted in it, and the ISO output of ten
converter builds run over 23 legacy messages.

Everything is seeded, so a rerun reproduces every file byte for byte. Nothing here is a real message,
institution or format. The legacy format ("LCT") is invented. The ISO element names follow the
pacs.008 naming in a flat path view; the lengths and mandatory flags are my simplification.

How the truth is made, and why it is separate from the checker:
  * The mapping under review (mapping.csv) is an intended mapping with two rows removed and one
    code-table entry removed. The removals are written to mapping_truth.csv.
  * Each build is a small converter that implements the reviewed mapping and then applies one
    planted defect (or none). While it converts, it records every place where its output differs
    from the lossless value. Those records are truth_events.csv. No checker code is imported here.
  * Hard negatives are planted on purpose: padded text, amounts written without trailing zeros, an
    explicit drop, constants that fill mandatory elements, values exactly at a limit.

Run (from data/):  python3 _generate.py
Writes: legacy_fields.csv, iso_elements.csv, mapping.csv, code_tables.json, legacy_messages.json,
        iso_outputs.json, builds.csv, truth_events.csv, mapping_truth.csv, example_pairs.json
"""
from __future__ import annotations

import csv
import json
import os
import random
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
rng = random.Random(73)

# (field, max_len, kind, codes)
LEGACY = [
    ("SNDREF", 16, "text", ""), ("TYP", 2, "code", "10|15|16"), ("AMT", 12, "amount", ""), ("VALDT", 8, "date", ""),
    ("SNDID", 9, "digits", ""), ("RCVID", 9, "digits", ""), ("CHGS", 1, "code", "S|B|O"),
    ("ORGNM", 35, "text", ""), ("ORGAD1", 35, "text", ""), ("ORGAD2", 35, "text", ""), ("ORGAD3", 35, "text", ""),
    ("BENNM", 35, "text", ""), ("BENAD1", 35, "text", ""), ("BENAD2", 35, "text", ""), ("BENACC", 35, "text", ""),
    ("OBI1", 35, "text", ""), ("OBI2", 35, "text", ""), ("OBI3", 35, "text", ""), ("OBI4", 35, "text", ""),
    ("INTNOTE", 35, "text", ""),
]
LEGACY_MAX = {f: m for f, m, _k, _c in LEGACY}
LEGACY_NAMES = [f for f, _m, _k, _c in LEGACY]

# (path, max_len, kind, mandatory, codes)
ISO = [
    ("GrpHdr/MsgId", 35, "text", "Y", ""), ("PmtId/InstrId", 35, "text", "N", ""),
    ("PmtId/EndToEndId", 35, "text", "Y", ""), ("PmtId/TxId", 35, "text", "N", ""),
    ("PmtTpInf/LclInstrm/Prtry", 35, "text", "N", ""),
    ("IntrBkSttlmAmt", 19, "decimal", "Y", ""), ("IntrBkSttlmAmt@Ccy", 3, "text", "Y", ""),
    ("IntrBkSttlmDt", 10, "date", "Y", ""), ("ChrgBr", 4, "code", "Y", "DEBT|CRED|SHAR|SLEV"),
    ("InstgAgt/MmbId", 35, "text", "N", ""), ("InstdAgt/MmbId", 35, "text", "N", ""),
    ("Dbtr/Nm", 140, "text", "Y", ""), ("Dbtr/PstlAdr/AdrLine[0]", 70, "text", "N", ""),
    ("Dbtr/PstlAdr/AdrLine[1]", 70, "text", "N", ""), ("Dbtr/PstlAdr/AdrLine[2]", 70, "text", "N", ""),
    ("Cdtr/Nm", 140, "text", "Y", ""), ("Cdtr/PstlAdr/AdrLine[0]", 70, "text", "N", ""),
    ("Cdtr/PstlAdr/AdrLine[1]", 70, "text", "N", ""), ("CdtrAcct/Id/Othr/Id", 34, "text", "N", ""),
    ("RmtInf/Ustrd", 140, "text", "N", ""),
]
ISO_MAX = {p: m for p, m, _k, _o, _c in ISO}

# The intended mapping. The two rows marked REMOVED are not in the mapping under review.
FULL = [
    ("SNDREF", "GrpHdr/MsgId", "copy", ""),  # REMOVED
    ("SNDREF", "PmtId/InstrId", "copy", ""),
    ("", "PmtId/EndToEndId", "const", "NOTPROVIDED"),
    ("SNDREF", "PmtId/TxId", "copy", ""),
    ("TYP", "PmtTpInf/LclInstrm/Prtry", "code_table", "typ"),
    ("AMT", "IntrBkSttlmAmt", "amount_implied2", ""),
    ("", "IntrBkSttlmAmt@Ccy", "const", "USD"),
    ("VALDT", "IntrBkSttlmDt", "date_yyyymmdd", ""),
    ("SNDID", "InstgAgt/MmbId", "copy", ""),
    ("RCVID", "InstdAgt/MmbId", "copy", ""),
    ("CHGS", "ChrgBr", "code_table", "chgs"),
    ("ORGNM", "Dbtr/Nm", "copy", ""),
    ("ORGAD1", "Dbtr/PstlAdr/AdrLine[0]", "copy", ""),
    ("ORGAD2", "Dbtr/PstlAdr/AdrLine[1]", "copy", ""),
    ("ORGAD3", "Dbtr/PstlAdr/AdrLine[2]", "copy", ""),  # REMOVED
    ("BENNM", "Cdtr/Nm", "copy", ""),
    ("BENAD1", "Cdtr/PstlAdr/AdrLine[0]", "copy", ""),
    ("BENAD2", "Cdtr/PstlAdr/AdrLine[1]", "copy", ""),
    ("BENACC", "CdtrAcct/Id/Othr/Id", "copy", ""),
    ("OBI1|OBI2|OBI3|OBI4", "RmtInf/Ustrd", "join_lines", " "),
    ("INTNOTE", "", "drop", ""),
]
REMOVED_PATHS = ("GrpHdr/MsgId", "Dbtr/PstlAdr/AdrLine[2]")
TABLES_FULL = {"typ": {"10": "CUSTOMER", "15": "BANK", "16": "DRAWDOWN"}, "chgs": {"S": "SHAR", "B": "DEBT", "O": "CRED"}}
TABLES_REVIEWED = {"typ": dict(TABLES_FULL["typ"]), "chgs": {"S": "SHAR", "B": "DEBT"}}  # "O" removed
CODE_FALLBACK = {"chgs": "SHAR"}  # what the converters do with a code the table lacks

BUILDS = [
    ("B01", "none", "", "", "", "clean converter, no variation"),
    ("B02", "none", "", "", "pad|amount_min", "clean, but pads text with spaces and writes amounts without trailing zeros"),
    ("B03", "cut_early", "ORGNM", "33", "", "originator name cut at 33 characters; the limit is 140"),
    ("B04", "cut_early", "ORGAD2", "33", "", "second originator address line cut at 33 characters; the limit is 70"),
    ("B05", "drop_field", "RCVID", "", "", "receiver identifier never written"),
    ("B06", "amount_round", "AMT", "", "", "amount rounded to whole units"),
    ("B07", "date_swap", "VALDT", "", "", "month and day swapped in the value date"),
    ("B08", "strip_zeros", "BENACC", "", "", "leading zeros removed from the beneficiary account"),
    ("B09", "lines_swapped", "ORGAD1", "", "", "first two originator address lines swapped"),
    ("B10", "cond_drop", "BENACC", "TYP=16 and CHGS=S", "", "beneficiary account dropped when TYP is 16 and CHGS is S"),
]

ADJ = ["NORTH", "RIVER", "SUMMIT", "HARBOR", "CEDAR", "LAKESIDE", "PRAIRIE", "GRANITE", "MAPLE", "COPPER", "BLUE", "SILVER"]
NOUN = ["FREIGHT", "TIMBER", "MACHINE", "PACKAGING", "LOGISTICS", "FOODS", "TEXTILE", "SUPPLY", "DESIGN", "CLEANING", "PRINT", "TOOLING"]
SUF = ["LLC", "INC", "LTD", "CO", "GROUP", "PARTNERS"]
STREETS = ["WILLOW", "ELM", "LAKEVIEW", "CHURCH", "MILL", "HIGHLAND", "ORCHARD", "STATION", "MEADOW", "QUARRY"]
KINDS = ["STREET", "AVENUE", "ROAD", "LANE"]
CITIES = ["FAIRVIEW", "GREENVILLE", "RIVERTON", "OAKDALE", "BROOKFIELD", "SPRINGDALE", "HILLCREST", "WESTPORT"]
STATES = ["OH", "TX", "WA", "GA", "MN", "NC", "CO", "AZ"]
WORDS = ["INVOICE", "PAYMENT", "ORDER", "REF", "SETTLEMENT", "PURCHASE", "DELIVERY", "SERVICES", "MONTHLY", "RENEWAL", "FINAL", "BALANCE", "ACCOUNT", "PERIOD"]
DIGITS = "0123456789" * 40


def pick(seq):
    return seq[rng.randrange(len(seq))]


def party_name() -> str:
    while True:
        parts = [pick(ADJ), pick(NOUN)] + ([pick(NOUN)] if rng.random() < 0.3 else []) + [pick(SUF)]
        text = " ".join(parts)
        if len(text) <= 32 and len(set(parts)) == len(parts):
            return text


def street() -> str:
    return "%d %s %s" % (rng.randrange(10, 9999), pick(STREETS), pick(KINDS))


def city_line() -> str:
    return "%s %s %d" % (pick(CITIES), pick(STATES), rng.randrange(10000, 99999))


def fill(size: int) -> str:
    text = ""
    while len(text) < size:
        text += pick(WORDS) + " "
    return text[:size].rstrip()


def long_obi() -> list:
    while True:
        lines = []
        for _ in range(4):
            line = fill(35)
            while len(line) < 34:
                line = fill(35)
            lines.append(line)
        if sum(len(x) for x in lines) + 3 > 140:
            return lines


def typical_message(i: int, long_obi_idx: set, o_idx: set, sixteen_idx: set) -> dict:
    typ = "16" if i in sixteen_idx else ("10" if rng.random() < 0.65 else "15")
    chgs = "O" if i in o_idx else ("B" if typ == "16" else ("S" if rng.random() < 0.55 else "B"))
    cents = rng.randrange(10000, 25000000)
    if rng.random() < 0.25:
        cents -= cents % 100
    month, day = rng.randrange(10, 13), rng.randrange(1, 29)
    acct_len = rng.randrange(8, 21)
    first = "0" if rng.random() < 0.45 else str(rng.randrange(1, 10))
    acct = first + "".join(str(rng.randrange(10)) for _ in range(acct_len - 1))
    if i in long_obi_idx:
        obi = long_obi()
    else:
        obi = [fill(rng.randrange(10, 30)) for _ in range(rng.randrange(1, 3))]
    msg = {
        "SNDREF": "R" + "".join(str(rng.randrange(10)) for _ in range(rng.randrange(9, 16))),
        "TYP": typ, "AMT": "%012d" % cents, "VALDT": "2026%02d%02d" % (month, day),
        "SNDID": "".join(str(rng.randrange(10)) for _ in range(9)),
        "RCVID": "".join(str(rng.randrange(10)) for _ in range(9)),
        "CHGS": chgs, "ORGNM": party_name(), "ORGAD1": street(), "ORGAD2": city_line(),
        "ORGAD3": pick(["SUITE 210", "FLOOR 3", "UNIT 12"]) if rng.random() < 0.4 else "",
        "BENNM": party_name(), "BENAD1": street(), "BENAD2": city_line(), "BENACC": acct,
        "INTNOTE": "TKT %d" % rng.randrange(1000, 9999) if rng.random() < 0.5 else "",
    }
    for n in range(4):
        msg["OBI%d" % (n + 1)] = obi[n] if n < len(obi) else ""
    return {f: msg[f].ljust(LEGACY_MAX[f]) for f in LEGACY_NAMES}


def probe_messages() -> dict:
    """Boundary messages: every field filled to its limit with a position pattern, codes cycled."""
    n_probes = max(len(c.split("|")) for _f, _m, k, c in LEGACY if k == "code")
    out = {}
    for k in range(n_probes):
        msg = {}
        for idx, (field, size, kind, codes) in enumerate(LEGACY):
            if kind == "code":
                value = codes.split("|")[k % len(codes.split("|"))]
            elif kind == "amount":
                value = "123456789012"[:size]
            elif kind == "date":
                value = "20261231"[:size]
            else:
                value = DIGITS[idx % 10: idx % 10 + size]
            msg[field] = value.ljust(size)
        out["P%d" % (k + 1)] = msg
    return out


def reviewed_rows() -> list:
    rows = []
    for fields, path, transform, param in FULL:
        if path in REMOVED_PATHS:
            continue
        rows.append({"row_id": "R%02d" % (len(rows) + 1), "fields": [f for f in fields.split("|") if f],
                     "iso_path": path, "transform": transform, "param": param})
    return rows


def convert(msg: dict, build: tuple, rows: list, counter: int):
    """A converter that implements the reviewed mapping, then applies the build's planted defect.
    Returns (iso element dict, events). An event is (subject, kind, category)."""
    _b, defect, dfield, dparam, benign, _d = build
    out, events = {}, []
    mapped = {f for r in rows for f in r["fields"]}
    for f in LEGACY_NAMES:
        if f not in mapped and msg[f].strip():
            events.append((f, "unmapped_lost", "mapping"))
    out["GrpHdr/MsgId"] = "MSG%06d" % counter
    events.append(("GrpHdr/MsgId", "generated_value", "mapping"))
    for r in rows:
        t, path = r["transform"], r["iso_path"]
        if t == "drop":
            continue
        vals = [msg[f].strip() for f in r["fields"]]
        if t == "const":
            val = r["param"]
        elif t == "copy":
            val = vals[0]
        elif t == "join_lines":
            val = r["param"].join(v for v in vals if v)
        elif t == "amount_implied2":
            val = "%d.%02d" % divmod(int(vals[0]), 100) if vals[0] else ""
        elif t == "date_yyyymmdd":
            val = "%s-%s-%s" % (vals[0][:4], vals[0][4:6], vals[0][6:]) if vals[0] else ""
        else:
            table = TABLES_REVIEWED[r["param"]]
            if not vals[0]:
                val = ""
            elif vals[0] in table:
                val = table[vals[0]]
            else:
                val = CODE_FALLBACK[r["param"]]
                events.append(("%s=%s" % (r["fields"][0], vals[0]), "code_fallback", "mapping"))
        if not val:
            continue
        if len(val) > ISO_MAX[path]:
            val = val[:ISO_MAX[path]]
            events.append((path, "capacity_cut", "capacity"))
        mine = r["fields"] == [dfield]
        before = val
        if defect == "cut_early" and mine:
            val = val[:int(dparam)]
        elif defect == "drop_field" and mine:
            val = ""
        elif defect == "cond_drop" and mine and msg["TYP"].strip() == "16" and msg["CHGS"].strip() == "S":
            val = ""
        elif defect == "amount_round" and t == "amount_implied2":
            rounded = Decimal(val).quantize(Decimal(1), ROUND_HALF_UP)
            if rounded != Decimal(val):  # a whole-dollar amount survives rounding unchanged
                val = str(rounded)
        elif defect == "date_swap" and t == "date_yyyymmdd":
            y, m, d = val.split("-")
            val = "%s-%s-%s" % (y, d, m)
        elif defect == "strip_zeros" and mine and val.startswith("0"):
            val = val.lstrip("0") or "0"
        if val != before:
            events.append((path, defect, "converter"))
        before = val
        if "pad" in benign.split("|") and t == "copy" and LEGACY_MAX[r["fields"][0]] <= ISO_MAX[path]:
            val = val.ljust(LEGACY_MAX[r["fields"][0]])
        if "amount_min" in benign.split("|") and t == "amount_implied2" and "." in val:
            val = val.rstrip("0").rstrip(".")
        if val != before:
            events.append((path, "benign_" + ("pad" if t == "copy" else "amount_format"), "benign"))
        if val.strip():
            out[path] = val
    if defect == "lines_swapped":
        a, b = "Dbtr/PstlAdr/AdrLine[0]", "Dbtr/PstlAdr/AdrLine[1]"
        if a in out and b in out and out[a].strip() != out[b].strip():
            out[a], out[b] = out[b], out[a]
            events.append((a, "lines_swapped", "converter"))
            events.append((b, "lines_swapped", "converter"))
    return out, events


def write_csv(name: str, header: list, rows: list) -> None:
    with open(os.path.join(HERE, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_json(name: str, obj) -> None:
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")


def main() -> None:
    long_idx = set(rng.sample(range(20), 3))
    o_idx = {2, 9, 14}
    sixteen_idx = {4, 11, 17}
    messages = {"M%02d" % (i + 1): typical_message(i, long_idx, o_idx, sixteen_idx) for i in range(20)}
    messages.update(probe_messages())
    rows = reviewed_rows()

    write_csv("legacy_fields.csv", ["field", "max_len", "kind", "codes"], LEGACY)
    write_csv("iso_elements.csv", ["path", "max_len", "kind", "mandatory", "codes"], ISO)
    write_csv("mapping.csv", ["row_id", "legacy_fields", "iso_path", "transform", "param"],
              [[r["row_id"], "|".join(r["fields"]), r["iso_path"], r["transform"], r["param"]] for r in rows])
    write_json("code_tables.json", TABLES_REVIEWED)
    write_json("legacy_messages.json", messages)

    outputs, events = {}, []
    counter = 0
    for build in BUILDS:
        outputs[build[0]] = {}
        for msg_id in sorted(messages):
            counter += 1
            iso, ev = convert(messages[msg_id], build, rows, counter)
            outputs[build[0]][msg_id] = iso
            events.extend((build[0], msg_id, s, k, c) for s, k, c in ev)
    lines = ["{"]
    for i, b in enumerate(sorted(outputs)):
        lines.append("%s: %s%s" % (json.dumps(b), json.dumps(outputs[b], sort_keys=True, separators=(",", ":")),
                                   "," if i < len(outputs) - 1 else ""))
    lines.append("}")
    with open(os.path.join(HERE, "iso_outputs.json"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    iso_of = {r["fields"][0]: r["iso_path"] for r in rows if len(r["fields"]) == 1 and r["transform"] != "drop"}
    write_csv("builds.csv", ["build", "defect", "legacy_field", "iso_path", "param", "benign", "description"],
              [[b, d, f, iso_of.get(f, ""), p, bn, desc] for b, d, f, p, bn, desc in BUILDS])
    write_csv("truth_events.csv", ["build", "msg", "subject", "kind", "category"], sorted(set(events)))
    write_csv("mapping_truth.csv", ["kind", "subject", "planted"], [
        ["legacy_unmapped", "ORGAD3", "yes"], ["iso_mandatory_unsourced", "GrpHdr/MsgId", "yes"],
        ["code_not_covered", "CHGS=O", "yes"], ["capacity_overflow", "CdtrAcct/Id/Othr/Id", "yes"],
        ["capacity_overflow", "RmtInf/Ustrd", "yes"],
        ["legacy_unmapped", "INTNOTE", "no"], ["iso_mandatory_unsourced", "PmtId/EndToEndId", "no"],
        ["iso_mandatory_unsourced", "IntrBkSttlmAmt@Ccy", "no"]])

    def first_event(build, kind):
        for b, m, _s, k, _c in sorted(set(events)):
            if b == build and k == kind and not m.startswith("P"):
                return m
        raise SystemExit("no %s event in %s" % (kind, build))

    pick_pairs = [("B03", "P1"), ("B06", first_event("B06", "amount_round")), ("B01", "M01")]
    write_json("example_pairs.json", {"pairs": [
        {"pair_id": "%s-%s" % (b, m), "source": messages[m], "target": outputs[b][m]} for b, m in pick_pairs]})


if __name__ == "__main__":
    main()
