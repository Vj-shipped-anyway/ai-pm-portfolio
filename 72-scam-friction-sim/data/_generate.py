"""Generate the synthetic data for project 72: 12,000 real-time payments, some of them scams.

Everything is seeded, so a rerun reproduces every file byte for byte. The scenario of each payment
(a scam type or a kind of legitimate payment) is drawn first; the features the policy can see are
then drawn from a distribution that belongs to that scenario. The risk rules in src/ are written
separately and never see the scenario, so the labels come from the generative process and not from
the rules. Two kinds are hard on purpose: legitimate payments that look like scams (a large first
payment to a new payee, a night payment from a new device, a payment made while on a phone call) and
scams that look like ordinary payments (a payee the customer has paid for weeks).

No rate in these files is a real rate. The share of scams is set far above anything real so that the
counts are big enough to read. The assumptions file holds the invented behavior of customers under
a hold; every number in it is an assumption, named as such in the READMEs.

Run (from data/):  python3 _generate.py
Writes:  payments.csv, truth.csv, assumptions.json
"""
from __future__ import annotations

import csv
import json
import math
import os
import random

SEED = 72

# scenario, is_scam, how many of the 12,000 payments
SCENARIOS = [
    ("ordinary", 0, 10820),
    ("big_first_time", 0, 330),
    ("night_new_device", 0, 170),
    ("on_call", 0, 350),
    ("coached_live", 1, 120),
    ("romance_invest", 1, 90),
    ("takeover", 1, 60),
    ("known_payee", 1, 60),
]

ASSUMPTIONS = {
    "hold_minutes": 20,
    "warn_minutes": 0.5,
    "legit_abandon_on_hold": 0.03,
    "legit_abandon_on_warn": 0.005,
    "warn_factor": 0.3,
    "coach_rate": 0.2,
    "scam_scenarios": {
        "coached_live": {"p_abandon": 0.4, "human_scammer": True},
        "romance_invest": {"p_abandon": 0.1, "human_scammer": True},
        "takeover": {"p_abandon": 0.35, "human_scammer": False},
        "known_payee": {"p_abandon": 0.15, "human_scammer": True},
    },
}

DAY = [1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 6, 4, 3, 2]
EVENING = [1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 5, 6, 8, 9, 9, 8, 6, 3]
NIGHT = [9, 9, 9, 8, 8, 7, 3, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 4]


def normal(rng: random.Random) -> float:
    u1 = 1.0 - rng.random()
    u2 = rng.random()
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def pick(rng: random.Random, weights: list) -> int:
    x = rng.random() * sum(weights)
    acc = 0
    for i, w in enumerate(weights):
        acc += w
        if x < acc:
            return i
    return len(weights) - 1


def between(rng: random.Random, lo: int, hi: int) -> int:
    return lo + int(rng.random() * (hi - lo + 1))


def uniform(rng: random.Random, lo: float, hi: float) -> float:
    return lo + (hi - lo) * rng.random()


def chance(rng: random.Random, p: float) -> int:
    return 1 if rng.random() < p else 0


def draw_usual(rng: random.Random) -> int:
    return min(1500, max(20, int(round(math.exp(5.0 + 0.8 * normal(rng))))))


def amount_from(usual: int, ratio: float) -> int:
    return max(1, int(round(usual * ratio)))


def ordinary_ratio(rng: random.Random) -> float:
    return min(2.6, max(0.1, math.exp(-0.2 + 0.55 * normal(rng))))


def known_or_new(rng: random.Random, p_known: float) -> int:
    """Payee age in days: established with probability p_known, otherwise first payment."""
    return between(rng, 30, 1500) if rng.random() < p_known else 0


def make_ordinary(rng):
    usual = draw_usual(rng)
    r = rng.random()
    age = between(rng, 30, 1500) if r < 0.80 else between(rng, 8, 29) if r < 0.92 else 0 if r < 0.98 else between(rng, 1, 7)
    return usual, amount_from(usual, ordinary_ratio(rng)), age, pick(rng, DAY), chance(rng, 0.03), chance(rng, 0.02)


