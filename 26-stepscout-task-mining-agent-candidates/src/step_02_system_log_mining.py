"""Step 2 - The basic approach: process-mine the case-system log, rank by volume times time.

The case system records status changes. That is the log most operations teams mine: the sequence of
statuses per case (the variants), the time from receipt to close, and for each status a count and a
time since the previous status. The usual candidate list multiplies the count by the time and puts
the biggest products first. This script does exactly that, with no desktop data and no answer key.

Time here is working time (08:00 to 18:00, Monday to Friday): nights and weekends are left out, which
is generous to the log. Cycle time stops at the first CLOSED, as most dashboards report it.

Run (from src/):
    python3 step_02_system_log_mining.py

Output: a readable summary, plus out/step_02_variants.csv, out/step_02_candidates_volume_first.csv and
out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from step_01_interview_process_map import (
    DAY_S, OUT_DIR, WORKDATES, fnum, load_all, pct, rnd,
)

TOP_N = 10
NON_STEP = ("RECEIVED", "REOPENED")      # statuses that mark the start of a case or a rework loop


def wall_dt(w: float) -> datetime:
    day, s = divmod(int(w), DAY_S)
    return datetime.combine(WORKDATES[day], time(8, 0)) + timedelta(seconds=s)


def percentile(v: list, p: float) -> float:
    v = sorted(v)
    k = (len(v) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def analyze(data: dict) -> dict:
    """Variants, cycle time and the volume-times-time candidate list from the system log only."""
    register = data["register"]
    step_of = {r["status"]: sid for sid, r in register.items() if r["status"]}
    n_cases = len(data["cases"])

    variants = Counter()
    act_n, act_min = Counter(), defaultdict(float)
    cycle_bh, cycle_wall, cycle_to_final_bh = [], [], []
    reopen_events = 0
    for cid, evs in data["sys_by_case"].items():
        variants[tuple(e["status"] for e in evs)] += 1
        for prev, cur in zip(evs, evs[1:]):
            act_n[cur["status"]] += 1
            act_min[cur["status"]] += (cur["ts"] - prev["ts"]) / 60.0
        reopen_events += sum(1 for e in evs if e["status"] == "REOPENED")
        closes = [e["ts"] for e in evs if e["status"] == "CLOSED"]
        start = evs[0]["ts"]
        if closes:
            cycle_bh.append((closes[0] - start) / 3600.0)
            cycle_to_final_bh.append((closes[-1] - start) / 3600.0)
            cycle_wall.append((wall_dt(closes[0]) - wall_dt(start)).total_seconds() / 3600.0)

    ordered = variants.most_common()
    cum, to80 = 0, 0
    for _, c in ordered:
        cum += c
        to80 += 1
        if cum >= 0.8 * n_cases:
            break

    rows = []
    for status, n in act_n.items():
        if status in NON_STEP:
            continue
        mean_min = act_min[status] / n
        rows.append({"status": status, "step": step_of.get(status, ""), "volume": n, "mean_elapsed_min": mean_min,
                     "elapsed_hours": act_min[status] / 60.0, "score": n * mean_min})
    rows.sort(key=lambda r: (-r["score"], r["status"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return {
        "n_cases": n_cases, "n_events": len(data["system"]), "n_variants": len(variants), "top_variant_cases": ordered[0][1],
        "top_variant": ordered[0][0], "variants_to_80pct": to80, "variants": ordered,
        "cycle_median_bh": statistics.median(cycle_bh), "cycle_mean_bh": statistics.mean(cycle_bh),
        "cycle_p90_bh": percentile(cycle_bh, 0.9), "cycle_median_wall_h": statistics.median(cycle_wall),
        "cycle_final_mean_bh": statistics.mean(cycle_to_final_bh), "reopen_events": reopen_events,
        "candidates": rows, "top10": [r["step"] for r in rows[:TOP_N]], "cycle_bh": cycle_bh,
        "elapsed_hours_total": sum(r["elapsed_hours"] for r in rows),
        "elapsed_hours_top10": sum(r["elapsed_hours"] for r in rows[:TOP_N]),
    }


def main() -> None:
    data = load_all()
    A = analyze(data)
    reg = data["register"]
    print("=" * 100)
    print("Step 2 - Process-mine the case-system log, rank by volume times time")
    print("=" * 100)
    print(f"\nSource: data/system_events.csv only. {A['n_events']:,} status changes on {A['n_cases']:,} cases. "
          "No desktop data, no answer key.\n")
    print("VARIANTS (the sequence of statuses per case)")
    print(f"  {A['n_variants']} distinct variants in the log.")
    print(f"  The most common: {A['top_variant_cases']:,} cases ({pct(A['top_variant_cases'], A['n_cases'])}%).")
    print(f"  It takes {A['variants_to_80pct']} variants to cover 80% of cases.")
    print(f"  Rework: {A['reopen_events']} REOPENED statuses ({pct(A['reopen_events'], A['n_cases'])}% of cases).")
    print("  Top variants (each status shown as the step that posts it; rcv = receipt):")
    step_of = {r["status"]: sid for sid, r in reg.items() if r["status"]}
    step_of.update({"RECEIVED": "rcv", "REOPENED": "REOPEN"})
    for seq, c in A["variants"][:5]:
        print(f"    {c:>4} cases ({pct(c, A['n_cases']):>4}%)  " + " > ".join(step_of[x] for x in seq))
    print("\nCYCLE TIME (receipt to the first CLOSED, working hours)")
    print(f"  median {fnum(A['cycle_median_bh'])} h   mean {fnum(A['cycle_mean_bh'])} h   90th percentile {fnum(A['cycle_p90_bh'])} h")
    print(f"  On the wall clock, nights and weekends included, the median is {fnum(A['cycle_median_wall_h'])} h.")
    print("\nTHE USUAL CANDIDATE LIST: volume x time since the previous status, biggest first")
    print(f"  {'rank':>4}  {'status':<19} {'step':<5} {'name':<30} {'volume':>6} {'mean min':>9} {'hours':>8}")
    for r in A["candidates"][:TOP_N]:
        name = reg[r["step"]]["name"] if r["step"] in reg else ""
        print(f"  {r['rank']:>4}  {r['status']:<19} {r['step']:<5} {name:<30} {r['volume']:>6,} "
              f"{fnum(r['mean_elapsed_min']):>9} {rnd(r['elapsed_hours']):>8,}")
    rest = A["candidates"][TOP_N:]
    if rest:
        print("  Below the cut: " + ", ".join(f"{r['step']} ({r['status']})" for r in rest))
    seen = {r["step"] for r in A["candidates"]}
    gone = [s for s in data["order"] if s not in seen]
    print(f"\n  Steps in the workflow the log never records: {len(gone)} of {len(data['order'])} ({', '.join(gone)}).")
    print(f"  The list's top {TOP_N} are credited {rnd(A['elapsed_hours_top10']):,} hours; each hour is the time since the "
          "previous status, so it contains waiting.")
    print("\nWhat this approach gets right: it is cheap, it covers every case, and the variants show real paths. "
          "Step 3 counts what it cannot see.")

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_02_variants.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["cases", "share_pct", "status_sequence"])
        for seq, c in A["variants"]:
            w.writerow([c, pct(c, A["n_cases"]), " > ".join(seq)])
    with open(OUT_DIR / "step_02_candidates_volume_first.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "status", "step_id", "volume", "mean_elapsed_min", "elapsed_hours"])
        for r in A["candidates"]:
            w.writerow([r["rank"], r["status"], r["step"], r["volume"], round(r["mean_elapsed_min"], 2),
                        round(r["elapsed_hours"], 1)])
    summ = {k: A[k] for k in ("n_cases", "n_events", "n_variants", "top_variant_cases", "variants_to_80pct",
                              "cycle_median_bh", "cycle_mean_bh", "cycle_p90_bh", "cycle_median_wall_h", "reopen_events",
                              "top10", "elapsed_hours_total", "elapsed_hours_top10")}
    (OUT_DIR / "step_02_summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")
    print("\nWrote src/out/step_02_variants.csv, step_02_candidates_volume_first.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
