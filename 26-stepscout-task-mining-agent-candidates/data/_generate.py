"""Generates the StepScout synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes six CSVs next to this file)

What it builds
  cases.csv           1,500 wire-repair exception cases created over 30 calendar days (22 working
                      days), each with a variant id (the step path it really took, rework included)
                      and a reopen flag. Two truth columns: true_path (the generator's record of the
                      steps taken) and offdesk_min_truth (minutes of work done off the desktop, phone
                      calls, that no event file records).
  desktop_events.csv  task-mining style events: case, pseudonymous worker, application, action, the
                      step label the miner infers, start, end, and typed_chars (a count, never the
                      text). Steps 1-3 never read the step label; step 4 does.
  system_events.csv   case-system status changes only: the subset of the work that posts a status.
  sme_process_map.csv the happy path as an interview with a subject-matter expert would give it,
                      with minutes per step.
  step_catalog.csv    the step catalog: register columns a team could supply, the ANSWER KEY
                      (truth_class) and the parameters planted in the events.
  workers.csv         14 workers, pseudonymous ids only.

The workflow is the modeled wire-repair queue from the shared contract (S01 to S12), plus four steps
added here (S13 to S16). Two of them are decoys, and the printed answer key says which:
  S13 triage_beneficiary_bank_reply: HUMAN_JUDGMENT, high volume, long waits, posts a status, so a
      ranking by volume times time puts it near the top.
  S14 choose_resolution_route: HUMAN_JUDGMENT that looks rule-based. On the desktop it is a short,
      tight-timed dropdown pick with no free text and no overrides. The judgment is made in a phone
      call before the pick, and no event file sees the call. It is the known miss.
Everything is synthetic. No real bank, process, vendor or person. No model is used anywhere.

Time. Workers work 08:00 to 18:00, Monday to Friday. Every duration here is in working time and is
written as a wall-clock timestamp, so nights and weekends are not part of any wait. Hour zero is
EPOCH, a constant; the clock is never read.

The parameters below are my assumptions about how such a queue behaves. They set the size of every
effect in the walkthrough, so each result is a property of this data and not an estimate of a real queue.
"""

from __future__ import annotations

import csv
import math
import random
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path

SEED = 20261018
OUT = Path(__file__).parent

N_CASES = 1500
EPOCH = date(2026, 9, 1)            # a Tuesday
CASE_WINDOW_END = date(2026, 9, 30)  # cases are created on working days up to here
DAY_S = 36000                        # one working day, 08:00 to 18:00, in seconds
N_WORKDAYS = 130                     # calendar room for waits that run past the window


def _workdates(n: int) -> list:
    d, out = EPOCH, []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


WORKDATES = _workdates(N_WORKDAYS)
CASE_DAYS = sum(1 for d in WORKDATES if d <= CASE_WINDOW_END)   # 22


def wall(w: float) -> datetime:
    day, s = divmod(int(w), DAY_S)
    return datetime.combine(WORKDATES[day], time(8, 0)) + timedelta(seconds=s)


def fmt(w: float) -> str:
    return wall(w).strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------------------------
# Workers (pseudonymous ids only)
# ---------------------------------------------------------------------------------------------
WORKERS = [
    ("W01", "operator", "repair_a", "3y+"), ("W02", "operator", "repair_a", "1-3y"),
    ("W03", "operator", "repair_a", "<1y"), ("W04", "operator", "repair_a", "1-3y"),
    ("W05", "operator", "repair_a", "3y+"), ("W06", "operator", "repair_b", "1-3y"),
    ("W07", "operator", "repair_b", "<1y"), ("W08", "operator", "repair_b", "3y+"),
    ("W09", "operator", "repair_b", "1-3y"), ("W10", "senior_operator", "repair_a", "3y+"),
    ("W11", "senior_operator", "repair_b", "3y+"), ("W12", "senior_operator", "repair_b", "3y+"),
    ("W13", "approver", "repair_a", "3y+"), ("W14", "approver", "repair_b", "3y+"),
]
SPEED = {"<1y": 1.15, "1-3y": 1.00, "3y+": 0.90}     # multiplier on touch time
OPERATORS = [w[0] for w in WORKERS if w[1] == "operator"]
SENIORS = [w[0] for w in WORKERS if w[1] == "senior_operator"]
CHECKERS = [w[0] for w in WORKERS if w[1] == "approver"] + SENIORS     # who may approve (four-eyes)
SPEED_OF = {w[0]: SPEED[w[3]] for w in WORKERS}

