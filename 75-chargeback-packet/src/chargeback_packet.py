"""chargeback_packet: check a dispute response packet against an evidence list and a deadline clock.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 chargeback_packet.py --demo
    python3 chargeback_packet.py check CASE_OR_CASES.json [--rules RULES.json] [--as-of YYYY-MM-DD]

Exit status: 0 when every packet is READY, 1 when any packet is FIX or LATE, 2 for bad or malformed input.
The demo always exits 0 so it can be shown in a README.
A packet is READY (nothing the checker can see is wrong), FIX (the clock is still running and the packet
has problems) or LATE (the response window has closed, whatever else is true). There is no model in this
file: the checklist, the clock and the consistency checks are plain rules read from rules.json.

The checker reads labels, dates, references, amounts and page counts. It cannot read a file, so a
document that carries the right label and the wrong content passes.

Case shape: {"case_id", "reason_code", "order_id", "txn_date", "received_date", "amount_cents",
             "submitted_date" ("" while the packet is a draft), "docs": [{"doc_id", "doc_type", "ref_id",
             "doc_date", "pages", "amount_cents" (optional)}]}
Dates are YYYY-MM-DD. The window is counted in calendar days from received_date, and the last day counts.
The bundled rules.json is invented for this prototype and is not any card network's rule set.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta

CHECKS = ("completeness", "clock", "consistency")
DEMO_AS_OF = "2026-02-28"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


# ---------------------------------------------------------------- small helpers
def safe(value, limit: int = 60) -> str:
    """Text from the input made safe to print: control characters become escapes, long text is cut."""
    out = "".join(ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in str(value))
    return out if len(out) <= limit else out[:limit - 3] + "..."


def money(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _need(cond, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_text(v) -> bool:
    return isinstance(v, str) and v != ""


def parse_date(value, label: str) -> date:
    _need(isinstance(value, str) and _DATE_RE.fullmatch(value) is not None, f"{label}: expected a date as YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label}: {safe(value)} is not a calendar date") from None


# ---------------------------------------------------------------- loading and validation
def validate_rules(rules, label: str = "rules") -> None:
    _need(isinstance(rules, dict), f"{label}: expected a JSON object, got {type(rules).__name__}")
    _need(_is_int(rules.get("max_pages")) and rules["max_pages"] >= 1, f"{label}: max_pages must be a positive integer")
    for key in ("after_purchase_types", "amount_types"):
        _need(isinstance(rules.get(key), list) and all(_is_text(x) for x in rules[key]), f"{label}: {key} must be a list of strings")
    codes = rules.get("reason_codes")
    _need(isinstance(codes, dict) and codes, f"{label}: reason_codes must be a non-empty object")
    for code, spec in codes.items():
        where = f"{label}: reason code {safe(code)}"
        _need(isinstance(spec, dict) and _is_text(spec.get("name")), f"{where} needs a name")
        _need(_is_int(spec.get("window_days")) and spec["window_days"] >= 1, f"{where}: window_days must be a positive integer")
        _need(isinstance(spec.get("slots"), list) and spec["slots"], f"{where}: slots must be a non-empty list")
        for s in spec["slots"]:
            _need(isinstance(s, dict) and _is_text(s.get("id")) and _is_text(s.get("label")), f"{where}: each slot needs an id and a label")
            _need(isinstance(s.get("accept"), list) and s["accept"] and all(_is_text(x) for x in s["accept"]),
                  f"{where}: slot {safe(s['id'])} needs a non-empty accept list")
            _need(isinstance(s.get("required"), bool), f"{where}: slot {safe(s['id'])} needs required as true or false")


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_rules(path: str | None = None) -> dict:
    path = path or os.path.join(DATA, "rules.json")
    rules = load_json(path)
    validate_rules(rules, os.path.basename(path))
    return rules


def validate_case(case, rules: dict, label: str = "case") -> None:
    """Raise ValueError (one line) when a case lacks what the checks read."""
    _need(isinstance(case, dict), f"{label}: expected a JSON object, got {type(case).__name__}")
    for key in ("case_id", "reason_code", "order_id"):
        _need(_is_text(case.get(key)), f"{label}: {key} must be a non-empty string")
    label = f"case {safe(case['case_id'])}"
    _need(case["reason_code"] in rules["reason_codes"], f"{label}: unknown reason code '{safe(case['reason_code'])}'")
    txn = parse_date(case.get("txn_date"), f"{label}: txn_date")
    received = parse_date(case.get("received_date"), f"{label}: received_date")
    _need(received >= txn, f"{label}: received_date is before txn_date")
    sub = case.get("submitted_date")
    if sub not in (None, ""):
        _need(parse_date(sub, f"{label}: submitted_date") >= received, f"{label}: submitted_date is before received_date")
    _need(_is_int(case.get("amount_cents")) and case["amount_cents"] > 0, f"{label}: amount_cents must be a positive integer")
    _need(isinstance(case.get("docs"), list), f"{label}: docs must be a list")
    for i, d in enumerate(case["docs"]):
        where = f"{label}: doc #{i}"
        _need(isinstance(d, dict), f"{where}: expected a JSON object, got {type(d).__name__}")
        for key in ("doc_id", "doc_type", "ref_id"):
            _need(_is_text(d.get(key)), f"{where}: {key} must be a non-empty string")
        parse_date(d.get("doc_date"), f"{where}: doc_date")
        _need(_is_int(d.get("pages")) and d["pages"] >= 1, f"{where}: pages must be a positive integer")
        _need("amount_cents" not in d or (_is_int(d["amount_cents"]) and d["amount_cents"] >= 0), f"{where}: amount_cents must be a non-negative integer")


# ---------------------------------------------------------------- the checks
def check_case(case: dict, rules: dict, as_of: date, checks=CHECKS) -> dict:
    """Run the chosen checks on one packet. The clock is as_of for a draft and submitted_date for a sent packet."""
    validate_case(case, rules)
    spec = rules["reason_codes"][case["reason_code"]]
    received, txn = date.fromisoformat(case["received_date"]), date.fromisoformat(case["txn_date"])
    due = received + timedelta(days=spec["window_days"])
    submitted = case.get("submitted_date") or ""
    clock = date.fromisoformat(submitted) if submitted else as_of
    days_left = (due - clock).days
    docs = case["docs"]
    problems, notes = [], []
    if "completeness" in checks:
        have = {d["doc_type"] for d in docs}
        for s in spec["slots"]:
            if s["required"] and not have.intersection(s["accept"]):
                need = "one of " + ", ".join(safe(x) for x in s["accept"]) if len(s["accept"]) > 1 else safe(s["accept"][0])
                problems.append({"kind": "missing_evidence", "detail": f"{safe(s['label'])}: need {need}"})
        listed = {t for s in spec["slots"] for t in s["accept"]}
        for d in docs:
            if d["doc_type"] not in listed:
                notes.append(f"{safe(d['doc_id'])}: type '{safe(d['doc_type'])}' is on no list for {safe(case['reason_code'])}, so it counts for nothing")
    if "consistency" in checks:
        for d in docs:
            tag = f"{safe(d['doc_id'])} ({safe(d['doc_type'])})"
            if d["ref_id"] != case["order_id"]:
                problems.append({"kind": "wrong_reference", "detail": f"{tag} carries reference {safe(d['ref_id'])}, the case is {safe(case['order_id'])}"})
            when = date.fromisoformat(d["doc_date"])
            if d["doc_type"] in rules["after_purchase_types"] and when < txn:
                problems.append({"kind": "dated_before_purchase", "detail": f"{tag} is dated {d['doc_date']}, before the purchase on {case['txn_date']}"})
            if when > clock:
                problems.append({"kind": "dated_in_future", "detail": f"{tag} is dated {d['doc_date']}, after the check date {clock.isoformat()}"})
            if d["doc_type"] in rules["amount_types"] and "amount_cents" in d and d["amount_cents"] < case["amount_cents"]:
                problems.append({"kind": "amount_short", "detail": f"{tag} states {money(d['amount_cents'])}, below the disputed {money(case['amount_cents'])}"})
        pages = sum(d["pages"] for d in docs)
        if pages > rules["max_pages"]:
            problems.append({"kind": "over_page_limit", "detail": f"{pages} pages, limit {rules['max_pages']}"})
    late = "clock" in checks and days_left < 0
    state = "LATE" if late else "FIX" if problems else "READY"
    return {"case_id": case["case_id"], "reason_code": case["reason_code"], "reason_name": safe(spec["name"]),
            "amount_cents": case["amount_cents"], "due": due.isoformat(), "clock": clock.isoformat(), "days_left": days_left,
            "submitted": submitted, "state": state, "problems": problems, "notes": notes}


# ---------------------------------------------------------------- output
def clock_phrase(r: dict) -> str:
    d = r["days_left"]
    if r["submitted"]:
        return f"submitted {r['submitted']}, due {r['due']}" + (f", {plural(-d, 'day')} late" if d < 0 else "")
    if d < 0:
        return f"due {r['due']}, {plural(-d, 'day')} overdue as of {r['clock']}"
    return f"due {r['due']}, " + ("due today" if d == 0 else f"{plural(d, 'day')} left") + f" as of {r['clock']}"


def render(r: dict) -> list:
    lines = [f"case {safe(r['case_id'])}  {safe(r['reason_code'])} {r['reason_name']}  amount {money(r['amount_cents'])}  {clock_phrase(r)}"]
    for p in r["problems"]:
        lines.append(f"  [{p['kind']:<22}] {p['detail']}")
    for n in r["notes"]:
        lines.append(f"  [{'note':<22}] {n}")
    d = r["days_left"]
    if r["state"] == "LATE":
        lines.append(f"decision: LATE ({plural(-d, 'day')} past the deadline)")
    elif r["state"] == "FIX":
        tail = f"submitted {r['submitted']}" if r["submitted"] else f"{plural(d, 'day')} left"
        lines.append(f"decision: FIX ({plural(len(r['problems']), 'problem')}, {tail})")
    else:
        lines.append("decision: READY" + ("" if r["submitted"] else f" ({plural(d, 'day')} left)"))
    return lines


def run_check(case_path: str, rules_path: str | None, as_of_text: str | None) -> int:
    try:
        rules = load_rules(rules_path)
        as_of = parse_date(as_of_text, "--as-of") if as_of_text else date.today()
        data = load_json(case_path)
        cases = data if isinstance(data, list) else [data]
        _need(cases, f"{os.path.basename(case_path)}: no cases in the file, so nothing was checked")
        results = []
        for i, c in enumerate(cases):
            validate_case(c, rules, f"case #{i}")
            results.append(check_case(c, rules, as_of))
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {safe(e, 300)}", file=sys.stderr)
        return 2
    for r in results:
        print("\n".join(render(r)))
    if len(results) > 1:
        counts = {s: sum(1 for r in results if r["state"] == s) for s in ("READY", "FIX", "LATE")}
        print(f"summary: {plural(len(results), 'packet')}: {counts['READY']} READY, {counts['FIX']} FIX, {counts['LATE']} LATE")
    return 0 if all(r["state"] == "READY" for r in results) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chargeback_packet")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_case.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check one case, or a JSON list of cases")
    c.add_argument("cases", help="JSON file holding one case or a list of cases")
    c.add_argument("--rules", help="evidence list (default: the bundled data/rules.json)")
    c.add_argument("--as-of", dest="as_of", help="date of the check as YYYY-MM-DD (default: today); a submitted packet uses its own submitted_date")
    a = ap.parse_args(argv)
    if a.demo:
        code = run_check(os.path.join(DATA, "example_case.json"), None, DEMO_AS_OF)
        return 0 if code == 1 else code
    if a.cmd == "check":
        return run_check(a.cases, a.rules, a.as_of)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
