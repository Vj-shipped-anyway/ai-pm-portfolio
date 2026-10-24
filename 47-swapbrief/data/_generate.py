"""Synthetic data for project 47 (swapbrief).

STUB: this file stands in for real evaluation runs. No model is called, and nothing here measures
any real model, vendor, bank or customer. Every number is drawn from a seeded process whose TRUE
effects are written down below, so a decision rule can be scored against the truth. The rules
live in src/swapbrief.py and never read the truth.

Run (standard library only, Python 3.9):   python3 _generate.py

Writes, next to this file:
    results.csv          the committed set: 600 items scored under two systems (1,200 rows)
    prices.csv           synthetic unit prices (parameters, not vendor prices)
    slices.csv           slice names, which are critical, size, description
    committed_truth.csv  the injected TRUE accuracy per slice for the committed set (scoring only)
    committed_world.json the injected verbosity, slow-path rate and the true cost and latency ratios
    scenario_truth.csv   80 simulated migrations: their parameters and the true problems they carry

The module is also imported by src/common.py, which re-draws each scenario's evaluation sample
from draw_spec(i) and simulate(). Running this file twice produces byte-identical files.
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from statistics import NormalDist

OUT = Path(__file__).parent

SEED = 4701                # the committed set
SCENARIO_SEED = 47000000   # scenario i draws its world from SCENARIO_SEED + i
SAMPLE_SEED = 47100000     # scenario i draws its evaluation sample from SAMPLE_SEED + i
TRUTH_SEED = 47900000      # scenario i measures its true p95 with TRUTH_SEED + i
N_SCENARIOS = 80
TRUTH_N = 10000            # draws used to measure a world's true latency percentiles

SYSTEMS = ("incumbent", "successor")

# The committed world: six slices of a back-office case-handling assistant.
#   p_base  true probability the incumbent answers an item correctly
#   d       true change in that probability for the successor
#   in_mean / out_mean   mean tokens per call for the incumbent
SLICES = [
    dict(name="card_disputes", n=130, critical=1, p_base=0.84, d=0.05, in_mean=820, out_mean=140,
         desc="Card dispute case notes: which reason code applies"),
    dict(name="wire_exceptions", n=100, critical=1, p_base=0.78, d=0.06, in_mean=940, out_mean=170,
         desc="Wire exceptions: what the operator does next"),
    dict(name="address_changes", n=130, critical=0, p_base=0.91, d=0.03, in_mean=520, out_mean=90,
         desc="Address-change requests: which checks are required"),
    dict(name="kyc_refresh", n=90, critical=1, p_base=0.72, d=0.07, in_mean=1350, out_mean=230,
         desc="Periodic customer-review files that cite several documents"),
    dict(name="fee_waivers", n=110, critical=0, p_base=0.77, d=0.04, in_mean=700, out_mean=120,
         desc="Fee-waiver requests: whether policy allows it"),
    dict(name="account_closure", n=40, critical=0, p_base=0.80, d=-0.08, in_mean=900, out_mean=160,
         desc="Account-closure cases (few items: slow to grade)"),
]

RHO = 0.60                 # share of latent difficulty common to both systems
IN_SIGMA, OUT_SIGMA = 0.22, 0.30
CAND_IN_MULT = 1.03        # the successor counts about 3% more input tokens for the same text
CAND_NOISE, OUT_NOISE = 0.05, 0.12
LAT_SIGMA = 0.25
INCUMBENT = dict(ttft=400.0, tpot=14.0, spike_lo=1.5, spike_hi=2.2)
SUCCESSOR = dict(ttft=260.0, tpot=6.0, spike_lo=3.0, spike_hi=6.0)
INCUMBENT_SPIKE = 0.03
PRICE_INCUMBENT = (0.0030, 0.0150)    # USD per 1,000 input and output tokens

COMMITTED_V_OUT = 2.4      # successor answers are 2.4x as long
COMMITTED_SPIKE = 0.10     # share of successor calls that hit a slow path
COMMITTED_PRICE_RATIO = 0.85

# Scenario mix: assumptions about the simulated worlds, not estimates of reality.
P_REGRESS, P_FLAT = 0.06, 0.25
SCALE_CHOICES = ((0.75, 3), (1.0, 4), (1.5, 3))
V_OUT_CHOICES = ((1.0, 4), (1.4, 3), (2.0, 2), (2.6, 1))
SPIKE_CHOICES = ((0.02, 5), (0.05, 2), (0.08, 2), (0.12, 1))
PRICE_CHOICES = ((0.75, 2), (0.85, 5), (1.0, 3))

HARD_MISS_SLICE = "account_closure"   # the smallest slice: where a planted regression is hardest to see

# What counts as "this migration has a real problem": levels I chose, applied to the TRUE values.
BAD_SLICE_PP = 0.05
BAD_COST_RATIO = 1.10
BAD_P95_RATIO = 1.25

_ND = NormalDist()


def clip(p: float) -> float:
    return max(0.02, min(0.98, p))


def prices_for(spec: dict) -> dict:
    r = spec["price_ratio"]
    return {"incumbent": PRICE_INCUMBENT, "successor": (round(PRICE_INCUMBENT[0] * r, 6), round(PRICE_INCUMBENT[1] * r, 6))}


def committed_spec() -> dict:
    return {"i": 0, "slices": [dict(s) for s in SLICES], "v_out": COMMITTED_V_OUT, "spike_b": COMMITTED_SPIKE,
            "price_ratio": COMMITTED_PRICE_RATIO}


def _pick(rng: random.Random, choices: tuple):
    total = sum(w for _, w in choices)
    u = rng.random() * total
    for value, w in choices:
        u -= w
        if u < 0:
            return value
    return choices[-1][0]


def _means(slices: list) -> tuple:
    """Accuracy of each system and mean tokens per call for a mix of slices, exact from the parameters."""
    total = float(sum(s["n"] for s in slices))
    return (sum(s["n"] * clip(s["p_base"]) for s in slices) / total,
            sum(s["n"] * clip(s["p_base"] + s["d"]) for s in slices) / total,
            sum(s["n"] * s["in_mean"] for s in slices) / total,
            sum(s["n"] * s["out_mean"] for s in slices) / total)


def _slices_for(rng: random.Random, scale: float, kind: str) -> list:
    out = []
    for base in SLICES:
        u = rng.random()
        if kind == "hard_miss":
            d = -rng.uniform(0.07, 0.10) if base["name"] == HARD_MISS_SLICE else rng.uniform(0.02, 0.08)
        elif kind == "hard_negative":
            d = rng.uniform(0.02, 0.08)
        elif u < P_REGRESS:
            d = -rng.uniform(0.06, 0.14)
        elif u < P_REGRESS + P_FLAT:
            d = rng.uniform(-0.012, 0.012)
        else:
            d = rng.uniform(0.02, 0.10)
        s = dict(base)
        s["n"] = max(30, int(round(base["n"] * scale)))
        s["d"] = round(d, 4)
        out.append(s)
    return out


def scenario_kind(i: int) -> str:
    return "hard_negative" if i % 10 == 0 else ("hard_miss" if i % 10 == 5 else "random")


def draw_spec(i: int) -> dict:
    """Scenario i: a world with its own true effects, verbosity, slow-path rate and price ratio.
    Every tenth scenario is planted as a hard negative (a good migration whose true cost per correct
    answer sits just under the line) and every tenth, offset by five, as a hard miss (a real
    regression in the smallest slice, in an otherwise clean migration)."""
    rng = random.Random(SCENARIO_SEED + i)
    kind = scenario_kind(i)
    if kind == "random":
        scale = _pick(rng, SCALE_CHOICES)
        return {"i": i, "kind": kind, "slices": _slices_for(rng, scale, kind), "v_out": _pick(rng, V_OUT_CHOICES),
                "spike_b": _pick(rng, SPIKE_CHOICES), "price_ratio": _pick(rng, PRICE_CHOICES)}
    slices = _slices_for(rng, 0.75, kind)
    spec = {"i": i, "kind": kind, "slices": slices, "v_out": 1.0, "spike_b": 0.02, "price_ratio": COMMITTED_PRICE_RATIO}
    if kind == "hard_negative":
        acc_a, acc_b, mean_in, mean_out = _means(slices)
        p = prices_for(spec)
        cost_a = (p["incumbent"][0] * mean_in + p["incumbent"][1] * mean_out) / 1000.0
        target = rng.uniform(1.06, 1.09) * cost_a * acc_b / acc_a
        spec["v_out"] = round((target * 1000.0 - p["successor"][0] * mean_in * CAND_IN_MULT) / (p["successor"][1] * mean_out), 2)
    return spec


def _latency(rng: random.Random, params: dict, out_tokens: int, spike_p: float) -> int:
    ms = (params["ttft"] + params["tpot"] * out_tokens) * math.exp(LAT_SIGMA * rng.gauss(0, 1))
    if rng.random() < spike_p:
        ms *= rng.uniform(params["spike_lo"], params["spike_hi"])
    return max(1, int(round(ms)))


def _tokens(rng: random.Random, s: dict, v_out: float) -> tuple:
    base_in = s["in_mean"] * math.exp(IN_SIGMA * rng.gauss(0, 1) - IN_SIGMA ** 2 / 2)
    base_out = s["out_mean"] * math.exp(OUT_SIGMA * rng.gauss(0, 1) - OUT_SIGMA ** 2 / 2)
    in_b = base_in * CAND_IN_MULT * math.exp(CAND_NOISE * rng.gauss(0, 1) - CAND_NOISE ** 2 / 2)
    out_b = base_out * v_out * math.exp(OUT_NOISE * rng.gauss(0, 1) - OUT_NOISE ** 2 / 2)
    return tuple(max(1, int(round(x))) for x in (base_in, base_out, in_b, out_b))


def simulate(spec: dict, seed: int) -> list:
    """Result rows (dicts of text, as the CSV holds them) for one evaluation sample of a world."""
    rng = random.Random(seed)
    shared, resid = math.sqrt(RHO), math.sqrt(1.0 - RHO)
    rows, k = [], 0
    for s in spec["slices"]:
        t_a = _ND.inv_cdf(clip(s["p_base"]))
        t_b = _ND.inv_cdf(clip(s["p_base"] + s["d"]))
        for _ in range(s["n"]):
            k += 1
            z = rng.gauss(0, 1)
            ok_a = int(shared * z + resid * rng.gauss(0, 1) < t_a)
            ok_b = int(shared * z + resid * rng.gauss(0, 1) < t_b)
            in_a, out_a, in_b, out_b = _tokens(rng, s, spec["v_out"])
            lat_a = _latency(rng, INCUMBENT, out_a, INCUMBENT_SPIKE)
            lat_b = _latency(rng, SUCCESSOR, out_b, spec["spike_b"])
            for system, ok, tin, tout, lat in (("incumbent", ok_a, in_a, out_a, lat_a), ("successor", ok_b, in_b, out_b, lat_b)):
                rows.append({"item_id": "C%04d" % k, "slice": s["name"], "system": system, "correct": str(ok),
                             "input_tokens": str(tin), "output_tokens": str(tout), "latency_ms": str(lat)})
    return rows


def _rank(sorted_values: list, q: float) -> int:
    return sorted_values[int(round(q * (len(sorted_values) - 1)))]


def truth(spec: dict, seed: int) -> dict:
    """The true effects of a world. Accuracy and cost are exact from the parameters; the latency
    percentiles are measured on TRUTH_N fresh draws from the world, not on the evaluation sample."""
    slices = spec["slices"]
    total = float(sum(s["n"] for s in slices))
    acc_a, acc_b, mean_in, mean_out = _means(slices)
    p = prices_for(spec)
    cost_a = (p["incumbent"][0] * mean_in + p["incumbent"][1] * mean_out) / 1000.0
    cost_b = (p["successor"][0] * mean_in * CAND_IN_MULT + p["successor"][1] * mean_out * spec["v_out"]) / 1000.0
    rng = random.Random(seed)
    cum, run = [], 0.0
    for s in slices:
        run += s["n"] / total
        cum.append(run)
    lat_a, lat_b = [], []
    for _ in range(TRUTH_N):
        u = rng.random()
        s = slices[next((k for k, c in enumerate(cum) if u < c), len(slices) - 1)]
        _, out_a, _, out_b = _tokens(rng, s, spec["v_out"])
        lat_a.append(_latency(rng, INCUMBENT, out_a, INCUMBENT_SPIKE))
        lat_b.append(_latency(rng, SUCCESSOR, out_b, spec["spike_b"]))
    lat_a.sort()
    lat_b.sort()
    effects = [(clip(s["p_base"] + s["d"]) - clip(s["p_base"]), s["name"]) for s in slices]
    worst_delta, worst_name = min(effects)
    out = {"true_acc_a": acc_a, "true_acc_b": acc_b, "true_cost_ratio": (cost_b / acc_b) / (cost_a / acc_a),
           "true_p50_ratio": _rank(lat_b, 0.50) / _rank(lat_a, 0.50), "true_p95_ratio": _rank(lat_b, 0.95) / _rank(lat_a, 0.95),
           "worst_slice": worst_name, "worst_delta": worst_delta,
           "regressing_slices": sum(1 for d, _ in effects if d <= -BAD_SLICE_PP)}
    out["bad_slice"] = int(out["regressing_slices"] > 0)
    out["bad_cost"] = int(out["true_cost_ratio"] >= BAD_COST_RATIO)
    out["bad_p95"] = int(out["true_p95_ratio"] >= BAD_P95_RATIO)
    out["bad"] = int(out["bad_slice"] or out["bad_cost"] or out["bad_p95"])
    return out


def _write_csv(name: str, header: list, rows: list) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    spec = committed_spec()
    rows = simulate(spec, SEED)
    cols = ["item_id", "slice", "system", "correct", "input_tokens", "output_tokens", "latency_ms"]
    _write_csv("results.csv", cols, [[r[c] for c in cols] for r in rows])
    prices = prices_for(spec)
    _write_csv("prices.csv", ["system", "input_usd_per_1k", "output_usd_per_1k"],
               [[name, "%.5f" % prices[name][0], "%.5f" % prices[name][1]] for name in SYSTEMS])
    _write_csv("slices.csv", ["slice", "critical", "n_items", "description"],
               [[s["name"], s["critical"], s["n"], s["desc"]] for s in SLICES])
    _write_csv("committed_truth.csv", ["slice", "true_accuracy_incumbent", "true_accuracy_successor", "true_change_pp"],
               [[s["name"], "%.2f" % clip(s["p_base"]), "%.2f" % clip(s["p_base"] + s["d"]),
                 "%+.1f" % ((clip(s["p_base"] + s["d"]) - clip(s["p_base"])) * 100)] for s in SLICES])
    t = truth(spec, TRUTH_SEED)
    with open(OUT / "committed_world.json", "w", encoding="utf-8") as fh:
        json.dump({"successor_answer_length_multiplier": spec["v_out"], "successor_slow_path_rate": spec["spike_b"],
                   "successor_price_ratio": spec["price_ratio"], "true_cost_per_correct_ratio": round(t["true_cost_ratio"], 3),
                   "true_p50_ratio": round(t["true_p50_ratio"], 3), "true_p95_ratio": round(t["true_p95_ratio"], 3)},
                  fh, indent=1, sort_keys=True)
        fh.write("\n")
    header = ["scenario", "kind", "items", "answer_length_x", "slow_path_rate", "price_ratio", "regressing_slices", "worst_slice",
              "worst_change_pp", "true_cost_ratio", "true_p95_ratio", "bad_slice", "bad_cost", "bad_p95", "bad"]
    table = []
    for i in range(1, N_SCENARIOS + 1):
        sp = draw_spec(i)
        t = truth(sp, TRUTH_SEED + i)
        table.append([i, sp["kind"], sum(s["n"] for s in sp["slices"]), "%.1f" % sp["v_out"], "%.2f" % sp["spike_b"], "%.2f" % sp["price_ratio"],
                      t["regressing_slices"], t["worst_slice"], "%+.1f" % (t["worst_delta"] * 100),
                      "%.3f" % t["true_cost_ratio"], "%.3f" % t["true_p95_ratio"],
                      t["bad_slice"], t["bad_cost"], t["bad_p95"], t["bad"]])
    _write_csv("scenario_truth.csv", header, table)
    print("Wrote results.csv, prices.csv, slices.csv, committed_truth.csv, committed_world.json, scenario_truth.csv")


if __name__ == "__main__":
    main()