# ---------------------------------------------------------------------------------------------
# Exception reasons: weight, share ambiguous match, share needing information, share cutoff check
# ---------------------------------------------------------------------------------------------
REASONS = [
    ("R01_invalid_account", 0.26, 0.12, 0.30, 0.15),
    ("R02_name_mismatch",   0.22, 0.62, 0.30, 0.10),
    ("R03_closed_account",  0.14, 0.10, 0.45, 0.15),
    ("R04_wrong_bank_id",   0.16, 0.10, 0.20, 0.20),
    ("R05_missing_field",   0.12, 0.05, 0.70, 0.10),
    ("R06_cutoff_missed",   0.10, 0.05, 0.10, 0.90),
]
P_ROUTE_IF_COMPLEX = 0.85      # a route is chosen in 85% of cases that had an ambiguity or a reply
P_ROUTE_OTHER = 0.20
P_BOUNCE = 0.10                # the second person sends the draft back
P_BOUNCE_AGAIN = 0.30
P_REPLY_AGAIN = 0.40           # another reply to triage
P_S07_AGAIN = 0.12
P_REOPEN = 0.09

# ---------------------------------------------------------------------------------------------
# The step catalog. truth is the ANSWER KEY. The rest is behavior planted in the events.
#   med, sig   median touch minutes and lognormal sigma of one occurrence
#   recipe     (application, action, share of the touch time) for the main events
#   text       mean characters typed per occurrence (a count; the text is never stored)
#   ovr        share of occurrences in which the worker overrides a proposed value
#   copy, pair share of occurrences with a cross-application copy, and from which app to which
#   wait       (median, sigma) of working minutes between the previous step ending and this one starting
#   offdesk    (share of occurrences, minutes low, minutes high) of work off the desktop (a phone call)
# ---------------------------------------------------------------------------------------------
STEPS = [
    dict(id="S01", name="open_exception", truth="AGENT", status="OPENED", restricted=0, control=0, gated="",
         fields="exception_id;queue;received_at", order=1, med=1.5, sig=0.25,
         recipe=[("case_system", "open", 1.0)], text=0, text_app="case_system", ovr=0.0, copy=0.0, pair=None,
         wait=(75, 0.8), offdesk=None),
    dict(id="S02", name="read_reason_code", truth="AGENT", status="REASON_CODED", restricted=0, control=0, gated="",
         fields="reason_code;return_text", order=2, med=1.0, sig=0.25,
         recipe=[("case_system", "read", 1.0)], text=0, text_app="case_system", ovr=0.0, copy=0.0, pair=None,
         wait=(0.4, 0.5), offdesk=None),
    dict(id="S15", name="check_cutoff_and_value_date", truth="AGENT", status="", restricted=0, control=0, gated="",
         fields="value_date;cutoff_time", order=3, med=1.5, sig=0.20,
         recipe=[("payments_hub", "read", 1.0)], text=0, text_app="payments_hub", ovr=0.0, copy=0.0, pair=None,
         wait=(0.4, 0.5), offdesk=None),
    dict(id="S03", name="lookup_original_payment", truth="AGENT", status="", restricted=0, control=0, gated="",
         fields="payment_reference;amount;value_date;beneficiary_bank", order=4, med=4.0, sig=0.35,
         recipe=[("payments_hub", "search", 0.4), ("payments_hub", "read", 0.6)], text=0, text_app="payments_hub",
         ovr=0.02, copy=0.55, pair=("case_system", "payments_hub"), wait=(0.4, 0.5), offdesk=None),
    dict(id="S04", name="copy_beneficiary_fields", truth="AGENT", status="", restricted=0, control=0, gated="",
         fields="beneficiary_name;account_number;bank_id", order=5, med=5.0, sig=0.30,
         recipe=[("payments_hub", "copy", 0.18), ("spreadsheet", "paste", 0.15), ("spreadsheet", "edit_cell", 0.25),
                 ("spreadsheet", "copy", 0.12), ("case_system", "paste", 0.30)],
         text=0, text_app="case_system", ovr=0.02, copy=0.95, pair=None, wait=(0.4, 0.5), offdesk=None),
    dict(id="S05", name="match_name_account", truth="AGENT", status="MATCH_CHECKED", restricted=0, control=0, gated="",
         fields="beneficiary_name;account_number;match_score", order=6, med=3.0, sig=0.35,
         recipe=[("matching_tool", "read", 0.6), ("matching_tool", "select", 0.4)], text=15, text_app="case_system",
         ovr=0.06, copy=0.0, pair=None, wait=(0.4, 0.5), offdesk=None),
    dict(id="S06", name="screen_watchlist", truth="AGENT", status="SCREENED", restricted=1, control=0, gated="",
         fields="party_name;country;list_result", order=7, med=3.5, sig=0.30,
         recipe=[("screening_app", "search", 0.45), ("screening_app", "read", 0.55)], text=40, text_app="screening_app",
         ovr=0.0, copy=0.0, pair=None, wait=(1.0, 0.5), offdesk=None),
    dict(id="S07", name="judge_ambiguous_match", truth="HUMAN_JUDGMENT", status="MATCH_REVIEWED", restricted=1,
         control=0, gated="", fields="match_score;party_documents;prior_cases", order=8, med=9.0, sig=0.60,
         recipe=[("case_system", "read", 0.25), ("matching_tool", "read", 0.25), ("payments_hub", "read", 0.2),
                 ("case_system", "type", 0.3)], text=240, text_app="case_system", ovr=0.55, copy=0.30,
         pair=("payments_hub", "case_system"), wait=(90, 0.8), offdesk=(0.20, 3, 8)),
    dict(id="S16", name="request_info_from_originator", truth="AGENT_HITL", status="INFO_REQUESTED", restricted=0,
         control=0, gated="", fields="originator_contact;missing_fields;template_id", order=9, med=4.5, sig=0.35,
         recipe=[("case_system", "read", 0.25), ("email", "type", 0.35), ("email", "send", 0.40)], text=150,
         text_app="email", ovr=0.10, copy=0.10, pair=("case_system", "email"), wait=(10, 0.6), offdesk=None),
    dict(id="S13", name="triage_beneficiary_bank_reply", truth="HUMAN_JUDGMENT", status="REPLY_LOGGED", restricted=0,
         control=0, gated="", fields="reply_text;case_history;requested_fields", order=10, med=7.0, sig=0.55,
         recipe=[("email", "read", 0.40), ("case_system", "type", 0.45), ("case_system", "select", 0.15)],
         text=420, text_app="case_system", ovr=0.35, copy=0.50, pair=("email", "case_system"), wait=(240, 0.9),
         offdesk=None),
    dict(id="S14", name="choose_resolution_route", truth="HUMAN_JUDGMENT", status="ROUTE_SET", restricted=0,
         control=0, gated="", fields="route_options;case_summary", order=11, med=2.0, sig=0.12,
         recipe=[("case_system", "select", 0.6), ("case_system", "submit", 0.4)], text=0, text_app="case_system",
         ovr=0.02, copy=0.0, pair=None, wait=(15, 0.6), offdesk=(1.0, 6, 14)),
    dict(id="S08", name="draft_correction", truth="AGENT_HITL", status="CORRECTION_DRAFTED", restricted=0, control=0,
         gated="", fields="corrected_beneficiary;correction_narrative", order=12, med=6.0, sig=0.40,
         recipe=[("case_system", "read", 0.3), ("case_system", "type", 0.7)], text=150, text_app="case_system",
         ovr=0.22, copy=0.0, pair=None, wait=(25, 0.7), offdesk=None),
    dict(id="S09", name="approve_four_eyes", truth="HUMAN_CONTROL", status="APPROVED", restricted=0, control=1,
         gated="", fields="draft_correction;approver_id", order=13, med=2.5, sig=0.40,
         recipe=[("case_system", "read", 0.7), ("case_system", "select", 0.3)], text=0, text_app="case_system",
         ovr=0.01, copy=0.0, pair=None, wait=(110, 0.8), offdesk=None),
    dict(id="S10", name="resubmit_payment", truth="AGENT_HITL", status="RESUBMITTED", restricted=0, control=0,
         gated="S09", fields="corrected_beneficiary;payment_reference;approval_id", order=14, med=2.5, sig=0.30,
         recipe=[("case_system", "read", 0.35), ("payments_hub", "submit", 0.65)], text=0, text_app="payments_hub",
         ovr=0.0, copy=0.70, pair=("case_system", "payments_hub"), wait=(12, 0.6), offdesk=None),
    dict(id="S11", name="write_case_note", truth="AGENT", status="NOTE_ADDED", restricted=0, control=0, gated="",
         fields="case_summary;actions_taken", order=15, med=3.0, sig=0.30,
         recipe=[("case_system", "read", 0.25), ("case_system", "type", 0.75)], text=210, text_app="case_system",
         ovr=0.04, copy=0.0, pair=None, wait=(2.0, 0.5), offdesk=None),
    dict(id="S12", name="close_case", truth="AGENT", status="CLOSED", restricted=0, control=0, gated="",
         fields="case_id;closure_code", order=16, med=1.0, sig=0.20,
         recipe=[("case_system", "submit", 1.0)], text=0, text_app="case_system", ovr=0.0, copy=0.0, pair=None,
         wait=(1.0, 0.5), offdesk=None),
]
BY_ID = {s["id"]: s for s in STEPS}

