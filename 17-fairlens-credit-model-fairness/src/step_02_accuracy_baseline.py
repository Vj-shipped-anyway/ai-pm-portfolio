"""Step 2 - The basic approach: overall accuracy, plus the usual accuracy-style metrics.

This is what a model-risk reviewer does with only the model card and the outcome data:
compute accuracy and a few more metrics that need nothing beyond the standard library
(no AUC, no packages), and look at accuracy by group if the group is known.

  * accuracy, approval rate
  * default rate among approved applicants (the approved book)
  * default catch rate (share of defaulters who were declined)
  * false decline rate (share of non-defaulters who were declined)
  * KS statistic (how far apart the score distributions of repaid and defaulted sit)
  * accuracy by group

Everything here is a correct, reasonable accuracy-style check. The question for step 3 is what
it cannot see. The scorecard is a stub, not a trained model; the data is synthetic.

Run (from src/):
    python3 step_02_accuracy_baseline.py

Output: a readable summary, plus out/step_02_baseline.json.
"""

from __future__ import annotations

import json

from step_01_model_card_only import (GROUPS, OUT_DIR, POLICY_CUTOFF, approved, correct, prepare, rate)


def ks_statistic(rows: list) -> float:
    """Largest gap between the cumulative score distributions of repaid and defaulted applicants."""
    good = sorted(a["score"] for a in rows if a["defaulted"] == 0)
    bad = sorted(a["score"] for a in rows if a["defaulted"] == 1)
    best, i, j = 0.0, 0, 0
    for s in sorted({a["score"] for a in rows}):
        while i < len(good) and good[i] <= s:
            i += 1
        while j < len(bad) and bad[j] <= s:
            j += 1
        best = max(best, abs(i / len(good) - j / len(bad)))
    return best


def overall_metrics(rows: list, cutoff: int = POLICY_CUTOFF) -> dict:
    n = len(rows)
    apr = [a for a in rows if approved(a["score"], cutoff)]
    dec = [a for a in rows if not approved(a["score"], cutoff)]
    bad = [a for a in rows if a["defaulted"] == 1]
    good = [a for a in rows if a["defaulted"] == 0]
    return {
        "n": n, "approved": len(apr),
        "accuracy": rate(sum(1 for a in rows if correct(a, approved(a["score"], cutoff))), n),
        "approval_rate": rate(len(apr), n),
        "approved_book_default_rate": rate(sum(a["defaulted"] for a in apr), len(apr)),
        "default_catch_rate": rate(sum(1 for a in bad if not approved(a["score"], cutoff)), len(bad)),
        "false_decline_rate": rate(sum(1 for a in good if not approved(a["score"], cutoff)), len(good)),
        "defaults": len(bad), "declined": len(dec), "ks": ks_statistic(rows),
    }


def accuracy_by_group(rows: list, cutoff: int = POLICY_CUTOFF) -> list:
    out = []
    for g in GROUPS:
        gr = [a for a in rows if a["group"] == g]
        ok = sum(1 for a in gr if correct(a, approved(a["score"], cutoff)))
        out.append({"group": g, "n": len(gr), "correct": ok, "accuracy": rate(ok, len(gr))})
    return out


def summarize(prep: dict) -> dict:
    rows = prep["rows"]
    o = overall_metrics(rows)
    by = accuracy_by_group(rows)
    accs = [b["accuracy"] for b in by]
    hi = max(by, key=lambda b: b["accuracy"])
    lo = min(by, key=lambda b: b["accuracy"])
    return {"overall": o, "by_group": by, "acc_spread_pts": 100 * (max(accs) - min(accs)),
            "acc_high_group": hi["group"], "acc_low_group": lo["group"],
            "acc_high": hi["accuracy"], "acc_low": lo["accuracy"]}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    prep = prepare()
    s = summarize(prep)
    o = s["overall"]

    print("\n" + "=" * 78)
    print("Step 2 - With the basic approach: overall accuracy and accuracy by group")
    print("=" * 78)
    print(f"\nSame {o['n']:,} synthetic applicants, same stub scorecard, same cutoff ({POLICY_CUTOFF} points).\n")
    print("OVERALL METRICS (standard library only, no AUC)")
    print(f"  Accuracy:                           {100 * o['accuracy']:.1f}%")
    print(f"  Approval rate:                      {100 * o['approval_rate']:.1f}%")
    print(f"  Default rate in the approved book:  {100 * o['approved_book_default_rate']:.1f}%")
    print(f"  Default catch rate:                 {100 * o['default_catch_rate']:.1f}% of {o['defaults']:,} defaulters declined")
    print(f"  False decline rate:                 {100 * o['false_decline_rate']:.1f}% of repaid applicants declined")
    print(f"  KS statistic (score separation):    {o['ks']:.3f}")

    print("\nACCURACY BY GROUP")
    print(f"  {'group':<9} {'applicants':>10} {'correct':>8} {'accuracy':>9}")
    for b in s["by_group"]:
        print(f"  {b['group']:<9} {b['n']:>10,} {b['correct']:>8,} {100 * b['accuracy']:>8.1f}%")
    print(f"  Spread: {s['acc_spread_pts']:.1f} points, from {100 * s['acc_low']:.1f}% ({s['acc_low_group']}) "
          f"to {100 * s['acc_high']:.1f}% ({s['acc_high_group']}).")

    print("\nWHAT THIS VIEW CONTAINS")
    print("  Accuracy-style metrics, overall and by group. Every number above is a fair way to")
    print("  describe how often the scorecard agrees with the outcome.")
    print("  What it does not contain: how many applicants of each group are approved, how that")
    print("  moves with the cutoff, whether one input is acting as a stand-in for group, or")
    print("  whether declined applicants are told consistent reasons. Step 3 measures those.")

    with open(OUT_DIR / "step_02_baseline.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_02_baseline.json")


if __name__ == "__main__":
    main()
