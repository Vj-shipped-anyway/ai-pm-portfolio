"""Generate the synthetic data for project 49: 150 disputes with their dates, and the clocks that
apply to each one.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth file is written
from the plan the generator followed (which step happened when, and for how long the bank paused
to wait for the customer), and labelled by counting elapsed days between two dates. The tool in
src/ computes a due date by stepping forward and compares the event to it. The two formulations
are separate on purpose, and the generator checks that they agree before it writes a row.

Hard on purpose:
  - events that land exactly on the due day (a tool that is off by one calls them late)
  - business-day windows that cross a holiday (a calendar-day count lands on the wrong day)
  - cases logged after first contact (a clock that starts at logging runs late)
  - investigations paused while the bank waited for the customer. The tool does not read the
    pause, so it calls some of them late or breached when the plan says they were on time.
  - disputes recorded as extended where the 60-day window never applied. The tool trusts the
    recorded class, so it gives them 60 days and can call a missed clock fine.

Run (from data/):  python3 _generate.py
Writes:  policy.csv, holidays.csv, as_of.txt, disputes.csv, truth.csv, example_disputes.csv
"""
from __future__ import annotations

import csv
import datetime as dt
import random

SEED = 49
rng = random.Random(SEED)
ONE = dt.timedelta(days=1)

AS_OF = dt.date(2026, 9, 30)
N_DISPUTES = 150
CONTACT_FIRST = dt.date(2026, 5, 4)
CONTACT_LAST = dt.date(2026, 9, 28)

ASSUMPTION = "assumption of a modeled bank, not read from any rule; confirm with counsel"

# The modeled calendar: weekdays on which the bank is closed. An assumption, not a statement of
# any institution's actual closing days.
HOLIDAYS = [dt.date(2026, 1, 1), dt.date(2026, 1, 19), dt.date(2026, 2, 16), dt.date(2026, 5, 25),
            dt.date(2026, 6, 19), dt.date(2026, 7, 3), dt.date(2026, 9, 7), dt.date(2026, 10, 12),
            dt.date(2026, 11, 11), dt.date(2026, 11, 26), dt.date(2026, 12, 25)]
HOLIDAY_SET = frozenset(HOLIDAYS)

# clock_id, name, applies_to, window, unit, anchor event, satisfied_by, note
CLOCKS = [
    ("DC1", "Acknowledge to customer", "all", 2, "business", "first_contact_on", "acknowledged_on",
     "Customer told the dispute was received, within 2 business days of first contact."),
    ("DC2", "Provisional credit decision", "credit_eligible", 7, "business", "first_contact_on",
     "provisional_credit_on|concluded_on",
     "Credit posted, or the investigation finished, within 7 business days of first contact. "
     "Applies to the two unauthorized-use dispute types."),
    ("DC3", "Investigation concluded (standard)", "standard", 30, "calendar", "first_contact_on", "concluded_on",
     "Investigation concluded within 30 calendar days of first contact. The modeled bank pauses it "
     "while it waits for customer information; the prototype does not apply the pause."),
    ("DC4", "Investigation concluded (extended)", "extended", 60, "calendar", "first_contact_on", "concluded_on",
     "Same, for disputes in the extended window class. Same pause note."),
    ("DC5", "Final notice to customer", "all", 3, "business", "concluded_on", "final_notice_on",
     "Customer told the result within 3 business days of the conclusion. The clock starts at the "
     "conclusion, so it has not started while the investigation is open."),
]

# (dispute_type, credit_eligible), weight
TYPES = [(("unauthorized_card", 1), 0.30), (("unauthorized_transfer", 1), 0.15), (("billing_error", 0), 0.25),
         (("merchant_dispute", 0), 0.20), (("duplicate_charge", 0), 0.10)]
LAGS = [(0, 0.55), (1, 0.20), (2, 0.12), (3, 0.07), (5, 0.06)]          # business days from contact to logging
PLANS = {
    "DC1": [("on_time", 0.60), ("boundary", 0.14), ("late", 0.16), ("never", 0.10)],
    "DC2": [("on_time", 0.50), ("boundary", 0.12), ("late", 0.22), ("never", 0.16)],
    "INV": [("on_time", 0.60), ("boundary", 0.08), ("late", 0.14), ("never", 0.18)],
    "DC5": [("on_time", 0.60), ("boundary", 0.10), ("late", 0.20), ("never", 0.10)],
}
P_EXTENDED = 0.18
P_MISRECORDED = 0.25      # of the disputes recorded as extended, the share where the extension never applied
P_PAUSE = 0.16


