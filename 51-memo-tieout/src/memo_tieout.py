#!/usr/bin/env python3
"""memo-tieout: tie every figure in a markdown credit memo back to the spread it was written from.

Standard library only, Python 3.9 or newer.

    python3 memo_tieout.py check MEMO.md --spread SPREAD.csv
    python3 memo_tieout.py --demo

How a memo marks a figure
  [$47.3 million](spread:revenue/FY2024)     a figure tied to one line and one period of the spread
  [2.16x](spread:debt_ebitda_x/FY2024)       a ratio, recomputed from the spread by a formula in this file
  [$5.0 million](term:facility_amount)       a proposed term, not a spread figure: counted, not checked
  $4.1 million, 2.75%, 1.2x                  a figure with no mark: reported as untied
A figure is a number written with a dollar sign, a percent sign or a trailing x. Years, counts and
section numbers are not figures. Fenced code, `code spans`, link targets and URLs are skipped.

How a figure ties
  The spread value, rounded half away from zero to the decimals the memo shows, must equal the figure.
  $47.3 million ties to 47,320 thousand. $47.4 million does not. No tolerance is applied.
  A name that is a line in the spread is read from the spread. Any other name must be one of the
  formulas in METRICS, which are this tool's own definitions and not a standard's.

Spread file: CSV with columns period, period_end, line, value, unit. unit is usd, usd_thousands or usd_millions.

Exit status: 0 when every figure ties, 1 when one does not (or nothing could be checked), 2 for bad input.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

MAX_BYTES = 5_000_000
UNIT_TO_DOLLARS = {"usd": Decimal(1), "usd_thousands": Decimal(1000), "usd_millions": Decimal(1000000)}
SCALE_WORDS = {"": 1, "thousand": 10 ** 3, "k": 10 ** 3, "million": 10 ** 6, "m": 10 ** 6, "mm": 10 ** 6,
               "billion": 10 ** 9, "bn": 10 ** 9}
SPREAD_COLUMNS = ("period", "period_end", "line", "value", "unit")
KIND_WORD = {"money": "dollar", "pct": "percent", "x": "multiple"}
FLAGGED = ("mismatch", "unresolved", "untied")
LABEL = {"mismatch": "does not tie", "unresolved": "unresolved", "untied": "untied"}

_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
FIGURE = re.compile(
    r"(?P<sign>(?<![\w.,$])[-−])?(?:"
    r"(?P<money>\$(?P<m_num>" + _NUM + r")(?:\s?(?P<m_scale>thousand|million|billion|mm|bn|k|m)(?![A-Za-z]))?)"
    r"|(?<![\w.,])(?:(?P<p_num>" + _NUM + r")\s?%|(?P<x_num>" + _NUM + r")x(?![A-Za-z0-9])))",
    re.IGNORECASE | re.ASCII)
CODE = re.compile(r"`[^`]*`")
LINK = re.compile(r"\[([^\[\]]*)\]\((spread|term):([^()]*)\)")
INERT = (re.compile(r"(?<=\])\([^)\s]*\)"), re.compile(r"https?://[^\s)>\]]+"))
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
PERIOD = re.compile(r"^[A-Za-z0-9_.-]+$")
TAG = re.compile(r"^([a-z][a-z0-9_]*)/([A-Za-z0-9_.-]+)$")
VALUE = re.compile(r"^-?\d{1,15}(?:\.\d{1,6})?$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class Unresolved(Exception):
    """A tie that cannot be checked, with a one-line reason."""


# ---------------------------------------------------------------- formulas
def _ebitda(d):
    return d["revenue"] - d["cogs"] - d["opex"]


# name: (kind, spread lines it needs, needs the prior period, formula as written for a reader, function)
METRICS = {
    "gross_profit": ("money", ("revenue", "cogs"), False, "revenue - cogs",
                     lambda d, p: d["revenue"] - d["cogs"]),
    "ebitda": ("money", ("revenue", "cogs", "opex"), False, "revenue - cogs - opex",
               lambda d, p: _ebitda(d)),
    "gross_margin_pct": ("pct", ("revenue", "cogs"), False, "100 * (revenue - cogs) / revenue",
                         lambda d, p: 100 * (d["revenue"] - d["cogs"]) / d["revenue"]),
    "ebitda_margin_pct": ("pct", ("revenue", "cogs", "opex"), False, "100 * ebitda / revenue",
                          lambda d, p: 100 * _ebitda(d) / d["revenue"]),
    "net_margin_pct": ("pct", ("revenue", "net_income"), False, "100 * net_income / revenue",
                       lambda d, p: 100 * d["net_income"] / d["revenue"]),
    "revenue_growth_pct": ("pct", ("revenue",), True, "100 * (revenue / prior-period revenue - 1)",
                           lambda d, p: 100 * (d["revenue"] / p["revenue"] - 1)),
    "debt_ebitda_x": ("x", ("total_debt", "revenue", "cogs", "opex"), False, "total_debt / ebitda",
                      lambda d, p: d["total_debt"] / _ebitda(d)),
    "current_ratio_x": ("x", ("current_assets", "current_liabilities"), False, "current_assets / current_liabilities",
                        lambda d, p: d["current_assets"] / d["current_liabilities"]),
    "dscr_x": ("x", ("revenue", "cogs", "opex", "interest_expense", "principal_payments"), False,
               "ebitda / (interest_expense + principal_payments)",
               lambda d, p: _ebitda(d) / (d["interest_expense"] + d["principal_payments"])),
    "debt_to_equity_x": ("x", ("total_debt", "total_equity"), False, "total_debt / total_equity",
                         lambda d, p: d["total_debt"] / d["total_equity"]),
}


# ---------------------------------------------------------------- figures
def clean(text) -> str:
    """One printable line: control characters, newlines included, become spaces."""
    return CONTROL.sub(" ", str(text))


def parse_figures(text: str) -> list:
    """Every figure in a piece of text, in reading order.

    Each is {"start", "end", "text", "kind" (money, pct or x), "value" (as written, signed), "decimals",
    "scale" (dollars per unit for money, else 1), "scale_word", "bad" (a reason, or "")}."""
    out = []
    for m in FIGURE.finditer(text):
        num = m.group("m_num") or m.group("p_num") or m.group("x_num")
        whole, _, frac = num.replace(",", "").partition(".")
        kind = "money" if m.group("money") else "pct" if m.group("p_num") else "x"
        word = (m.group("m_scale") or "").lower()
        value = Decimal(num.replace(",", ""))
        out.append({"start": m.start(), "end": m.end(), "text": m.group(), "kind": kind,
                    "value": -value if m.group("sign") else value, "decimals": len(frac),
                    "scale": Decimal(SCALE_WORDS[word]) if kind == "money" else Decimal(1), "scale_word": word,
                    "bad": "more than 15 whole digits or 6 decimals" if len(whole) > 15 or len(frac) > 6 else ""})
    return out


def ties(fig: dict, actual: Decimal, tolerance=None) -> bool:
    """Does the spread value (in dollars for money) round to the figure at the precision the memo shows?

    With tolerance None the comparison is exact at that precision. A Decimal such as 0.01 compares within
    that share of the spread value instead; step_03 uses it to show what a 1% tolerance lets through."""
    scaled = actual / fig["scale"]
    if tolerance is None:
        return scaled.quantize(Decimal(1).scaleb(-fig["decimals"]), rounding=ROUND_HALF_UP) == fig["value"]
    return abs(scaled - fig["value"]) <= tolerance * abs(scaled)


def shown(x: Decimal, decimals: int) -> str:
    """x with thousands commas, three more decimals than the memo shows, and trailing zeros trimmed back to that."""
    s = f"{x.quantize(Decimal(1).scaleb(-(decimals + 3)), rounding=ROUND_HALF_UP):,f}"
    if "." in s:
        keep = s.index(".") + 1 + decimals
        s = s[:keep] + s[keep:].rstrip("0")
    return s.rstrip(".")


def describe(kind: str, actual: Decimal, fig: dict) -> str:
    if kind == "money":
        word = fig["scale_word"]
        return "$" + shown(actual / fig["scale"], fig["decimals"]) + (" " + word if word else "")
    return shown(actual, fig["decimals"]) + ("%" if kind == "pct" else "x")


# ---------------------------------------------------------------- spread
def build_spread(rows: list) -> dict:
    """Validate rows of {period, period_end, line, value, unit} and return the spread. Raises ValueError with one line."""
    values, ends, lines = {}, {}, set()
    for n, r in enumerate(rows, 1):
        where = f"spread row {n}"
        line, period, end, unit = (str(r.get(k) or "").strip() for k in ("line", "period", "period_end", "unit"))
        if not NAME.match(line):
            raise ValueError(f"{where}: line {clean(line)!r} must be lowercase letters, digits and underscores, starting with a letter")
        if not PERIOD.match(period):
            raise ValueError(f"{where}: period {clean(period)!r} may hold only letters, digits, dot, dash and underscore")
        try:
            date.fromisoformat(end)
        except ValueError:
            raise ValueError(f"{where}: period_end {clean(end)!r} is not a date like 2024-12-31") from None
        if ends.setdefault(period, end) != end:
            raise ValueError(f"{where}: period {period} has two different period_end dates")
        if unit not in UNIT_TO_DOLLARS:
            raise ValueError(f"{where}: unit {clean(unit)!r} must be one of {', '.join(sorted(UNIT_TO_DOLLARS))}")
        text = str(r.get("value") or "").strip()
        if not VALUE.match(text):
            raise ValueError(f"{where}: value {clean(text)!r} is not a plain number (no commas, up to 15 whole digits and 6 decimals)")
        if (line, period) in values:
            raise ValueError(f"{where}: {line} for {period} appears twice")
        values[(line, period)] = Decimal(text) * UNIT_TO_DOLLARS[unit]
        lines.add(line)
    if not values:
        raise ValueError("spread has no rows")
    periods = sorted(ends, key=lambda p: (ends[p], p))
    if len({ends[p] for p in periods}) != len(periods):
        raise ValueError("two periods share one period_end date")
    return {"periods": periods, "values": values, "lines": sorted(lines)}


def evaluate(spread: dict, name: str, period: str):
    """(kind, value, how) of a spread line or formula at one period. Raises Unresolved, or ArithmeticError on a zero divisor."""
    if name not in spread["lines"] and name not in METRICS:
        raise Unresolved(f"{name!r} is neither a line in the spread nor a formula this tool knows")
    if period not in spread["periods"]:
        raise Unresolved(f"period {period!r} is not in the spread (it has {', '.join(spread['periods'])})")

    def get(line: str, p: str) -> Decimal:
        v = spread["values"].get((line, p))
        if v is None:
            raise Unresolved(f"the spread has no {line} value for {p}")
        return v

    if name in spread["lines"]:
        return "money", get(name, period), "spread line"
    kind, needs, prior, how, fn = METRICS[name]
    d = {n: get(n, period) for n in needs}
    p = {}
    if prior:
        i = spread["periods"].index(period)
        if i == 0:
            raise Unresolved(f"{period} is the earliest period in the spread, so {name} has no prior period to compare with")
        p = {n: get(n, spread["periods"][i - 1]) for n in needs}
    return kind, fn(d, p), how


def find_ties(spread: dict, fig: dict, skip: tuple, tolerance=None) -> list:
    """Up to three name/period pairs, other than skip, whose value the figure does tie to."""
    found = []
    for name in sorted(set(spread["lines"]) | set(METRICS)):
        for period in spread["periods"]:
            if (name, period) == skip:
                continue
            try:
                kind, actual, _ = evaluate(spread, name, period)
                if kind == fig["kind"] and ties(fig, actual, tolerance):
                    found.append(f"{name}/{period}")
            except (Unresolved, ArithmeticError):
                continue
    return found[:3]


# ---------------------------------------------------------------- reading a memo
def scan_memo(text: str) -> list:
    """Every figure and tie mark in a memo, in reading order, as {"line", "col", "mark" (tie, term or bare), "target", "figures", "label"}.

    Raises ValueError when a code fence is never closed, since the rest of the memo would be skipped without a word."""
    items, fence = [], 0
    for no, raw in enumerate(text.split("\n"), 1):
        line = raw.rstrip("\r")
        if line.strip().startswith("```"):
            fence = 0 if fence else no
            continue
        if fence:
            continue
        rest = list(CODE.sub(lambda m: " " * len(m.group()), line))
        masked = "".join(rest)
        found = []
        for m in LINK.finditer(masked):
            figs = parse_figures(m.group(1))
            for f in figs:
                f["start"] += m.start(1)
            anchor = figs[0]["start"] if figs else m.start(1)
            found.append({"line": no, "col": anchor + 1, "mark": m.group(2), "target": m.group(3).strip(),
                          "figures": figs, "label": clean(m.group(1))[:30]})
            rest[m.start():m.end()] = " " * (m.end() - m.start())
        bare = "".join(rest)
        for pattern in INERT:
            bare = pattern.sub(lambda m: " " * len(m.group()), bare)
        for f in parse_figures(bare):
            found.append({"line": no, "col": f["start"] + 1, "mark": "bare", "target": "", "figures": [f], "label": ""})
        items.extend(sorted(found, key=lambda i: i["col"]))
    if fence:
        raise ValueError(f"the code fence opened on line {fence} never closes, so the rest of the memo would be skipped")
    return items


# ---------------------------------------------------------------- checking
def _result(item: dict, status: str, why: str = "", tag: str = "") -> dict:
    figs = item["figures"]
    return {"line": item["line"], "col": item["col"], "text": figs[0]["text"] if figs else item["label"],
            "tag": tag, "status": status, "why": why}


def _resolve(item: dict, spread: dict, tolerance) -> dict:
    if item["mark"] == "term":
        if not NAME.match(item["target"]):
            return _result(item, "unresolved", f"malformed term mark {item['target']!r}; write term:name", item["target"])
        return _result(item, "term", "proposed term, not checked against the spread", item["target"])
    if item["mark"] == "bare":
        return _result(item, "untied", "no spread mark; write [figure](spread:line/period), or term:name for a proposed term")
    tag = item["target"]
    m = TAG.match(tag)
    if not m:
        return _result(item, "unresolved", f"malformed tag {tag!r}; write spread:line/period", tag)
    if len(item["figures"]) != 1:
        return _result(item, "unresolved", f"the link text holds {len(item['figures'])} figures; tie one figure per link", tag)
    fig, (name, period) = item["figures"][0], m.groups()
    if fig["bad"]:
        return _result(item, "unresolved", "figure has " + fig["bad"], tag)
    try:
        kind, actual, how = evaluate(spread, name, period)
        if kind != fig["kind"]:
            raise Unresolved(f"{name} is a {KIND_WORD[kind]} figure and the memo writes a {KIND_WORD[fig['kind']]} figure")
        if ties(fig, actual, tolerance):
            return _result(item, "tied", "", tag)
        derived = how != "spread line"
        why = (f"{tag} recomputes to {describe(kind, actual, fig)} from the spread ({how})" if derived
               else f"{tag} is {describe(kind, actual, fig)} in the spread") + f"; the memo says {fig['text']}"
        also = find_ties(spread, fig, (name, period), tolerance)
        return _result(item, "mismatch", why + (f". The figure does tie to {', '.join(also)}" if also else ""), tag)
    except Unresolved as e:
        return _result(item, "unresolved", str(e), tag)
    except ArithmeticError:
        return _result(item, "unresolved", f"{name} cannot be computed for {period} (a divisor is zero or a number is too large)", tag)


def check_memo(text: str, spread: dict, tolerance=None) -> list:
    """One result per figure or mark: {"line", "col", "text", "tag", "status", "why"}.

    status is tied, mismatch, unresolved, untied or term. tolerance is passed to ties()."""
    return [_resolve(item, spread, tolerance) for item in scan_memo(text)]


def tally(results: list) -> dict:
    counts = {s: 0 for s in ("tied", "mismatch", "unresolved", "untied", "term")}
    for r in results:
        counts[r["status"]] += 1
    counts["read"] = len(results)
    counts["flagged"] = counts["mismatch"] + counts["unresolved"] + counts["untied"]
    counts["checked"] = counts["read"] - counts["term"]
    return counts


# ---------------------------------------------------------------- output
def escape_data(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so memo text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def render_text(shown_memo: str, shown_spread: str, spread: dict, results: list) -> str:
    n = tally(results)
    lines = [f"memo-tieout: {clean(shown_memo)} against {clean(shown_spread)} "
             f"({len(spread['periods'])} periods, {len(spread['lines'])} lines)"]
    for r in results:
        if r["status"] in FLAGGED:
            quoted = '"' + clean(r["text"]) + '"'
            lines.append(f"  line {r['line']:<4} col {r['col']:<4} {LABEL[r['status']]:<13} {quoted:<20} {clean(r['why'])}")
    if not n["checked"]:
        lines.append("figures: none to check. The memo holds no figure with a $, % or x and no spread mark, so nothing was checked.")
    else:
        lines.append(f"figures: {n['read']} read: {n['tied']} tie, {n['mismatch']} do not tie, {n['unresolved']} unresolved, "
                     f"{n['untied']} untied, {n['term']} set aside as terms")
    lines.append("result: " + ("FAIL" if n["flagged"] else "PASS" if n["checked"] else "NOTHING CHECKED"))
    return "\n".join(lines)


def render_github(shown_memo: str, results: list) -> str:
    n = tally(results)
    where = escape_property(shown_memo)
    lines = [f"::error file={where},line={r['line']},col={r['col']},title=memo-tieout {r['status']}::"
             + escape_data(f"{r['text']}: {r['why']}") for r in results if r["status"] in FLAGGED]
    if n["checked"]:
        lines.append(f"::notice title=memo-tieout::{n['read']} read, {n['tied']} tie, {n['flagged']} not tied, {n['term']} terms set aside")
    else:
        lines.append(f"::error file={where},title=memo-tieout::nothing was checked: no figure with a $, % or x and no spread mark was found")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def read_text(path: str, label: str) -> str:
    """Read a UTF-8 text file, or raise ValueError with a one-line reason."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES + 1)
    except OSError as e:
        raise ValueError(f"cannot read {label} {clean(path)}: {e.strerror or type(e).__name__}") from None
    if len(raw) > MAX_BYTES:
        raise ValueError(f"{label} {clean(path)} is larger than {MAX_BYTES // 1_000_000} MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(f"{label} {clean(path)} is not valid UTF-8 text (truncated or binary?)") from None
    if "\x00" in text:
        raise ValueError(f"{label} {clean(path)} contains NUL bytes, so it is not a text file")
    if not text.strip():
        raise ValueError(f"{label} {clean(path)} is empty")
    return text


def read_spread(path: str) -> dict:
    text = read_text(path, "spread file")
    try:
        table = list(csv.reader(io.StringIO(text)))
    except csv.Error as e:
        raise ValueError(f"spread file {clean(path)} is not readable CSV: {clean(e)}") from None
    header = [h.strip() for h in table[0]]
    missing = [c for c in SPREAD_COLUMNS if c not in header]
    if missing:
        raise ValueError(f"spread file {clean(path)} needs the columns {', '.join(SPREAD_COLUMNS)}; missing {', '.join(missing)}")
    rows = []
    for n, row in enumerate(table[1:], 1):
        if not row:
            continue
        if len(row) != len(header):
            raise ValueError(f"spread row {n} has {len(row)} fields and the header has {len(header)} (truncated?)")
        rows.append(dict(zip(header, row)))
    return build_spread(rows)


def run_check(memo_path, spread_path, fail_on="problems", fmt="text", shown_memo=None, shown_spread=None) -> int:
    try:
        memo = read_text(memo_path, "memo")
        spread = read_spread(spread_path)
        results = check_memo(memo, spread)
    except ValueError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    shown_memo = memo_path if shown_memo is None else shown_memo
    shown_spread = spread_path if shown_spread is None else shown_spread
    print(render_github(shown_memo, results) if fmt == "github" else render_text(shown_memo, shown_spread, spread, results))
    n = tally(results)
    return 1 if (n["flagged"] or not n["checked"]) and fail_on == "problems" else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print("usage error: " + clean(message), file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="memo_tieout", description="Tie the figures in a markdown credit memo back to a spread.")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_memo.md)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one memo against one spread")
    c.add_argument("memo")
    c.add_argument("--spread", required=True, help="CSV with columns period, period_end, line, value, unit")
    c.add_argument("--fail-on", choices=["problems", "never"], default="problems")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(data, "example_memo.md"), os.path.join(data, "example_spread.csv"), "never", "text",
                         "example_memo.md", "example_spread.csv")
    if a.cmd == "check":
        return run_check(a.memo, a.spread, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
