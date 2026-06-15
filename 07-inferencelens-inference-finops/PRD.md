# PRD · InferenceLens — Inference Economics Dashboard

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype, designed for engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I would bring to a Tier-1 retail bank's Head of FinOps, AI Platform Lead, and CFO's office in the seat. It is not a record of a PRD landed at a named bank. The six-deficiency taxonomy, the architecture, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD stub

| Field | Value |
| --- | --- |
| **Product** | InferenceLens — per-feature inference economics layer for the bank's GenAI portfolio. |
| **Owner** | Vijay Saharan, Sr PM (AI Platform / FinOps). |
| **Stage** | Portfolio prototype, designed for engagement. Synthetic data, no production deployment. |
| **Users** | Primary: Head of FinOps, AI Platform PM. Secondary: CFO's office, individual feature owners (line-1 product managers), CTO. Tertiary: Procurement, vendor-relationship leads. |
| **Problem** | Tier-1 BFSI shops run 12-20 customer-facing GenAI features against $4-30M/yr aggregate inference spend. Per-feature attribution is ~0%. A single misconfigured feature can burn $50k/day for 6 weeks before quarterly cost review notices. Cheaper-model substitutions are obvious in retrospect, invisible in the moment. Dead features rack up bill long after their UIs were shut down. CFO asks "what are we paying for?" — nobody can answer. |
| **Solution** | Per-feature inference economics layer that reads OpenTelemetry span attributes (feature_id, tenant_id, model, tokens), reconciles against vendor billing APIs, and runs five derived views: per-feature attribution, runaway detection, cheaper-model substitution recommender, dead-feature flagger, per-feature ROI ranking. Six-deficiency taxonomy closed by design. |
| **North-star metric** | % of inference spend that is per-feature attributed within 24 hours of cost incurrence, with revenue-attribution joined within 7 days. |
| **Modeled metrics (12-month horizon)** | 🟡 Per-feature attribution coverage: **0% → 100%** (assumes the OpenTelemetry span attributes ship on every feature). 🟡 Modeled spend reduction: **25-30%** (assumes cheaper-model substitutions on the over-tiered fleet + dead-feature pruning + runaway prevention; reference baseline is the synthetic 18-feature fleet). 🟡 Runaway detection lag: **6 weeks → 1 day** (modeled — assumes 3x trailing-7-day baseline threshold and per-feature alerting). |
| **Modeled cost** | 🔴 ~$340k for a 90-day engagement in a real deployment (compute on existing ClickHouse footprint + 1 PM + 1.5 FTE engineers + 0.25 FTE Finance partner + Snowflake reads for revenue join) — designed, not executed. |
| **Risk #1** | Per-feature attribution requires consistent OpenTelemetry span attributes from every feature. Solution: ship a shared SDK (`bank-genai-otel`) that wraps the vendor SDKs and emits the canonical span shape; release as a CI policy gate. |
| **Risk #2** | Substitution recommender's accuracy deltas are eval-suite-dependent. If the eval suite is wrong, the recommendation is wrong. Solution: interlock with [EvalForge](../04-evalforge-llm-eval-platform/) — substitution recommendations are gated on probe-set pass rates per (feature_family, candidate_model) pair. |
| **Risk #3** | Dead-feature alerts can fire on features that are legitimately low-traffic (e.g., year-end batch jobs). Solution: status-mismatch logic uses the catalog's declared status as ground truth, with a 60-day rolling window and a feature-owner ack workflow. |
| **Out of scope** | (1) Replacing the bank's existing FinOps tooling (Apptio Cloudability, CloudHealth) — we publish per-feature spend, they aggregate. (2) Real-time per-token cost in the inference hot path (handled by the gateway sidecar). (3) Fine-tuning training cost (handled by the MLOps platform). (4) GPU instance-hour cost for in-VPC Bedrock workloads (handled by AWS Cost Explorer). (5) Customer-facing surfaces — internal-only tool. |

---

## 2. Stakeholder map

