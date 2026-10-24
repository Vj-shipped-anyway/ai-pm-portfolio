"""review_capacity: how many reviewers does a human-review queue need? A small queueing calculator.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 review_capacity.py --demo
    python3 review_capacity.py size QUEUES.csv [--fail-on short|never] [--format text|github]
    python3 review_capacity.py fit CASELOG.csv [--days FIRST-LAST] [--hours-open 8]

size   reads one row of assumptions per queue and prints the reviewers needed at the desk ("seats"),
       the roster that implies once shrinkage is counted, and the same figure from Erlang C on the
       mean rate alone, for comparison. Exit 0 when every queue with a current_headcount is covered,
       1 when one is short, 2 for bad or malformed input.
fit    reads a case log and prints a QUEUES.csv with the arrival and handling-time columns measured
       from it. The target columns are defaults for you to edit.

Queue columns: queue_id, hours_open, arrivals_per_hour (live cases), opening_batch (cases that land
at open, mean per day), handling_minutes (mean), handling_cv (standard deviation over mean),
arrival_cv (same, for the gaps between live arrivals; 1 is Poisson), target_wait_min, target_share
(share of cases that must start review within the target), max_utilization, shrinkage,
current_headcount (may be blank).
Case log columns: queue_id, day, arrival_min (minutes after open), handle_min, channel (live or batch).

Method. A case is late when it waits longer than target_wait_min for a free reviewer. Late share is
modeled as the sum of two parts. The live stream uses the Allen-Cunneen adjustment of Erlang C: the
tail of the wait is exponential with its rate scaled by 2 / (arrival_cv^2 + handling_cv^2). The
opening batch uses a fluid drain: the k-th batch case starts about when k / seats service times have
passed, and live cases that arrive during the drain wait behind it. Seats are raised until the late
share is within 1 - target_share and utilization is within max_utilization. There is no model and no
sampling in this file; every figure is arithmetic on the inputs. The method is a planning
approximation checked against replay on synthetic data, not a guarantee.
"""
from __future__ import annotations

import argparse
import csv
import heapq
import math
import os
import re
import sys

MAX_SEATS = 500
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.\-]{0,63}")
QUEUE_COLUMNS = ["queue_id", "hours_open", "arrivals_per_hour", "opening_batch", "handling_minutes", "handling_cv",
                 "arrival_cv", "target_wait_min", "target_share", "max_utilization", "shrinkage", "current_headcount"]
LOG_COLUMNS = ["queue_id", "day", "arrival_min", "handle_min", "channel"]
DEFAULT_TARGETS = {"target_wait_min": "30", "target_share": "0.90", "max_utilization": "0.85", "shrinkage": "0.25"}


class InputError(ValueError):
    """Raised for input the tool cannot read; the command line turns it into exit status 2."""


# ---------------------------------------------------------------- safe text
def safe(text) -> str:
    """Untrusted text made safe for one line of output: percent, CR and LF escaped as GitHub documents,
    other control characters replaced, length capped."""
    s = str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return "".join("?" if ord(ch) < 32 or ord(ch) == 127 else ch for ch in s)[:80]


