"""Step 1 - Before AgentKit: the human-only baseline on the 600 historical cases.

What it measures (on the shipped synthetic data, from the recorded human outcomes):
  * touch minutes per case: mean, median, 90th percentile, and the total over the 30 day window
  * the outcome mix: how many cases a worker resubmitted, returned, escalated or closed as a duplicate
  * where the minutes go, by recorded outcome and by the generator's scenario

The minutes are 🟡 modeled: the generator sums its own per-step minutes (data/step_minutes.csv) with
noise. They are an assumption, not a time study. The total is the size of the pool, not a saving.
The outcome mix is a count of the recorded outcomes. Run from src/:  python3 step_01_manual_handling.py
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agentkit.data_io import load_world  # noqa: E402
from common import fnum, median, pct, quantile, table, write_csv, write_json  # noqa: E402


def compute(world: dict) -> dict:
    outcomes, truth = world["outcomes"], world["truth"]
    mins = [o["touch_minutes"] for o in outcomes.values()]
    mix = Counter(o["human_outcome"] for o in outcomes.values())
    by_outcome = defaultdict(list)
    by_scenario = defaultdict(list)
    for cid, o in outcomes.items():
        by_outcome[o["human_outcome"]].append(o["touch_minutes"])
        by_scenario[truth[cid]["scenario"]].append(o["touch_minutes"])
    resub = [o for o in outcomes.values() if o["human_outcome"] == "RESUBMIT"]
    total_min = sum(mins)
    workers = Counter(o["handled_by"] for o in outcomes.values())
    return {
        "cases": len(mins),
        "window_days": 30,
        "minutes_mean": round(sum(mins) / len(mins), 1),
        "minutes_median": round(median(mins), 1),
        "minutes_p90": round(quantile(mins, 0.9), 1),
        "minutes_total": round(total_min, 1),
        "hours_total": round(total_min / 60, 1),
        "outcome_mix": dict(sorted(mix.items())),
        "by_outcome": {k: {"n": len(v), "mean": round(sum(v) / len(v), 1), "total_hours": round(sum(v) / 60, 1)}
                       for k, v in sorted(by_outcome.items())},
        "by_scenario": {k: {"n": len(v), "mean": round(sum(v) / len(v), 1)} for k, v in sorted(by_scenario.items())},
        "four_eyes_approvals": len(resub),
        "step_minutes": {s: v["minutes"] for s, v in world["step_minutes"].items()},
        "workers": len(workers),
    }


def main() -> int:
    world = load_world()
    r = compute(world)
    print("=" * 100)
    print("Step 1 - Before AgentKit: the human-only baseline on the historical cases")
    print("=" * 100)
    print("\nASSUMPTION (modeled): touch minutes come from the generator's per-step minutes in data/step_minutes.csv,")
    print("summed over the steps a worker performed and multiplied by case-level noise. Not a time study.")
    print("\nPer-step minutes the generator uses (S07 and S09 are the person-held steps):")
    for s, m in r["step_minutes"].items():
        print(f"  {s}  {world['step_minutes'][s]['step_name']:26s} {world['step_minutes'][s]['truth_class']:15s} {m:4.1f}")

    print(f"\nRESULT ({r['cases']} cases, {r['window_days']} days, {r['workers']} pseudonymous workers)")
    print(f"  touch minutes per case   mean {r['minutes_mean']}   median {r['minutes_median']}   90th percentile {r['minutes_p90']}")
    print(f"  total touch time         {fnum(r['minutes_total'], 0)} minutes = {r['hours_total']} hours (modeled; the size of the pool, not a saving)")
    print("\nOutcome mix (recorded):")
    rows = [(k, v, pct(v / r["cases"]), r["by_outcome"][k]["mean"], r["by_outcome"][k]["total_hours"])
            for k, v in r["outcome_mix"].items()]
    print(table(rows, ["recorded outcome", "cases", "share", "mean min", "hours"]))
    print(f"\n  {r['four_eyes_approvals']} resubmissions; the generator's manual path includes a second person's approval (S09) on each, by construction.")
    print("\nWhere the minutes go, by the generator's scenario (the answer key; explains the mix, not an input):")
    rows = [(k, v["n"], v["mean"]) for k, v in sorted(r["by_scenario"].items(), key=lambda kv: -kv[1]["mean"])]
    print(table(rows, ["scenario", "cases", "mean min"]))
    sm = r["step_minutes"]
    path = sum(sm[x] for x in ("S01", "S02", "S03", "S04", "S05", "S06", "S08", "S09", "S10", "S11", "S12"))
    print(f"\nWhat this baseline shows: a resubmit path sums to {path:.0f} minutes in the generator's table, of which the")
    print(f"person-held steps are S09 ({sm['S09']:.0f} min, the second person) and, when a match is ambiguous, S07 ({sm['S07']:.0f} min).")
    print("The other steps are rule-following: copy, match, screen, draft, note, close.")
    write_csv("step_01_by_scenario.csv", ["scenario", "cases", "mean_minutes"],
              [(k, v["n"], v["mean"]) for k, v in sorted(r["by_scenario"].items())])
    write_json("step_01_summary.json", r)
    print("\nWrote src/out/step_01_by_scenario.csv and step_01_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
