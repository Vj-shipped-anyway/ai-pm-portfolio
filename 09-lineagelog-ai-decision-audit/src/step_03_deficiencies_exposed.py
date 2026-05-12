"""
Step 3 — Six deficiencies, each illustrated on the headline decision.

This script takes the headline decision (DEC_0150_20260312 — the loan denial
on March 12, 2026 the OCC will ask about on May 8) and walks the six named
deficiencies one by one. For each, it surfaces the exam-style question a
regulator actually asks, and shows what raw logs return today.

The point: each question has a real, dollar-and-finding consequence. The
fragments exist. The composition does not.

Run:
    python step_03_deficiencies_exposed.py

Output: prints the six exam questions and the gap each one exposes; writes
src/out/step_03_deficiency_examples.csv.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_DECISION_ID = "DEC_0150_20260312"

# Real-feeling exam queries and the gap each one exposes.
DEFICIENCIES = [
    {
        "n": 1,
        "key": "prompt_versioning",
        "label": "No prompt versioning",
        "exam_question": (
            "Which exact system instruction was used for this loan denial? "
            "Was it version A (released Feb 8) or version B (released Mar 5)?"
        ),
        "what_logs_return": (
            "Cloud Logging stores a SHA-256 of the request body. The system instruction "
            "is loaded server-side from a template file — neither the file path nor the "
            "template version ID is bound to the request. The platform team can guess "
            "from deployment timestamps; they cannot prove."
        ),
        "consequence": (
            "OCC writes 'inability to evidence the decision-time prompt' as a finding. "
            "Bank cannot demonstrate the decision applied the post-Mar-5 fair-lending "
            "language. Becomes a Matter Requiring Attention (MRA)."
        ),
    },
    {
        "n": 2,
        "key": "retrieval_set_capture",
        "label": "No retrieval-set capture",
        "exam_question": (
            "Which documents was the model shown when it scored this decision? "
            "Was the disclosure pack the version with the corrected APR table, or "
            "the pre-correction draft?"
        ),
        "what_logs_return": (
            "The vector store retains the documents. The retrieval call retains its "
            "own trace ID. There is no decision_id-to-doc_id join key in either system. "
            "Reconstructing the retrieval set 8 weeks later is a manual reverse-search "
            "by timestamp + customer_id_hash — and 7% of cases hit ambiguity."
        ),
        "consequence": (
            "The disclosure-pack version determines whether the bank gave the "
            "customer the correct APR table. Cannot prove version → potential "
            "TILA / Reg Z violation. Modeled exposure: $40K/case civil penalty plus "
            "remediation cost."
        ),
    },
    {
        "n": 3,
        "key": "model_snapshot_pin",
        "label": "No model-snapshot pin",
        "exam_question": (
            "Which exact vendor model version produced this output? "
            "If the answer is 'claude-sonnet-4-20251101' — can you prove it wasn't "
            "the silently rolled minor update from Feb 24?"
        ),
        "what_logs_return": (
            "The model registry shows the deployment window. It does NOT show the "
            "vendor's post-roll behavioral change. The bank's logs say one thing; "
            "the vendor's behavior may have changed without a registry write. "
            "(See: Anthropic Feb 24, 2026 silent minor update — public reference incident.)"
        ),
        "consequence": (
            "OCC asks 'is your model under change control.' Today the answer is 'mostly.' "
            "The vendor-snapshot-pin gap interlocks with [DriftSentinel] v0.5 vendor-pin "
            "detector. Cost of missing this: a redo of the model risk attestation under "
            "SR 11-7 + a horizontal review."
        ),
    },
    {
        "n": 4,
        "key": "feature_at_decision_time",
        "label": "No feature-at-decision-time",
        "exam_question": (
            "What was this customer's FICO and DTI AT the moment of decision on March 12? "
            "Customer's profile has been updated since."
        ),
        "what_logs_return": (
            "The feature store returns the CURRENT values, not the March 12 values. "
            "Reconstructing requires replaying the source-of-truth transaction history "
            "to March 12. The data warehouse has it; the temporal rebuild takes 6-12 hours "
            "per customer per decision and 11% of cases hit data-quality gaps."
        ),
        "consequence": (
            "Without feature-at-decision-time, the bank cannot defend the model's "
            "decision logic. Fair-lending counter-evidence vanishes. The customer's "
            "lawyer in a class-action gets to claim the model used unfavorable "
            "post-March-12 data. The bank settles."
        ),
    },
    {
        "n": 5,
        "key": "reviewer_attribution",
        "label": "No reviewer attribution",
        "exam_question": (
            "Who or what authorized this action? Was it a human underwriter (with "
            "delegated authority) or did the agent act autonomously on its own "
            "agent-identity credentials?"
        ),
        "what_logs_return": (
            "Agent Identity Logs show that workload identity `loan-decisioning-sa@bank.iam` "
            "acquired credentials and called the model. They do NOT distinguish "
            "user-delegated tokens (where a human authorized the action) from "
            "autonomous-agent action. Without this distinction, the bank cannot "
            "answer the question of human accountability."
        ),
        "consequence": (
            "EU AI Act Article 14 requires human oversight on high-risk AI systems. "
            "OCC's expectation under SR 11-7 is documented effective challenge by line 2. "
            "If we cannot prove a human authorized the action, we cannot demonstrate "
            "either. The model gets removed from production until the audit trail is "
            "rebuilt. Modeled outage: 14 days, 50,000 declined applications backlogged."
        ),
    },
    {
        "n": 6,
        "key": "outcome_backlink",
        "label": "No outcome backlink",
        "exam_question": (
            "Did this decision result in a customer complaint, a charge-off, or a "
            "CFPB filing? Show us the link from this decision to the downstream outcome."
        ),
        "what_logs_return": (
            "Outcomes live in three separate systems: the loss-event lake, the "
            "CFPB complaint system, and the claims platform. None of them carries "
            "the decision_id. Reconstructing the link is a manual lookup by "
            "customer_id_hash + a date window. 18% of cases have ambiguous matches "
            "(customer has multiple complaints, multiple decisions); a human has to disambiguate."
        ),
        "consequence": (
            "The single most important loop for the bank's own learning is severed. "
            "Bad outcomes don't backflow to model retraining. Good outcomes don't "
            "backflow to validation evidence. Internal Audit (line 3) writes this up "
            "every cycle and it never gets fixed because no single team owns it."
        ),
    },
]


def main():
    decisions = list(csv.DictReader(open(DATA_DIR / "decisions.csv")))
    target = next((d for d in decisions if d["decision_id"] == TARGET_DECISION_ID), None)
    if target is None:
        raise SystemExit(f"Could not find {TARGET_DECISION_ID} in decisions.csv")

    print("\n" + "=" * 80)
    print("Step 3 — Six named deficiencies on the headline decision")
    print("=" * 80)
    print()
    print(f"Decision:    {target['decision_id']}")
    print(f"Customer:    {target['customer_id']} (hashed)")
    print(f"Model:       {target['model_id']}")
    print(f"Timestamp:   {target['timestamp']}")
    print(f"Outcome:     {target['outcome']}  (${float(target['decision_value']):,.2f} loan)")
    print()
    print("The OCC examiner picks ONE decision and asks six questions. Walk through")
    print("each. The fragments exist; the composition does not.")
    print()

    for d in DEFICIENCIES:
        print("-" * 80)
        print(f"  Deficiency #{d['n']}: {d['label']}")
        print("-" * 80)
        print(f"  EXAM QUESTION")
        print(f"    {d['exam_question']}")
        print()
        print(f"  WHAT RAW LOGS RETURN TODAY")
        print(f"    {d['what_logs_return']}")
        print()
        print(f"  CONSEQUENCE")
        print(f"    {d['consequence']}")
        print()

    # Write the CSV
    out_csv = OUT_DIR / "step_03_deficiency_examples.csv"
    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(
            out,
            fieldnames=["n", "key", "label", "exam_question", "what_logs_return", "consequence"],
        )
        w.writeheader()
        for d in DEFICIENCIES:
            w.writerow(d)

    print("=" * 80)
    print("Summary — six fields, six gaps, six exam questions the bank cannot answer")
    print("=" * 80)
    print(f"  Total deficiencies named:       {len(DEFICIENCIES)}")
    print(f"  Closed by Cloud Logging alone:  0")
    print(f"  Closed in Step 4 (LineageLog):  6")
    print()
    print("  Each deficiency is a specific, named taxonomy class — not a vague")
    print("  'we need better logging' wish. Step 4 closes all six by composing")
    print("  the four log sources into one immutable decision-grain record,")
    print("  indexed by (customer_id, decision_id, timestamp).")
    print()
    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
