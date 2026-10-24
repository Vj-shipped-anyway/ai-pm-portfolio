"""Shared loading and cheap rules for the four step scripts of project 47."""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")
for _p in (HERE, DATA):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _generate as gen  # noqa: E402
from swapbrief import (DEMO, GO, GUARD, NOGO, analyze, build_pairs, headline_rule, percentile,  # noqa: E402,F401
                       read_prices, read_results, render_text)

BASE, CAND = DEMO["baseline"], DEMO["candidate"]


def committed():
    """The committed set as (pairs, prices), read through the same reader the command line uses."""
    return (read_results(os.path.join(DATA, "results.csv"), BASE, CAND),
            read_prices(os.path.join(DATA, "prices.csv"), BASE, CAND))


def scenario(i: int):
    """(pairs, prices, spec) for scenario i: a fresh evaluation sample drawn from its world."""
    spec = gen.draw_spec(i)
    pairs = build_pairs(gen.simulate(spec, gen.SAMPLE_SEED + i), BASE, CAND)
    p = gen.prices_for(spec)
    return pairs, {"base": p[BASE], "cand": p[CAND]}, spec


def load_truth() -> list:
    """Planted truth per scenario, from data/scenario_truth.csv."""
    out = []
    with open(os.path.join(DATA, "scenario_truth.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.append({"scenario": int(r["scenario"]), "kind": r["kind"], "worst_slice": r["worst_slice"],
                        "true_cost_ratio": float(r["true_cost_ratio"]), "true_p95_ratio": float(r["true_p95_ratio"]),
                        **{k: int(r[k]) for k in ("regressing_slices", "bad_slice", "bad_cost", "bad_p95", "bad")}})
    return out


def point_metrics(pairs: dict, prices: dict) -> dict:
    """The numbers a quick benchmark gives, with no interval: accuracy, cost per correct answer, p50, p95."""
    base, cand = pairs["base"], pairs["cand"]
    n = len(pairs["item"])

    def cost(col, price):
        return sum(a * price[0] + b * price[1] for a, b in zip(col["tin"], col["tout"])) / 1000.0

    la, lb = sorted(base["lat"]), sorted(cand["lat"])
    return {"acc_a": sum(base["ok"]) / n, "acc_b": sum(cand["ok"]) / n,
            "cost_ratio": (cost(cand, prices["cand"]) / sum(cand["ok"])) / (cost(base, prices["base"]) / sum(base["ok"])),
            "p50_ratio": percentile(lb, 0.50) / percentile(la, 0.50), "p95_ratio": percentile(lb, 0.95) / percentile(la, 0.95)}


def basic_rule(m: dict, prices: dict) -> str:
    """What a vendor page and a quick benchmark give: average accuracy, list price per token, median latency."""
    cheaper = prices["cand"][0] <= prices["base"][0] and prices["cand"][1] <= prices["base"][1]
    return GO if (m["acc_b"] >= m["acc_a"] and cheaper and m["p50_ratio"] <= 1.0) else NOGO


def rate(num: int, den: int) -> str:
    return "%d of %d (%.1f%%)" % (num, den, 100.0 * num / den) if den else "0 of 0"


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
