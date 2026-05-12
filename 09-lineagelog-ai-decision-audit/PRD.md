# PRD · LineageLog — AI Decision Audit Trail

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype, designed for engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I would bring to a Tier-1 retail bank's Head of Compliance and CRO in the seat. It is not a record of a PRD landed at a named bank. The six-deficiency taxonomy, the architecture, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD stub

| Field | Value |
| --- | --- |
| **Product** | LineageLog — immutable decision-grain composition layer for regulated AI decisions. |
| **Owner** | Vijay Saharan, Sr PM (BFSI AI Platform). |
| **Stage** | Portfolio prototype, designed for engagement. Synthetic data, no production deployment. |
| **Users** | Primary: Head of Compliance, Internal Audit (L3). Secondary: CRO, Line-2 validators, MRM committee chairs, regulator-facing teams (OCC liaison, EU AI Act competent-authority liaison). Tertiary: line-1 model owners. |
| **Problem** | Every regulator (OCC, Fed, EU AI Act Article 12, NIST AI RMF) asks the same question: "explain this AI decision for this customer on this date." Today: 14 days, paralegal-led, fragmented across 6 vendors + 4 cloud accounts. The lineage fragments exist; the composition does not. The bank produces a narrative for the OCC, not a record. Findings escalate. |
| **Solution** | Decision-grain composition layer that binds Cloud Logging + Cloud Audit Logs + Agent Identity Logs + OpenTelemetry traces at `(decision_id, customer_id_hash, timestamp)`. Immutable record per decision. Six-deficiency taxonomy closed by design: prompt versioning, retrieval-set capture, model-snapshot pin, feature-at-decision-time, reviewer attribution, outcome backlink. Auto-assembled exam-pack export in sub-second on the prototype. |
| **North-star metric** | % of regulated AI decisions with complete six-deficiency lineage composed within 5 minutes of decision time, queryable by `(customer_id_hash, decision_id, timestamp)`. |
| **Modeled metrics (12-month horizon)** | 🟡 Audit-pack assembly time: **3 weeks → 3 seconds** (assumes the synthetic 200-decision corpus and a Tier-1-style four-model fleet). 🟡 Exam-readiness coverage: **22% → 100%** (assumes published BFSI baseline for sample-driven readiness vs. continuous). 🔴 Time-to-decision-evidence: **14 days → 12 minutes** (designed against published OCC exam patterns; not yet tested in a real exam). |
| **Modeled cost** | 🔴 ~$420k for a 90-day engagement in a real deployment (compute on existing Cloud Logging/Audit infra + 1 PM + 1.5 FTE engineers + 0.5 FTE compliance partner + WORM bucket storage) — designed, not executed. |
| **Risk #1** | Composition latency under load. 50-200M decisions/yr means ~16-65 decisions/second peak. Solution: stateless composers + Pub/Sub sharded by `customer_id_hash`. |
| **Risk #2** | Vendor snapshot pin verification gap. If the vendor (Anthropic, Azure OpenAI, Bedrock) silently rolls a snapshot, the registry's post-roll value is wrong for pre-roll decisions. Solution: interlock with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5 vendor-pin detector + daily diff job + response-header pin extraction. |
| **Risk #3** | Compliance pushback on "auto-assembled" exam packs — regulators want a human in the loop. Solution: human-review-and-edit before WORM seal, never auto-attest; the bank's MRM workbench remains the system of record for sign-off. |
| **Out of scope** | (1) Replacing the bank's existing logging vendors — we compose, we do not collect. (2) Adjudicating disputed decisions — we provide lineage, not adjudication. (3) Real-time decision blocking — we are off the request path. (4) Customer-facing surfaces — internal compliance tool only. (5) Building a new IdP — we integrate with the bank's existing Okta / Entra ID / Ping. |

---

## 2. Stakeholder map

