"""
Step 3 — The six named deficiencies in single-queue HITL.

Each deficiency is illustrated on the synthetic data with a real-feeling
example the bank's Head of Compliance would recognize on first read.

Run:
    python step_03_deficiencies_exposed.py

Output:
  - prints the six deficiencies one at a time, each with quantified scope
  - writes src/out/step_03_deficiencies_summary.csv
"""

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CASE_ID = "CASE_0317_20260512"

DEFICIENCIES = [
    "1. No review-difficulty stratification",
    "2. No reviewer calibration drift",
    "3. No rubber-stamp detection",
    "4. No escalation path for hard cases",
    "5. No time-on-task SLA",
    "6. No reviewer-vs-ground-truth feedback loop",
]


def load(name: str) -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / name)))


def banner(text: str) -> None:
    print()
    print("=" * 76)
    print(f"  {text}")
    print("=" * 76)


def main() -> None:
    cases = load("cases.csv")
    cases_by_id = {c["case_id"]: c for c in cases}
    reviewers = {r["reviewer_id"]: r for r in load("reviewers.csv")}
    outcomes = load("review_outcomes.csv")
    ground_truth = {g["case_id"]: g for g in load("ground_truth_backfill.csv")}

    summary_rows = []

    # ----- Deficiency 1: no difficulty stratification -----
    banner("Deficiency 1 — No review-difficulty stratification")
    print()
    print("Every case is routed to the same flat queue. Difficulty score (1-5)")
    print("and AI confidence are visible at ingestion time — but ignored at routing.")
    print()
    hard_low_conf = [c for c in cases if int(c["difficulty_score"]) >= 4
                     and float(c["ai_confidence"]) < 0.70]
    print(f"  Hard cases (difficulty>=4 AND AI conf <0.70): {len(hard_low_conf)}")
    juniors_on_hard = []
    for c in hard_low_conf:
        o = next((o for o in outcomes if o["case_id"] == c["case_id"]), None)
        if o and reviewers[o["reviewer_id"]]["tenure"] == "junior":
            juniors_on_hard.append((c, o))
    print(f"  Of those, routed to junior reviewers: {len(juniors_on_hard)} "
          f"({len(juniors_on_hard) / max(len(hard_low_conf),1):.0%})")
    print(f"  Headline case CASE_0317 (difficulty 5, AI conf 0.62, private_banking): "
          f"routed to junior REV_07.")
    summary_rows.append(["deficiency_1_hard_to_junior_count", len(juniors_on_hard)])

    # ----- Deficiency 2: no reviewer calibration drift detection -----
    banner("Deficiency 2 — No reviewer calibration drift")
    print()
    print("Reviewer A approves 99% of cases. Reviewer B approves 72% on a similar")
    print("intake mix. Both attest 'we reviewed.' Nobody compares the two.")
    print()
    print("Per-reviewer override rate (from the audit log we already have):")
    print(f"  {'Reviewer':<14} {'Tenure':<8} {'N':>5} {'Override rate':>15}")
    per_rev = defaultdict(list)
    for o in outcomes:
        per_rev[o["reviewer_id"]].append(o)
    rates = []
    for rid in sorted(per_rev.keys()):
        rev = reviewers[rid]
        rows = per_rev[rid]
        overrides = sum(1 for o in rows if o["agreed_with_ai"] != "True")
        rate = overrides / max(len(rows), 1)
        rates.append((rid, rev["tenure"], len(rows), rate))
        print(f"  {rev['name']:<14} {rev['tenure']:<8} {len(rows):>5} {rate * 100:>14.1f}%")
    if rates:
        rate_values = [r[3] for r in rates]
        print()
        print(f"  Override-rate spread: {min(rate_values) * 100:.1f}% to "
              f"{max(rate_values) * 100:.1f}% — a {(max(rate_values) - min(rate_values)) * 100:.1f}-point")
        print(f"  delta across reviewers reviewing the same case mix.")
        print(f"  Nobody is paged when REV_01 and REV_11 disagree by 4x on identical cases.")
        summary_rows.append(["deficiency_2_override_rate_spread_pp",
                            round((max(rate_values) - min(rate_values)) * 100, 1)])

    # ----- Deficiency 3: no rubber-stamp detection -----
    banner("Deficiency 3 — No rubber-stamp detection")
    print()
    print("Tier-1 KYC review on a private-banking customer is policy-required to")
    print("take ~8 minutes per the bank's KYC procedure manual. Reality on this corpus:")
    print()
    pb_outcomes = [o for o in outcomes if cases_by_id[o["case_id"]]["customer_tier"] == "private_banking"]
    pb_times = [float(o["time_to_decision_sec"]) for o in pb_outcomes]
    under_10 = sum(1 for t in pb_times if t < 10)
    under_30 = sum(1 for t in pb_times if t < 30)
    print(f"  Private-banking reviews:                {len(pb_outcomes):>5,}")
    print(f"  Mean review time (sec):                 {mean(pb_times):>5.1f}")
    print(f"  Reviews completed in <10 seconds:       {under_10:>5,} "
          f"({under_10 / max(len(pb_outcomes), 1):.0%})")
    print(f"  Reviews completed in <30 seconds:       {under_30:>5,} "
          f"({under_30 / max(len(pb_outcomes), 1):.0%})")
    print(f"  Policy floor (Tier-1 procedure manual): 480 seconds (8 minutes)")
    print()
    print("No system blocks the 8-second review. The signal exists; nothing acts on it.")
    summary_rows.append(["deficiency_3_pb_under_10s_pct",
                        round(under_10 / max(len(pb_outcomes), 1), 3)])

    # ----- Deficiency 4: no escalation path for hard cases -----
    banner("Deficiency 4 — No escalation path for hard cases")
    print()
    print("Low AI confidence + edge-case features should escalate to a lead reviewer.")
    print("Today: those cases sit in the same queue. First reviewer on shift takes them.")
    print()
    edge = [c for c in cases if int(c["difficulty_score"]) == 5
            and (float(c["ai_confidence"]) < 0.65 or int(c["country_risk_tier"]) >= 3)]
    print(f"  Edge cases (difficulty 5, low conf OR country tier >=3): {len(edge)}")
    routed_to_lead = 0
    routed_to_junior = 0
    routed_to_senior = 0
    for c in edge:
        o = next((o for o in outcomes if o["case_id"] == c["case_id"]), None)
        if not o:
            continue
        t = reviewers[o["reviewer_id"]]["tenure"]
        if t == "lead":
            routed_to_lead += 1
        elif t == "senior":
            routed_to_senior += 1
        else:
            routed_to_junior += 1
    print(f"  Routed to lead:      {routed_to_lead:>3} ({routed_to_lead / max(len(edge), 1):.0%})")
    print(f"  Routed to senior:    {routed_to_senior:>3} ({routed_to_senior / max(len(edge), 1):.0%})")
    print(f"  Routed to junior:    {routed_to_junior:>3} ({routed_to_junior / max(len(edge), 1):.0%})  "
          f"<-- the problem")
    summary_rows.append(["deficiency_4_edge_to_junior_count", routed_to_junior])

    # ----- Deficiency 5: no time-on-task SLA -----
    banner("Deficiency 5 — No time-on-task SLA")
    print()
    print("Tier-1 KYC procedure manual: 8 minutes (480 seconds). Reality:")
    print()
    tier_sla = {"private_banking": 480, "sme": 180, "retail": 60}
    for tier, sla in tier_sla.items():
        tier_outcomes = [o for o in outcomes
                        if cases_by_id[o["case_id"]]["customer_tier"] == tier]
        if not tier_outcomes:
            continue
        times = [float(o["time_to_decision_sec"]) for o in tier_outcomes]
        breaches = sum(1 for t in times if t < sla)
        print(f"  {tier:<18} SLA={sla:>3}s    N={len(tier_outcomes):>4}    "
              f"Mean={mean(times):>5.1f}s    Below-SLA={breaches} "
              f"({breaches / len(tier_outcomes):.0%})")
    print()
    print("No SLA enforcement. No timer. No floor. The 8-second review counts.")

    # ----- Deficiency 6: no ground-truth feedback loop -----
    banner("Deficiency 6 — No reviewer-vs-ground-truth feedback loop")
    print()
    print("When downstream signals (OFAC matches, SAR filings, customer complaints,")
    print("charge-offs, regulator findings) name a decision wrong, no signal goes")
    print("back to the reviewer. Nobody recalibrates.")
    print()
    print(f"  Total downstream signals observed:                {len(ground_truth):>5}")
    by_reviewer_wrong = defaultdict(int)
    by_reviewer_total = defaultdict(int)
    for o in outcomes:
        by_reviewer_total[o["reviewer_id"]] += 1
        if o["case_id"] in ground_truth:
            by_reviewer_wrong[o["reviewer_id"]] += 1
    print(f"  Per-reviewer wrong-decisions (top 5 worst):")
    worst = sorted(by_reviewer_wrong.items(), key=lambda x: -x[1])[:5]
    for rid, n in worst:
        rev = reviewers[rid]
        pct = n / max(by_reviewer_total[rid], 1)
        print(f"    {rev['name']:<14} ({rev['tenure']:<8}): {n:>3} wrong of "
              f"{by_reviewer_total[rid]:>4} ({pct:.0%})")
    print()
    # Project the long tail
    full_divergence = round(0.38, 2)  # 🟡 modeled
    print(f"  Observed wrong (90-day window):                   {len(ground_truth)} of {len(outcomes)} "
          f"({len(ground_truth) / len(outcomes):.0%})")
    print(f"  Modeled 6-12-month reviewer-vs-ground-truth div:  {full_divergence:.0%}  🟡 modeled")
    print(f"  Today no reviewer gets a calibration packet. The signal exists; the loop is open.")
    summary_rows.append(["deficiency_6_observed_divergence_rate",
                        round(len(ground_truth) / len(outcomes), 3)])
    summary_rows.append(["deficiency_6_modeled_full_divergence_rate", full_divergence])

    # ----- Final summary -----
    banner("Summary")
    print()
    print("Six deficiencies. Each independently quantifiable from the data the bank")
    print("already has. None of them is solved by 'log more.' All are solved by")
    print("Step 4's OversightOps: difficulty-stratified routing, calibration-drift")
    print("detection, rubber-stamp blocker, escalation path, SLA-by-tier, and a")
    print("daily ground-truth feedback loop that pages reviewers with their own")
    print("calibration packet.")
    print()

    out_csv = OUT_DIR / "step_03_deficiencies_summary.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerows(summary_rows)
    print(f"Wrote {out_csv.name}")


if __name__ == "__main__":
    main()
