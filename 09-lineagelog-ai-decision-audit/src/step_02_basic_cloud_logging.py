"""
Step 2 — Basic Cloud Logging only: request/response pairs without decision context.

Most banks call this "we have audit logging." A FastAPI / Cloud Run service
writes the request payload and the response payload to Cloud Logging. The
log line says: "loan_pd_v3 scored a $65,673.12 request and returned DENY at
2026-03-12T18:41:32Z."

That is necessary. It is nowhere near sufficient for a regulator.

This script reads the synthetic decision data and renders it the way Cloud
Logging would surface it. It then evaluates whether the six lineage
deficiencies are addressed. Spoiler: 0 of 6.

Run:
    python step_02_basic_cloud_logging.py

Output: prints a sample log entry for the headline decision and a per-field
audit, writes src/out/step_02_cloud_log_view.csv.
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

TARGET_DECISION_ID = "DEC_0150_20260312"

# The six deficiency classes. The product's intellectual property — do not change.
DEFICIENCY_CLASSES = [
    ("prompt_versioning",       "No prompt versioning",       "Which exact prompt was used. Was system instruction A or B."),
    ("retrieval_set_capture",   "No retrieval-set capture",   "Which documents the model was shown."),
    ("model_snapshot_pin",      "No model-snapshot pin",      "Which vendor model version answered. Was it Claude 3.5 or 3.7."),
    ("feature_at_decision_time","No feature-at-decision-time","What the customer's credit score / DTI was AT the moment of decision."),
    ("reviewer_attribution",    "No reviewer attribution",    "Who or what (human user, agent identity) authorized this action."),
    ("outcome_backlink",        "No outcome backlink",        "Whether the decision led to a complaint, charge-off, fraud loss."),
]


def basic_cloud_log_entry(decision_row: dict) -> dict:
    """The exact shape Cloud Logging gives you with default audit logging enabled.

    Request / response pairs. No business-grain composition. This is the SOTA
    most teams ship for the bank's GenAI / ML decision surfaces.
    """
    return {
        "timestamp": decision_row["timestamp"],
        "severity": "INFO",
        "resource": {
            "type": "cloud_run_revision",
            "labels": {
                "service_name": f"{decision_row['model_id']}-service",
                "location": "us-east1",
            }
        },
        "httpRequest": {
            "requestMethod": "POST",
            "requestUrl": f"/v1/score/{decision_row['decision_type']}",
            "status": 200,
            "latency": "0.482s",
        },
        "jsonPayload": {
            "request_body_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb924...",
            "response": {
                "outcome": decision_row["outcome"],
                "value": float(decision_row["decision_value"]),
            },
            "customer_id_hash": decision_row["customer_id"],
        },
        "labels": {
            "model_id": decision_row["model_id"],
        },
        "trace": "projects/bank-prod/traces/aXk49fJ2...",  # OTel trace ID, TTL 7-15 days
    }


def evaluate_deficiencies(log_entry: dict) -> list[dict]:
    """For each of the six deficiency classes, evaluate whether the log entry
    addresses it."""
    rows = []
    for key, label, definition in DEFICIENCY_CLASSES:
        # Cloud Logging alone addresses none of the six. We name each one explicitly.
        if key == "prompt_versioning":
            present = False
            evidence = "Log captures request hash, not the prompt template ID."
        elif key == "retrieval_set_capture":
            present = False
            evidence = "Retrieved docs live in the vector store with no decision-grain join key."
        elif key == "model_snapshot_pin":
            present = False
            evidence = "Service name appears; vendor snapshot ID is not bound to this log line."
        elif key == "feature_at_decision_time":
            present = False
            evidence = "Request body hash, not the feature values. Even if values were captured, no temporal pin to customer state at decision moment."
        elif key == "reviewer_attribution":
            present = False
            evidence = "No principal in jsonPayload. Cloud Audit Logs have it; not joined to this surface."
        else:  # outcome_backlink
            present = False
            evidence = "Outcomes land in loss-event lake / CFPB complaint system; no link back to this decision_id."

        rows.append({
            "deficiency_key": key,
            "deficiency_label": label,
            "definition": definition,
            "addressed_by_cloud_logging_alone": "yes" if present else "no",
            "evidence": evidence,
        })
    return rows


def main():
    print("\n" + "=" * 80)
    print("Step 2 — Basic Cloud Logging: request/response pairs, no decision context")
    print("=" * 80)
    print()

    decisions = list(csv.DictReader(open(DATA_DIR / "decisions.csv")))
    target = next((d for d in decisions if d["decision_id"] == TARGET_DECISION_ID), None)
    if target is None:
        raise SystemExit(f"Could not find {TARGET_DECISION_ID} in decisions.csv")

    print(f"Headline decision: {TARGET_DECISION_ID}")
    print()
    print("What Cloud Logging gives you (one log line per request/response):")
    print()
    entry = basic_cloud_log_entry(target)
    print(json.dumps(entry, indent=2))
    print()

    # Aggregate stats over the full 200-decision file
    by_model = {}
    for d in decisions:
        by_model[d["model_id"]] = by_model.get(d["model_id"], 0) + 1
    print("=" * 80)
    print("Coverage — what Cloud Logging captures across the 200-decision file")
    print("=" * 80)
    print(f"  Total decisions in 60-day window:    {len(decisions)}")
    for mid, n in sorted(by_model.items()):
        print(f"  {mid:<22} {n:>4} decisions logged")
    print()
    print("  Every decision has ONE log line. The schema is identical across")
    print("  models. Cloud Logging is the easy part. The hard part is the six")
    print("  fields it doesn't carry.")
    print()

    print("=" * 80)
    print("Six-deficiency evaluation — does Cloud Logging alone resolve them?")
    print("=" * 80)
    deficiency_rows = evaluate_deficiencies(entry)
    caught = sum(1 for r in deficiency_rows if r["addressed_by_cloud_logging_alone"] == "yes")
    print(f"  Deficiencies addressed by Cloud Logging alone: {caught} of 6")
    print()
    print(f"  {'Deficiency':<32} {'Addressed?':<12} {'Why'}")
    for r in deficiency_rows:
        why = r["evidence"][:42] + ("..." if len(r["evidence"]) > 42 else "")
        print(f"  {r['deficiency_label']:<32} {r['addressed_by_cloud_logging_alone']:<12} {why}")
    print()
    print("  Cloud Logging is the FOUNDATION. It is not the lineage product.")
    print("  Step 3 names each of the six deficiencies with a real-feeling")
    print("  exam-question example. Step 4 closes all six with the composition layer.")

    out_csv = OUT_DIR / "step_02_cloud_log_view.csv"
    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(deficiency_rows[0].keys()))
        w.writeheader()
        for r in deficiency_rows:
            w.writerow(r)

    # Also write the sample log entry as JSON so the README can link to it
    out_json = OUT_DIR / "step_02_sample_log_entry.json"
    with open(out_json, "w") as f:
        json.dump(entry, f, indent=2)

    print()
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
