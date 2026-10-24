"""dispute_clock: put every deadline of a customer dispute on a clock and say which ones were missed.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 dispute_clock.py --demo
    python3 dispute_clock.py check DISPUTES.csv --as-of YYYY-MM-DD [--policy POLICY.csv] [--holidays HOLIDAYS.csv]
                                  [--fail-on missed|never] [--due-soon DAYS] [--limit N] [--all]
                                  [--format text|github]

Exit status: 0 when nothing was missed (or --fail-on never), 1 when at least one clock was missed,
2 for input that cannot be read. There is no model in this file. The windows in data/policy.csv are
assumptions of a modeled bank, not read from any rule.

A clock has an anchor event (a date column of the dispute file), a window in business or calendar days,
and one or more events that satisfy it (the earliest one counts). Business days skip weekends and the
dates in the holiday file. A due date that lands on a day off stays where it lands. The tool reads only
the dispute columns that the policy names, plus dispute_id, dispute_type, window_class and credit_eligible.
It does not read pauses: a clock keeps running while the bank waits for the customer.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
DEMO_AS_OF = "2026-09-30"

DAY_TYPES = ("business", "calendar")
APPLIES_TO = ("all", "standard", "extended", "credit_eligible")
POLICY_COLUMNS = ("clock_id", "clock_name", "applies_to", "window_days", "day_type", "anchor_event", "satisfied_by")
DISPUTE_COLUMNS = ("dispute_id", "dispute_type", "window_class", "credit_eligible")
STATUSES = ("on_time", "late", "breached", "running", "not_started")
ONE = dt.timedelta(days=1)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_NUMBER = re.compile(r"[0-9]+")


class InputError(ValueError):
    """Input that cannot be used. The command line turns it into a one-line message and exit status 2."""


# ---------------------------------------------------------------- dates
def parse_date(text: str, label: str) -> dt.date:
    text = text.strip()
    if not _DATE.fullmatch(text):
        raise InputError(f"{label}: {text!r} is not a date in YYYY-MM-DD form")
    try:
        d = dt.date.fromisoformat(text)
    except ValueError:
        raise InputError(f"{label}: {text!r} is not a real date") from None
    if not 1900 <= d.year <= 2200:
        raise InputError(f"{label}: {text!r} is outside the years 1900 to 2200")
    return d


def is_business_day(d: dt.date, holidays) -> bool:
    return d.weekday() < 5 and d not in holidays


def add_days(start: dt.date, n: int, unit: str, holidays) -> dt.date:
    """The date n days after start. For business days, step forward and count only business days; start is not counted."""
    if unit == "calendar":
        return start + n * ONE
    day = start
    while n > 0:
        day += ONE
        if is_business_day(day, holidays):
            n -= 1
    return day


def count_days(a: dt.date, b: dt.date, unit: str, holidays) -> int:
    """Days in the range after a, up to and including b. Negative when b is before a."""
    if b < a:
        return -count_days(b, a, unit, holidays)
    if unit == "calendar":
        return (b - a).days
    return sum(1 for k in range(1, (b - a).days + 1) if is_business_day(a + k * ONE, holidays))


def status_of(due: dt.date, sent, as_of: dt.date) -> str:
    """on_time or late when the event happened; breached or running when it has not."""
    if sent is not None:
        return "on_time" if sent <= due else "late"
    return "breached" if due < as_of else "running"


# ---------------------------------------------------------------- loading
def read_rows(path: str, required, label: str) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise InputError(f"{label}: line {reader.line_num} has the wrong number of fields")
            rows.append(row)
    return rows


def load_policy(path: str) -> list:
    clocks, seen = [], set()
    for row in read_rows(path, POLICY_COLUMNS, "policy"):
        cid = row["clock_id"].strip()
        where = f"policy: clock {cid!r}"
        if not cid or cid in seen:
            raise InputError(f"policy: clock_id {cid!r} is empty or repeated")
        seen.add(cid)
        if row["applies_to"] not in APPLIES_TO:
            raise InputError(f"{where}: applies_to must be one of {', '.join(APPLIES_TO)}")
        if row["day_type"] not in DAY_TYPES:
            raise InputError(f"{where}: day_type must be business or calendar")
        window = row["window_days"].strip()
        if not _NUMBER.fullmatch(window) or not 0 < int(window) <= 3650:
            raise InputError(f"{where}: window_days must be a whole number from 1 to 3650")
        satisfied = tuple(s.strip() for s in row["satisfied_by"].split("|"))
        if not row["anchor_event"].strip() or not all(satisfied):
            raise InputError(f"{where}: anchor_event and satisfied_by must name dispute columns")
        clocks.append({"clock_id": cid, "name": row["clock_name"].strip(), "applies_to": row["applies_to"],
                       "window": int(window), "unit": row["day_type"], "anchor": row["anchor_event"].strip(),
                       "satisfied_by": satisfied})
    if not clocks:
        raise InputError("policy: no clocks")
    return clocks


def load_holidays(path: str) -> frozenset:
    rows = read_rows(path, ("date",), "holidays")
    return frozenset(parse_date(r["date"], f"holidays line {n}") for n, r in enumerate(rows, start=2))


def date_columns(policy) -> list:
    """The dispute columns the policy reads, in first-use order."""
    cols = []
    for c in policy:
        for name in (c["anchor"],) + c["satisfied_by"]:
            if name not in cols:
                cols.append(name)
    return cols


def load_disputes(path: str, columns) -> list:
    """Disputes with the named columns parsed as dates (an empty cell becomes None)."""
    rows = read_rows(path, DISPUTE_COLUMNS + tuple(columns), "disputes")
    if not rows:
        raise InputError("disputes: no rows")
    out, seen = [], set()
    for n, row in enumerate(rows, start=2):
        did = row["dispute_id"].strip()
        where = f"disputes line {n}"
        if not did or did in seen:
            raise InputError(f"{where}: dispute_id {did!r} is empty or repeated")
        seen.add(did)
        if row["window_class"] not in ("standard", "extended"):
            raise InputError(f"{where}: window_class must be standard or extended, got {row['window_class']!r}")
        if row["credit_eligible"] not in ("0", "1"):
            raise InputError(f"{where}: credit_eligible must be 0 or 1, got {row['credit_eligible']!r}")
        dates = {c: (parse_date(row[c], f"{where} {c}") if row[c].strip() else None) for c in columns}
        out.append({"dispute_id": did, "dispute_type": row["dispute_type"].strip(),
                    "window_class": row["window_class"], "credit_eligible": int(row["credit_eligible"]),
                    "dates": dates})
    return out


# ---------------------------------------------------------------- the clocks
def applies(dispute: dict, applies_to: str) -> bool:
    if applies_to == "standard":
        return dispute["window_class"] == "standard"
    if applies_to == "extended":
        return dispute["window_class"] == "extended"
    if applies_to == "credit_eligible":
        return dispute["credit_eligible"] == 1
    return True


def sent_date(dispute: dict, clock: dict):
    found = [dispute["dates"][c] for c in clock["satisfied_by"] if dispute["dates"][c] is not None]
    return min(found) if found else None


def evaluate_clock(dispute: dict, clock: dict, holidays, as_of: dt.date) -> dict:
    start, sent = dispute["dates"][clock["anchor"]], sent_date(dispute, clock)
    rec = {"dispute_id": dispute["dispute_id"], "dispute_type": dispute["dispute_type"], "clock_id": clock["clock_id"],
           "clock_name": clock["name"], "unit": clock["unit"], "window": clock["window"], "anchor": clock["anchor"],
           "start": start, "due": None, "sent": sent, "status": "not_started", "days": None}
    for label, d in (("start", start), ("sent", sent)):
        if d is not None and d > as_of:
            raise InputError(f"dispute {dispute['dispute_id']!r}: {label} date {d.isoformat()} is after --as-of "
                             f"{as_of.isoformat()}")
    if start is None:
        return rec
    rec["due"] = add_days(start, clock["window"], clock["unit"], holidays)
    rec["status"] = status_of(rec["due"], sent, as_of)
    if rec["status"] == "late":
        rec["days"] = count_days(rec["due"], sent, clock["unit"], holidays)
    elif rec["status"] == "breached":
        rec["days"] = count_days(rec["due"], as_of, clock["unit"], holidays)
    elif rec["status"] == "running":
        rec["days"] = count_days(as_of, rec["due"], clock["unit"], holidays)
    return rec


def evaluate_all(disputes, policy, holidays, as_of: dt.date) -> list:
    return [evaluate_clock(d, c, holidays, as_of) for d in disputes for c in policy if applies(d, c["applies_to"])]


def count_statuses(results) -> dict:
    out = {s: sum(1 for r in results if r["status"] == s) for s in STATUSES}
    out["missed"] = out["late"] + out["breached"]
    return out


def due_soon(results, as_of: dt.date, soon_days: int) -> list:
    return [r for r in results if r["status"] == "running" and (r["due"] - as_of).days <= soon_days]


def outside_holiday_years(results, holidays) -> int:
    """Business-day clocks whose stepped range touches a year that has no holiday in the holiday file."""
    years = {h.year for h in holidays}
    return sum(1 for r in results if r["unit"] == "business" and r["due"] is not None
               and not all(y in years for y in range(r["start"].year, r["due"].year + 1)))


# ---------------------------------------------------------------- output
def clean(text: str) -> str:
    """Make text from the input safe to print on one line: control characters become a question mark."""
    return "".join("?" if ord(ch) < 32 or ord(ch) == 127 else ch for ch in str(text))


def escape_data(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(text: str) -> str:
    return escape_data(text).replace(":", "%3A").replace(",", "%2C")


def unit_word(r: dict, n: int) -> str:
    word = "business day" if r["unit"] == "business" else "day"
    return f"{n} {word}" + ("" if n == 1 else "s")


def describe(r: dict) -> str:
    s, n = r["status"], r["days"]
    if s == "on_time":
        return "on time"
    if s == "late":
        return f"late by {unit_word(r, n)}"
    if s == "breached":
        return f"breached, {unit_word(r, n)} over"
    if s == "running":
        return f"running, {unit_word(r, n)} left"
    return "not started"


def clock_line(r: dict) -> str:
    head = f"{r['clock_id']} {clean(r['clock_name'])}"
    if r["status"] == "not_started":
        return f"{head:<42} not started (waits for {clean(r['anchor'])})"
    sent = r["sent"].isoformat() if r["sent"] else "not done"
    return f"{head:<42} due {r['due'].isoformat()}  sent {sent:<10}  {describe(r)}"


def render_text(disputes, results, holidays, policy, as_of, soon_days, limit, show_all) -> str:
    c = count_statuses(results)
    soon = due_soon(results, as_of, soon_days)
    lines = [f"as of {as_of.isoformat()}: {len(disputes)} dispute{'' if len(disputes) == 1 else 's'}, "
             f"{len(results)} clocks apply ({len(policy)} clocks in policy, {len(holidays)} holidays loaded)",
             f"missed {c['missed']} (late {c['late']}, breached {c['breached']}); running {c['running']}, "
             f"of which {len(soon)} due within {soon_days} days; not started {c['not_started']}; on time {c['on_time']}"]
    if not holidays:
        lines.append("note: the holiday file is empty, so only weekends are skipped")
    outside = outside_holiday_years(results, holidays)
    if holidays and outside:
        lines.append(f"note: {outside} business-day due dates reach a year with no holiday in the holiday file")
    if show_all:
        for d in disputes:
            mine = [r for r in results if r["dispute_id"] == d["dispute_id"]]
            lines.append(f"{clean(d['dispute_id'])}  {clean(d['dispute_type'])}")
            lines.extend("  " + clock_line(r) for r in mine)
        return "\n".join(lines)
    for title, group in (("missed", sorted((r for r in results if r["status"] in ("late", "breached")),
                                           key=lambda r: (r["due"], r["dispute_id"], r["clock_id"]))),
                         (f"due within {soon_days} days", sorted(soon, key=lambda r: (r["due"], r["dispute_id"], r["clock_id"])))):
        if group:
            lines.append(f"{title} (oldest due date first, showing {min(limit, len(group))} of {len(group)}):")
            lines.extend(f"  {clean(r['dispute_id'])}  {clock_line(r)}" for r in group[:limit])
    return "\n".join(lines)


def render_github(results, as_of, soon_days, limit) -> str:
    lines = []
    missed = sorted((r for r in results if r["status"] in ("late", "breached")),
                    key=lambda r: (r["due"], r["dispute_id"], r["clock_id"]))
    for r in missed[:limit]:
        lines.append(f"::error title={escape_property('dispute-clock ' + r['clock_id'])}::"
                     + escape_data(f"{r['dispute_id']} {r['clock_name']}: due {r['due'].isoformat()}, {describe(r)}"))
    for r in sorted(due_soon(results, as_of, soon_days), key=lambda r: (r["due"], r["dispute_id"], r["clock_id"]))[:limit]:
        lines.append(f"::warning title={escape_property('dispute-clock ' + r['clock_id'])}::"
                     + escape_data(f"{r['dispute_id']} {r['clock_name']}: due {r['due'].isoformat()}, {describe(r)}"))
    c = count_statuses(results)
    lines.append(f"::notice title=dispute-clock::as of {as_of.isoformat()}: {len(results)} clocks, missed {c['missed']}, "
                 f"running {c['running']}, on time {c['on_time']}, not started {c['not_started']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
def run_check(args) -> int:
    try:
        as_of = parse_date(args.as_of, "--as-of")
        policy = load_policy(args.policy)
        holidays = load_holidays(args.holidays)
        disputes = load_disputes(args.disputes, date_columns(policy))
        results = evaluate_all(disputes, policy, holidays, as_of)
        if not results:
            raise InputError("no clock applies to any of the disputes; check applies_to in the policy against "
                             "window_class and credit_eligible in the dispute file")
    except (OSError, ValueError, csv.Error) as e:
        print(f"input error: {clean(e)}", file=sys.stderr)
        return 2
    if args.format == "github":
        print(render_github(results, as_of, args.due_soon, args.limit))
    else:
        print(render_text(disputes, results, holidays, policy, as_of, args.due_soon, args.limit, args.all))
    return 1 if args.fail_on == "missed" and count_statuses(results)["missed"] else 0


def whole_number(minimum: int):
    def parse(text: str) -> int:
        if not _NUMBER.fullmatch(text) or int(text) < minimum:
            raise argparse.ArgumentTypeError(f"must be a whole number of {minimum} or more")
        return int(text)
    return parse


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dispute_clock")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_disputes.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="evaluate every clock in a dispute file")
    c.add_argument("disputes")
    c.add_argument("--as-of", required=True, help="the date to read the clocks at, YYYY-MM-DD")
    c.add_argument("--policy", default=os.path.join(DATA, "policy.csv"))
    c.add_argument("--holidays", default=os.path.join(DATA, "holidays.csv"))
    c.add_argument("--fail-on", choices=["missed", "never"], default="missed")
    c.add_argument("--due-soon", type=whole_number(0), default=5, help="list running clocks due within this many calendar days")
    c.add_argument("--limit", type=whole_number(1), default=20, help="most lines to print per list")
    c.add_argument("--all", action="store_true", help="print every clock of every dispute")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        demo = ap.parse_args(["check", os.path.join(DATA, "example_disputes.csv"), "--as-of", DEMO_AS_OF,
                              "--fail-on", "never", "--all"])
        return run_check(demo)
    if a.cmd == "check":
        return run_check(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