| Role | Line | Stake | What they want from InferenceLens |
| --- | --- | --- | --- |
| **Head of FinOps** | Finance | Owns the cloud/AI cost discipline | Per-feature attribution, dead-feature flagger, substitution recommender. Lands the AI platform team's FinOps maturity at Level 3 (FinOps Foundation framework). |
| **CFO's office** | Finance | Owns the quarterly cost review | Per-feature monthly spend, per-feature ROI ranking, runaway alert. The "what are we paying for" answer that's been missing for two years. |
| **CTO** | Platform | Owns the AI strategy + cost | Fleet-level health metric; aging-features-without-ROI report; cheaper-model substitution recommendations ranked by modeled savings. |
| **AI Platform PM (me)** | Platform | Owns the platform substrate | The substrate that lets every feature owner self-serve their own ROI story. The dashboard that ends the "we are looking into it" pattern. |
| **Individual feature owners (line-1 PMs)** | L1 | Own the deployed features | Per-feature cost, per-feature ROI, runaway alerts so the platform team doesn't ambush them at quarter-end. Substitution recommendations they can act on. |
| **Procurement / vendor-relationship lead** | Finance | Owns Anthropic + Azure + Bedrock contracts | Vendor-mix view; substitution recommendations to drive contract renegotiation. |
| **Cloud Security / CISO** | Platform | Owns endpoint governance | Dead-feature alerts (a leaked SDK key still hitting the endpoint is a security smell, not just a cost smell). |
| **Legal / Compliance (L2)** | L2 | Owns the data-handling posture | Per-feature spend attributable to data-residency-locked workloads (EU, India RBI). |

---

## 3. RICE-prioritized backlog

> RICE = (Reach × Impact × Confidence) ÷ Effort.
> Status: "Sequenced for v0.x" = committed to a release. "Queued" = will be sequenced after v0.5.

| # | Item | Reach | Impact | Confidence | Effort | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | **Per-feature attribution composer (v0.1)** — OpenTelemetry span ingest; ClickHouse cost-event table; per-feature monthly rollup. | 20 | 3 | 0.9 | 8 | 6.8 | Sequenced for v0.1 |
| 02 | **Canonical OpenTelemetry SDK** (`bank-genai-otel`) — wraps Anthropic, Azure OpenAI, Bedrock SDKs; emits canonical span shape. Released as a CI policy gate. | 20 | 3 | 0.85 | 13 | 3.9 | Sequenced for v0.1 |
| 03 | **Vendor billing API reconciler** — daily reconciliation of per-feature OTEL-derived cost against Anthropic, Azure, Bedrock billing APIs. Drift > 2% pages on-call. | 20 | 2 | 0.8 | 8 | 4.0 | Sequenced for v0.2 |
| 04 | **Runaway detection (v0.2)** — per-feature daily spend; 3x trailing-7-day baseline threshold; PagerDuty integration. | 20 | 3 | 0.85 | 5 | 10.2 | Sequenced for v0.2 |
| 05 | **Cheaper-model substitution recommender (v0.3)** — per-feature workload-fit scoring; interlocks with [EvalForge](../04-evalforge-llm-eval-platform/) probe-set pass rates per (feature_family, candidate_model). | 20 | 3 | 0.7 | 13 | 3.2 | Sequenced for v0.3 |
| 06 | **Dead-feature flagger (v0.3)** — status-mismatch logic; catalog status vs sampled traffic; feature-owner ack workflow. | 20 | 2 | 0.85 | 5 | 6.8 | Sequenced for v0.3 |
| 07 | **Per-feature ROI ranking (v0.4)** — revenue-attribution join from Snowflake; net = revenue - cost; ranking output to CFO dashboard. | 20 | 2 | 0.7 | 8 | 3.5 | Sequenced for v0.4 |
| 08 | **Per-tenant attribution** — span attribute `tenant_id` reconciliation; segment-level spend breakdown. | 20 | 2 | 0.7 | 8 | 3.5 | Sequenced for v0.4 |
| 09 | **Streamlit prototype** — single-feature drill-down, six-deficiency view, CFO-pack download. | 0.1 | 2 | 1.0 | 5 | 0.04 | Sequenced for v0.1 (this repo) |
| 10 | **FinOps tooling integration** — push per-feature spend to Apptio Cloudability / CloudHealth; the bank's existing executive view aggregates AI with non-AI compute. | 20 | 2 | 0.7 | 8 | 3.5 | Sequenced for v0.5 |
| 11 | **Vendor mix optimizer** — model the cross-vendor reallocation that minimizes spend at fixed accuracy; quarterly report for procurement. | 20 | 2 | 0.55 | 13 | 1.7 | Sequenced for v0.5 |
| 12 | **Auto-attestation of substitution recs** — feature owner clicks "accept"; substitution scheduled into the next deploy cycle. | 20 | 2 | 0.6 | 13 | 1.8 | Queued (post v0.5) |
| 13 | **Real-time budget guard** — per-feature monthly envelope; gateway-level rate limit when 80% consumed; alert to feature owner. | 20 | 3 | 0.5 | 21 | 1.4 | Queued (post v0.5) |
| 14 | **EU + India regional attribution** — data-residency-aware spend rollup; segregation for RBI + GDPR-locked workloads. | 12 | 2 | 0.6 | 13 | 1.1 | Queued (post v0.5) |

