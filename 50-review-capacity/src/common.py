"""Shared loading and scoring for the four step scripts of project 50."""
from __future__ import annotations

import csv
import math
import os

from review_capacity import fit_queue, load_log, offered_load, replay

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")
PAST = (1, 10)
REPLAYED = (11, 20)


def read_csv(name: str) -> list:
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_world(measure_on: tuple = REPLAYED) -> list:
    """One dict per queue: targets, assumptions measured on the days in `measure_on`, the planted kind and the
    true number of seats, and the cases of the replayed days. With the default, the assumptions are measured on
    the same days that are replayed, so a miss comes from the method and not from a forecast."""
    log = load_log(os.path.join(DATA, "cases.csv"))
    truth = {r["queue_id"]: r for r in read_csv("queue_truth.csv")}
    world = []
    for t in read_csv("queues.csv"):
        qid = t["queue_id"]
        window = [c for c in log[qid] if measure_on[0] <= c["day"] <= measure_on[1]]
        hours = float(t["hours_open"])
        fitted, _notes = fit_queue(window, hours, measure_on[1] - measure_on[0] + 1)
        q = dict(fitted, queue_id=qid, target_wait_min=float(t["target_wait_min"]), target_share=float(t["target_share"]),
                 max_utilization=float(t["max_utilization"]), shrinkage=float(t["shrinkage"]), current_headcount=None)
        q["kind"] = truth[qid]["kind"]
        q["true_seats"] = int(truth[qid]["true_seats"])
        q["replayed"] = [c for c in log[qid] if REPLAYED[0] <= c["day"] <= REPLAYED[1]]
        world.append(q)
    return world


def judge(q: dict, seats: int) -> dict:
    """Replay the replayed days with `seats` reviewers and test both targets."""
    r = replay(q["replayed"], seats, q["target_wait_min"], q["hours_open"], REPLAYED[1] - REPLAYED[0] + 1)
    r["wait_ok"] = r["late_share"] <= 1.0 - q["target_share"] + 1e-12
    r["util_ok"] = r["utilization"] <= q["max_utilization"] + 1e-12
    r["meets"] = r["wait_ok"] and r["util_ok"]
    return r


def average_load_seats(q: dict) -> int:
    """Seats that cover the average workload and nothing more."""
    return max(1, math.ceil(offered_load(q) - 1e-9))


def score(world: list, seats: dict) -> dict:
    """Compare the seats chosen for each queue with the truth and with a replay."""
    exact = sum(1 for q in world if seats[q["queue_id"]] == q["true_seats"])
    under = [q for q in world if seats[q["queue_id"]] < q["true_seats"]]
    over = [q for q in world if seats[q["queue_id"]] > q["true_seats"]]
    results = {q["queue_id"]: judge(q, seats[q["queue_id"]]) for q in world}
    late = sum(r["late"] for r in results.values())
    cases = sum(r["cases"] for r in results.values())
    return {"exact": exact, "within_one": sum(1 for q in world if abs(seats[q["queue_id"]] - q["true_seats"]) <= 1),
            "under": under, "over": over, "queues": len(world),
            "wait_ok": sum(1 for r in results.values() if r["wait_ok"]),
            "util_ok": sum(1 for r in results.values() if r["util_ok"]),
            "meets": sum(1 for r in results.values() if r["meets"]),
            "late": late, "cases": cases, "seats": sum(seats.values()), "true_seats": sum(q["true_seats"] for q in world),
            "results": results}


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