def escape_annotation(text) -> str:
    """Escape a workflow-command message so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


# ---------------------------------------------------------------- queueing arithmetic
def erlang_c(seats: int, load: float) -> float:
    """Probability that an arriving case has to wait: seats reviewers, offered load in Erlangs.
    Returns 1.0 when the load is at or above the number of seats."""
    if load >= seats:
        return 1.0
    b = 1.0
    for k in range(1, seats + 1):
        b = load * b / (k + load * b)
    rho = load / seats
    return b / (1.0 - rho * (1.0 - b))


def offered_load(q: dict) -> float:
    """Work arriving per minute of an open shift, in reviewer-minutes per minute (Erlangs)."""
    minutes = q["hours_open"] * 60.0
    return (q["opening_batch"] + q["arrivals_per_hour"] * q["hours_open"]) * q["handling_minutes"] / minutes


def late_share(q: dict, seats: int, use_variability: bool = True, use_batch: bool = True) -> float:
    """Modeled share of cases that wait longer than target_wait_min.
    use_variability False treats arrivals and handling times as exponential (Erlang C).
    use_batch False folds the opening batch into the mean arrival rate instead of draining it."""
    minutes = q["hours_open"] * 60.0
    m, target = q["handling_minutes"], q["target_wait_min"]
    live = q["arrivals_per_hour"] / 60.0
    batch = q["opening_batch"]
    total = batch + live * minutes
    if use_variability:
        spread = q["arrival_cv"] ** 2 + q["handling_cv"] ** 2
    else:
        spread = 2.0
    if use_batch:
        stream = live
    else:
        stream, batch = total / minutes, 0.0
    load = stream * m
    if stream <= 0:
        tail = 0.0
    elif seats <= load:
        tail = 1.0
    else:
        tail = erlang_c(seats, load) * math.exp(-(seats - load) / m * target * 2.0 / max(spread, 1e-6))
    late_batch, drain = 0.0, 0.0
    slack = seats * (1.0 + target / m)
    if batch > slack:
        late_batch = batch - slack
        rate = seats / m - live
        drain = minutes if rate <= 0 else min(minutes, late_batch / rate)
    late = late_batch + stream * drain + tail * stream * (minutes - drain)
    return min(1.0, late / total)


def required_seats(q: dict, use_variability: bool = True, use_batch: bool = True) -> int:
    """Smallest number of reviewers at the desk that meets the service target and the utilization cap."""
    seats = max(1, math.ceil(offered_load(q) / q["max_utilization"] - 1e-9))
    while seats <= MAX_SEATS:
        if late_share(q, seats, use_variability, use_batch) <= 1.0 - q["target_share"] + 1e-12:
            return seats
        seats += 1
    raise InputError(f"queue {safe(q['queue_id'])}: more than {MAX_SEATS} reviewers would be needed, check the inputs")


def roster(seats: int, shrinkage: float) -> int:
    """Headcount to hire so that `seats` are at the desk once breaks, training and leave take their share."""
    return math.ceil(seats / (1.0 - shrinkage) - 1e-9)


# ---------------------------------------------------------------- replay and fit
def replay(cases: list, seats: int, target_wait_min: float, hours_open: float, days: int) -> dict:
    """Run recorded cases through `seats` reviewers, first come first served, one day at a time.
    Each day starts empty and cases still waiting at close are worked off after close.
    cases: dicts with day, arrival_min, handle_min. days: length of the window, counting days with no cases."""
    ordered = sorted(cases, key=lambda c: (c["day"], c["arrival_min"]))
    late, busy, day, free = 0, 0.0, None, []
    for c in ordered:
        if c["day"] != day:
            day, free = c["day"], [0.0] * seats
        start = max(c["arrival_min"], heapq.heappop(free))
        heapq.heappush(free, start + c["handle_min"])
        busy += c["handle_min"]
        if start - c["arrival_min"] > target_wait_min:
            late += 1
    n = len(ordered)
    return {"cases": n, "late": late, "late_share": late / n if n else 0.0,
            "utilization": busy / (seats * hours_open * 60.0 * days) if days else 0.0}


def fit_queue(cases: list, hours_open: float, days: int) -> tuple:
    """Measure the assumption columns from logged cases. Returns (assumptions, notes)."""
    if len(cases) < 2:
        raise InputError("fewer than 2 cases in the window, so there is nothing to measure")
    minutes = hours_open * 60.0
    notes = []
    inside = [c for c in cases if c["arrival_min"] <= minutes]
    if len(inside) < len(cases):
        notes.append(f"{len(cases) - len(inside)} cases arrive after the shift and were ignored")
    live = [c for c in inside if c["channel"] == "live"]
    batch = [c for c in inside if c["channel"] == "batch"]
    handles = [c["handle_min"] for c in inside]
    if len(handles) < 2:
        raise InputError("fewer than 2 cases inside the shift, so there is nothing to measure")
    mean_h = sum(handles) / len(handles)
    cv_h = math.sqrt(sum((h - mean_h) ** 2 for h in handles) / len(handles)) / mean_h
    gaps = []
    by_day = {}
    for c in live:
        by_day.setdefault(c["day"], []).append(c["arrival_min"])
    for day in sorted(by_day):
        xs = sorted(by_day[day])
        gaps.extend(b - a for a, b in zip(xs, xs[1:]))
    cv_a = 1.0
    if len(gaps) >= 2 and sum(gaps) > 0:
        mean_g = sum(gaps) / len(gaps)
        cv_a = math.sqrt(sum((g - mean_g) ** 2 for g in gaps) / len(gaps)) / mean_g
    else:
        notes.append("too few live arrivals to measure the gaps between them, so arrival_cv is set to 1")
    return ({"hours_open": hours_open, "arrivals_per_hour": len(live) / (days * hours_open),
             "opening_batch": len(batch) / days, "handling_minutes": mean_h, "handling_cv": cv_h,
             "arrival_cv": cv_a}, notes)


# ---------------------------------------------------------------- reading files
def read_rows(path: str, columns: list) -> list:
    """Rows of a CSV as dicts, with the header and every row checked for the columns we need."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{safe(path)}: the file is empty")
            missing = [c for c in columns if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{safe(path)}: missing columns {', '.join(missing)}")
            rows = []
            for i, row in enumerate(reader, start=2):
                if None in row:
                    raise InputError(f"{safe(path)} row {i}: more fields than the header")
                gaps = [c for c in columns if row.get(c) is None and c != "current_headcount"]
                if gaps:
                    raise InputError(f"{safe(path)} row {i}: the row is truncated, no value for {', '.join(gaps)}")
                rows.append((i, row))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise InputError(f"{safe(path)}: cannot read the file ({safe(type(e).__name__)})")
    if not rows:
        raise InputError(f"{safe(path)}: the file has a header and no rows")
    return rows


def number(row: dict, key: str, where: str, low: float, high: float, low_open: bool = False, high_open: bool = False) -> float:
    raw = row[key].strip()
    try:
        v = float(raw)
    except ValueError:
        raise InputError(f"{where}: {key} is not a number: {safe(raw)!r}")
    ok = math.isfinite(v) and (v > low if low_open else v >= low) and (v < high if high_open else v <= high)
    if not ok:
        raise InputError(f"{where}: {key} must be between {low} and {high}, got {safe(raw)!r}")
    return v


def queue_id(row: dict, where: str) -> str:
    qid = row["queue_id"].strip()
    if not ID_RE.fullmatch(qid):
        raise InputError(f"{where}: queue_id must be 1 to 64 letters, digits, spaces, underscores, dots or hyphens "
                         f"and start with a letter or digit, got {safe(qid)!r}")
    return qid


def load_queues(path: str) -> list:
    """Validated queue assumptions from a QUEUES.csv."""
    queues, seen = [], set()
    for i, row in read_rows(path, QUEUE_COLUMNS):
        where = f"{safe(path)} row {i}"
        qid = queue_id(row, where)
        if qid in seen:
            raise InputError(f"{where}: queue_id {qid!r} appears twice")
        seen.add(qid)
        q = {"queue_id": qid,
             "hours_open": number(row, "hours_open", where, 0, 24, low_open=True),
             "arrivals_per_hour": number(row, "arrivals_per_hour", where, 0, 1e6),
             "opening_batch": number(row, "opening_batch", where, 0, 1e6),
             "handling_minutes": number(row, "handling_minutes", where, 0, 1e5, low_open=True),
             "handling_cv": number(row, "handling_cv", where, 0, 100),
             "arrival_cv": number(row, "arrival_cv", where, 0, 100),
             "target_wait_min": number(row, "target_wait_min", where, 0, 1e5),
             "target_share": number(row, "target_share", where, 0, 1, low_open=True, high_open=True),
             "max_utilization": number(row, "max_utilization", where, 0, 1, low_open=True),
             "shrinkage": number(row, "shrinkage", where, 0, 0.95)}
        if q["arrivals_per_hour"] == 0 and q["opening_batch"] == 0:
            raise InputError(f"{where}: arrivals_per_hour and opening_batch are both 0, so the queue has no work")
        held = (row.get("current_headcount") or "").strip()
        q["current_headcount"] = None
        if held:
            v = number(row, "current_headcount", where, 0, 1e6)
            if v != int(v):
                raise InputError(f"{where}: current_headcount must be a whole number, got {safe(held)!r}")
            q["current_headcount"] = int(v)
        queues.append(q)
    return queues


def load_log(path: str) -> dict:
    """Cases grouped by queue_id, in file order: {queue_id: [{day, arrival_min, handle_min, channel}]}."""
    out = {}
    for i, row in read_rows(path, LOG_COLUMNS):
        where = f"{safe(path)} row {i}"
        channel = row["channel"].strip()
        if channel not in ("live", "batch"):
            raise InputError(f"{where}: channel must be live or batch, got {safe(channel)!r}")
        day = number(row, "day", where, 1, 1e6)
        if day != int(day):
            raise InputError(f"{where}: day must be a whole number, got {safe(row['day'])!r}")
        out.setdefault(queue_id(row, where), []).append({
            "day": int(day), "channel": channel,
            "arrival_min": number(row, "arrival_min", where, 0, 1e6),
            "handle_min": number(row, "handle_min", where, 0, 1e6, low_open=True)})
    return out


def parse_days(text: str) -> tuple:
    m = re.fullmatch(r"(\d{1,6})-(\d{1,6})", text.strip())
    if not m or int(m.group(1)) < 1 or int(m.group(1)) > int(m.group(2)):
        raise InputError(f"--days must look like 1-10 with the first day not after the last, got {safe(text)!r}")
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------- commands
def render_size(rows: list, fmt: str) -> tuple:
    """Lines to print and the number of queues that are short."""
    short = [r for r in rows if r["held"] is not None and r["held"] < r["roster"]]
    given = [r for r in rows if r["held"] is not None]
    if fmt == "github":
        lines = [f"::error title=review-capacity::" + escape_annotation(
            f"{r['q']['queue_id']}: {r['held']} on the roster, {r['roster']} needed ({r['seats']} at the desk)") for r in short]
        lines.append("::notice title=review-capacity::" + escape_annotation(
            f"{len(short)} of {len(given)} queues with a current_headcount are short" if given
            else "no current_headcount given, so nothing was compared"))
        return lines, len(short)
    width = max(len("queue"), max(len(r["q"]["queue_id"]) for r in rows))
    lines = [f"{'queue':<{width}}  {'load':>5}  {'seats':>5}  {'util':>4}  {'mean-only':>9}  {'roster':>6}  {'have':>4}  status"]
    for r in rows:
        status = "-" if r["held"] is None else "ok" if r["held"] >= r["roster"] else f"SHORT by {r['roster'] - r['held']}"
        have = "-" if r["held"] is None else str(r["held"])
        lines.append(f"{r['q']['queue_id']:<{width}}  {r['load']:>5.1f}  {r['seats']:>5}  {r['util']:>3.0f}%  {r['plain']:>9}  "
                     f"{r['roster']:>6}  {have:>4}  {status}")
    lines.append("decision: " + (f"SHORT on {len(short)} of {len(given)} queues with a current_headcount" if short else
                                  f"covered on all {len(given)} queues with a current_headcount" if given else
                                  "sized only; no current_headcount given, so nothing was compared"))
    return lines, len(short)


def run_size(path: str, fail_on: str, fmt: str) -> int:
    try:
        queues = load_queues(path)
        rows = []
        for q in queues:
            seats = required_seats(q)
            rows.append({"q": q, "load": offered_load(q), "seats": seats, "util": 100.0 * offered_load(q) / seats,
                         "plain": required_seats(q, use_variability=False, use_batch=False),
                         "roster": roster(seats, q["shrinkage"]), "held": q["current_headcount"]})
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    lines, short = render_size(rows, fmt)
    print("\n".join(lines))
    return 1 if short and fail_on == "short" else 0


def run_fit(path: str, days_arg: str, hours_open: float) -> int:
    try:
        if not (math.isfinite(hours_open) and 0 < hours_open <= 24):
            raise InputError(f"--hours-open must be above 0 and at most 24, got {safe(hours_open)!r}")
        log = load_log(path)
        window = parse_days(days_arg) if days_arg else None
        out, notes = [], []
        for qid in sorted(log):
            cases = log[qid]
            if window:
                first, last = window
                cases = [c for c in cases if first <= c["day"] <= last]
            else:
                first, last = min(c["day"] for c in cases), max(c["day"] for c in cases)
            try:
                fitted, qnotes = fit_queue(cases, hours_open, last - first + 1)
            except InputError as e:
                raise InputError(f"queue {qid}: {e}")
            notes.extend(f"queue {qid}: {n}" for n in qnotes)
            out.append((qid, fitted))
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(QUEUE_COLUMNS)
    for qid, f in out:
        writer.writerow([qid, f"{f['hours_open']:g}", f"{f['arrivals_per_hour']:.3f}", f"{f['opening_batch']:.3f}",
                         f"{f['handling_minutes']:.2f}", f"{f['handling_cv']:.3f}", f"{f['arrival_cv']:.3f}",
                         DEFAULT_TARGETS["target_wait_min"], DEFAULT_TARGETS["target_share"],
                         DEFAULT_TARGETS["max_utilization"], DEFAULT_TARGETS["shrinkage"], ""])
    for n in notes:
        print(f"note: {safe(n)}", file=sys.stderr)
    print(f"note: target columns are defaults, edit them before you size; {len(out)} queues fitted", file=sys.stderr)
    return 0


class OneLineParser(argparse.ArgumentParser):
    def error(self, message):
        print(f"usage error: {safe(message)}", file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    ap = OneLineParser(prog="review_capacity")
    ap.add_argument("--demo", action="store_true", help="size the bundled example queues (data/example_queues.csv)")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("size", help="size reviewers from a QUEUES.csv of assumptions")
    s.add_argument("queues")
    s.add_argument("--fail-on", choices=["short", "never"], default="short")
    s.add_argument("--format", choices=["text", "github"], default="text")
    f = sub.add_parser("fit", help="measure the assumption columns from a case log")
    f.add_argument("log")
    f.add_argument("--days", help="first-last day to use, for example 1-10")
    f.add_argument("--hours-open", type=float, default=8.0)
    a = ap.parse_args(argv)
    if a.demo:
        return run_size(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "example_queues.csv"), "never", "text")
    if a.cmd == "size":
        return run_size(a.queues, a.fail_on, a.format)
    if a.cmd == "fit":
        return run_fit(a.log, a.days, a.hours_open)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
