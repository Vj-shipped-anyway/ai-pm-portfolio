"""
Step 1 - Before: one spreadsheet, every case gets the same review, first in first out.

A sponsor fills in an intake form. A reviewer opens the next row in the
spreadsheet and runs the same standard review on it, whatever the use case is.
Nobody can say how many AI use cases exist, which tier each one sits in, or what
evidence each one owes.

What this script measures, all on synthetic data:
  - how long the truly high-risk cases (reference tier 3-4) wait in the queue
  - total reviewer hours

Everything in the queue simulation is a modeled assumption (yellow). The
assumptions are printed first. The arrival pattern comes from the dataset; the
service times, reviewer count and noise are assumptions.

This file also holds the shared loaders and the queue simulator that steps 2-4
import, so run the steps from this folder:  python3 step_01_spreadsheet_fifo.py

Output:
  - prints the assumptions and the result
  - writes src/out/step_01_results.json and src/out/step_01_cases.csv
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import random
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

# ---------------------------------------------------------------------------
# Modeled assumptions (yellow). Printed by every step that uses them.
# ---------------------------------------------------------------------------
N_REVIEWERS = 3                         # reviewers working the intake queue
INTAKE_HOURS_PER_REVIEWER_PER_WEEK = 16  # the rest of their week goes to validating live models
HOURS_PER_REVIEWER_PER_DAY = INTAKE_HOURS_PER_REVIEWER_PER_WEEK / 5.0
UNIFORM_REVIEW_H = 6.0                  # Step 1: the same standard review for every case (close to the tier-mix average)
TIER_REVIEW_H = {1: 1.5, 2: 3.0, 3: 8.0, 4: 14.0}   # Steps 2 and 4: review depth by tier
LINK_CHECK_H = 0.5                      # Step 4: a reviewer confirms a proposed duplicate link
SERVICE_SIGMA = 0.35                    # lognormal noise on every review time, mean 1.0
REPLICATIONS = 200                      # seeded replications of the queue
SIM_SEED = 20261011
HI_TIERS = (3, 4)                       # "high risk" for every wait and recall number

START = dt.date(2026, 1, 5)             # first Monday of the dataset


def assumptions_text(uniform: bool = True, tiered: bool = True) -> list[str]:
    lines = [
        "Arrivals: the 150 submitted_date values in the dataset (business days, FIFO tie-break by id)",
        "Reviewers: %d, each with %d intake hours per week (%.1f hours per business day)"
        % (N_REVIEWERS, INTAKE_HOURS_PER_REVIEWER_PER_WEEK, HOURS_PER_REVIEWER_PER_DAY),
        "Noise: every review time x lognormal (sigma %.2f, mean 1.0); %d seeded replications, "
        "same noise draws in every scenario" % (SERVICE_SIGMA, REPLICATIONS),
        "Queue: non-preemptive, no rework loop, evidence requests do not re-enter the queue",
    ]
    if uniform:
        lines.insert(2, "Step 1 review time: %.1f hours for every case (set close to the tier-mix average of the tier times)"
                     % UNIFORM_REVIEW_H)
    if tiered:
        lines.insert(3 if uniform else 2,
                     "Review time by tier (Steps 2 and 4): T1 %.1fh, T2 %.1fh, T3 %.1fh, T4 %.1fh"
                     % (TIER_REVIEW_H[1], TIER_REVIEW_H[2], TIER_REVIEW_H[3], TIER_REVIEW_H[4]))
    return lines


# ---------------------------------------------------------------------------
# Loaders (shared by steps 2-4 and the app)
# ---------------------------------------------------------------------------
def read_csv(name: str) -> list[dict]:
    with open(DATA_DIR / name, newline="") as fh:
        return list(csv.DictReader(fh))


def business_day_index(date_str: str) -> int:
    d = dt.date.fromisoformat(date_str)
    days = (d - START).days
    return (days // 7) * 5 + (days % 7)


def load_cases() -> list[dict]:
    rows = read_csv("intake_submissions.csv")
    for r in rows:
        r["self_declared_tier"] = int(r["self_declared_tier"])
        r["reference_tier"] = int(r["reference_tier"])
        r["reference_score"] = int(r["reference_score"])
        r["arrival_day"] = business_day_index(r["submitted_date"])
    rows.sort(key=lambda r: r["use_case_id"])
    return rows


def load_checklist() -> dict:
    """tier -> list of evidence ids required (cumulative)."""
    out: dict[int, list[str]] = {1: [], 2: [], 3: [], 4: []}
    for r in read_csv("evidence_checklist.csv"):
        out[int(r["tier"])].append(r["evidence_id"])
    return out


def load_evidence_names() -> dict:
    names = {}
    for r in read_csv("evidence_checklist.csv"):
        names[r["evidence_id"]] = (r["evidence_item"], r["interlock"])
    return names


def load_evidence_on_file() -> dict:
    out: dict[str, set] = {}
    for r in read_csv("evidence_on_file.csv"):
        out.setdefault(r["use_case_id"], set()).add(r["evidence_id"])
    return out


# ---------------------------------------------------------------------------
# Queue simulator
# ---------------------------------------------------------------------------
def simulate(arrivals: list[float], service_days: list[float],
             priority: list[int] | None = None, n_servers: int | None = None) -> list[float]:
    """Non-preemptive multi-server queue. Returns the start time of each case.

    priority None -> first in first out (ties by index).
    priority list -> higher value is served first, FIFO inside a priority level.
    """
    n = len(arrivals)
    if n_servers is None:
        n_servers = N_REVIEWERS
    order = sorted(range(n), key=lambda i: (arrivals[i], i))
    free = [0.0] * n_servers
    start = [0.0] * n
    waiting: list[int] = []
    k = 0
    done = 0
    while done < n:
        s = min(range(n_servers), key=lambda j: free[j])
        t = free[s]
        while k < n and arrivals[order[k]] <= t:
            waiting.append(order[k])
            k += 1
        eligible = [x for x in waiting if arrivals[x] <= t]
        if not eligible:
            # the reviewer is idle until the next case arrives
            nxt = arrivals[order[k]] if k < n else float("inf")
            t = min([nxt] + [arrivals[x] for x in waiting])
            while k < n and arrivals[order[k]] <= t:
                waiting.append(order[k])
                k += 1
            eligible = [x for x in waiting if arrivals[x] <= t]
        if priority is None:
            i = min(eligible, key=lambda x: (arrivals[x], x))
        else:
            i = min(eligible, key=lambda x: (-priority[x], arrivals[x], x))
        waiting.remove(i)
        start[i] = t
        free[s] = t + service_days[i]
        done += 1
    return start


def _noise(n: int, rep: int) -> list[float]:
    r = random.Random(SIM_SEED * 1000 + rep)
    mu = -(SERVICE_SIGMA ** 2) / 2.0   # lognormal with mean 1.0
    return [r.lognormvariate(mu, SERVICE_SIGMA) for _ in range(n)]


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[int(round(q * (len(s) - 1)))]


def run_queue(cases: list[dict], service_hours: list[float],
              priority: list[int] | None = None, reps: int = REPLICATIONS,
              n_reviewers: int | None = None) -> dict:
    """Replicate the queue and summarize waits (business days) by REFERENCE tier."""
    if n_reviewers is None:
        n_reviewers = N_REVIEWERS
    arrivals = [float(c["arrival_day"]) for c in cases]
    hi_idx = [i for i, c in enumerate(cases) if c["reference_tier"] in HI_TIERS]
    lo_idx = [i for i, c in enumerate(cases) if c["reference_tier"] not in HI_TIERS]
    per_case_sum = [0.0] * len(cases)
    hi_means, lo_means, all_means = [], [], []
    for rep in range(reps):
        noise = _noise(len(cases), rep)
        service_days = [service_hours[i] * noise[i] / HOURS_PER_REVIEWER_PER_DAY
                        for i in range(len(cases))]
        start = simulate(arrivals, service_days, priority, n_reviewers)
        waits = [start[i] - arrivals[i] for i in range(len(cases))]
        for i, w in enumerate(waits):
            per_case_sum[i] += w
        hi_means.append(mean(waits[i] for i in hi_idx))
        lo_means.append(mean(waits[i] for i in lo_idx))
        all_means.append(mean(waits))
    window_days = max(a for a in arrivals) - min(a for a in arrivals) + 1
    capacity_h = n_reviewers * HOURS_PER_REVIEWER_PER_DAY * window_days
    return {
        "wait_hi_mean": mean(hi_means),
        "wait_hi_p5": _pct(hi_means, 0.05),
        "wait_hi_p95": _pct(hi_means, 0.95),
        "wait_lo_mean": mean(lo_means),
        "wait_all_mean": mean(all_means),
        "per_case_mean_wait": [s / reps for s in per_case_sum],
        "total_hours": sum(service_hours),
        "offered_load": sum(service_hours) / capacity_h,
        "n_hi": len(hi_idx),
        "n_lo": len(lo_idx),
    }


# ---------------------------------------------------------------------------
# The step
# ---------------------------------------------------------------------------
def run() -> dict:
    cases = load_cases()
    hours = [UNIFORM_REVIEW_H] * len(cases)
    q = run_queue(cases, hours, priority=None)
    # What the uniform review gives each reference tier, against what the tier needs.
    by_tier = []
    for t in (1, 2, 3, 4):
        n_t = sum(1 for c in cases if c["reference_tier"] == t)
        by_tier.append({"tier": t, "cases": n_t, "given_h": UNIFORM_REVIEW_H,
                        "tier_depth_h": TIER_REVIEW_H[t]})
    return {
        "n_cases": len(cases),
        "n_hi": q["n_hi"],
        "wait_hi_mean": q["wait_hi_mean"],
        "wait_hi_p5": q["wait_hi_p5"],
        "wait_hi_p95": q["wait_hi_p95"],
        "wait_lo_mean": q["wait_lo_mean"],
        "total_hours": q["total_hours"],
        "offered_load": q["offered_load"],
        "by_tier": by_tier,
        "per_case_mean_wait": q["per_case_mean_wait"],
        "case_ids": [c["use_case_id"] for c in cases],
        "assumptions": assumptions_text(),
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    print("\n" + "=" * 80)
    print("Step 1 - Before: one spreadsheet, same review for every case, first in first out")
    print("=" * 80)
    print("\nASSUMPTIONS (yellow, modeled - the queue numbers below depend on every line):")
    res = run()
    for line in res["assumptions"]:
        print("  - " + line)

    print("\nWHAT THE SPREADSHEET KNOWS")
    print("  Rows in the sheet:                       %d" % res["n_cases"])
    print("  Tier recorded per row:                   whatever the sponsor typed (no check)")
    print("  Evidence owed per row:                   not recorded")
    print("  Duplicate flag per row:                  none")

    print("\nRESULT (yellow, modeled; reference tier is used only to label who is high risk)")
    print("  Truly high-risk cases (reference tier 3-4):  %d of %d" % (res["n_hi"], res["n_cases"]))
    print("  Tier 3-4 mean queue wait, FIFO:              %.1f business days  (5th-95th pct of %d replications: %.1f to %.1f)"
          % (res["wait_hi_mean"], REPLICATIONS, res["wait_hi_p5"], res["wait_hi_p95"]))
    print("  Tier 1-2 mean queue wait, FIFO:              %.1f business days" % res["wait_lo_mean"])
    print("  Total reviewer hours:                        %.1f  (%d cases x %.1fh)"
          % (res["total_hours"], res["n_cases"], UNIFORM_REVIEW_H))
    print("  Offered load on the reviewers:               %.0f%%" % (100 * res["offered_load"]))

    print("\n  Review depth given vs what the reference tier needs (hours, modeled):")
    print("    tier  cases  given  needs")
    for r in res["by_tier"]:
        print("    T%d    %3d    %4.1f   %4.1f" % (r["tier"], r["cases"], r["given_h"], r["tier_depth_h"]))
    avg = sum(TIER_REVIEW_H[r["tier"]] * r["cases"] for r in res["by_tier"]) / res["n_cases"]
    print("\n  The tier-depth times average %.1fh per case at this reference-tier mix; the standard review is set near that." % avg)
    print("  Tier 3-4 cases get %.1fh of review where the tier calls for %.1f-%.1fh; tier 1 cases get %.1fh where %.1fh is enough."
          % (UNIFORM_REVIEW_H, TIER_REVIEW_H[3], TIER_REVIEW_H[4], UNIFORM_REVIEW_H, TIER_REVIEW_H[1]))

    cases = load_cases()
    print("\n  Sensitivity to the standard review time (the one assumption Step 1 hangs on):")
    print("    hours per case  total hours  offered load  tier 3-4 mean wait (days)")
    for h in (4.0, 6.0, 8.0):
        qs = run_queue(cases, [h] * len(cases), priority=None)
        print("    %14.1f  %11.1f  %11.0f%%  %24.1f" % (h, qs["total_hours"], 100 * qs["offered_load"], qs["wait_hi_mean"]))
    with open(OUT_DIR / "step_01_cases.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["use_case_id", "arrival_day", "reference_tier", "mean_wait_days_fifo"])
        for c, wv in zip(cases, res["per_case_mean_wait"]):
            w.writerow([c["use_case_id"], c["arrival_day"], c["reference_tier"], round(wv, 2)])
    summary = {k: v for k, v in res.items() if k not in ("per_case_mean_wait", "case_ids")}
    summary["per_case_mean_wait"] = {cid: round(w, 3) for cid, w in zip(res["case_ids"], res["per_case_mean_wait"])}
    with open(OUT_DIR / "step_01_results.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nWrote src/out/step_01_results.json and src/out/step_01_cases.csv")


if __name__ == "__main__":
    main()
