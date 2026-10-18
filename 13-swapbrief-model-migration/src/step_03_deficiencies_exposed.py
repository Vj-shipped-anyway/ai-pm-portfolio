"""
Step 3 - Where the basic approach breaks: six named deficiencies.

Steps 1 and 2 decide on the aggregate. This script takes the same simulated
evaluation set and shows six ways that decision goes wrong, each with numbers:

  1  AGGREGATE_HIDES_SLICES      the average rises while slices fall
  2  SMALL_SAMPLE_FLIPS          on a small sample the ranking flips
  3  COST_PER_CORRECT_REVERSAL   a lower price per token, a higher cost per correct answer
  4  TAIL_LATENCY_HIDDEN         p50 improves while p95 regresses
  5  PROMPT_SENSITIVITY          the verdict changes with the prompt, not the model
  6  NO_ROLLBACK_TRIGGER         nothing says when to roll back

All results are SIMULATED (data/_generate.py is a seeded stub). No model was
called, and nothing here measures any real model, vendor or bank.

Run (standard library only, Python 3.9):
    python step_03_deficiencies_exposed.py

Output: prints the six findings and writes src/out/step_03_results.json.
"""

from __future__ import annotations

import json
import random
import sys
from operator import itemgetter

from step_01_headline_average import CANDIDATE, DATA_DIR, OUT_DIR, headline_rule, load_dataset, overall_accuracy
from step_02_aggregate_significance import aggregate_rule, percentile

sys.path.insert(0, str(DATA_DIR))
import _generate as gen  # noqa: E402  (the same seeded generator that wrote the CSVs)

SUBSAMPLE_SEED = 31337
SUBSAMPLE_SIZES = (60, 120, 180, 240)
SUBSAMPLE_REPS = 1000
REPLAY_SEED = 8800
REPLAY_WEEKS = 8
REPLAY_PER_WEEK = 3000
REPLAY_SLIP_WEEK = 5
REPLAY_SLIP_SLICE = "numeric_units"
REPLAY_SLIP = 0.12
REPLAY_ALERT_BUFFER = 0.02   # average-only monitor: alert if the weekly average is 2 pp below A's baseline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slice_deltas(ds: dict, system: str) -> list:
    """Point-estimate accuracy change per slice (B minus A)."""
    a = ds["cols"]["A"]["correct"]
    b = ds["cols"][system]["correct"]
    out = []
    for k, sl in enumerate(ds["slices"]):
        idx = [i for i, s in enumerate(ds["slice_idx"]) if s == k]
        out.append({
            "slice": sl["slice"], "severity": sl["severity"], "n": len(idx),
            "acc_a": sum(a[i] for i in idx) / len(idx),
            "acc_b": sum(b[i] for i in idx) / len(idx),
            "delta": (sum(b[i] for i in idx) - sum(a[i] for i in idx)) / len(idx),
        })
    return out


def item_costs(ds: dict, system: str) -> list:
    p = ds["prices"][ds["model_of"][system]]
    c = ds["cols"][system]
    return [ti / 1000.0 * p["in"] + to / 1000.0 * p["out"] for ti, to in zip(c["tin"], c["tout"])]


def cost_per_correct(ds: dict, system: str) -> float:
    return sum(item_costs(ds, system)) / sum(ds["cols"][system]["correct"])


def latency_stats(ds: dict, system: str) -> dict:
    lat = sorted(ds["cols"][system]["lat"])
    return {"p50": percentile(lat, 0.50), "p95": percentile(lat, 0.95),
            "over_10s": sum(1 for x in lat if x > 10000) / len(lat)}


# ---------------------------------------------------------------------------
# Production replay (used by deficiency 6 here and by step 4)
# ---------------------------------------------------------------------------
def replay_production(ds: dict, slip_week: int = REPLAY_SLIP_WEEK, slip_slice: str = REPLAY_SLIP_SLICE,
                      slip: float = REPLAY_SLIP, weeks: int = REPLAY_WEEKS,
                      per_week: int = REPLAY_PER_WEEK, seed: int = REPLAY_SEED) -> list:
    """Simulate weeks of production traffic on model B (retuned prompt).

    The traffic is drawn from the same world as the evaluation set. From
    `slip_week` on, one slice gets worse by `slip` (a stand-in for a silent
    vendor update to B). Returns one record per week.
    """
    total = float(sum(sl["n_items"] for sl in ds["slices"]))
    base = gen.committed_spec()
    records = []
    for w in range(1, weeks + 1):
        slices = []
        for sl in base["slices"]:
            s = dict(sl)
            s["n"] = max(2, int(round(per_week * sl["n"] / total)))
            if w >= slip_week and s["name"] == slip_slice:
                s["d_new"] = sl["d_new"] - slip
            slices.append(s)
        spec = {"slices": slices, "v_out": base["v_out"], "spike_b": base["spike_b"]}
        sim = gen.simulate(spec, seed + w)
        correct = sim["cols"][CANDIDATE]["correct"]
        per_slice = {}
        for k, s in enumerate(slices):
            idx = [i for i, si in enumerate(sim["slice_idx"]) if si == k]
            per_slice[s["name"]] = {"n": len(idx), "acc": sum(correct[i] for i in idx) / len(idx)}
        records.append({"week": w, "overall_acc": sum(correct) / len(correct), "n": len(correct),
                        "slices": per_slice})
    return records


