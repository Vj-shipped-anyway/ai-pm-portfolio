#!/usr/bin/env python3
"""narrative-trace: trace every sentence of a case narrative to the transaction it cites.

A narrative cites its evidence as [txn: ID] or [txn: ID, ID]. This tool splits the narrative into
sentences, looks each cited ID up in a transactions file and compares what the sentence says with
the record. Standard library only, Python 3.9 or newer.

    python3 narrative_trace.py check narrative.txt txns.csv --case C-007
    python3 narrative_trace.py --demo

Transactions file (CSV, UTF-8): txn_id, date (YYYY-MM-DD), amount (plain number), direction (in or out),
channel, counterparty; case_id is optional and is needed for --case.

What is compared, for the records a sentence cites
  amount     a figure written with $ or USD (9,812.40  9,812  9.8k) must equal a cited amount, or the sum
             of the cited amounts. A figure is rounded to the precision it is written with.
  date       a date (2026-03-03, March 3, 2026, 3 March 2026) must be the date of a cited record
  party      a counterparty named in the file, anywhere in it, must be one a cited record names
  direction  words such as deposited, received, sent, paid must agree with a cited record
  channel    cash, wire, ACH, check, card must be the channel of a cited record
  count      "three deposits" must match the number of distinct IDs cited

A sentence is "traced" when it cites at least one record, every ID exists (and belongs to --case),
and every fact it states matches. A sentence that cites a real record but states none of the facts
above is "unchecked": the tool cannot say whether it is true, and it says so.

Exit status: 0 nothing untraced, 1 at least one sentence is not traced, 2 for input that cannot be read.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import io
import os
import re
import sys
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
MAX_BYTES = 5_000_000

REQUIRED = ("txn_id", "date", "amount", "direction", "channel", "counterparty")
FACTS = ("amount", "date", "party", "direction", "channel", "count")
UNTRACED = ("uncited", "dangling", "other_case", "mismatch")
LABEL = {"uncited": "uncited", "dangling": "dangling citation", "other_case": "other case", "amount": "amount mismatch",
         "date": "date mismatch", "party": "party mismatch", "direction": "direction mismatch",
         "channel": "channel mismatch", "count": "count mismatch", "unchecked": "unchecked"}

CITE = re.compile(r"\[\s*txn\s*:\s*([^\]]*)\]", re.I)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class InputError(Exception):
    """Input that cannot be read. Reported as one line on stderr, exit status 2."""


# ---------------------------------------------------------------- reading input
def read_text(path: str, label: str) -> str:
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except OSError as e:
        raise InputError("cannot read %s %r: %s" % (label, path, e.strerror or e))
    if len(raw) > MAX_BYTES:
        raise InputError("%s %r is larger than %d bytes" % (label, path, MAX_BYTES))
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InputError("%s %r is not UTF-8 text" % (label, path))
    if "\x00" in text:
        raise InputError("%s %r is not a text file" % (label, path))
    return text


class Ledger:
    """The transactions file: records by ID, plus one pattern that finds every counterparty name in a sentence."""

    def __init__(self, records: list, has_case: bool):
        self.by_id = {r["id"]: r for r in records}
        self.has_case = has_case
        names = sorted({r["party"].lower() for r in records if len(r["party"]) >= 3}, key=lambda n: (-len(n), n))
        self.names_re = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in names) + r")(?!\w)", re.I) if names else None

    def case_ids(self) -> set:
        return {r["case"] for r in self.by_id.values()}


def load_records(path: str) -> Ledger:
    text = read_text(path, "transactions file")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        header = reader.fieldnames
        rows = list(reader)
    except csv.Error as e:
        raise InputError("transactions file is not valid CSV: %s" % e)
    if not header:
        raise InputError("transactions file is empty")
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise InputError("transactions file lacks column(s): " + ", ".join(missing))
    if not rows:
        raise InputError("transactions file has a header and no rows")
    records, seen = [], set()
    for n, row in enumerate(rows, 2):
        if None in row or any(v is None for v in row.values()):
            raise InputError("transactions line %d: wrong number of fields" % n)
        rid = row["txn_id"].strip()
        if not rid:
            raise InputError("transactions line %d: txn_id is empty" % n)
        if rid in seen:
            raise InputError("transactions line %d: duplicate txn_id %r" % (n, rid))
        seen.add(rid)
        day, amount = row["date"].strip(), row["amount"].strip()
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
            raise InputError("transactions line %d: date %r is not YYYY-MM-DD" % (n, day))
        try:
            when = datetime.date.fromisoformat(day)
        except ValueError:
            raise InputError("transactions line %d: date %r does not exist" % (n, day))
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", amount):
            raise InputError("transactions line %d: amount %r is not a plain number" % (n, amount))
        direction = row["direction"].strip().lower()
        if direction not in ("in", "out"):
            raise InputError("transactions line %d: direction %r is not in or out" % (n, direction))
        channel = row["channel"].strip().lower()
        if not channel:
            raise InputError("transactions line %d: channel is empty" % n)
        records.append({"id": rid, "case": (row.get("case_id") or "").strip(), "date": when, "amount": Decimal(amount),
                        "direction": direction, "channel": channel, "party": row["counterparty"].strip()})
    return Ledger(records, "case_id" in header)


# ---------------------------------------------------------------- sentences
ABBREV = frozenset(["inc", "ltd", "corp", "co", "st", "no", "mr", "ms", "mrs", "dr", "vs", "approx", "jr", "sr",
                    "ave", "dept", "e.g", "i.e", "u.s"])
_TERM = re.compile(r"[.!?]+[\"')\]]*")
_TOKEN = re.compile(r"(?<![A-Za-z.])([A-Za-z]+(?:\.[A-Za-z]+)*)$")
_BREAK = re.compile(r"\n[ \t\r]*\n")


def split_sentences(text: str) -> list:
    """Sentences as {"start", "end", "text"} offsets into text. A blank line ends a sentence. A period after an
    abbreviation, an initial or a digit does not. A citation that follows the period belongs to the sentence before it."""
    out, pos = [], 0
    for m in list(_BREAK.finditer(text)) + [None]:
        stop = m.start() if m else len(text)
        out.extend(_split_paragraph(text, pos, stop))
        if m:
            pos = m.end()
    return out


def _split_paragraph(text: str, lo: int, hi: int) -> list:
    found, start, i = [], lo, lo
    while True:
        m = _TERM.search(text, i, hi)
        if m is None:
            break
        i = m.end()
        if i < hi and not text[i].isspace():
            continue
        if m.group().rstrip("\"')]") == ".":
            tok = _TOKEN.search(text, max(start, m.start() - 40), m.start())
            if tok and (tok.group(1).lower() in ABBREV or (len(tok.group(1)) == 1 and tok.group(1).isupper())):
                continue
        k = i
        while k < hi and text[k].isspace():
            k += 1
        if k < hi and text[k].islower():
            continue
        end = i
        while True:
            c = CITE.match(text, k, hi)
            if not c:
                break
            end = k = c.end()
            t = _TERM.match(text, end, hi)
            if t:
                end = k = t.end()
            while k < hi and text[k] in " \t":
                k += 1
        _add(found, text, start, end)
        start = i = end
    _add(found, text, start, hi)
    return found


def _add(found: list, text: str, start: int, end: int) -> None:
    while start < end and text[start].isspace():
        start += 1
    chunk = text[start:end].rstrip()
    if any(ch.isalnum() for ch in chunk):
        found.append({"start": start, "end": start + len(chunk), "text": chunk})


# ---------------------------------------------------------------- facts a sentence states
MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
          "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
          "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
AMOUNT = re.compile(r"(?<![\w.,])(\$\s?)?" + _NUM + r"(?:\s?(k|thousand|million)\b)?(\s?USD\b)?(?!\d)", re.I)
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
DATE_MDY = re.compile(r"\b(" + _MON + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)
DATE_DMY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + _MON + r")\.?,?\s+(\d{4})\b", re.I)
NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "eleven": 11, "twelve": 12}
COUNT = re.compile(r"(?<![\d,.$])\b(\d+|" + "|".join(NUMWORDS) + r")\s+(?:[a-z-]+\s+)?"
                   r"(?:deposits|withdrawals|payments|transfers|transactions|wires|checks|purchases|credits|debits)\b", re.I)
IN_WORDS = re.compile(r"\b(?:deposited|received|credited|incoming|inbound)\b", re.I)
OUT_WORDS = re.compile(r"\b(?:sent|paid|withdrew|withdrawn|debited|outgoing|outbound)\b", re.I)
CHANNEL_WORDS = {"cash": re.compile(r"\bcash\b(?!-)", re.I), "wire": re.compile(r"\bwire[sd]?\b", re.I),
                 "ach": re.compile(r"\bach\b", re.I), "check": re.compile(r"\b(?:check|cheque)s?\b", re.I),
                 "card": re.compile(r"\bcard\b", re.I)}


def amounts_in(text: str) -> list:
    """(position, as written, value, tolerance) for each figure written with $ or USD."""
    out = []
    for m in AMOUNT.finditer(text):
        dollar, whole, frac, suffix, usd = m.groups()
        if not dollar and not usd:
            continue
        scale = 1 if not suffix else 1000000 if suffix.lower() == "million" else 1000
        places = len(frac) - 1 if frac else 0
        out.append((m.start(), m.group().strip(), Decimal(whole.replace(",", "") + (frac or "")) * scale,
                    Decimal("0.5") * Decimal(10) ** -places * scale))
    return out


def dates_in(text: str) -> list:
    """(position, as written, date or None when the day does not exist) for each date."""
    def make(y, mo, d):
        try:
            return datetime.date(int(y), int(mo), int(d))
        except ValueError:
            return None
    out = [(m.start(), m.group(), make(m.group(1), m.group(2), m.group(3))) for m in DATE_ISO.finditer(text)]
    out += [(m.start(), m.group(), make(m.group(3), MONTHS[m.group(1).lower()], m.group(2))) for m in DATE_MDY.finditer(text)]
    out += [(m.start(), m.group(), make(m.group(3), MONTHS[m.group(2).lower()], m.group(1))) for m in DATE_DMY.finditer(text)]
    return sorted(out, key=lambda f: f[0])


def counts_in(text: str) -> list:
    return [(m.group(), int(m.group(1)) if m.group(1).isdigit() else NUMWORDS[m.group(1).lower()]) for m in COUNT.finditer(text)]


def direction_in(text: str):
    heard_in, heard_out = bool(IN_WORDS.search(text)), bool(OUT_WORDS.search(text))
    return "in" if heard_in and not heard_out else "out" if heard_out and not heard_in else None


def channels_in(text: str) -> list:
    """(channel, as written) for each channel the sentence names."""
    return [(name, m.group()) for name, pat in CHANNEL_WORDS.items() for m in [pat.search(text)] if m]


# ---------------------------------------------------------------- tracing
def _shown(rec_list: list, field) -> str:
    return ", ".join("%s %s" % (r["id"], field(r)) for r in rec_list)


def check_facts(text: str, cited: list, ledger: Ledger, facts, sums: bool, rounding: bool) -> tuple:
    """Compare the facts in text with the cited records. Returns (findings, number of facts found)."""
    findings, found = [], 0
    if "amount" in facts:
        pool = [r["amount"] for r in cited]
        if sums and len(cited) > 1:
            pool.append(sum(pool))
        for _, shown, value, tol in amounts_in(text):
            found += 1
            if not any(abs(value - c) <= (tol if rounding else Decimal("0.005")) for c in pool):
                findings.append(("amount", "says %s; cited %s" % (shown, _shown(cited, lambda r: r["amount"]) +
                                                                  ("; sum %s" % sum(r["amount"] for r in cited) if sums and len(cited) > 1 else ""))))
    if "date" in facts:
        for _, shown, value in dates_in(text):
            found += 1
            if value is None:
                findings.append(("date", "says %s, which is not a day that exists" % shown))
            elif value not in {r["date"] for r in cited}:
                findings.append(("date", "says %s; cited %s" % (shown, _shown(cited, lambda r: r["date"].isoformat()))))
    if "party" in facts and ledger.names_re:
        for m in ledger.names_re.finditer(text):
            found += 1
            if m.group().lower() not in {r["party"].lower() for r in cited}:
                findings.append(("party", "names %s; cited %s" % (m.group(), _shown(cited, lambda r: r["party"] or "(no counterparty)"))))
    if "direction" in facts:
        said = direction_in(text)
        if said:
            found += 1
            if said not in {r["direction"] for r in cited}:
                findings.append(("direction", "says %s; cited %s" % (said, _shown(cited, lambda r: r["direction"]))))
    if "channel" in facts:
        for name, shown in channels_in(text):
            found += 1
            if name not in {r["channel"] for r in cited}:
                findings.append(("channel", "says %s; cited %s" % (shown, _shown(cited, lambda r: r["channel"]))))
    return findings, found


def trace_sentence(n: int, s: dict, text: str, ledger: Ledger, case, resolve: bool, facts, sums: bool, rounding: bool) -> dict:
    res = {"n": n, "start": s["start"], "end": s["end"], "line": text.count("\n", 0, s["start"]) + 1,
           "text": s["text"], "ids": [], "findings": [], "facts": 0}
    cites = list(CITE.finditer(s["text"]))
    if not cites:
        res["status"] = "uncited"
        res["findings"].append(("uncited", "no [txn: ID] citation"))
        return res
    ids = []
    for c in cites:
        for part in c.group(1).split(","):
            if part.strip() and part.strip() not in ids:
                ids.append(part.strip())
    res["ids"] = ids
    known = [ledger.by_id.get(i) for i in ids]
    cited = [r for r in known if r]
    if resolve:
        if not ids:
            res["findings"].append(("dangling", "the citation holds no ID"))
        missing = [i for i, r in zip(ids, known) if r is None]
        if missing:
            res["findings"].append(("dangling", "cites %s, not in the transactions file" % ", ".join(missing)))
        if case is not None:
            foreign = [r for r in cited if r["case"] != case]
            if foreign:
                res["findings"].append(("other_case", "cites %s" % ", ".join("%s (case %s)" % (r["id"], r["case"] or "none") for r in foreign)))
            cited = [r for r in cited if r["case"] == case]
    body = CITE.sub(" ", s["text"])
    n_ids = len(ids)
    if cited:
        found_facts, res["facts"] = check_facts(body, cited, ledger, facts, sums, rounding)
        res["findings"] += found_facts
    if "count" in facts:
        for shown, claimed in counts_in(body):
            res["facts"] += 1
            if claimed != n_ids:
                res["findings"].append(("count", "says %s; the sentence cites %d record%s" % (shown, n_ids, "" if n_ids == 1 else "s")))
    kinds = [f[0] for f in res["findings"]]
    if "dangling" in kinds:
        res["status"] = "dangling"
    elif "other_case" in kinds:
        res["status"] = "other_case"
    elif kinds:
        res["status"] = "mismatch"
    else:
        res["status"] = "unchecked" if res["facts"] == 0 else "traced"
    return res


def analyse(text: str, ledger: Ledger, case=None, *, resolve: bool = True, facts=FACTS, sums: bool = True, rounding: bool = True) -> list:
    """Trace every sentence of text. The keyword options switch parts of the check off, so a weaker version can be measured."""
    return [trace_sentence(i, s, text, ledger, case, resolve, facts, sums, rounding) for i, s in enumerate(split_sentences(text), 1)]


def summarise(results: list) -> dict:
    counts = {"sentences": len(results), "traced": 0, "unchecked": 0, "untraced": 0}
    for r in results:
        counts["untraced" if r["status"] in UNTRACED else r["status"]] += 1
    return counts


def is_failure(results: list, fail_on: str) -> bool:
    if fail_on == "never":
        return False
    bad = UNTRACED + (("unchecked",) if fail_on == "unchecked" else ())
    return any(r["status"] in bad for r in results)


# ---------------------------------------------------------------- output
def clean(text) -> str:
    """One printable line: control characters, newlines included, become spaces."""
    return CONTROL.sub(" ", str(text))


def escape_data(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def quote(text: str, width: int = 90) -> str:
    one = " ".join(clean(text).split())
    return '"' + (one if len(one) <= width else one[:width - 3] + "...") + '"'


def notes_for(results: list, ledger: Ledger) -> list:
    notes = []
    cited = [i for r in results for i in r["ids"]]
    if not cited:
        notes.append("no sentence has a citation in the form [txn: ID], so nothing could be traced")
    elif not any(i in ledger.by_id for i in cited):
        notes.append("none of the %d cited IDs is in the transactions file; check that the file matches the narrative" % len(set(cited)))
    return notes


def render_text(label: str, ledger: Ledger, case, results: list, notes: list) -> str:
    head = "narrative-trace: %s against %d records" % (clean(label), len(ledger.by_id))
    lines = [head + (" (case %s)" % clean(case) if case is not None else "")]
    for r in results:
        if r["status"] == "traced":
            continue
        findings = r["findings"] or [("unchecked", "cites %s; states no amount, date, party, direction, channel or count to compare" % ", ".join(r["ids"]))]
        for k, (kind, why) in enumerate(findings):
            lines.append("  s%-3d %-18s %s" % (r["n"], LABEL[kind], clean(why)))
            if k == 0:
                lines.append("       " + quote(r["text"]))
    lines += ["note: " + n for n in notes]
    c = summarise(results)
    lines.append("sentences: %d checked, %d traced, %d cite a record but state nothing checkable, %d not traced"
                 % (c["sentences"], c["traced"], c["unchecked"], c["untraced"]))
    return "\n".join(lines)


def render_github(label: str, results: list, notes: list) -> str:
    where = escape_property(label)
    lines = []
    for r in results:
        if r["status"] == "traced":
            continue
        level = "warning" if r["status"] == "unchecked" else "error"
        why = "; ".join("%s: %s" % (LABEL[k], w) for k, w in r["findings"]) or "cites a record but states nothing checkable"
        lines.append("::%s file=%s,line=%d,title=narrative-trace::%s" % (level, where, r["line"], escape_data("sentence %d: %s" % (r["n"], why))))
    lines += ["::warning file=%s,title=narrative-trace::%s" % (where, escape_data(n)) for n in notes]
    c = summarise(results)
    lines.append("::notice title=narrative-trace::%d checked, %d traced, %d unchecked, %d not traced" % (c["sentences"], c["traced"], c["unchecked"], c["untraced"]))
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def run_check(narrative_path: str, txns_path: str, case, fail_on: str = "untraced", fmt: str = "text") -> int:
    try:
        text = read_text(narrative_path, "narrative")
        ledger = load_records(txns_path)
        if not text.strip():
            raise InputError("narrative %r is empty" % narrative_path)
        if case is not None:
            if not ledger.has_case:
                raise InputError("--case needs a case_id column in the transactions file")
            if case not in ledger.case_ids():
                raise InputError("the transactions file has no records for case %r" % case)
        results = analyse(text, ledger, case)
        if not results:
            raise InputError("narrative %r holds no sentences" % narrative_path)
    except InputError as e:
        sys.stderr.write("narrative-trace: %s\n" % e)
        return 2
    label = os.path.basename(narrative_path)
    notes = notes_for(results, ledger)
    print(render_github(label, results, notes) if fmt == "github" else render_text(label, ledger, case, results, notes))
    if fmt == "text":
        print("result: " + ("FAIL" if is_failure(results, fail_on) else "PASS"))
    return 1 if is_failure(results, fail_on) else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write("narrative-trace: %s\n" % message)
        sys.exit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="narrative_trace.py", description="Trace every sentence of a narrative to the transaction it cites.")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_narrative.txt)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one narrative against a transactions file")
    c.add_argument("narrative")
    c.add_argument("transactions")
    c.add_argument("--case", help="only records with this case_id count as this narrative's evidence")
    c.add_argument("--fail-on", choices=["untraced", "unchecked", "never"], default="untraced",
                   help="untraced (default): fail on a sentence that is not traced; unchecked: also fail on a sentence that states nothing checkable")
    c.add_argument("--format", choices=["text", "github"], default="text")
    args = ap.parse_args(argv)
    if args.demo:  # the example is built to fail; the demo itself succeeds when it can show that
        code = run_check(os.path.join(DATA, "example_narrative.txt"), os.path.join(DATA, "example_txns.csv"), "EX-1")
        return 0 if code == 1 else code
    if args.cmd == "check":
        return run_check(args.narrative, args.transactions, args.case, args.fail_on, args.format)
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
