"""
Step 2 - The basic approach: overall average plus a significance test.

The careful version of Step 1. The team still compares overall averages, but
it asks whether the difference is bigger than noise before it decides. This
script runs two standard tests on the paired 720-item set:

  * McNemar's exact test on the items where A and B disagree
  * a paired bootstrap interval on the overall accuracy difference

Rule: GO if B is higher and the difference is significant; NO-GO if B is lower
and the difference is significant; HOLD if the difference is within noise.

All results are SIMULATED (data/_generate.py is a seeded stub). No model was
called.

Run (standard library only, Python 3.9):
    python step_02_aggregate_significance.py

Output: prints the decision and writes src/out/step_02_results.json.
"""

from __future__ import annotations

import json
import math
import random

from step_01_headline_average import CANDIDATE, OUT_DIR, load_dataset

B_MAIN = 2000       # bootstrap resamples for the committed dataset
BOOT_SEED = 20261018


# ---------------------------------------------------------------------------
# Statistics (standard library only; imported by steps 3 and 4)
# ---------------------------------------------------------------------------
def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value. b = A right, B wrong; c = A wrong, B right."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / float(2 ** n)
    return min(1.0, 2.0 * tail)


def percentile(sorted_vals: list, q: float) -> float:
    """Linear-interpolated percentile of an already sorted list; q in [0, 1]."""
    if not sorted_vals:
        raise ValueError("empty list")
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def paired_diffs(ds: dict, system: str) -> list:
    a = ds["cols"]["A"]["correct"]
    b = ds["cols"][system]["correct"]
    return [y - x for x, y in zip(a, b)]


def discordant(ds: dict, system: str) -> tuple:
    d = paired_diffs(ds, system)
    return sum(1 for x in d if x == -1), sum(1 for x in d if x == 1)   # (A right B wrong, A wrong B right)


def overall_bootstrap(ds: dict, system: str, B: int, seed: int, confidence: float = 0.95) -> tuple:
    """Paired bootstrap CI for B's overall accuracy minus A's (items resampled as pairs)."""
    d = paired_diffs(ds, system)
    n = len(d)
    rng = random.Random(seed)
    get = rng.choices
    reps = sorted(sum(get(d, k=n)) / n for _ in range(B))
    tail = (1.0 - confidence) / 2.0
    return percentile(reps, tail), percentile(reps, 1.0 - tail)


def aggregate_rule(ds: dict, system: str = CANDIDATE, B: int = B_MAIN, seed: int = BOOT_SEED) -> dict:
    alpha = float(ds["policy"].get("aggregate_alpha", 0.05))
    n = len(ds["slice_idx"])
    b, c = discordant(ds, system)
    delta = (c - b) / n
    p = mcnemar_exact(b, c)
    lo, hi = overall_bootstrap(ds, system, B, seed, float(ds["policy"].get("bootstrap_confidence", 0.95)))
    if p < alpha and delta > 0:
        decision = "GO"
    elif p < alpha and delta < 0:
        decision = "NO-GO"
    else:
        decision = "HOLD"
    return {
        "system": system,
        "n_items": n,
        "a_right_b_wrong": b,
        "a_wrong_b_right": c,
        "delta": delta,
        "ci_lo": lo,
        "ci_hi": hi,
        "mcnemar_p": p,
        "alpha": alpha,
        "bootstrap_resamples": B,
        "decision": decision,
        "rollback_triggers": [],
    }


def run() -> dict:
    ds = load_dataset()
    return aggregate_rule(ds)


def main() -> None:
    res = run()
    print("\n" + "=" * 80)
    print("Step 2 - The basic approach: overall average plus a significance test")
    print("=" * 80)
    print("SIMULATED results from a seeded generator (data/_generate.py). No model was called.\n")
    print("Items scored:                    %d (paired: every item is scored for A and for B)" % res["n_items"])
    print("Items where only A is right:     %d" % res["a_right_b_wrong"])
    print("Items where only B is right:     %d" % res["a_wrong_b_right"])
    print("Overall change (B minus A):      %+.1f pp" % (res["delta"] * 100))
    print("Paired bootstrap 95%% interval:   %+.1f pp to %+.1f pp  (%d resamples, fixed seed)" % (
        res["ci_lo"] * 100, res["ci_hi"] * 100, res["bootstrap_resamples"]))
    print("McNemar exact p-value:           %.4f   (significant if below %.2f)" % (res["mcnemar_p"], res["alpha"]))
    print("Decision rule:                   GO if B is higher and significant; HOLD if within noise")
    print("\nDECISION: %s" % res["decision"])
    print("\nWhat this decision contains:")
    print("  per-slice results:             none (the test is on the aggregate)")
    print("  cost per correct answer:       not looked at")
    print("  p50 / p95 latency:             not looked at")
    print("  rollback triggers:             %d defined" % len(res["rollback_triggers"]))

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_02_results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("\nwrote src/out/step_02_results.json")


if __name__ == "__main__":
    main()