| Role | Line | Stake | What they want from LineageLog |
| --- | --- | --- | --- |
| **Head of Compliance** | L2 | Owns regulator response posture | One-click exam-pack export per decision; continuous coverage instead of sample-based readiness. |
| **CRO** | L2 oversight | Owns model risk at the portfolio level | Fleet-level lineage health metric; aging-decisions-without-lineage report; integrates with the bank's MRM workbench. |
| **Internal Audit (L3)** | L3 | Owns the bank's effective-challenge function | Read-only access to immutable lineage records; sample-pull workflow that does not require pulling 6 log surfaces by hand. |
| **Cloud Security** | Platform | Owns log surface configuration | Workload-identity-based ingest; no long-lived service-account keys; egress restricted to the bank's VPC; aligns with the Google Cloud *Building secure multi-agent systems* pattern. |
| **Regulator-facing teams (OCC liaison, EU AI Act competent-authority liaison)** | L2 | Owns the bank's regulator-facing relationship | Pre-formatted decision lineage in the regulator's preferred format; trail of who saw the lineage record (audit-on-audit). |
| **Line-2 Validators (MRM team)** | L2 | Owns model attestation | Decision-grain context attached to the attestation workflow; reduces collation time from 3 weeks to ~1 hour with human edit before sign-off. |
| **Line-1 Model Owners** | L1 | Owns the deployed model | Outcome-backlink visibility so bad outcomes flow back into model retraining cycles. |
| **Platform Engineering** | Platform | Owns the AI platform substrate | Composition layer is platform-owned, ingest is composable, no new logging vendor introduced. |
| **InfoSec (CISO)** | L2 | Owns the bank's data-handling posture | All composition runs inside the bank's VPC; WORM retention; field-level encryption on customer_id_hash; SR 11-7 + SOC 2 + GLBA alignment. |
| **Legal (E&G)** | L2 | Owns disclosure and consent posture | Lineage records have legal-hold flag; cannot be deleted while a matter is open; GDPR right-to-erasure cascades to hash deletion. |

---

## 3. RICE-prioritized backlog

> RICE = (Reach × Impact × Confidence) ÷ Effort.
> Status: "Sequenced for v0.x" = committed to a release. "Queued" = will be sequenced after v0.5.

| # | Item | Reach | Impact | Confidence | Effort | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | **Decision-grain composer (v0.1)** — bind the four log sources at `(decision_id, customer_id_hash, timestamp)`; write immutable Postgres row. | 100M | 3 | 0.9 | 13 | 20.8 | Sequenced for v0.1 |
| 02 | **Six-deficiency schema** — Postgres CREATE TABLE for `decision_lineage`; field-level encryption for `customer_id_hash`. | 100M | 3 | 0.9 | 5 | 54.0 | Sequenced for v0.1 |
| 03 | **Exam-pack export (v0.1)** — auto-assemble PDF + JSON per `decision_id`; WORM upload to GCS Object Lock. | 100M | 3 | 0.85 | 8 | 31.9 | Sequenced for v0.2 |
| 04 | **Prompt-template registry ingest** — every prompt deploy writes a registry row; composer joins by `(model_id, effective_at)`. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.2 |
| 05 | **Retrieval-set capture** — RAG pipeline writes `(decision_id, doc_id, doc_version, retrieved_at)` to a sidecar topic. | 80M | 3 | 0.75 | 13 | 13.8 | Sequenced for v0.3 |
| 06 | **Feature-at-decision-time** — temporal feature-store API; composer calls it per decision; cached for 24h. | 100M | 3 | 0.7 | 21 | 10.0 | Sequenced for v0.3 |
| 07 | **Reviewer attribution** — Agent Identity Auth Manager integration; distinguish `human_user_delegated` from `agent_autonomous`. | 100M | 3 | 0.8 | 8 | 30.0 | Sequenced for v0.4 |
| 08 | **Outcome backlink ingester** — daily job that joins downstream-system outcomes back to `decision_id` via customer-hash + time window. | 100M | 3 | 0.65 | 13 | 15.0 | Sequenced for v0.4 |
| 09 | **Vendor-pin verifier** — interlock with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5; response-header pin extraction; daily diff. | 50M | 3 | 0.7 | 8 | 13.1 | Sequenced for v0.5 |
| 10 | **Streamlit prototype** — single-decision drill-down, six-deficiency lineage card, exam-pack download. | 1k | 2 | 1.0 | 5 | 0.4 | Sequenced for v0.1 (this repo) |
| 11 | **MRM workbench integration** — push lineage record ID to Archer / ServiceNow GRC / MetricStream; bidirectional sync on attestation. | 100M | 2 | 0.6 | 13 | 9.2 | Sequenced for v0.6 |
| 12 | **OPA policy gates** — RBAC matrix scoped per region; OPA evaluates every exam-pack export. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.5 |
| 13 | **GDPR right-to-erasure cascade** — customer_id_hash deletion cascades to lineage records (with legal-hold override). | 30M | 2 | 0.7 | 8 | 5.2 | Queued (post v0.6) |
| 14 | **Multi-region EU + India instances** — separate KMS key rings, no cross-region replication, RBI + GDPR alignment. | 60M | 2 | 0.6 | 21 | 3.4 | Queued (post v0.6) |

