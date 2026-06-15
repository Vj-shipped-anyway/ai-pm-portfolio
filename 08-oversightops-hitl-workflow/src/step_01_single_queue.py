"""
Step 1 — Before OversightOps: the single-queue HITL.

Every case the AI flags for human review hits the same queue. Every reviewer
on shift draws the next case. No routing by case difficulty, customer tier,
country-risk tier, or AI confidence. No SLA. No time-on-task floor.

This is the shape of HITL most regulated AI workflows ship today: a "review"
column on the MRM attestation, satisfied by *the queue exists*, not by
*the queue produces real review*. The bank's regulator-facing posture is
that human oversight is in place. The reality on this script's output is
that ~94% of reviews complete in under 10 seconds and the reviewer-vs-AI
agreement rate is 94%+.

Run:
    python step_01_single_queue.py

Output:
  - prints the headline rubber-stamp stats across the 1,000-case corpus
  - writes src/out/step_01_single_queue_summary.csv
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CASE_ID = "CASE_0317_20260512"


def load(name: str) -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / name)))


def main() -> None:
    cases = load("cases.csv")
    reviewers = {r["reviewer_id"]: r for r in load("reviewers.csv")}
    outcomes = load("review_outcomes.csv")

    print("=" * 76)
    print(" Step 1 — Single-queue HITL: every case to the same queue")
    print("=" * 76)
    print()
    print(f"Corpus: {len(cases)} KYC review cases, {len(reviewers)} reviewers on shift.")
    print("Routing rule: round-robin by reviewer availability. No tiering.")
    print()

    # Headline rubber-stamp stats
    review_times = [float(o["time_to_decision_sec"]) for o in outcomes]
    under_10s = sum(1 for t in review_times if t < 10)
    agreed = sum(1 for o in outcomes if o["agreed_with_ai"] == "True")

    print("Headline single-queue stats")
    print("-" * 76)
    print(f"  Total reviews completed:                  {len(outcomes):>6,}")
    print(f"  Mean time-to-decision (sec):              {mean(review_times):>6.1f}")
    print(f"  Median time-to-decision (sec):            "
          f"{sorted(review_times)[len(review_times)//2]:>6.1f}")
    print(f"  Reviews completed in <10 seconds:         {under_10s:>6,}  "
          f"({under_10s/len(outcomes):.0%})")
    print(f"  Reviewer agreed with AI:                  {agreed:>6,}  "
          f"({agreed/len(outcomes):.0%})")
    print(f"  Reviewer override rate (fleet-wide):      {(1 - agreed/len(outcomes)):.0%}")
    print()

    # Breakdown by tenure
    by_tenure_times = defaultdict(list)
    by_tenure_overrides = defaultdict(list)
    for o in outcomes:
        rev = reviewers.get(o["reviewer_id"], {})
        ten = rev.get("tenure", "unknown")
        by_tenure_times[ten].append(float(o["time_to_decision_sec"]))
        by_tenure_overrides[ten].append(0 if o["agreed_with_ai"] == "True" else 1)

    print("Breakdown by reviewer tenure")
    print("-" * 76)
    print(f"  {'Tenure':<10} {'Reviews':>8} {'Mean sec':>10} {'Override %':>12}")
    for ten in ("junior", "senior", "lead"):
        times = by_tenure_times.get(ten, [])
        overrides = by_tenure_overrides.get(ten, [])
        if not times:
            continue
        print(f"  {ten:<10} {len(times):>8} {mean(times):>10.1f} "
              f"{mean(overrides) * 100:>11.1f}%")
    print()

    # Distribution by case tier vs reviewer tenure
    cases_by_id = {c["case_id"]: c for c in cases}
    mismatch_count = 0
    for o in outcomes:
        case = cases_by_id.get(o["case_id"], {})
        rev = reviewers.get(o["reviewer_id"], {})
        if case.get("customer_tier") == "private_banking" and rev.get("tenure") == "junior":
            mismatch_count += 1

    print("Tier-1 case routing mistakes (single-queue)")
    print("-" * 76)
    print(f"  Private-banking cases routed to a junior reviewer:  {mismatch_count}")
    print(f"  Of those, completed in <10 seconds:                 "
          f"{sum(1 for o in outcomes if float(o['time_to_decision_sec']) < 10 and reviewers.get(o['reviewer_id'], {}).get('tenure') == 'junior' and cases_by_id.get(o['case_id'], {}).get('customer_tier') == 'private_banking')}")
    print()

    # Headline case
    headline_case = cases_by_id.get(TARGET_CASE_ID, {})
    headline_outcome = next((o for o in outcomes if o["case_id"] == TARGET_CASE_ID), {})
    headline_reviewer = reviewers.get(headline_outcome.get("reviewer_id", ""), {})
    print(f"The headline case — {TARGET_CASE_ID}")
    print("-" * 76)
    print(f"  Customer tier:           {headline_case.get('customer_tier')}")
    print(f"  Country risk tier:       {headline_case.get('country_risk_tier')}")
    print(f"  AI confidence:           {headline_case.get('ai_confidence')}")
    print(f"  AI decision:             {headline_case.get('ai_decision')}")
    print(f"  Difficulty score:        {headline_case.get('difficulty_score')} (of 5)")
    print(f"  Routed to:               {headline_reviewer.get('name')} "
          f"({headline_reviewer.get('tenure')}, {headline_reviewer.get('training_level')})")
    print(f"  Reviewer decision:       {headline_outcome.get('decision')}")
    print(f"  Time to decision:        {headline_outcome.get('time_to_decision_sec')}s")
    print(f"  -> {'RUBBER-STAMPED' if float(headline_outcome.get('time_to_decision_sec', 0)) < 10 else 'REVIEWED'}")
    print()
    print("The single-queue HITL satisfies the regulator's letter-of-the-law line.")
    print("It does not produce review. Step 2 adds approval logging but still misses.")
    print()

    summary = OUT_DIR / "step_01_single_queue_summary.csv"
    with open(summary, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["total_reviews", len(outcomes)])
        w.writerow(["mean_time_sec", round(mean(review_times), 2)])
        w.writerow(["pct_under_10s", round(under_10s / len(outcomes), 3)])
        w.writerow(["agreement_rate", round(agreed / len(outcomes), 3)])
        w.writerow(["private_banking_to_junior_count", mismatch_count])
    print(f"Wrote {summary.relative_to(Path.cwd()) if summary.is_relative_to(Path.cwd()) else summary}")


if __name__ == "__main__":
    main()
