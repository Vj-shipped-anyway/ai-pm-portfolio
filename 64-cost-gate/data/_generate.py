"""Generate the synthetic data for project 64: one baseline eval run and 40 change requests, each
with its own eval run of 236 items over five slices, plus the budget file the gate reads.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth label of a change
request comes from the parameters that generated its run (accuracy, mean tokens, price), never
from the gate: the expected cost per correct answer of each slice is computed in closed form and
compared with the ceiling. The gate only ever sees the sampled rows, so noise can move its answer
away from the truth, and that is the point.

Prices are synthetic parameters, not vendor prices. model-a and model-b reuse the two price points
of project 13 (swapbrief); model-c is a dearer model invented for the swap cases.

Run (from data/):  python3 _generate.py
Writes:  budget.json, eval_runs.csv, cr_truth.csv, example_results.csv
"""
from __future__ import annotations

import copy
import csv
import json
import math
import random

rng = random.Random(64)

# USD per 1,000 tokens: (input, output)
PRICES = {"model-a": (0.0030, 0.0150), "model-b": (0.0024, 0.0120), "model-c": (0.0051, 0.0255)}

# Token counts for one item are the slice mean times a factor. The factor is uniform on 0.5 to 1.5,
# except one item in twenty (a long conversation) where it is uniform on 2.0 to 3.0. Its mean is
# 0.95 * 1.0 + 0.05 * 2.5 = 1.075, which the closed-form truth uses.
TAIL_PROB = 0.05
TAIL_MEAN = (1 - TAIL_PROB) * 1.0 + TAIL_PROB * 2.5

# slice, items in the eval set, accuracy, mean input tokens, mean output tokens (on model-a, before any change)
BASE_SLICES = [
    ("balance_inquiry", 64, 0.92, 420, 90),
    ("dispute_status", 56, 0.78, 900, 220),
    ("fee_questions", 56, 0.84, 700, 180),
    ("card_services", 48, 0.86, 600, 140),
    ("wire_exceptions", 12, 0.62, 1300, 380),
]
OVERALL_HEADROOM = 1.15   # assumption: the overall ceiling sits 15% above the baseline cost per correct answer
SLICE_HEADROOM = 1.25     # assumption: a slice ceiling sits 25% above that slice's baseline
MIN_ITEMS = 30            # assumption: fewer items than this in a slice and the gate does not judge it alone

# (planted change, number of change requests)
QUOTA = [
    ("unchanged", 8), ("near_budget_ok", 6), ("richer_prompt_better", 5),
    ("model_swap_pricier", 3), ("verbose_output", 3), ("accuracy_drop", 3), ("cheaper_but_worse", 3),
    ("slice_regression", 4), ("small_overshoot", 3), ("thin_slice_regression", 2),
]

BASE = {"model": "model-a", "slices": {name: dict(n=n, p=p, tin=tin, tout=tout) for name, n, p, tin, tout in BASE_SLICES}}


def true_cpc(world: dict) -> dict:
    """Expected cost per correct answer per slice and overall, from the generating parameters."""
    pin, pout = PRICES[world["model"]]
    out, cost_total, correct_total = {}, 0.0, 0.0
    for name, s in world["slices"].items():
        cost = (s["tin"] * pin + s["tout"] * pout) / 1000.0 * TAIL_MEAN
        out[name] = cost / s["p"]
        cost_total += s["n"] * cost
        correct_total += s["n"] * s["p"]
    out["overall"] = cost_total / correct_total
    return out


def ceil5(x: float) -> float:
    return math.ceil(x * 100000) / 100000


def scale(world: dict, factor: float, only: str = "") -> None:
    for name, s in world["slices"].items():
        if not only or name == only:
            s["tin"] *= factor
            s["tout"] *= factor