# ---------------------------------------------------------------------------
# The six deficiencies
# ---------------------------------------------------------------------------
def d1_aggregate_hides_slices(ds: dict) -> dict:
    head = headline_rule(ds, CANDIDATE)
    rows = slice_deltas(ds, CANDIDATE)
    down = [r for r in rows if r["delta"] < 0]
    down5 = [r for r in rows if r["delta"] <= -0.05]
    worst = min(rows, key=lambda r: r["delta"])
    return {"headline_delta": head["delta"], "slices": rows, "n_slices": len(rows),
            "n_down": len(down), "n_down_5pp": len(down5),
            "down_names": [r["slice"] for r in down], "worst": worst}


def d2_small_sample_flips(ds: dict) -> dict:
    n = len(ds["slice_idx"])
    diff = [y - x for x, y in zip(ds["cols"]["A"]["correct"], ds["cols"][CANDIDATE]["correct"])]
    diff_old = [y - x for x, y in zip(ds["cols"]["A"]["correct"], ds["cols"]["B_old_prompt"]["correct"])]
    rng = random.Random(SUBSAMPLE_SEED)
    rows = []
    for size in SUBSAMPLE_SIZES:
        better = worse = tie = 0
        better_old = 0
        for _ in range(SUBSAMPLE_REPS):
            idx = rng.sample(range(n), size)
            g = itemgetter(*idx)
            s = sum(g(diff))
            if s > 0:
                better += 1
            elif s < 0:
                worse += 1
            else:
                tie += 1
            if sum(g(diff_old)) > 0:
                better_old += 1
        rows.append({"size": size, "b_higher": better / SUBSAMPLE_REPS, "b_lower": worse / SUBSAMPLE_REPS,
                     "tie": tie / SUBSAMPLE_REPS, "b_old_higher": better_old / SUBSAMPLE_REPS})
    return {"rows": rows, "reps": SUBSAMPLE_REPS, "seed": SUBSAMPLE_SEED}


def d3_cost_reversal(ds: dict) -> dict:
    pa = ds["prices"][ds["model_of"]["A"]]
    pb = ds["prices"][ds["model_of"][CANDIDATE]]
    n = len(ds["slice_idx"])
    cost_a = sum(item_costs(ds, "A"))
    cost_b = sum(item_costs(ds, CANDIDATE))
    ok_a = sum(ds["cols"]["A"]["correct"])
    ok_b = sum(ds["cols"][CANDIDATE]["correct"])
    in_a, in_b = sum(ds["cols"]["A"]["tin"]) / n, sum(ds["cols"][CANDIDATE]["tin"]) / n
    out_a, out_b = sum(ds["cols"]["A"]["tout"]) / n, sum(ds["cols"][CANDIDATE]["tout"]) / n
    cpc_a, cpc_b = cost_a / ok_a, cost_b / ok_b
    return {
        "price_in_ratio": pb["in"] / pa["in"], "price_out_ratio": pb["out"] / pa["out"],
        "cost_per_item_a": cost_a / n, "cost_per_item_b": cost_b / n,
        "cpc_a": cpc_a, "cpc_b": cpc_b, "cpc_ratio": cpc_b / cpc_a,
        "avg_in_a": in_a, "avg_in_b": in_b, "avg_out_a": out_a, "avg_out_b": out_b,
        "correct_a": ok_a, "correct_b": ok_b,
        "per_1000_correct_a": cpc_a * 1000, "per_1000_correct_b": cpc_b * 1000,
    }


def d4_tail_latency(ds: dict) -> dict:
    a = latency_stats(ds, "A")
    b = latency_stats(ds, CANDIDATE)
    return {"p50_a": a["p50"], "p50_b": b["p50"], "p50_ratio": b["p50"] / a["p50"],
            "p95_a": a["p95"], "p95_b": b["p95"], "p95_ratio": b["p95"] / a["p95"],
            "over_10s_a": a["over_10s"], "over_10s_b": b["over_10s"]}