# ---------------------------------------------------------------- day arithmetic (generator's own)
def is_bd(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAY_SET


def roll_forward(d: dt.date) -> dt.date:
    while not is_bd(d):
        d += ONE
    return d


def roll_back(d: dt.date) -> dt.date:
    while not is_bd(d):
        d -= ONE
    return d


def step_bd(d: dt.date, n: int) -> dt.date:
    """The date reached by stepping n business days forward from d. d itself is not counted."""
    while n > 0:
        d += ONE
        if is_bd(d):
            n -= 1
    return d


def bd_elapsed(a: dt.date, b: dt.date) -> int:
    """Business days in the range after a, up to and including b."""
    return sum(1 for k in range(1, (b - a).days + 1) if is_bd(a + k * ONE))


def days_between(a: dt.date, b: dt.date):
    return [a + k * ONE for k in range((b - a).days + 1)]


def pick(pairs):
    x, acc = rng.random(), 0.0
    for value, weight in pairs:
        acc += weight
        if x < acc:
            return value
    return pairs[-1][0]


def place(plan: str, earliest: dt.date, due: dt.date):
    """Choose the date a step happened under the plan, or None when it did not happen."""
    if plan == "never":
        return None
    if plan == "on_time":
        days = [d for d in days_between(earliest, due) if is_bd(d)]
        return rng.choice(days) if days else earliest
    if plan == "boundary":
        return max(earliest, roll_back(due))
    return max(earliest, step_bd(due, rng.choice([1, 1, 2, 2, 3, 4, 6, 9])))


def kept(d):
    """A step dated after the as-of date has not happened yet."""
    return d if d is not None and d <= AS_OF else None


# ---------------------------------------------------------------- one dispute
def make_dispute() -> dict:
    dtype, credit = pick(TYPES)
    extended = rng.random() < P_EXTENDED
    misrecorded = extended and rng.random() < P_MISRECORDED
    window = 60 if extended and not misrecorded else 30      # the window that really applied
    contact = CONTACT_FIRST + rng.randrange((CONTACT_LAST - CONTACT_FIRST).days + 1) * ONE
    lag = pick(LAGS)
    logged = step_bd(roll_forward(contact), lag)
    while logged > AS_OF:
        lag -= 1
        logged = step_bd(roll_forward(contact), lag)

    requested = received = None
    pause_days = 0
    if rng.random() < P_PAUSE:
        requested = step_bd(logged, rng.randrange(1, 6))
        received = requested + rng.randrange(3, 22) * ONE
        if received > AS_OF:
            requested = received = None
        else:
            pause_days = (received - requested).days

    # investigation: the planted due date includes the pause
    inv_due = contact + (window + pause_days) * ONE
    inv_earliest = max(step_bd(logged, 3), roll_forward(received) if received else logged)
    concluded = kept(place(pick(PLANS["INV"]), inv_earliest, inv_due))
    final = None
    if concluded:
        final = kept(place(pick(PLANS["DC5"]), concluded, step_bd(concluded, 3)))
    ack = kept(place(pick(PLANS["DC1"]), logged, step_bd(contact, 2)))
    if ack and concluded and ack > concluded:
        ack = None
    cred = None
    if credit:
        cred = kept(place(pick(PLANS["DC2"]), logged, step_bd(contact, 7)))
        if cred and concluded and cred > concluded:
            cred = None
    return {"dispute_type": dtype, "window_class": "extended" if extended else "standard", "credit_eligible": credit,
            "first_contact_on": contact, "logged_on": logged, "acknowledged_on": ack, "provisional_credit_on": cred,
            "concluded_on": concluded, "final_notice_on": final, "info_requested_on": requested,
            "info_received_on": received, "pause_days": pause_days, "window_true": window,
            "misrecorded": misrecorded}


# ---------------------------------------------------------------- truth
def applies(d: dict, applies_to: str) -> bool:
    return {"all": True, "credit_eligible": d["credit_eligible"] == 1, "standard": d["window_class"] == "standard",
            "extended": d["window_class"] == "extended"}[applies_to]


def truth_rows(d: dict):
    rows = []
    for cid, _name, applies_to, window, unit, anchor_col, sat_cols, _note in CLOCKS:
        if not applies(d, applies_to):
            continue
        anchor = d[anchor_col]
        if anchor is None:
            rows.append((d["dispute_id"], cid, "not_started", "", ""))
            continue
        pause = d["pause_days"] if cid in ("DC3", "DC4") else 0
        window = d["window_true"] if cid in ("DC3", "DC4") else window
        sent_dates = [d[c] for c in sat_cols.split("|") if d[c] is not None]
        sent = min(sent_dates) if sent_dates else None
        if unit == "business":
            due = step_bd(anchor, window)
            elapsed = lambda x: bd_elapsed(anchor, x)                  # noqa: E731
        else:
            due = anchor + (window + pause) * ONE
            elapsed = lambda x: (x - anchor).days - pause              # noqa: E731
        if sent is not None:
            status = "on_time" if elapsed(sent) <= window else "late"
            assert (sent <= due) == (status == "on_time"), (d["dispute_id"], cid)
        else:
            status = "running" if elapsed(AS_OF) <= window else "breached"
            assert (AS_OF <= due) == (status == "running"), (d["dispute_id"], cid)
        tags = []
        if sent is not None and sent == due:
            tags.append("boundary")
        if unit == "business" and any(h.weekday() < 5 and anchor < h <= due for h in HOLIDAYS):
            tags.append("holiday")
        if cid in ("DC1", "DC2", "DC3", "DC4") and d["logged_on"] > d["first_contact_on"]:
            tags.append("logged_late")
        if pause:
            tags.append("pause")
        if cid == "DC4" and d["misrecorded"]:
            tags.append("misrecorded")
        rows.append((d["dispute_id"], cid, status, due.isoformat(), "|".join(sorted(tags))))
    return rows


# ---------------------------------------------------------------- write
def iso(d) -> str:
    return d.isoformat() if d is not None else ""


def write_csv(path: str, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


DISPUTE_HEADER = ["dispute_id", "dispute_type", "window_class", "credit_eligible", "first_contact_on", "logged_on",
                  "acknowledged_on", "provisional_credit_on", "concluded_on", "final_notice_on",
                  "info_requested_on", "info_received_on"]


def dispute_row(d: dict):
    return [d["dispute_id"], d["dispute_type"], d["window_class"], d["credit_eligible"]] + \
           [iso(d[c]) for c in DISPUTE_HEADER[4:]]


def main() -> None:
    disputes = [make_dispute() for _ in range(N_DISPUTES)]
    disputes.sort(key=lambda d: d["first_contact_on"])
    for i, d in enumerate(disputes, start=1):
        d["dispute_id"] = "DSP-%04d" % i

    write_csv("policy.csv",
              ["clock_id", "clock_name", "applies_to", "window_days", "day_type", "anchor_event", "satisfied_by",
               "basis", "note"],
              [[cid, name, applies_to, window, unit, anchor, sat, ASSUMPTION, note]
               for cid, name, applies_to, window, unit, anchor, sat, note in CLOCKS])
    write_csv("holidays.csv", ["date", "name"],
              [[h.isoformat(), "Modeled holiday %02d" % k] for k, h in enumerate(HOLIDAYS, start=1)])
    with open("as_of.txt", "w", encoding="utf-8", newline="") as fh:
        fh.write(AS_OF.isoformat() + "\n")
    write_csv("disputes.csv", DISPUTE_HEADER, [dispute_row(d) for d in disputes])
    truth = [r for d in disputes for r in truth_rows(d)]
    write_csv("truth.csv", ["dispute_id", "clock_id", "planted_status", "planted_due", "hard_case"], truth)
    example = {"dispute_id": "DSP-EX1", "dispute_type": "unauthorized_card", "window_class": "standard",
               "credit_eligible": 1, "first_contact_on": dt.date(2026, 9, 4), "logged_on": dt.date(2026, 9, 4),
               "acknowledged_on": dt.date(2026, 9, 9), "provisional_credit_on": dt.date(2026, 9, 18),
               "concluded_on": None, "final_notice_on": None, "info_requested_on": None, "info_received_on": None}
    write_csv("example_disputes.csv", DISPUTE_HEADER, [dispute_row(example)])


if __name__ == "__main__":
    main()
