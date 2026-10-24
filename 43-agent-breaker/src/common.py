"""Shared loading, the two baseline approaches and the scoring for the four step scripts of project 43.

Every approach is run over the same recorded stream (data/events.csv). The stream holds what each agent did
or would have done on every call; an approach decides which of those calls actually reach the agent. The
truth (data/truth_calls.csv, data/faults.csv) was written by the generator and is read only by the scoring.
"""
from __future__ import annotations

import csv
import os
import sys
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from agent_breaker import CLOSED, HALF_OPEN, OPEN, load_controls, load_events, load_policy, run_stream  # noqa: E402


def _rows(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_all() -> dict:
    return {
        "events": load_events(os.path.join(DATA, "events.csv")),
        "controls": load_controls(os.path.join(DATA, "controls.csv")),
        "policy": load_policy(os.path.join(DATA, "policy.csv")),
        "assume": {r["parameter"]: float(r["value"]) for r in _rows("model_assumptions.csv")},
        "truth": {r["case_id"]: (r["fault_id"], int(r["harm"])) for r in _rows("truth_calls.csv")},
        "faults": [{"id": r["fault_id"], "agent": r["agent"], "kind": r["kind"], "cls": r["truth_class"],
                    "start": int(r["start_min"]), "end": int(r["end_min"]), "intensity": r["intensity"],
                    "calls": int(r["calls"]), "harm": int(r["harm_calls"])} for r in _rows("faults.csv")],
    }


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


def _rec(e: dict, route: str, state: str) -> dict:
    return {"t": e["t"], "agent": e["agent"], "case": e["case"], "route": route, "state": state}


# ---------------------------------------------------------------- the approaches
def no_stop_run(d: dict) -> dict:
    return {"records": [_rec(e, "agent", CLOSED) for e in d["events"]], "trips": [], "closes": []}


def manual_run(d: dict) -> dict:
    """An operator switch and a person who reads the failure rate on a schedule (all numbers are assumptions)."""
    a = d["assume"]
    every, back, hold = int(a["manual_review_interval_min"]), int(a["manual_lookback_min"]), int(a["manual_hold_min"])
    served, until = {}, {}
    records, trips, closes = [], [], []
    review = every
    for e in d["events"]:
        while e["t"] >= review:
            for agent in sorted(served):
                if agent in until:
                    if review >= until[agent]:
                        del until[agent]
                        closes.append((agent, review))
                    continue
                recent = [bad for t, bad in served[agent] if review - back <= t < review]
                if len(recent) >= a["manual_min_calls"] and sum(recent) / len(recent) >= a["manual_trip_failure_rate"]:
                    until[agent] = review + hold
                    trips.append((agent, review))
            review += every
        agent = e["agent"]
        served.setdefault(agent, [])
        if agent in until:
            records.append(_rec(e, "human_queue", OPEN))
        else:
            records.append(_rec(e, "agent", CLOSED))
            served[agent].append((e["t"], e["outcome"] == "fail"))
    return {"records": records, "trips": trips, "closes": closes}


def basic_run(d: dict, consecutive: int | None = None, hold: int | None = None) -> dict:
    """The common shape: count failures in a row, open for a fixed time, let one probe through, close on its success.
    The count and the hold default to the breaker's own consecutive_trip and hold_min, so only the rules differ."""
    consecutive = d["policy"]["consecutive_trip"] if consecutive is None else consecutive
    hold = d["policy"]["hold_min"] if hold is None else hold
    st = {}
    records, trips, closes = [], [], []
    for e in d["events"]:
        s = st.setdefault(e["agent"], {"state": CLOSED, "run": 0, "opened": 0})
        if s["state"] == OPEN and e["t"] - s["opened"] >= hold:
            s["state"] = HALF_OPEN
        if s["state"] == OPEN:
            records.append(_rec(e, "human_queue", OPEN))
            continue
        records.append(_rec(e, "agent", s["state"]))
        failed = e["outcome"] == "fail"
        if s["state"] == HALF_OPEN:
            if failed:
                s["state"], s["opened"] = OPEN, e["t"]
            else:
                s["state"], s["run"] = CLOSED, 0
                closes.append((e["agent"], e["t"]))
            continue
        s["run"] = s["run"] + 1 if failed else 0
        if s["run"] >= consecutive:
            s["state"], s["opened"] = OPEN, e["t"]
            trips.append((e["agent"], e["t"]))
    return {"records": records, "trips": trips, "closes": closes}


def breaker_run(d: dict, policy: dict | None = None, use_controls: bool = True) -> dict:
    fleet, records = run_stream(d["events"], d["controls"] if use_controls else [], policy or d["policy"])
    trips, closes, warns = [], [], 0
    for ev in fleet.log.events:
        if ev["kind"] == "warn":
            warns += 1
        if ev["kind"] == "transition":
            x = ev["data"]
            if x["from"] == CLOSED and x["to"] == OPEN:
                trips.append((ev["agent"], ev["t"]))
            if x["to"] == CLOSED:
                closes.append((ev["agent"], ev["t"]))
    return {"records": records, "trips": trips, "closes": closes, "fleet": fleet, "warns": warns}


# ---------------------------------------------------------------- scoring
def evaluate(d: dict, run: dict, grace: int) -> dict:
    """Score a run against the planted truth. A trip belongs to a fault of that agent that was running, or had
    ended less than `grace` minutes before. A trip that belongs to no fault, or to a must_not_trip fault, is false."""
    per = {f["id"]: {"id": f["id"], "agent": f["agent"], "kind": f["kind"], "cls": f["cls"], "start": f["start"],
                     "end": f["end"], "harm": f["harm"], "harm_served": 0, "trips": []} for f in d["faults"]}
    harm_served = held = held_harmless = held_operator = 0
    for r in run["records"]:
        fid, harm = d["truth"][r["case"]]
        if r["route"] == "agent":
            harm_served += harm
            if fid:
                per[fid]["harm_served"] += harm
        else:
            held += 1
            held_operator += r["state"] != OPEN
            held_harmless += r["state"] == OPEN and harm == 0
    stray = 0
    for agent, t in run["trips"]:
        hit = [f for f in d["faults"] if f["agent"] == agent and f["start"] <= t <= f["end"] + grace]
        if hit:
            per[hit[0]["id"]]["trips"].append(t)
        else:
            stray += 1
    faults = []
    for f in d["faults"]:
        p = per[f["id"]]
        first = min(p["trips"]) if p["trips"] else None
        lag = None
        if first is not None:
            later = [t for a, t in run["closes"] if a == f["agent"] and t >= f["end"]]
            lag = min(later) - f["end"] if later else None
        faults.append(dict(p, tripped=first is not None, first_trip=first,
                           minutes_to_trip=None if first is None else first - f["start"],
                           in_time=first is not None and first <= f["end"], recovery_lag=lag, trip_count=len(p["trips"])))
    blip_trips = sum(f["trip_count"] for f in faults if f["cls"] == "must_not_trip")
    premature = sum(1 for a, t in run["closes"] if any(a == a2 and t < t2 <= t + int(d["assume"]["premature_close_window_min"])
                                                       for a2, t2 in run["trips"]))
    return {"calls": len(run["records"]), "harm_total": sum(h for _, h in d["truth"].values()), "harm_served": harm_served,
            "held": held, "held_harmless": held_harmless, "held_operator": held_operator, "trips": len(run["trips"]),
            "stray_trips": stray, "blip_trips": blip_trips, "false_trips": stray + blip_trips,
            "premature_closes": premature, "faults": faults}


def of_class(ev: dict, cls: str) -> list:
    return [f for f in ev["faults"] if f["cls"] == cls]


def of_kind(ev: dict, kind: str) -> list:
    return [f for f in ev["faults"] if f["kind"] == kind]


def tripped(faults: list) -> int:
    return sum(1 for f in faults if f["tripped"])


def median_text(values: list) -> str:
    return "n/a" if not values else ("%g" % median(values))
