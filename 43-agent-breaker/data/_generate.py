"""Generate the synthetic data for project 43: three days of calls from five agents, with 25 planted faults.

Everything is seeded, so a rerun reproduces every file byte for byte. The generator decides, call by call,
what the agent did and whether it did harm; the breaker never sees the harm column. The truth class of each
fault comes from the kind of fault that was planted, not from the breaker's rules.

Four kinds are hard on purpose. A blip of 3 or 4 failures in a row, and 2 failures in 3 calls from a quiet
agent, are harmless and a breaker should stay closed (hard negatives). A blip of 5 or 6 failures in a row is
also harmless but looks exactly like an outage to a count of failures in a row (a false alarm the rules
cannot avoid). Silent errors (the agent reports ok and is wrong) and a slow burn (a failure rate below the
trip level) are things the breaker is expected to miss.

Run (from data/):  python3 _generate.py
Writes:  events.csv, truth_calls.csv, faults.csv, controls.csv, example_events.csv
(policy.csv and model_assumptions.csv are written by hand and read by the scripts.)
"""
from __future__ import annotations

import csv
import random

rng = random.Random(43)
DAY, MINUTES, SLOT = 1440, 3 * 1440, 360
BASE_FAIL = 0.03
NIGHT_END, NIGHT_FACTOR = 360, 0.3
AGENTS = [("payment-repair", 0.80), ("kyc-refresh", 0.50), ("dispute-intake", 0.40),
          ("statement-summary", 0.30), ("limit-review", 0.12)]
PLAN = {
    "payment-repair": ["hard_outage", "brownout", "flapping", "silent_bad", "blip_short", "blip_long"],
    "kyc-refresh": ["hard_outage", "brownout", "scope_violation", "slow_burn", "blip_short"],
    "dispute-intake": ["hard_outage", "brownout", "scope_violation", "flapping", "blip_short"],
    "statement-summary": ["brownout", "scope_violation", "silent_bad", "slow_burn", "blip_long"],
    "limit-review": ["hard_outage", "brownout", "blip_short", "low_volume_noise"],
}
TRUTH_CLASS = {"hard_outage": "must_trip", "brownout": "must_trip", "flapping": "must_trip", "scope_violation": "must_trip",
               "blip_short": "must_not_trip", "blip_long": "must_not_trip", "low_volume_noise": "must_not_trip",
               "silent_bad": "hard_miss", "slow_burn": "hard_miss"}
# minutes the fault window lasts (or the room reserved for it, for the faults made of a fixed run of calls)
DURATION = {"hard_outage": (40, 90), "brownout": (60, 150), "flapping": (96, 96), "scope_violation": (40, 40),
            "silent_bad": (60, 120), "slow_burn": (180, 240), "blip_short": (30, 30), "blip_long": (30, 30),
            "low_volume_noise": (60, 60)}
FORCED = ("blip_short", "blip_long", "low_volume_noise")


def shuffled(items):
    items = list(items)
    for i in range(len(items) - 1, 0, -1):
        j = rng.randint(0, i)
        items[i], items[j] = items[j], items[i]
    return items


def make_faults() -> list:
    faults = []
    for agent, kinds in PLAN.items():
        slots, order, chosen = shuffled(range(0, 12, 2)), shuffled(kinds), []      # even slots only: 360 quiet minutes between faults
        order.sort(key=lambda k: k != "flapping")                                  # flapping first: it needs a daytime slot
        for kind in order:
            chosen.append([s for s in slots if s not in chosen and (kind != "flapping" or s % 4 == 2)][0])
        for slot, kind in zip(chosen, order):
            lo, hi = DURATION[kind]
            dur = rng.randint(lo, hi)
            start = slot * SLOT + rng.randint(30, SLOT - dur - 10)
            f = {"agent": agent, "kind": kind, "truth_class": TRUTH_CLASS[kind], "start": start, "end": start + dur - 1,
                 "intensity": "", "pattern": [], "first_done": False, "harm": 0, "calls": 0}
            if kind == "hard_outage":
                f["p"] = round(rng.uniform(0.95, 1.0), 2)
            elif kind == "brownout":
                f["p"] = round(rng.uniform(0.55, 0.75), 2)
            elif kind == "flapping":
                f["p"] = 0.9
            elif kind == "slow_burn":
                f["p"] = 0.28
            elif kind == "scope_violation":
                f["p"] = 0.25
            elif kind == "silent_bad":
                f["p"] = 0.5
            elif kind == "blip_short":
                f["pattern"] = ["fail"] * rng.randint(3, 4)
            elif kind == "blip_long":
                f["pattern"] = ["fail"] * rng.randint(5, 6)
            else:
                f["pattern"] = ["fail", "fail", "ok"]
            f["intensity"] = str(f["p"]) if "p" in f else str(len(f["pattern"]))
            faults.append(f)
    faults.sort(key=lambda f: (f["start"], f["agent"]))
    for i, f in enumerate(faults, 1):
        f["id"] = "F%02d" % i
    return faults


