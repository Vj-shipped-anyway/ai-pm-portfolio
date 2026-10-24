"""Generate the synthetic data for project 50 (review-capacity). Standard library only.
Run from data/:  python3 _generate.py
A rerun reproduces every file byte for byte.

The world: 13 review queues, each observed for 20 working days of 8 hours. Days 1 to 10 are the history a
planner would see; days 11 to 20 are the days that actually happen. The truth for each queue is the
smallest number of reviewers at the desk that meets the queue's target on days 11 to 20, found by
replaying those cases first come first served. The replay below is written separately from the
replay in src/review_capacity.py, and a test checks that the two agree.

Each queue has a planted kind. The kinds are the reason the data exists: some are easy for a mean-rate
formula, some are hard for it, two are hard negatives (they look risky and are not), and two are
changes the history cannot show.
"""
from __future__ import annotations

import csv
import heapq
import math
import os
import random

SEED = 20261024
HOURS = 8
MINUTES = HOURS * 60
DAYS = 20
HISTORY_DAYS = 10
MAX_SEATS = 80

# kind: what is planted. live: cases per hour (mean) and 'poisson' or 'wave' (alternating busy and quiet
# spells). batch: mean cases that land at open each day. svc: handling time, a lognormal (mean, cv) or a mixture
# of easy and hard cases. drift: factor on the live rate on days 11 to 20.
QUEUES = [
    dict(id="onboarding_review", kind="plain", live=6, arrivals="poisson", batch=0, svc=("lognormal", 33, 1.0),
         wait=30, share=0.90, cap=0.85, note="Poisson arrivals, handling times near the exponential case Erlang C assumes"),
    dict(id="complaint_triage", kind="plain", live=7, arrivals="poisson", batch=0, svc=("lognormal", 18, 1.0),
         wait=20, share=0.90, cap=0.85, note="same as above, shorter handling"),
    dict(id="payment_exception_review", kind="plain", live=5, arrivals="poisson", batch=0, svc=("lognormal", 45, 1.0),
         wait=60, share=0.85, cap=0.85, note="same as above, longer handling, looser share"),
    dict(id="sanctions_alert_review", kind="variable_handling", live=7, arrivals="poisson", batch=0,
         svc=("mixture", 0.12, 12, 90, 0.5), wait=30, share=0.90, cap=0.85,
         note="most alerts clear in minutes, one in eight takes an hour and a half"),
    dict(id="dispute_summary_check", kind="variable_handling", live=8, arrivals="poisson", batch=0,
         svc=("lognormal", 20, 2.2), wait=20, share=0.90, cap=0.85, note="one long-tailed handling distribution"),
    dict(id="fraud_alert_review", kind="opening_batch", live=4, arrivals="poisson", batch=30,
         svc=("lognormal", 15, 0.8), wait=45, share=0.90, cap=0.85, note="an overnight scoring run drops about 30 cases at open"),
    dict(id="kyc_refresh_review", kind="opening_batch", live=2, arrivals="poisson", batch=36,
         svc=("lognormal", 20, 1.0), wait=90, share=0.90, cap=0.85, note="a periodic-review batch lands at open"),
    dict(id="card_dispute_wave", kind="bursty_arrivals", live=7, arrivals="wave", batch=0, svc=("lognormal", 20, 1.0),
         wait=15, share=0.90, cap=0.85, note="busy and quiet spells of about 45 minutes alternate"),
    dict(id="model_override_audit", kind="low_variance", live=7, arrivals="poisson", batch=0,
         svc=("lognormal", 30, 0.3), wait=30, share=0.90, cap=0.90, note="handling times close to constant"),
    dict(id="adverse_media_review", kind="hard_negative", live=3, arrivals="poisson", batch=20,
         svc=("lognormal", 30, 2.0), wait=240, share=0.90, cap=0.85,
         note="a batch and long-tailed handling, but a four-hour target absorbs both"),
    dict(id="policy_qa_escalations", kind="hard_negative", live=3, arrivals="wave", batch=0, svc=("lognormal", 20, 1.0),
         wait=60, share=0.90, cap=0.85, note="bursty arrivals on a light load with a loose target"),
    dict(id="payment_limit_exceptions", kind="drift", live=5, arrivals="poisson", batch=0, svc=("lognormal", 30, 1.0),
         wait=45, share=0.90, cap=0.85, drift=1.4, note="live volume is 1.4 times higher on days 11 to 20; the history cannot show it"),
    dict(id="document_extraction_exceptions", kind="heavy_tail", live=10, arrivals="poisson", batch=0,
         svc=("mixture", 0.04, 8, 120, 0.5), wait=30, share=0.90, cap=0.85,
         note="one case in twenty-five takes two hours; ten days hold about thirty of them"),
]

