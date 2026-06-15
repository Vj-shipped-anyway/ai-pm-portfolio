# Sample Data — OversightOps walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`random.seed(20260615)`), and reproducible. No customer data. No PII. Shapes are calibrated to what a Tier-1 retail bank's KYC HITL substrate actually looks like — confidence-scored AI decisions routed to a flat reviewer queue, where ~94% of reviews complete in under 10 seconds and the bank can't tell which approvals are real.

The headline case the walkthrough resolves is `CASE_0317_20260512` — a `private_banking` KYC application from a country-tier-4 jurisdiction that the AI approved with 0.62 confidence and a junior reviewer rubber-stamped in 8 seconds. The ground-truth backfill on June 8 surfaces an OFAC sanctions-list match that should have been blocked. Today: this case ships and the bank books a 🟡 modeled $420k regulatory-finding exposure. With OversightOps: this case is auto-blocked from the junior queue, routed to a lead reviewer with a 6-minute SLA, and rejected before it ships.

---

## `cases.csv` — 1,000 synthetic KYC review cases

The case-grain spine. Every KYC decision the AI flagged for human review in the 90-day window starting March 1, 2026.

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | Format `CASE_NNNN_YYYYMMDD`. Stable join key across the four CSVs. |
| `customer_id` | string | Format `CUST_NNNNNN`. Hashed customer identifier — never raw PII in production. |
| `ingested_at` | ISO-8601 | The moment the AI flagged the case into the review queue. UTC. |
| `ai_confidence` | float | The AI's calibrated confidence in its decision. 0.40 - 0.99. Bimodal distribution. |
| `ai_decision` | string | `APPROVE` / `EDD_REQUIRED` / `REJECT`. |
| `difficulty_score` | int | 1 (easy / well-precedented) - 5 (hardest / edge case). Inverse-correlates with AI confidence. |
| `customer_tier` | string | `retail` / `sme` / `private_banking`. Private-banking cases warrant Tier-1 review SLA. |
| `country_risk_tier` | int | 1 (low) - 4 (high — sanctions-adjacent). |
| `true_outcome` | string | Backfilled from downstream signals when known. Blank if not yet observed. |
| `case_value_usd` | float | The dollar value of the underlying transaction or relationship. |

1,000 rows. Reproducible from the generator embedded in `step_04_with_oversightops.py` if regenerated with the same seed.

## `reviewers.csv` — 12 synthetic KYC reviewers

The reviewer roster. Three tenure tiers (`junior` / `senior` / `lead`) with calibrated decision-time and override-rate priors. Reality: junior reviewers are 10x faster than leads — because they're not actually reviewing.

| Column | Type | What it is |
| --- | --- | --- |
| `reviewer_id` | string | Format `REV_NN`. |
| `name` | string | Display name for the UI. |
| `tenure` | string | `junior` / `senior` / `lead`. |
| `training_level` | string | `basic_kyc` / `kyc_plus_sanctions` / `kyc_full_aml`. |
| `average_decision_time_sec` | float | Mean review time. Juniors ~8-14s, seniors ~30-40s, leads ~95-115s. |
| `override_rate` | float | Fraction of cases the reviewer overrides the AI on. Juniors ~4%, leads ~18%. |
| `tier_authorization` | int | Highest case tier this reviewer is authorized for. 1 = Tier-1 (private banking, sanctions-adjacent); 3 = Tier-3 (retail only). |

12 rows.

## `review_outcomes.csv` — 1,000 actual review decisions

One row per case. The reviewer's decision, the time they took, whether they agreed with the AI.

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | Foreign key to `cases.csv`. |
| `reviewer_id` | string | Foreign key to `reviewers.csv`. |
| `decision` | string | The reviewer's final decision. `APPROVE` / `EDD_REQUIRED` / `REJECT`. |
| `time_to_decision_sec` | float | Wall-clock review time. The headline metric for rubber-stamp detection. |
| `agreed_with_ai` | bool | Whether the reviewer's decision matched the AI's. |
| `review_completed_at` | ISO-8601 | When the decision was logged. |

1,000 rows. **Watch for:** rows with `time_to_decision_sec < 10` on `customer_tier=private_banking` cases — those are rubber-stamps the OversightOps blocker catches in Step 4.

## `ground_truth_backfill.csv` — downstream signals that backfill ground truth

Reviewer decisions don't get a verdict at the moment of decision. They get one weeks or months later when a downstream system (SAR filings, charge-offs, customer complaints, OFAC list matches, regulator exam findings) names the original decision as wrong.

| Column | Type | What it is |
| --- | --- | --- |
| `case_id` | string | Foreign key to `cases.csv`. |
| `ground_truth_outcome` | string | What the decision should have been. |
| `downstream_signal` | string | The signal type. One of `regulatory_finding_ofac_match`, `sar_filed_later`, `customer_complaint_cfpb`, `charge_off_30d`, `fraud_loss`, `regulatory_finding_aml`. |
| `backfill_observed_at` | date | When the downstream signal first surfaced. |
| `modeled_loss_usd` | float | The bank's modeled exposure on this single case. `0.00` for non-monetary findings (complaints, MRAs in narrative form). |
| `reviewer_was_wrong` | bool | Always `True` in this file — this CSV is the universe of cases where the human reviewer's decision contradicted the eventual outcome. |

196 rows. Of the 1,000 cases, ~20% surface a downstream-signal contradiction within the 90-day study window. The full reviewer-vs-ground-truth divergence rate (~38% modeled) materializes over the 6-12-month tail.

---

## Why this shape

OversightOps is a workflow product. The CSVs are sized to demonstrate the six deficiencies and the fix end-to-end on a laptop in seconds — not to be a production training set. If you fork this for your own fleet, drop in your real KYC / claims / credit / fraud review logs, match the column names, and the four step scripts and the Streamlit prototype run unchanged. The schema is the contract.