def d5_prompt_sensitivity(ds: dict) -> dict:
    out = {}
    for system, label in (("B_old_prompt", "old"), ("B_new_prompt", "retuned")):
        head = headline_rule(ds, system)
        agg = aggregate_rule(ds, system)
        rows = slice_deltas(ds, system)
        out[label] = {
            "system": system, "headline_delta": head["delta"], "headline_decision": head["decision"],
            "mcnemar_p": agg["mcnemar_p"], "aggregate_decision": agg["decision"],
            "slices_down_5pp": [r["slice"] for r in rows if r["delta"] <= -0.05],
            "slice_deltas": {r["slice"]: r["delta"] for r in rows},
        }
    swing = {s: out["retuned"]["slice_deltas"][s] - out["old"]["slice_deltas"][s] for s in out["old"]["slice_deltas"]}
    biggest = max(swing, key=lambda s: abs(swing[s]))
    out["biggest_swing_slice"] = biggest
    out["biggest_swing"] = swing[biggest]
    out["verdict_changes"] = out["old"]["aggregate_decision"] != out["retuned"]["aggregate_decision"]
    return out


def d6_no_rollback_trigger(ds: dict) -> dict:
    head = headline_rule(ds, CANDIDATE)
    replay = replay_production(ds)
    a_acc = overall_accuracy(ds, "A")
    a_slice = {r["slice"]: r["acc_a"] for r in slice_deltas(ds, "A")}
    weeks = []
    alert_weeks = 0
    gap_weeks = 0
    for rec in replay:
        alert = rec["overall_acc"] < a_acc - REPLAY_ALERT_BUFFER   # the only monitor the headline rule implies
        gap = rec["slices"][REPLAY_SLIP_SLICE]["acc"] - a_slice[REPLAY_SLIP_SLICE]
        tol = next(s["tol"] for s in ds["slices"] if s["slice"] == REPLAY_SLIP_SLICE)
        alert_weeks += 1 if alert else 0
        gap_weeks += 1 if gap <= -tol else 0
        weeks.append({"week": rec["week"], "overall_acc": rec["overall_acc"], "overall_vs_a": rec["overall_acc"] - a_acc,
                      "slice_acc": rec["slices"][REPLAY_SLIP_SLICE]["acc"], "slice_gap_vs_a": gap, "alert": alert})
    return {"triggers_defined": len(head["rollback_triggers"]), "weeks": weeks, "alert_weeks": alert_weeks,
            "slice_gap_weeks": gap_weeks, "n_weeks": len(replay), "a_acc": a_acc,
            "slip_week": REPLAY_SLIP_WEEK, "slip_slice": REPLAY_SLIP_SLICE, "slip": REPLAY_SLIP, "alert_buffer": REPLAY_ALERT_BUFFER,
            "per_week": REPLAY_PER_WEEK}


def run() -> dict:
    ds = load_dataset()
    return {
        "d1": d1_aggregate_hides_slices(ds),
        "d2": d2_small_sample_flips(ds),
        "d3": d3_cost_reversal(ds),
        "d4": d4_tail_latency(ds),
        "d5": d5_prompt_sensitivity(ds),
        "d6": d6_no_rollback_trigger(ds),
    }


def _pp(x: float) -> str:
    return "%+.1f pp" % (x * 100)


