"""
Step 2 — Single queue + approval logging.

Most banks call this "we have HITL audit logging." Every reviewer decision
gets written to an immutable log with the case_id, reviewer_id, decision,
timestamp, and time_to_decision_sec.

This is the "letter of the law" satisfied. The MRM attestation reads:
"All Tier-1 KYC decisions undergo human review; all reviews are logged
to an immutable audit trail." The CRO signs the attestation. The OCC
nods on the exam.

But the data the log captures is not the data anyone queries. It accumulates.
Nobody asks: how many of those reviews took less than 10 seconds? Are
junior reviewers handling private-banking cases? When the AI was
low-confidence, did the reviewer slow down? Are reviewers A and B making
the same call on identical cases?

The information is on disk. The signal is invisible. The fix is not "log
more" — it is "compose the signal that already exists." That is what
Step 3 names and Step 4 builds.

Run:
    python step_02_with_logging.py

Output:
  - prints the audit-log shape and what queries it does NOT enable
  - writes src/out/step_02_audit_log_sample.csv (first 100 rows of the log)
"""

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_CASE_ID = "CASE_0317_20260512"


def load(name: str) -> list[dict]:
    return list(csv.DictReader(open(DATA_DIR / name)))


def main() -> None:
    cases = {c["case_id"]: c for c in load("cases.csv")}
    reviewers = {r["reviewer_id"]: r for r in load("reviewers.csv")}
    outcomes = load("review_outcomes.csv")

    print("=" * 76)
    print(" Step 2 — Single-queue HITL with approval logging")
    print("=" * 76)
    print()
    print("Schema we shipped:")
    print()
    sample_log = {
        "ts": outcomes[0]["review_completed_at"],
        "actor": {"reviewer_id": outcomes[0]["reviewer_id"], "service_account": "kyc-review-ui.iam"},
        "case_id": outcomes[0]["case_id"],
        "ai_decision": cases.get(outcomes[0]["case_id"], {}).get("ai_decision"),
        "ai_confidence": cases.get(outcomes[0]["case_id"], {}).get("ai_confidence"),
        "reviewer_decision": outcomes[0]["decision"],
        "agreed_with_ai": outcomes[0]["agreed_with_ai"],
        "time_to_decision_sec": outcomes[0]["time_to_decision_sec"],
        "audit_log_ref": f"projects/bank-prod/audit/kyc/{outcomes[0]['case_id']}",
    }
    print(json.dumps(sample_log, indent=2))
    print()

    # Show what this gets you and doesn't
    print("What this enables")
    print("-" * 76)
    print("  - Per-case reviewer attribution: yes")
    print("  - Timestamped audit trail: yes")
    print("  - Reviewer override rate fleet-wide: yes (aggregate)")
    print(f"     -> reviewer override rate across {len(outcomes)} cases: "
          f"{(1 - sum(1 for o in outcomes if o['agreed_with_ai'] == 'True') / len(outcomes)):.0%}")
    print("  - SR 11-7 ongoing-monitoring attestation row: yes")
    print()
    print("What this does NOT enable (the silent gaps)")
    print("-" * 76)
    questions = [
        "How many reviews completed in <10s on Tier-1 cases?",
        "Are reviewers A and B agreeing on identical cases?",
        "Did reviewer override rate drop after the last shift change?",
        "Which AI-confidence band is rubber-stamped most?",
        "Which reviewers should not be on private-banking cases?",
        "When the AI is wrong, do reviewers catch it?",
    ]
    for q in questions:
        print(f"  - {q}")
    print()
    print("Each question is answerable from the log we shipped. None is asked.")
    print("Nobody queries the audit log until the exam letter shows up.")
    print()

    # The headline case in the log
    headline = next((o for o in outcomes if o["case_id"] == TARGET_CASE_ID), None)
    if headline:
        case = cases[TARGET_CASE_ID]
        rev = reviewers[headline["reviewer_id"]]
        print(f"What the log captures on {TARGET_CASE_ID} (the headline case)")
        print("-" * 76)
        print(f"  Case (private_banking, country tier 4) reviewed by {rev['name']} "
              f"({rev['tenure']}) in {headline['time_to_decision_sec']}s — "
              f"decision {headline['decision']}.")
        print(f"  AI confidence was {case['ai_confidence']} (low). Difficulty score "
              f"{case['difficulty_score']} of 5 (hard).")
        print(f"  The log row is correct, immutable, and queryable. Nobody queried it.")
        print(f"  Time-to-OFAC-finding from this case: 27 days. Bank exposure: 🟡 modeled $420k.")
        print()

    # Aggregate: what the log shows by AI confidence band
    band_buckets = defaultdict(list)
    for o in outcomes:
        case = cases.get(o["case_id"], {})
        conf = float(case.get("ai_confidence", 0))
        if conf >= 0.90:
            band_buckets["AI conf >= 0.90 (high)"].append(o)
        elif conf >= 0.70:
            band_buckets["AI conf 0.70-0.90 (med)"].append(o)
        else:
            band_buckets["AI conf < 0.70 (low)"].append(o)

    print("What the audit log COULD be queried for (but isn't)")
    print("-" * 76)
    print(f"  {'AI confidence band':<32} {'N':>6} {'Mean review sec':>18} "
          f"{'% under 10s':>14}")
    for band in ("AI conf >= 0.90 (high)", "AI conf 0.70-0.90 (med)",
                 "AI conf < 0.70 (low)"):
        rows = band_buckets.get(band, [])
        if not rows:
            continue
        times = [float(o["time_to_decision_sec"]) for o in rows]
        under_10 = sum(1 for t in times if t < 10)
        print(f"  {band:<32} {len(rows):>6} {mean(times):>18.1f} "
              f"{under_10 / len(rows):>13.0%}")
    print()
    print("Notice: low-confidence AI cases are not slowing reviewers down.")
    print("The reviewer is not signal-aware. The log knows this. Nobody reads it.")
    print()

    # Write sample
    sample_path = OUT_DIR / "step_02_audit_log_sample.csv"
    with open(sample_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "case_id", "reviewer_id", "ai_confidence", "ai_decision",
                    "reviewer_decision", "agreed_with_ai", "time_to_decision_sec"])
        for o in outcomes[:100]:
            case = cases.get(o["case_id"], {})
            w.writerow([o["review_completed_at"], o["case_id"], o["reviewer_id"],
                        case.get("ai_confidence"), case.get("ai_decision"),
                        o["decision"], o["agreed_with_ai"], o["time_to_decision_sec"]])
    print(f"Wrote {sample_path.name} (first 100 rows of the audit log).")


if __name__ == "__main__":
    main()
