"""
Step 1 — Before lineage: the paralegal walks the six log sources by hand.

This is what happens today at a Tier-1 retail bank when the OCC opens an exam
and asks "show me the full AI decision lineage for customer CUST_851897 on
March 12, 2026."

The paralegal does NOT have a single record. The fragments are scattered
across six places:

  1. Cloud Logging (system interaction trail)         — Google Cloud / AWS CloudWatch / Azure Monitor
  2. Cloud Audit Logs (sensitive resource access)     — separate log surface
  3. Agent Identity Logs (who or what acted)          — Agent Identity Auth Manager
  4. OpenTelemetry traces (chain of thought)          — Cloud Trace / Datadog APM / Langfuse
  5. Model registry side-channel (snapshot pin)       — MLflow / SageMaker / Vertex
  6. Feature store / data warehouse (feature-at-time) — Snowflake / Databricks / BigQuery

Each lives in a different vendor's UI, with a different auth model, a
different query language, a different retention policy, and a different
on-call team. Collating one decision takes about 14 days of paralegal time.

This script does NOT do lineage composition. That is the whole point. It
prints the timesheet a real paralegal would produce, with the gaps named.

Run:
    python step_01_paralegal_audit.py

Output: prints the per-source walk, writes a CSV that itemizes which lineage
fields could be reconstructed from raw logs and which could not, to
src/out/step_01_paralegal_timesheet.csv.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)

# The headline OCC exam question. This is the decision the regulator picks.
TARGET_DECISION_ID = "DEC_0150_20260312"
TARGET_CUSTOMER = "CUST_851897"
TARGET_DATE = "2026-03-12"

# The six log sources a paralegal walks, with estimated per-source dwell time.
# Hours are modeled against industry baselines for OCC exam evidence collation
# at a $50B-asset retail bank: 14 days end-to-end, 8-9 hours/day, divided
# across the six sources roughly in proportion to query complexity.
SOURCES = [
    {
        "name": "Cloud Logging",
        "owner": "Cloud Platform team",
        "auth": "VPC-scoped service account, exam read role",
        "dwell_hours": 18,
        "what_it_has": "request payloads, response payloads, system interaction trail",
        "what_it_lacks": "no link to model snapshot; no retrieval-set capture; no reviewer attribution",
    },
    {
        "name": "Cloud Audit Logs",
        "owner": "InfoSec / Cloud Sec",
        "auth": "separate read role; audit-only project",
        "dwell_hours": 14,
        "what_it_has": "BigQuery / S3 access events, who-looked-at-what-data",
        "what_it_lacks": "does not correlate to a decision_id; timestamps must be reconciled manually",
    },
    {
        "name": "Agent Identity Logs",
        "owner": "IAM / Agent Identity Auth Manager",
        "auth": "Workload Identity Federation, principal trace",
        "dwell_hours": 11,
        "what_it_has": "cryptographic record of when an agent acquired credentials",
        "what_it_lacks": "no business context — the credential acquisition is logged, the BUSINESS decision is not",
    },
    {
        "name": "OpenTelemetry traces (ADK)",
        "owner": "Observability team (Datadog / Cloud Trace / Langfuse)",
        "auth": "APM read scope",
        "dwell_hours": 22,
        "what_it_has": "chain-of-thought waterfall for the agent's reasoning steps",
        "what_it_lacks": "trace TTL is typically 7-15 days — for a March 12 decision under May 8 exam, the trace is already aged out",
    },
    {
        "name": "Model registry side-channel",
        "owner": "ML Platform",
        "auth": "MLflow / SageMaker / Vertex registry read",
        "dwell_hours": 9,
        "what_it_has": "the model snapshot_id, deployment date, training metadata",
        "what_it_lacks": "no per-decision binding — only the deployment window; if a vendor silently rolled the snapshot, the registry may show the post-roll value",
    },
    {
        "name": "Feature store / data warehouse",
        "owner": "Data Platform",
        "auth": "Snowflake / Databricks / BigQuery read on a frozen exam dataset",
        "dwell_hours": 26,
        "what_it_has": "current customer profile, current feature values",
        "what_it_lacks": "feature-AT-DECISION-TIME is gone — customer profile has been updated since March 12; the moment-of-decision feature vector is not recoverable from current state",
    },
]

# The six deficiency classes — fields the paralegal tries to reconstruct.
DEFICIENCY_FIELDS = [
    ("prompt_version", "Which prompt / system instruction was used", "no", "Cloud Logging stores the request body but not the system-instruction template version. We can guess from deployment date; we cannot prove."),
    ("retrieval_set", "Which documents the model was shown", "no", "RAG pipeline didn't log retrieved doc IDs against the decision. Vector store has retention but no decision-grain key."),
    ("model_snapshot", "Which vendor model version answered", "partial", "Registry says claude-sonnet-4-20251101; that's the post-roll snapshot. Anthropic rolled silently on Feb 24. We do not know which snapshot scored March 12 with confidence."),
    ("feature_at_decision_time", "Customer feature values AT the moment of decision", "no", "Customer profile has been updated 4 times since March 12. Feature store does not maintain a per-decision snapshot. Reconstructing FICO and DTI on the decision day requires a separate temporal rebuild from raw transaction history."),
    ("reviewer_attribution", "Who or what authorized this decision", "partial", "Agent Identity Log shows the workload-identity principal. We do NOT know whether a human user delegated this action or whether the agent acted autonomously."),
    ("outcome_backlink", "Did this decision lead to a complaint / charge-off / fraud loss", "no", "Outcome data lives in the loss-event lake, the CFPB complaint system, and the claims platform. Three separate joins on three different keys. The customer has since filed a complaint; the link is not recoverable from the decision side."),
]


def main():
    print("\n" + "=" * 80)
    print("Step 1 — Before lineage: paralegal walks six log sources by hand")
    print("=" * 80)
    print()
    print(f"OCC exam question (May 8, 2026):")
    print(f"  'Show us the full AI decision lineage for {TARGET_CUSTOMER}")
    print(f"   on {TARGET_DATE}, decision {TARGET_DECISION_ID}.'")
    print()
    print("Paralegal pulls logs from six sources. Tallies dwell time per source.")
    print()

    total_hours = 0
    for src in SOURCES:
        print("-" * 80)
        print(f"  Source: {src['name']}")
        print(f"    Owner:           {src['owner']}")
        print(f"    Auth model:      {src['auth']}")
        print(f"    What it has:     {src['what_it_has']}")
        print(f"    What it lacks:   {src['what_it_lacks']}")
        print(f"    Dwell time:      {src['dwell_hours']} hours")
        total_hours += src['dwell_hours']

    print()
    print("=" * 80)
    print("Per-field reconstruction attempt")
    print("=" * 80)
    print(f"  {'Field':<28} {'Status':<10} {'Note'}")
    fields_lost = 0
    fields_partial = 0
    for field, label, status, note in DEFICIENCY_FIELDS:
        print(f"  {field:<28} {status:<10} {note[:60]}{'...' if len(note) > 60 else ''}")
        if status == "no":
            fields_lost += 1
        elif status == "partial":
            fields_partial += 1

    # Write the timesheet
    out_path = OUT_DIR / "step_01_paralegal_timesheet.csv"
    with open(out_path, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["source", "owner", "dwell_hours", "what_it_has", "what_it_lacks"])
        for src in SOURCES:
            w.writerow([src["name"], src["owner"], src["dwell_hours"], src["what_it_has"], src["what_it_lacks"]])

    out_fields = OUT_DIR / "step_01_field_reconstruction.csv"
    with open(out_fields, "w", newline="") as out:
        w = csv.writer(out)
        w.writerow(["lineage_field", "label", "reconstruction_status", "paralegal_note"])
        for row in DEFICIENCY_FIELDS:
            w.writerow(row)

    print()
    print("=" * 80)
    print("Summary — the paralegal-led baseline")
    print("=" * 80)
    print(f"  Total dwell time:                 {total_hours} hours (~{total_hours/8:.1f} working days)")
    print(f"  Modeled paralegal cost:           ${total_hours * 95:,} at $95/hr loaded")
    print(f"  Lineage fields fully recovered:   {6 - fields_lost - fields_partial} of 6")
    print(f"  Fields partially recoverable:     {fields_partial}")
    print(f"  Fields unrecoverable:             {fields_lost}")
    print()
    print("  The bank can produce a NARRATIVE for the OCC. It cannot produce")
    print("  the lineage. The exam goes to a finding, the finding goes to")
    print("  the consent order, the consent order goes to the budget for the")
    print("  next thing. This is the bleed Step 4 is here to fix.")
    print()
    print(f"Wrote: {out_path}")
    print(f"Wrote: {out_fields}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