def make_big_first_time(rng):
    usual = draw_usual(rng)
    age = 0 if rng.random() < 0.9 else between(rng, 1, 3)
    return usual, amount_from(usual, uniform(rng, 3.0, 14.0)), age, pick(rng, DAY), chance(rng, 0.20), chance(rng, 0.03)


def make_night_new_device(rng):
    usual = draw_usual(rng)
    return usual, amount_from(usual, ordinary_ratio(rng)), known_or_new(rng, 0.6), pick(rng, NIGHT), 0, 1


def make_on_call(rng):
    usual = draw_usual(rng)
    return usual, amount_from(usual, ordinary_ratio(rng)), known_or_new(rng, 0.7), pick(rng, DAY), 1, chance(rng, 0.02)


def make_coached_live(rng):
    usual = draw_usual(rng)
    quiet = rng.random() < 0.10
    ratio = uniform(rng, 1.0, 2.5) if quiet else uniform(rng, 3.0, 15.0)
    age = 0 if rng.random() < 0.95 else between(rng, 1, 3)
    return usual, amount_from(usual, ratio), age, pick(rng, DAY), chance(rng, 0.80), chance(rng, 0.05)


def make_romance_invest(rng):
    usual = draw_usual(rng)
    r = rng.random()
    age = 0 if r < 0.5 else between(rng, 1, 7) if r < 0.8 else between(rng, 8, 60)
    return usual, amount_from(usual, uniform(rng, 1.5, 7.0)), age, pick(rng, EVENING), chance(rng, 0.05), chance(rng, 0.02)


def make_takeover(rng):
    usual = draw_usual(rng)
    age = 0 if rng.random() < 0.9 else between(rng, 1, 3)
    return usual, amount_from(usual, uniform(rng, 2.0, 12.0)), age, pick(rng, NIGHT), chance(rng, 0.05), chance(rng, 0.85)


def make_known_payee(rng):
    usual = draw_usual(rng)
    return usual, amount_from(usual, uniform(rng, 0.8, 2.2)), between(rng, 20, 400), pick(rng, DAY), chance(rng, 0.10), chance(rng, 0.03)


MAKERS = {"ordinary": make_ordinary, "big_first_time": make_big_first_time, "night_new_device": make_night_new_device,
          "on_call": make_on_call, "coached_live": make_coached_live, "romance_invest": make_romance_invest,
          "takeover": make_takeover, "known_payee": make_known_payee}


def build() -> tuple:
    rng = random.Random(SEED)
    rows = []
    for scenario, is_scam, count in SCENARIOS:
        for _ in range(count):
            usual, amount, age, hour, call, device = MAKERS[scenario](rng)
            u_abandon = int(rng.random() * 10000) / 10000
            u_evade = int(rng.random() * 10000) / 10000
            rows.append((rng.random(), scenario, is_scam, amount, usual, age, hour, call, device, u_abandon, u_evade))
    rows.sort(key=lambda r: r[0])
    payments, truth = [], []
    for i, r in enumerate(rows, 1):
        pid = f"P{i:05d}"
        payments.append([pid, r[3], r[4], r[5], r[6], r[7], r[8]])
        truth.append([pid, r[2], r[1], f"{r[9]:.4f}", f"{r[10]:.4f}"])
    return payments, truth


def write_csv(path: str, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main(out_dir: str | None = None) -> None:
    out_dir = out_dir or os.path.dirname(os.path.abspath(__file__))
    payments, truth = build()
    write_csv(os.path.join(out_dir, "payments.csv"),
              ["payment_id", "amount", "usual_amount", "payee_age_days", "hour", "call_active", "device_new"], payments)
    write_csv(os.path.join(out_dir, "truth.csv"), ["payment_id", "is_scam", "scenario", "u_abandon", "u_evade"], truth)
    with open(os.path.join(out_dir, "assumptions.json"), "w", encoding="utf-8") as fh:
        json.dump(ASSUMPTIONS, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"Wrote payments.csv ({len(payments)} rows), truth.csv and assumptions.json in {out_dir}")


if __name__ == "__main__":
    main()