def main() -> None:
    r = run()
    print("\n" + "=" * 80)
    print("Step 3 - Where the basic approach breaks: six named deficiencies")
    print("=" * 80)
    print("SIMULATED results from a seeded generator (data/_generate.py). No model was called.\n")

    d1 = r["d1"]
    print("1. AGGREGATE_HIDES_SLICES")
    print("   Headline change (B retuned minus A): %s" % _pp(d1["headline_delta"]))
    for row in d1["slices"]:
        print("     %-22s n=%3d  A %5.1f%%  B %5.1f%%  change %s" % (
            row["slice"], row["n"], row["acc_a"] * 100, row["acc_b"] * 100, _pp(row["delta"])))
    print("   Slices below A: %d of %d (%s). Slices down 5 pp or more: %d." % (
        d1["n_down"], d1["n_slices"], ", ".join(d1["down_names"]), d1["n_down_5pp"]))

    d2 = r["d2"]
    print("\n2. SMALL_SAMPLE_FLIPS   (%d random subsamples per size, fixed seed %d)" % (d2["reps"], d2["seed"]))
    print("   items   B higher   B lower   tie     B (old prompt) higher")
    for row in d2["rows"]:
        print("   %5d   %5.1f%%    %5.1f%%   %4.1f%%   %5.1f%%" % (
            row["size"], row["b_higher"] * 100, row["b_lower"] * 100, row["tie"] * 100, row["b_old_higher"] * 100))

    d3 = r["d3"]
    print("\n3. COST_PER_CORRECT_REVERSAL")
    print("   List price per token, B / A:          input %.2fx, output %.2fx" % (d3["price_in_ratio"], d3["price_out_ratio"]))
    print("   Average tokens per item, A -> B:      input %.0f -> %.0f, output %.0f -> %.0f  (output %+.1f%%)" % (
        d3["avg_in_a"], d3["avg_in_b"], d3["avg_out_a"], d3["avg_out_b"], (d3["avg_out_b"] / d3["avg_out_a"] - 1) * 100))
    print("   Cost per item, A -> B:                $%.5f -> $%.5f" % (d3["cost_per_item_a"], d3["cost_per_item_b"]))
    print("   Correct answers, A -> B:              %d -> %d" % (d3["correct_a"], d3["correct_b"]))
    print("   Cost per correct answer, A -> B:      $%.5f -> $%.5f  (%+.1f%%)" % (
        d3["cpc_a"], d3["cpc_b"], (d3["cpc_ratio"] - 1) * 100))

    d4 = r["d4"]
    print("\n4. TAIL_LATENCY_HIDDEN")
    print("   p50 latency, A -> B:   %5.0f ms -> %5.0f ms  (%+.1f%%)" % (d4["p50_a"], d4["p50_b"], (d4["p50_ratio"] - 1) * 100))
    print("   p95 latency, A -> B:   %5.0f ms -> %5.0f ms  (%+.1f%%)" % (d4["p95_a"], d4["p95_b"], (d4["p95_ratio"] - 1) * 100))
    print("   Calls slower than 10 s: A %.1f%%, B %.1f%%" % (d4["over_10s_a"] * 100, d4["over_10s_b"] * 100))

    d5 = r["d5"]
    print("\n5. PROMPT_SENSITIVITY   (same model B, two prompts)")
    print("   %-26s %-14s %-14s" % ("", "A's old prompt", "retuned prompt"))
    print("   %-26s %-14s %-14s" % ("headline change", _pp(d5["old"]["headline_delta"]), _pp(d5["retuned"]["headline_delta"])))
    print("   %-26s %-14s %-14s" % ("step 1 decision", d5["old"]["headline_decision"], d5["retuned"]["headline_decision"]))
    print("   %-26s %-14.4f %-14.4f" % ("McNemar p-value", d5["old"]["mcnemar_p"], d5["retuned"]["mcnemar_p"]))
    print("   %-26s %-14s %-14s" % ("step 2 decision", d5["old"]["aggregate_decision"], d5["retuned"]["aggregate_decision"]))
    print("   %-26s %-14d %-14d" % ("slices down 5 pp or more", len(d5["old"]["slices_down_5pp"]), len(d5["retuned"]["slices_down_5pp"])))
    print("   Biggest swing: %s moves %s between the two prompts." % (d5["biggest_swing_slice"], _pp(d5["biggest_swing"])))

    d6 = r["d6"]
    print("\n6. NO_ROLLBACK_TRIGGER   (%d weeks of simulated production traffic, %d responses a week)" % (
        d6["n_weeks"], d6["per_week"]))
    print("   Rollback triggers defined by steps 1 and 2: %d" % d6["triggers_defined"])
    print("   A silent change at week %d lowers %s by a further %.0f points." % (d6["slip_week"], d6["slip_slice"], d6["slip"] * 100))
    print("   week   overall vs A   %s vs A   average-only alert" % d6["slip_slice"])
    for w in d6["weeks"]:
        print("   %4d   %+6.1f pp      %+6.1f pp      %s" % (w["week"], w["overall_vs_a"] * 100, w["slice_gap_vs_a"] * 100,
                                                         "ALERT" if w["alert"] else "-"))
    print("   Weeks the average-only monitor alerted: %d of %d" % (d6["alert_weeks"], d6["n_weeks"]))
    print("   Weeks %s sat at or beyond its tolerance below A: %d of %d" % (d6["slip_slice"], d6["slice_gap_weeks"], d6["n_weeks"]))

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_03_results.json", "w") as f:
        json.dump(r, f, indent=2)
    print("\nwrote src/out/step_03_results.json")


if __name__ == "__main__":
    main()