# Typed by hand, not drawn: the three rows behind `python3 review_capacity.py --demo`.
EXAMPLE_HEADER = ["queue_id", "hours_open", "arrivals_per_hour", "opening_batch", "handling_minutes", "handling_cv",
                  "arrival_cv", "target_wait_min", "target_share", "max_utilization", "shrinkage", "current_headcount"]
EXAMPLE_ROWS = [
    ["morning_batch_review", "8", "4", "30", "15", "0.8", "1.0", "45", "0.90", "0.85", "0.25", "6"],
    ["onboarding_exceptions", "8", "6", "0", "30", "1.0", "1.0", "30", "0.90", "0.85", "0.25", "6"],
    ["complaint_escalations", "8", "8", "0", "20", "2.0", "1.2", "20", "0.90", "0.85", "0.25", "7"],
]


def lognormal(rng, mean, cv):
    s2 = math.log(1.0 + cv * cv)
    return math.exp(rng.normalvariate(math.log(mean) - s2 / 2.0, math.sqrt(s2)))


def poisson(rng, mean):
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def handling(rng, svc):
    if svc[0] == "lognormal":
        x = lognormal(rng, svc[1], svc[2])
    else:
        _, p_hard, easy, hard, cv = svc
        x = lognormal(rng, hard if rng.random() < p_hard else easy, cv)
    return round(max(1.0, x), 2)


def live_arrivals(rng, per_hour, style):
    rate = per_hour / 60.0
    if style == "poisson":
        spells = [(0.0, MINUTES, rate)]
    else:
        spells, t, busy = [], 0.0, rng.random() < 0.5
        while t < MINUTES:
            end = min(float(MINUTES), t + rng.expovariate(1.0 / 45.0))
            spells.append((t, end, rate * (1.8 if busy else 0.2)))
            t, busy = end, not busy
    out = []
    for start, end, r in spells:
        u = start
        while True:
            u += rng.expovariate(r)
            if u >= end:
                break
            out.append(u)
    return out


def build_cases():
    rows = []
    for index, spec in enumerate(QUEUES):
        rng = random.Random(SEED * 100 + index)
        for day in range(1, DAYS + 1):
            factor = spec.get("drift", 1.0) if day > HISTORY_DAYS else 1.0
            day_rows = [(0.0, handling(rng, spec["svc"]), "batch") for _ in range(poisson(rng, spec["batch"]))]
            live = sorted(live_arrivals(rng, spec["live"] * factor, spec["arrivals"]))
            day_rows += [(round(t, 2), handling(rng, spec["svc"]), "live") for t in live]
            rows += [[spec["id"], day, f"{a:.2f}", f"{h:.2f}", ch] for a, h, ch in day_rows]
    return rows


def simulate(cases, seats, wait):
    """First come first served, seats identical reviewers, each day starts empty. Returns (late, n, busy)."""
    late, busy, n, day, free = 0, 0.0, 0, None, []
    for d, arrival, handle in cases:
        if d != day:
            day, free = d, [0.0] * seats
        start = max(arrival, heapq.heappop(free))
        heapq.heappush(free, start + handle)
        busy += handle
        n += 1
        if start - arrival > wait:
            late += 1
    return late, n, busy


def truth(case_rows):
    out = []
    for spec in QUEUES:
        future = [(int(r[1]), float(r[2]), float(r[3])) for r in case_rows if r[0] == spec["id"] and int(r[1]) > HISTORY_DAYS]
        for seats in range(1, MAX_SEATS + 1):
            late, n, busy = simulate(future, seats, spec["wait"])
            util = busy / (seats * MINUTES * (DAYS - HISTORY_DAYS))
            if late / n <= 1.0 - spec["share"] + 1e-12 and util <= spec["cap"] + 1e-12:
                out.append([spec["id"], spec["kind"], seats, f"{late / n:.4f}", f"{util:.4f}", spec["note"]])
                break
        else:
            raise SystemExit("no seat count up to %d meets the target for %s" % (MAX_SEATS, spec["id"]))
    return out


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    cases = build_cases()
    write(os.path.join(here, "cases.csv"), ["queue_id", "day", "arrival_min", "handle_min", "channel"], cases)
    write(os.path.join(here, "queues.csv"), ["queue_id", "hours_open", "target_wait_min", "target_share", "max_utilization", "shrinkage"],
          [[s["id"], HOURS, s["wait"], f"{s['share']:.2f}", f"{s['cap']:.2f}", "0.25"] for s in QUEUES])
    write(os.path.join(here, "queue_truth.csv"),
          ["queue_id", "kind", "true_seats", "late_share_at_truth", "utilization_at_truth", "planted"], truth(cases))
    write(os.path.join(here, "example_queues.csv"), EXAMPLE_HEADER, EXAMPLE_ROWS)
    print("Wrote cases.csv (%d rows), queues.csv, queue_truth.csv, example_queues.csv" % len(cases))


if __name__ == "__main__":
    main()