---

## 4. Why now

- **EU AI Act Article 12** is in effect. High-risk AI systems (which includes BFSI credit and insurance) must keep records that allow tracing of all events relevant to the system's operation. Banks operating in the EU need this on disk, not in narrative form, by the post-grace-period enforcement window.
- **OCC exam cycles** are shifting toward sample-based decision lineage audits. The published shape of recent supervisory letters is increasingly granular: "show us this specific decision," not "show us your model risk framework."
- **NIST AI RMF 1.0** is the federal-government reference framework. Federal counterparty work — Treasury, FHFA, Fannie/Freddie counterparties — is increasingly RMF-aligned.
- **Vendor model silent updates** (Anthropic Feb 24, 2026 reference incident) make the model-snapshot-pin question harder every quarter.
- **The substrate is finally there.** Cloud Logging + Cloud Audit Logs + Agent Identity Auth Manager + OpenTelemetry on ADK is published, productized, and adopted at every Tier-1 bank. The composition layer is the missing piece.

## 5. Goals (12-month horizon)

| Goal | Metric | Target | Tier |
| --- | --- | --- | --- |
| Reduce audit-pack assembly time | Median seconds from regulator request to exam-pack PDF | 3 weeks → 3 seconds | 🟡 |
| Increase exam-readiness coverage | % of regulated AI decisions with complete six-deficiency lineage composed within 5 min of decision time | 22% → 100% | 🟡 |
| Reduce time-to-decision-evidence | Median minutes from "show me this decision" to delivered exam-pack | 14 days → 12 minutes | 🔴 |
| Zero finding rate | OCC / Fed / EU AI Act exam findings related to AI decision lineage | unknown → zero (designed target) | 🔴 |

## 6. Non-goals

- Not a logging vendor — we compose, we do not collect. Cloud Logging, Cloud Audit Logs, Agent Identity Auth Manager, OTel are the source-of-truth tail.
- Not an adjudication engine — we provide lineage; we do not decide whether the decision was correct.
- Not in the request path — composition is asynchronous, off the hot path, with a 5-minute compose SLO.
- Not a customer-facing surface — internal-only.
- Not a fourth line of defense — line-2 tooling that line-3 audits, not a separate function.

## 7. User stories

- **As Head of Compliance**, I want a one-click exam-pack export per decision_id so I do not have to assemble a paralegal team every time the OCC opens an exam.
- **As CRO**, I want a portfolio-level lineage health metric so I know which models have continuous coverage and which do not.
- **As Internal Audit (L3)**, I want read-only access to immutable lineage records so I can validate effective challenge without pulling six log surfaces by hand.
- **As a Line-2 Validator**, I want decision-grain context attached to my attestation workflow so I spend my time on judgment, not collation.
- **As a Regulator-facing team member**, I want the exam pack pre-formatted in the regulator's preferred shape so the first three exam questions are answered before the meeting.

## 8. Solution detail — the six-deficiency composition

The product is a composition layer. Each deficiency maps to a specific source signal and a specific composer action.

| # | Deficiency | Source signal | Composition action |
| --- | --- | --- | --- |
| 1 | Prompt versioning | Prompt-template registry table (`(model_id, template_id, effective_at)`) | Join by `(model_id, effective_at <= decision_timestamp)`, write `template_id` + `policy_hash` to the lineage record. |
| 2 | Retrieval-set capture | RAG pipeline sidecar topic (Pub/Sub) | Subscribe; bind by `decision_id`; write retrieved doc list with versions to the lineage record. |
| 3 | Model-snapshot pin | Model registry + vendor response headers | Join by `model_id`; cross-check vendor response header pin against registry; flag if mismatch (interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5). |
| 4 | Feature-at-decision-time | Feature store temporal API (Tecton / Databricks Feature Store / Vertex AI) | Call temporal API with `(customer_id, decision_timestamp)`; write feature vector with `feature_pipeline_version` to the lineage record. |
| 5 | Reviewer attribution | Agent Identity Auth Manager logs | Distinguish `human_user_delegated` (with `delegation_token_id`) from `agent_autonomous` (with `agent_identity` SPIFFE ID); write to the lineage record. |
| 6 | Outcome backlink | Daily ETL from loss-event lake, CFPB complaint system, claims platform | Match by `customer_id_hash` + time window (2-180 days post-decision); write outcome with `outcome_type` + `outcome_date` to the lineage record. |