---

## 4. Why now

- **GenAI portfolios at Tier-1 BFSI are at 12-20 customer-facing features.** Each one was built with the vendor SDK's default settings. None of them was instrumented for per-feature cost from day one.
- **Aggregate inference spend is now CFO-attention-grabbing.** $8-30M/yr is in the range where Finance asks for an account, and nobody can give one.
- **Vendor pricing differentials are real.** [Anthropic Haiku 4.5](https://www.anthropic.com/pricing) is 1/15 the cost of [Opus 4.1](https://www.anthropic.com/pricing) per output token. [gpt-4o-mini](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) is 1/17 the cost of gpt-4o. The substitution candidate space is wide and well-priced.
- **OpenTelemetry has won.** Every modern LLM SDK either emits OTEL natively or has a community shim. The substrate exists; the composition layer is missing.
- **FinOps Foundation framework** is the published industry reference. AI is currently in the framework's "emerging" tier; getting a bank to Level 3 maturity on AI/inference is now table stakes for the FinOps practice.

## 5. Goals (12-month horizon)

| Goal | Metric | Target | Tier |
| --- | --- | --- | --- |
| Increase per-feature attribution coverage | % of inference spend attributed per-feature within 24 hours | 0% → 100% | 🟡 |
| Reduce runaway detection lag | Median days from misconfiguration to alert | 42 → 1 | 🟡 |
| Reduce fleet spend via substitution + dead-feature kill | % of total inference spend recovered annually | unknown → 25-30% | 🟡 |
| Establish per-feature ROI as a defensible number | % of features with a per-feature ROI number reportable to the board | <10% → 100% | 🔴 |

## 6. Non-goals

- Not a logging vendor — we read OpenTelemetry, we do not collect.
- Not a vendor billing platform — we reconcile against vendor billing APIs but Anthropic, Azure, and AWS remain the systems of record for invoicing.
- Not a budget enforcement layer in the inference hot path — that lives at the gateway, on the request path. We are off the request path.
- Not a customer-facing surface — internal AI Platform + FinOps tool only.
- Not a replacement for the bank's existing FinOps tooling — we publish per-feature spend; Apptio / CloudHealth aggregates.

## 7. User stories

- **As Head of FinOps**, I want a per-feature monthly spend report so I can have the "what are we paying for" conversation at quarterly review with an answer.
- **As a CFO**, I want a per-feature ROI ranking so I can defend the AI roadmap on a per-feature basis at the board offsite.
- **As an AI Platform PM**, I want a runaway alert within 24 hours of a misconfig so I don't have to explain a $1.5M overspend at the next QBR.
- **As an individual feature owner (line-1 PM)**, I want to see my feature's modeled cost and the substitution recommender's verdict so I can act on cost reductions without waiting for a Finance ask.
- **As a Procurement lead**, I want a vendor-mix report so I can negotiate the next Anthropic / Azure renewal with leverage.

## 8. Solution detail — the six-deficiency taxonomy

The product is a composition + detection layer. Each deficiency maps to a specific source signal and a specific composer action.

| # | Deficiency | Source signal | Composition action |
| --- | --- | --- | --- |
| 1 | No per-feature attribution | OpenTelemetry span attribute `feature_id` | Aggregate cost-events per feature; join feature catalog metadata. |
| 2 | No per-tenant / segment attribution | OpenTelemetry span attribute `tenant_id` | Aggregate per (feature_id, tenant_id) pair; segment-level views. |
| 3 | No runaway detection | Per-feature daily cost time series | SPC threshold: alert when day > 3x trailing-7-day baseline; PagerDuty fires. |
| 4 | No cheaper-model substitution recs | [EvalForge](../04-evalforge-llm-eval-platform/) probe-set pass rates per (feature_family, candidate_model) | Score each candidate model for the feature; recommend if accuracy_delta acceptable AND cost_delta meaningful. |
| 5 | No dead-feature detection | Feature catalog status + sampled traffic | Flag when status=dormant/decommissioned AND sampled_calls > 0; ack workflow to feature owner. |
| 6 | No per-feature ROI dashboard | Snowflake revenue-attribution table | Join by feature_id; net = revenue - cost; ranked view. |

## 9. Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 4w | OpenTelemetry SDK published; ClickHouse cost-event table; per-feature attribution composer; 1 pilot feature (customer-service-assistant). |
| 1 — Tier-1 retail rollout | 8w | All customer-facing retail GenAI features instrumented; per-feature attribution running; vendor billing-API reconciler live. |
| 2 — Runaway detection | 6w | 3x baseline threshold; PagerDuty integration; first 90 days of historical backfill. |
| 3 — Substitution recommender | 8w | EvalForge interlock; per-feature workload-fit scoring; first round of substitution recs published. |
| 4 — Dead-feature flagger | 4w | Status-mismatch logic; feature-owner ack workflow; first round of kill recs. |
| 5 — Per-feature ROI | 6w | Snowflake revenue-attribution join; ranking dashboard; CFO pack export. |
| 6 — FinOps tooling integration | 6w | Apptio / CloudHealth push; the bank's executive view aggregates AI with non-AI compute. |

## 10. Open questions

1. **Tenant boundary granularity.** Customer-segment-level or per-customer? Default: customer-segment for retail; per-customer for wealth, where the segment is the customer.
2. **Substitution acceptance threshold.** What accuracy delta is acceptable per feature family? Default: -1.5pp for customer-service; -0.5pp for ECOA-regulated; -3pp for marketing.
3. **Runaway alert routing.** Page the feature owner directly, or page the AI Platform on-call who then triages? Default: feature owner first, AI Platform escalation if no ack in 4h.
4. **Revenue-attribution authority.** Does the bank's revenue-attribution model (the Snowflake `product_revenue_attribution` table) carry enough fidelity to support per-feature ROI claims at the board level? Default: yes for revenue-generating features (wealth, SMB, sales-CRM); no for cost-center features (customer-service, KYC, fraud-explainer) where ROI is "deflected operating cost."

## 11. Build & scale notes

**Reference architecture.** Composition runs on Cloud Run (stateless) backed by Pub/Sub fan-in from the OpenTelemetry collector. ClickHouse (Aiven / Altinity managed) holds the high-cardinality cost-event table; Postgres holds the feature catalog; Snowflake is read-only for revenue join. The CFO pack is generated on-demand from the immutable ClickHouse aggregate + the latest feature catalog snapshot.

**Throughput envelope.** ~50-500M inference calls/yr at Tier-1 BFSI fleet scale = ~1.5-16 calls/second average, ~16-150 calls/second peak. The cost-aggregator's 5-minute SLO is far from latency-critical; the constraint is completeness, not throughput.

**Failure modes.**
- *Vendor billing API down.* Reconciliation runs daily; if 24h pass without reconciliation, page operator. Cost-event table remains source-of-truth for InferenceLens; vendor invoice arrives later as a cross-check.
- *OpenTelemetry span missing `feature_id`.* Falls into an "unattributed" bucket; weekly report names unattributed features; CI policy gate enforces the attribute on new features.
- *Revenue-attribution join lag.* ROI ranking has a 7-day lag by design. Per-feature attribution + runaway + substitution + dead-feature views are all real-time.

**Migration path.** If the bank is already running Apptio Cloudability or CloudHealth at the cloud-infrastructure level: InferenceLens publishes per-feature AI spend into their data model; nothing rips out. If the bank is on the spreadsheet-FinOps world: 4-week foundation phase to ship the OpenTelemetry SDK; the per-feature view starts working immediately as features adopt the SDK.

**Org dependencies.** AI Platform team owns the OpenTelemetry SDK rollout. Each line-1 feature team adopts the SDK at their next deploy. FinOps team consumes the per-feature attribution; CFO's office consumes the ROI ranking. CTO sign-off on the substitution recommendations before they are acted on.

---

*This PRD interlocks with [EvalForge](../04-evalforge-llm-eval-platform/) (substitution-recommender eval suite), [AgentWatch](../05-agentwatch-agent-observability/) (agent-spend attribution), and [LineageLog](../09-lineagelog-ai-decision-audit/) (decision-grain composition).*
