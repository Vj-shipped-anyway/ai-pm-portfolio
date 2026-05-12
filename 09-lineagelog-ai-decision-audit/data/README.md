# Sample Data — LineageLog walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`random.seed(20260512)`), and reproducible. No customer data. No PII. Shapes are calibrated to what a Tier-1 retail bank's regulated-decision substrate actually looks like across loan approval, claims triage, KYC review, and fraud screening.

The headline decision the walkthrough resolves is `DEC_0150_20260312` — a `loan_pd_v3` denial of customer `CUST_851897` on March 12, 2026. The OCC opens an exam on May 8 asking for the full lineage. Today: 14 days. With LineageLog: 12 minutes.

---

## `decisions.csv` — 200 synthetic AI decisions

The decision-grain spine. Every regulated AI decision the bank produced in the 60-day window starting March 1, 2026, across four deployed models.

| Column | Type | What it is |
| --- | --- | --- |
| `decision_id` | string | Format `DEC_NNNN_YYYYMMDD`. Stable join key across the four CSVs. |
| `customer_id` | string | Format `CUST_NNNNNN`. Hashed customer identifier — never raw PII in production. |
| `model_id` | string | Foreign key to `models.csv`. One of: `loan_pd_v3`, `claims_triage_v2`, `kyc_review_v4`, `fraud_screen_v6`. |
| `decision_type` | string | `loan_approval`, `claims_triage`, `kyc_review`, `fraud_screen`. |
| `timestamp` | ISO-8601 | The moment of decision. UTC. |
| `outcome` | string | Model's decision — `APPROVE` / `DENY` / `CONDITIONAL` for credit; `AUTO_PAY` / `ADJUSTER_REVIEW` / `SIU_FLAG` for claims; etc. |
| `decision_value` | float | The dollar amount or risk score the decision was about. |

200 rows. Reproducible from `step_04_with_lineagelog.py` if regenerated with the same seed.

## `models.csv` — 4 deployed models

Model metadata that pins the snapshot per decision. Without this row, deficiency #3 (no model-snapshot pin) is unresolvable.

| Column | Type | What it is |
| --- | --- | --- |
| `model_id` | string | Primary key. |
| `name` | string | Human-readable model name. |
| `family` | string | `credit`, `genai`, `kyc`, `fraud`. |
| `vendor` | string | `internal`, `anthropic`, `azure_openai`. |
| `snapshot_id` | string | The exact vendor pin in effect when the model scored the decision. The single field most regulated-AI logs lose first. |
| `training_date` | date | When the snapshot was trained / cut. |
| `tier` | int | Bank's three-tier risk classification. Tier 1 = consumer impact. |
| `owner_team` | string | The line-1 team responsible. Routes regulator questions. |

4 rows.

## `retrieval_sets.csv` — 599 retrieval-set captures

Which exact documents the model was shown when it made each decision. RAG without this trail is a black box at exam time.

| Column | Type | What it is |
| --- | --- | --- |
| `decision_id` | string | Foreign key to `decisions.csv`. |
| `doc_id` | string | The retrieved document — policy version, rate card, OFAC list, etc. |
| `doc_version` | string | Pinned version (`v2.3`, `v2026.03.08`). Without this, you can't answer "which version of the policy was applied." |
| `retrieved_at` | ISO-8601 | The retrieval moment. Always within 1 second of decision timestamp. |

Each decision has 2-4 retrieved documents. 599 rows total.

## `outcomes.csv` — 200 downstream outcomes

The outcome backlink — what happened AFTER the decision. Today this is stored in a separate system (claims platform, CFPB complaint database, loss-event log) and almost never linked back. LineageLog's last deficiency is severing this gap.

| Column | Type | What it is |
| --- | --- | --- |
| `decision_id` | string | Foreign key. |
| `outcome_type` | string | `repaid_on_time`, `charge_off_30d`, `customer_complaint_cfpb`, `sar_filed_later`, `fraud_prevented`, `legitimate_blocked`, etc. |
| `outcome_value` | string | `closed_clean`, `case_filed`, a dollar loss amount, or blank if no outcome observed. |
| `outcome_date` | date | When the outcome materialized (2-75 days post-decision). |

200 rows. One outcome per decision.

---

## Headline lineage walk — `DEC_0150_20260312`

This is the decision the OCC asks about. Walk the four CSVs and you get the full lineage in one record:

| Source | What it gives you |
| --- | --- |
| `decisions.csv` | `loan_pd_v3` denied `CUST_851897` a `$65,673.12` loan on `2026-03-12T18:41:32Z`. |
| `models.csv` | The model was `internal-xgb-3.2.1`, trained `2025-08-12`, owned by `line1.credit-risk`. |
| `retrieval_sets.csv` | The model was shown `policy_credit_v2.3`, `rate_card_2026q1`, the disclosure pack, and the underwriting guide — all retrieved at decision time. |
| `outcomes.csv` | Downstream outcome filed within 75 days. |

In raw-log form: 6 vendors × 4 cloud accounts. In LineageLog: one record, indexed by `(customer_id, decision_id, timestamp)`, returned in under a second.