def make_world(kind: str) -> dict:
    """The world behind one change request. One effect-size draw per request, whatever the kind."""
    w = copy.deepcopy(BASE)
    r = rng.random()
    sl = w["slices"]
    if kind == "near_budget_ok":
        scale(w, 1.09 + 0.03 * r)                      # longer prompts everywhere, still under the ceiling
    elif kind == "richer_prompt_better":
        for s in sl.values():                           # more context: more input tokens, better answers
            s["tin"] *= 1.30 + 0.10 * r
            s["p"] = min(0.97, s["p"] + 0.06 + 0.04 * r)
    elif kind == "model_swap_pricier":
        w["model"] = "model-c"
    elif kind == "verbose_output":
        for s in sl.values():
            s["tout"] *= 1.7 + 0.3 * r
    elif kind == "accuracy_drop":
        for s in sl.values():                           # same tokens and price, fewer right answers
            s["p"] = max(0.30, s["p"] - (0.20 + 0.08 * r))
    elif kind == "cheaper_but_worse":
        w["model"] = "model-b"                          # cheaper per call, far less accurate
        for s in sl.values():
            s["p"] = max(0.30, s["p"] - (0.30 + 0.08 * r))
    elif kind == "slice_regression":
        scale(w, 1.60 + 0.10 * r, only=("balance_inquiry" if r < 0.5 else "card_services"))
    elif kind == "small_overshoot":
        scale(w, 1.16 + 0.04 * r)                       # a few percent over the overall ceiling
    elif kind == "thin_slice_regression":
        scale(w, 1.90 + 0.20 * r, only="wire_exceptions")
    return w


def run_rows(world: dict) -> list:
    rows, idx = [], 0
    for name, s in world["slices"].items():
        for _ in range(s["n"]):
            idx += 1
            correct = 1 if rng.random() < s["p"] else 0
            tail = rng.random() < TAIL_PROB
            m_in = (2.0 + rng.random()) if tail else (0.5 + rng.random())
            m_out = (2.0 + rng.random()) if tail else (0.5 + rng.random())
            rows.append((f"Q{idx:03d}", name, world["model"], correct,
                         max(1, round(s["tin"] * m_in)), max(1, round(s["tout"] * m_out))))
    return rows


def main() -> None:
    base_true = true_cpc(BASE)
    ceilings = {k: ceil5(v * (OVERALL_HEADROOM if k == "overall" else SLICE_HEADROOM)) for k, v in base_true.items()}
    budget = {
        "min_items": MIN_ITEMS,
        "prices_usd_per_1k_tokens": {m: {"input": i, "output": o} for m, (i, o) in PRICES.items()},
        "overall": {"max_cost_per_correct_usd": ceilings["overall"]},
        "slices": {name: {"max_cost_per_correct_usd": ceilings[name]} for name, *_ in BASE_SLICES},
    }
    with open("budget.json", "w", encoding="utf-8") as f:
        json.dump(budget, f, indent=1, sort_keys=True)
        f.write("\n")

    kinds = [k for k, q in QUOTA for _ in range(q)]
    rng.shuffle(kinds)
    header = ["item_id", "slice", "model", "correct", "input_tokens", "output_tokens"]
    example = None
    with open("eval_runs.csv", "w", newline="", encoding="utf-8") as f, \
            open("cr_truth.csv", "w", newline="", encoding="utf-8") as g:
        w, t = csv.writer(f), csv.writer(g)
        w.writerow(["cr_id"] + header)
        t.writerow(["cr_id", "change_kind", "truth_class", "true_worst_ratio", "true_scopes_over"])
        for row in run_rows(BASE):
            w.writerow(["BASE"] + list(row))
        for i, kind in enumerate(kinds, 1):
            cr = f"CR-{i:03d}"
            world = make_world(kind)
            truth = true_cpc(world)
            over = sorted(k for k in truth if truth[k] > ceilings[k])
            worst = max(truth[k] / ceilings[k] for k in truth)
            t.writerow([cr, kind, "over_budget" if over else "within_budget", "%.3f" % worst, ";".join(over) or "none"])
            rows = run_rows(world)
            for row in rows:
                w.writerow([cr] + list(row))
            if example is None and kind == "slice_regression":
                example = rows
    with open("example_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(example)
    print("wrote the budget, 1 baseline run and %d change requests of %d items" % (len(kinds), sum(s[1] for s in BASE_SLICES)))


if __name__ == "__main__":
    main()