# What the interview with the subject-matter expert documents: one happy path, minutes per step.
SME_MAP = [
    ("S01", "Open the exception from the queue", "case system", "operator", 2),
    ("S02", "Read the reason code", "case system", "operator", 2),
    ("S03", "Look up the original payment", "payments hub", "operator", 5),
    ("S04", "Copy the beneficiary details", "case system", "operator", 3),
    ("S05", "Check that name and account match", "case system", "operator", 4),
    ("S06", "Screen the party against the watch list", "screening application", "operator", 3),
    ("S08", "Draft the correction", "case system", "operator", 8),
    ("S09", "Second person approves", "case system", "approver", 3),
    ("S10", "Resubmit the payment", "payments hub", "operator", 3),
    ("S11", "Write the case note", "case system", "operator", 4),
    ("S12", "Close the case", "case system", "operator", 1),
]
HAPPY = [r[0] for r in SME_MAP]

# ---------------------------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------------------------
rng = random.Random(SEED)
SLOT_S = 10                      # a worker's time is booked in 10-second slots
BUSY = {w[0]: bytearray(N_WORKDAYS * DAY_S // SLOT_S + 360) for w in WORKERS}
BLANK_STEP_SHARE = 0.025        # events whose step the miner cannot infer
GAP_S = (2, 12)                 # seconds between the events of one occurrence
MAX_SPEED = max(SPEED.values())


def lognorm(median: float, sigma: float) -> float:
    return math.exp(math.log(median) + rng.gauss(0.0, sigma))


def fit_workday(t: float, span: float) -> float:
    """Push a start to the next morning if the occurrence would run past 18:00."""
    if (t % DAY_S) + span > DAY_S:
        return (t // DAY_S + 1) * DAY_S + rng.randint(0, 120)
    return t


def first_free(w: str, t: float, span: float) -> float:
    ba = BUSY[w]
    while True:
        t = fit_workday(t, span)
        a, b = int(t // SLOT_S), int((t + span) // SLOT_S) + 1
        k = ba.find(1, a, b)
        if k < 0:
            return t
        t = (k + 1) * SLOT_S


def claim(pool: list, ready: float, span: float, patience: float = 240.0):
    """Take the first worker in pool order who can start within `patience` seconds of `ready`; if none
    can, the worker who can start earliest. Books the time and returns (worker, start)."""
    best = None
    for w in pool:
        s = first_free(w, ready, span)
        if s <= ready + patience:
            best = (w, s)
            break
        if best is None or s < best[1]:
            best = (w, s)
    w, s = best
    a, b = int(s // SLOT_S), int((s + span) // SLOT_S) + 1
    BUSY[w][a:b] = b"\x01" * (b - a)
    return w, s


def make_events(step: dict, total_s: float, flags: dict):
    """The events of one occurrence on a relative clock that starts at 0. Returns (events, span).
    Each event is [application, action, step label, start, end, typed_chars]."""
    ev, t = [], 0.0

    def add(app, action, dur, chars=0):
        nonlocal t
        dur = max(3.0, dur)
        label = step["id"] if rng.random() > BLANK_STEP_SHARE else ""
        ev.append([app, action, label, t, t + dur, chars])
        t += dur + rng.uniform(*GAP_S)

    chars = flags["chars"]
    recipe = step["recipe"]
    if step["id"] == "S04" and not flags["copy_flow"]:
        recipe = [("payments_hub", "read", 0.4), ("case_system", "type", 0.6)]
        chars = int(rng.uniform(25, 70))
    if flags["pair"]:
        src, dst = step["pair"]
        add(src, "copy", rng.uniform(6, 14))
        add(dst, "paste", rng.uniform(6, 14))
    n_type = sum(1 for r in recipe if r[1] == "type")
    for app, action, share in recipe:
        add(app, action, total_s * share * rng.uniform(0.92, 1.08), int(chars / n_type) if action == "type" else 0)
    if chars and not n_type:
        add(step["text_app"], "type", rng.uniform(6, 15), chars)
    if flags["override"]:
        add(step["text_app"], "override_value", rng.uniform(15, 35))
    if step["id"] == "S06" and flags["hit"]:
        add("screening_app", "submit", rng.uniform(10, 25))
    return ev, ev[-1][4]


def planted_repeats(step_id: str) -> float:
    """Expected runs of a step per case that includes it, from the path rules (rework excluded)."""
    if step_id == "S07":
        return round(1 + P_S07_AGAIN, 2)
    if step_id == "S13":
        p, n_max = P_REPLY_AGAIN, 4
        probs = [(1 - p) * p ** (k - 1) for k in range(1, n_max)] + [p ** (n_max - 1)]
        return round(sum(k * q for k, q in enumerate(probs, 1)), 2)
    if step_id in ("S08", "S09"):
        return round(1 + P_BOUNCE * (1 + P_BOUNCE_AGAIN), 2)
    return 1.0


def reopen_sequence() -> list:
    seq = ["S01", "S03"] + ["S13"] * (2 if rng.random() < P_REPLY_AGAIN else 1)
    if rng.random() < 0.5:
        seq.append("S14")
    return seq + ["S08", "S09", "S10", "S11", "S12"]


def build_path(reason: tuple) -> tuple:
    _, _, p_amb, p_info, p_cut = reason
    amb = rng.random() < p_amb
    info = rng.random() < min(0.9, p_info * (1.5 if amb else 1.0))
    cut = rng.random() < p_cut
    route = rng.random() < (P_ROUTE_IF_COMPLEX if (amb or info) else P_ROUTE_OTHER)
    seq = ["S01", "S02"] + (["S15"] if cut else []) + ["S03", "S04", "S05", "S06"]
    if amb:
        seq += ["S07"] * (2 if rng.random() < P_S07_AGAIN else 1)
    if info:
        n = 1
        while rng.random() < P_REPLY_AGAIN and n < 4:
            n += 1
        seq += ["S16"] + ["S13"] * n
    if route:
        seq.append("S14")
    n_draft = 1
    if rng.random() < P_BOUNCE:
        n_draft = 3 if rng.random() < P_BOUNCE_AGAIN else 2
    for _ in range(n_draft):
        seq += ["S08", "S09"]
    seq += ["S10", "S11", "S12"]
    return seq, rng.random() < P_REOPEN


def main() -> None:
    # --- case arrivals: weighted hours of the day, working days only ---------------------------
    hour_w = [1.2, 1.3, 1.2, 1.0, 0.8, 0.9, 1.0, 0.9, 0.8, 0.5]
    day_w = [1.15 if WORKDATES[d].weekday() == 0 else 1.0 for d in range(CASE_DAYS)]
    created = []
    for _ in range(N_CASES):
        d = rng.choices(range(CASE_DAYS), weights=day_w)[0]
        h = rng.choices(range(10), weights=hour_w)[0]
        created.append(d * DAY_S + h * 3600 + rng.randint(0, 3599))
    created.sort()
    reason_w = [r[1] for r in REASONS]

    cases, desk_rows, sys_rows, paths = [], [], [], []
    for i, c_w in enumerate(created):
        cid = f"C{i + 1:05d}"
        reason = rng.choices(REASONS, weights=reason_w)[0]
        seq, reopen = build_path(reason)
        primary = rng.choice(OPERATORS)
        sys_rows.append([cid, "RECEIVED", fmt(c_w), "system"])
        state = {"cur": float(c_w), "offdesk": 0.0, "drafter": primary}

        def run(step_id: str, tag: str = "") -> None:
            st = BY_ID[step_id]
            wait_med, wait_sig = (900, 0.6) if tag == "reopen" else st["wait"]
            ready = state["cur"] + lognorm(wait_med, wait_sig) * 60
            if step_id == "S07":
                pool = list(SENIORS)
                rng.shuffle(pool)
            elif step_id == "S09":
                pool = [w for w in CHECKERS if w != state["drafter"]]
                rng.shuffle(pool)
            else:
                others = [w for w in OPERATORS if w != primary]
                rng.shuffle(others)
                pool = [primary] + others
            flags = {"override": rng.random() < st["ovr"],
                     "pair": bool(st["pair"]) and rng.random() < st["copy"],
                     "copy_flow": rng.random() < st["copy"] if step_id == "S04" else True,
                     "hit": rng.random() < 0.12,
                     "chars": int(max(1, lognorm(st["text"], 0.35))) if st["text"] else 0}
            evs, span = make_events(st, lognorm(st["med"], st["sig"]) * 60 * MAX_SPEED, flags)
            call_s = 0.0
            if st["offdesk"] and rng.random() < st["offdesk"][0]:
                call_s = rng.uniform(st["offdesk"][1], st["offdesk"][2]) * 60
            w_sel, start = claim(pool, ready, call_s + span)
            f = SPEED_OF[w_sel] / MAX_SPEED          # a faster worker shrinks the whole occurrence
            base = start + call_s
            for app, action, label, a, b, chars in evs:
                desk_rows.append([cid, w_sel, app, action, label, fmt(base + a * f), fmt(base + b * f), chars])
            end = base + span * f
            state["offdesk"] += call_s
            if st["status"] or tag == "reopen":
                status = "REOPENED" if tag == "reopen" else st["status"]
                sys_rows.append([cid, status, fmt(end + rng.uniform(0, 25)), w_sel])
            if step_id == "S08":
                state["drafter"] = w_sel
            state["cur"] = end

        for sid in seq:
            run(sid)
        if reopen:
            extra = reopen_sequence()
            for k, sid in enumerate(extra):
                run(sid, "reopen" if k == 0 else "")
            seq = seq + extra
        paths.append(seq)
        cases.append({"id": cid, "created": fmt(c_w), "reason": reason[0], "reopened": int(reopen),
                      "primary": primary, "offdesk": round(state["offdesk"] / 60, 1)})

    # variant ids: V01 is the most common true path
    counts = Counter(tuple(p) for p in paths)
    first_seen = {}
    for idx, p in enumerate(paths):
        first_seen.setdefault(tuple(p), idx)
    order = sorted(counts, key=lambda k: (-counts[k], first_seen[k]))
    vid = {k: f"V{n + 1:02d}" for n, k in enumerate(order)}
    closes = {}
    for r in sorted(sys_rows, key=lambda r: r[2]):
        if r[1] == "CLOSED":
            closes.setdefault(r[0], []).append(r[2])
    case_rows = [[c["id"], c["created"], closes[c["id"]][0], closes[c["id"]][-1], c["reason"], vid[tuple(p)],
                  c["reopened"], c["primary"], c["offdesk"], ">".join(p)] for c, p in zip(cases, paths)]
    desk_rows.sort(key=lambda r: (r[5], r[0], r[6]))
    sys_rows.sort(key=lambda r: (r[0], r[2]))

    # --- write files ------------------------------------------------------------------------
    def write(name, header, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    write("cases.csv", ["case_id", "created", "first_closed", "final_closed", "reason_code", "variant_id", "reopened",
                        "primary_worker", "offdesk_min_truth", "true_path"], case_rows)
    write("desktop_events.csv", ["case_id", "worker_id", "application", "action", "step_id", "start", "end",
                                 "typed_chars"], desk_rows)
    write("system_events.csv", ["case_id", "status", "ts", "worker_id"], sys_rows)
    write("sme_process_map.csv", ["seq", "step_id", "step", "systems_named", "owner_role", "minutes_per_step"],
          [[n + 1, r[0], r[1], r[2], r[3], r[4]] for n, r in enumerate(SME_MAP)])
    write("workers.csv", ["worker_id", "role", "team", "tenure_band"], [list(w) for w in WORKERS])
    write("step_catalog.csv",
          ["step_id", "step_name", "process_order", "status_event", "restricted_data", "control_flag", "gated_by",
           "data_fields", "truth_class", "planted_median_touch_min", "planted_timing_sigma", "planted_text_chars",
           "planted_override_rate", "planted_cross_app_copy", "planted_repeats_per_case", "planted_offdesk_share"],
          [[s["id"], s["name"], s["order"], s["status"], s["restricted"], s["control"], s["gated"], s["fields"],
            s["truth"], s["med"], s["sig"], s["text"], s["ovr"], s["copy"], planted_repeats(s["id"]),
            (s["offdesk"][0] if s["offdesk"] else 0)]
           for s in sorted(STEPS, key=lambda s: s["id"])])

    # --- print what was built -------------------------------------------------------------
    happy_n = sum(1 for p, c in zip(paths, cases) if p == HAPPY)
    print(f"cases.csv           {len(case_rows):>7,} cases, {len(counts)} variants, {sum(c['reopened'] for c in cases)} reopened")
    print(f"desktop_events.csv  {len(desk_rows):>7,} events, {sum(1 for r in desk_rows if not r[4]):,} without a step label")
    print(f"system_events.csv   {len(sys_rows):>7,} status events")
    print(f"exact happy path, no reopen: {happy_n} cases ({100 * happy_n / len(cases):.1f}%)")
    overlaps, by_worker = 0, {}
    for r in desk_rows:
        by_worker.setdefault(r[1], []).append((r[5], r[6]))
    for rows in by_worker.values():
        rows.sort()
        overlaps += sum(1 for (a0, a1), (b0, b1) in zip(rows, rows[1:]) if b0 < a1)
    print(f"overlapping events for one worker: {overlaps}")


if __name__ == "__main__":
    main()