def active(faults, agent, t):
    for f in faults:
        if f["agent"] != agent:
            continue
        if f["kind"] in FORCED:
            if f["pattern"] and t >= f["start"]:
                return f
        elif f["start"] <= t <= f["end"]:
            return f
    return None


def baseline():
    if rng.random() < BASE_FAIL:
        return "fail", "timeout" if rng.random() < 0.3 else "tool_error", 0
    return "ok", "", 0


def fault_fail():
    return "fail", "timeout" if rng.random() < 0.3 else "tool_error", 1


def draw(f, t):
    """(outcome, failure_kind, harm) for one call inside fault f."""
    k = f["kind"]
    if k in FORCED:
        outcome = f["pattern"].pop(0)
        f["end"] = t
        return outcome, "tool_error" if outcome == "fail" else "", 0
    if k in ("hard_outage", "brownout", "slow_burn"):
        return fault_fail() if rng.random() < f["p"] else ("ok", "", 0)
    if k == "flapping":
        if ((t - f["start"]) // 12) % 2 == 0:
            return fault_fail() if rng.random() < f["p"] else ("ok", "", 0)
        return baseline()
    if k == "scope_violation":
        if not f["first_done"] or rng.random() < f["p"]:
            f["first_done"] = True
            return "fail", "scope_violation", 1
        return baseline()
    if rng.random() < f["p"]:                       # silent_bad: reports ok, is wrong
        return "ok", "", 1
    return baseline()


def write_csv(name, header, rows):
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def make_example() -> list:
    """90 calls from one agent, one every 2 minutes: two stray failures, then an outage from t=60 to t=111."""
    rows = []
    for i in range(90):
        t = 2 * i
        bad = 60 <= t < 112
        stray = t in (14, 38)
        rows.append([t, "payment-repair", "E%03d" % (i + 1), "fail" if bad or stray else "ok",
                     "tool_error" if bad else "timeout" if stray else ""])
    return rows


def main() -> None:
    faults = make_faults()
    events, truth = [], []
    for t in range(MINUTES):
        for agent, rate in AGENTS:
            if rng.random() >= rate * (NIGHT_FACTOR if t % DAY < NIGHT_END else 1.0):
                continue
            case = "C%05d" % (len(events) + 1)
            f = active(faults, agent, t)
            outcome, kind, harm = draw(f, t) if f else baseline()
            if f:
                f["calls"] += 1
                f["harm"] += harm
            events.append([t, agent, case, outcome, kind])
            truth.append([case, f["id"] if f else "", harm])
    write_csv("events.csv", ["t_min", "agent", "case_id", "outcome", "failure_kind"], events)
    write_csv("truth_calls.csv", ["case_id", "fault_id", "harm"], truth)
    write_csv("faults.csv", ["fault_id", "agent", "kind", "truth_class", "start_min", "end_min", "intensity", "calls", "harm_calls"],
              [[f["id"], f["agent"], f["kind"], f["truth_class"], f["start"], f["end"], f["intensity"], f["calls"], f["harm"]]
               for f in faults])
    write_csv("controls.csv", ["t_min", "agent", "action", "by", "reason"],
              [[5 * SLOT + 150, "dispute-intake", "engage", "ops-oncall", "planned maintenance on the upstream"],
               [5 * SLOT + 240, "dispute-intake", "release", "ops-oncall", "maintenance finished"],
               [9 * SLOT + 150, "statement-summary", "engage", "ops-oncall", "planned maintenance on the upstream"],
               [9 * SLOT + 240, "statement-summary", "release", "ops-oncall", "maintenance finished"]])
    write_csv("example_events.csv", ["t_min", "agent", "case_id", "outcome", "failure_kind"], make_example())


if __name__ == "__main__":
    main()
