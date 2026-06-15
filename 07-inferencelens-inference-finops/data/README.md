# Sample Data — InferenceLens walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`random.seed(20260601)`), and reproducible. No customer data. No PII. Shapes are calibrated to what a Tier-1 retail bank's customer-facing GenAI portfolio actually looks like: ~18 deployed features, $8-30M/yr aggregate inference spend, monthly vendor invoice as the only feedback loop.

The headline runaway the walkthrough resolves is **`FT_001` (customer-service-assistant)** — retrieval depth misconfigured from 5 documents to 50 on 2026-05-01. Per-query cost jumps from ~$0.02 to ~$0.85. Daily spend on that one feature jumps from ~$1,200 to ~$51,000. The runaway buries itself in the bank's $4M aggregate monthly compute spend for 6 weeks before anyone notices. InferenceLens catches it on day 1 via per-feature attribution.

The headline dead feature is **`FT_009` (internal-research-copilot)** — UI shut down 2026-03-15, endpoint kept receiving ~4,700 calls/day from a leaked SDK key. Zero business value; ~$28k/mo of avoidable spend.

---

## `features.csv` — 18 deployed GenAI features

The feature catalog. One row per customer-facing or internal-facing GenAI surface the bank ships.

| Column | Type | What it is |
| --- | --- | --- |
| `feature_id` | string | Format `FT_NNN`. Stable join key. |
| `feature_name` | string | Human-readable feature name (e.g., `customer-service-assistant`). |
| `owner_team` | string | Line-1 / line-2 owner team. Routes attribution. |
| `business_line` | string | `retail`, `wealth`, `enterprise`. |
| `model_used` | string | Foreign key to `model_pricing.csv`. |
| `status` | string | `active` / `dormant` / `decommissioned`. The status is what the product team THINKS is happening; `inference_logs.csv` is what is actually happening. |
| `deployed_date` | date | When the feature first went live. |
| `monthly_query_volume` | int | Modeled monthly query count. |
| `avg_query_tokens` | int | Average input-token volume per query. **This is the field that misbehaves in the FT_001 runaway.** |
| `avg_response_tokens` | int | Average output-token volume per query. |
| `retrieval_depth` | int | RAG retrieval depth — number of documents pulled per query. **Misconfigured to 50 instead of 5 on FT_001 starting 2026-05-01.** |
| `p50_latency_ms` | int | Median end-to-end latency. |
| `revenue_attributed_monthly_usd` | float | Monthly revenue this feature is credited with. Used for the per-feature ROI ranking. |
| `notes` | string | Free-text note. The runaway/dead/dormant features are flagged here. |

18 rows.

## `inference_logs.csv` — 30 days of synthetic per-query logs

The decision-grain spine. One row per sampled inference call across the 18 features in the 30-day window ending 2026-06-14 (the walkthrough is run on 2026-06-15).

| Column | Type | What it is |
| --- | --- | --- |
| `timestamp` | ISO-8601 | The moment of the inference call. UTC. |
| `feature_id` | string | Foreign key to `features.csv`. |
| `model` | string | Foreign key to `model_pricing.csv`. |
| `query_tokens` | int | Input token count for this single call. |
| `response_tokens` | int | Output token count for this single call. |
| `cost_usd` | float | Computed cost in USD using the pricing in `model_pricing.csv`. |
| `latency_ms` | int | End-to-end latency for this call. |

1,350 rows. Each represents a sampled call; volumes scale to the per-feature `monthly_query_volume` for the dollar math in Step 4.

## `model_pricing.csv` — current vendor pricing snapshot

The pricing surface that drives every cost calculation. Pulled from the published pricing pages on:

- [Anthropic pricing](https://www.anthropic.com/pricing) — Opus 4.1, Sonnet 4.5, Haiku 4.5
- [Azure OpenAI pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) — gpt-4o, gpt-4o-mini
- [AWS Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) — Llama 3.1 family, Mistral Large 2

| Column | Type | What it is |
| --- | --- | --- |
| `model` | string | Primary key. Vendor model identifier. |
| `vendor` | string | `anthropic` / `azure_openai` / `bedrock`. |
| `tier` | string | `fast` / `balanced` / `frontier`. Drives the substitution recommender. |
| `input_price_per_mtok` | float | Cost per million input tokens (USD). |
| `output_price_per_mtok` | float | Cost per million output tokens (USD). |
| `context_window` | int | Max context window in tokens. |
| `notes` | string | Plain-English routing guidance. |

9 rows.

## `substitution_recommendations.csv` — cheaper-model candidate per feature

For each feature, the recommender's verdict: keep the current model, swap to a cheaper tier, decommission the endpoint, or kill a dead feature.

| Column | Type | What it is |
| --- | --- | --- |
| `feature_id` | string | Foreign key. |
| `current_model` | string | What the feature is on today. |
| `candidate_model` | string | Recommended substitution. Can be `DEAD_FEATURE` or `DECOMMISSION` for the kill verdicts. |
| `accuracy_delta_pct` | float | Modeled accuracy lift / loss (percentage points) of the substitution, measured against a 200-probe eval suite (modeled). |
| `cost_delta_pct` | float | Modeled cost reduction as a percentage of current spend. |
| `monthly_savings_usd` | float | Modeled monthly savings from the substitution. |
| `confidence` | string | `high` / `medium` / `low` confidence in the substitution recommendation. |
| `rationale` | string | One-sentence plain-English why. |

18 rows.

---

## Headline runaway walk — `FT_001`

This is the feature the CFO would be ambushed by at the next quarterly cost review. Walk the four CSVs and you get the runaway named in one record:

| Source | What it gives you |
| --- | --- |
| `features.csv` | `FT_001` (customer-service-assistant) on `claude-sonnet-4-5`; product team thinks retrieval depth is 5; volume is 4.2M queries/month. |
| `inference_logs.csv` | Sampled per-query cost jumps from ~$0.02 to ~$0.85 starting 2026-05-01 (visible as a step function in the daily cost roll-up). |
| `model_pricing.csv` | Claude Sonnet 4.5 input pricing is $3.00/Mtok — the cost jump is consistent with input tokens ballooning ~6.7x, which is consistent with a retrieval-depth misconfiguration from 5 docs to 50 docs. |
| `substitution_recommendations.csv` | Even after the runaway is fixed, `FT_001` should drop to Claude Haiku 4.5 — modeled savings $182k/mo at a -1.4pp accuracy delta. |

In raw vendor-invoice form: invisible inside a $4M aggregate compute line. In InferenceLens: per-feature attribution flags a 42x daily-spend anomaly on day 1.