## 9. Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 6w | Postgres `decision_lineage` schema; composer service; Cloud Logging + Audit + Agent Identity + OTel ingesters; 1 pilot model (loan_pd_v3). |
| 1 — Tier-1 ML | 12w | All Tier-1 classical ML; prompt-template registry rolled out; retrieval-set capture for non-RAG models trivially satisfied. |
| 2 — GenAI fleet | 12w | All customer-facing GenAI; vendor-pin verifier live (interlocks with DriftSentinel); retrieval-set capture for RAG pipelines. |
| 3 — Feature-at-time | 8w | Feature-store temporal API; composer's feature-at-time call. |
| 4 — Outcome backlink | 8w | ETL from loss lake + CFPB + claims; backfill 90 days at go-live. |
| 5 — Exam-pack export & MRM integration | 6w | PDF/JSON export; MRM workbench (Archer / ServiceNow GRC) integration; legal-hold workflow. |
| 6 — Multi-region | 12w | EU instance (Frankfurt) + India instance (Mumbai); independent KMS rings. |

## 10. Open questions

1. **WORM vs append-only.** Does the bank's CISO require GCS/S3 Object Lock for the seven-year retention, or does a tamper-evident append-only Postgres table (with HSM-signed row hashes) satisfy the auditor? Default: both, since the cost delta is small.
2. **Decision sampling boundary.** Do we compose lineage for every decision (100%) or only for tier-1 decisions? Default: 100% for tier 1, 10% sampled for tier 2/3 with the sample stratified by `customer_id_hash` for reproducibility.
3. **Legal-hold workflow.** When a customer files a lawsuit, what is the cascade rule for marking related lineage records as legal-hold? Default: Legal flags `customer_id_hash`; cascade is automatic.
4. **MRM workbench primary integration.** Archer, ServiceNow GRC, or MetricStream first? Depends on the bank's existing license. Default: build the integration as a generic OIDC-based push so the third one isn't a rewrite.

## 11. Build & scale notes

**Reference architecture.** Composition runs on Cloud Run (stateless) backed by a Pub/Sub fan-in across the four log surfaces. Postgres (Cloud SQL with high-availability + read replicas) holds the immutable lineage table; ClickHouse holds the high-cardinality observability stream; GCS Object Lock + Cross-region replication holds the WORM archive. The exam-pack PDF is generated on-demand from the immutable Postgres row + retrieval set + cached vendor-snapshot diff.

**Throughput envelope.** ~50-200M regulated AI decisions/yr at Tier-1 retail bank = ~1.5-6.5 decisions/second average, ~16-65 decisions/second peak. The composer's 5-minute compose SLO is far from latency-critical; the constraint is durability, not throughput.

**Failure modes.**
- *Source-log delay.* Cloud Logging is ~2-5s lag; OTel traces are ~5-15s; Agent Identity Logs are <1s. The composer waits up to 5 minutes for all four; if any source is missing at T+5min, it composes what it has and writes a `lineage_partial: true` flag. The partial record is the artifact; backfill upgrades to complete in the next composer pass.
- *Feature-store temporal API down.* Cached point-in-time fallback for 24h; flag the record `feature_at_decision_time: cached`; downgrade severity.
- *Vendor response-header pin missing.* Fall back to the registry pin; flag `vendor_pin_verification: registry_only`; alert P3.

**Migration path.** If the bank is already running an MRM workbench (Archer/ServiceNow GRC/MetricStream) with attestation workflows: LineageLog ingests into the existing workbench; it does NOT replace the bank's compliance system of record. If the bank is on the quarterly Word-doc world: 6-week foundation phase to wire up the four log sources first; lineage gets composed as a side-effect; the Word doc gets replaced over a 12-month transition.

**Org dependencies.** Internal Audit (L3) signs off on the immutability properties of the lineage table. CISO signs off on the field-level encryption + KMS key handling. Cloud Platform team owns the four log source feeds. The MRM workbench owner owns the GRC tool integration (typically a 3-month vendor conversation; start on day one).

---

*This PRD interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) (vendor-pin detection), [AgentWatch](../05-agentwatch-agent-observability/) (multi-agent A2A lineage), and [OversightOps](../08-oversightops-hitl-workflow/) (HITL evidence routing).*
