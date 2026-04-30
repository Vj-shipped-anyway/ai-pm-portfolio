# PRD · AI Audit Trail & Decision Lineage

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.1 — pre-AI Governance Council read
**Date:** 2026-Q2

---

## 1. Problem

The bank has 140+ AI/ML models in production, spanning credit, fraud, AML, marketing, and GenAI customer-facing. Decision logs are fragmented across 6 vendor stacks, 4 cloud accounts, and 3 logging backends. Pulling the lineage of a single decision — for an exam, a customer dispute, or an internal investigation — takes a paralegal, a forensic engineer, and 14 days. There's no decision-grain audit surface.

This is structurally indefensible. NIST AI RMF, EU AI Act Article 12 (record-keeping), and the Fed/OCC's signaled extensions to SR 11-7 all converge on the same expectation: produce the full lineage of any AI decision, on demand. Today the bank cannot.

**Primary user:** Head of MRM / AI Governance (line 2).
**Secondary user:** Compliance Counsel + Regulator-Liaison (line 2).
**Tertiary user:** Production AI Operations Lead (line 1), Customer Disputes Ops, Internal Audit (line 3).

## 2. Why now

- EU AI Act Article 12 is in force; US regulators are converging.
- Over 30% of the AI fleet is now GenAI, where vendor silent updates make version capture mandatory.
- The first wave of AI-decision lawsuits is in flight. Defensibility now depends on lineage.
- Existing logging stacks were built for app telemetry, not decision provenance.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Cut audit-evidence latency | Median time to assemble single-decision lineage | 14 days to under 15 min |
| Universal coverage | % of production AI/ML decisions in lineage store | 0% to 100% Tier-1, at least 95% all |
| Continuous exam-readiness | One-click audit-pack generation | Manual to 1 click |
| Eliminate reg-exam findings on traceability | Findings/year | Baseline to 0 |
| Cost-per-record | $ per lineage record stored 7 yrs | Industry parity or better |

## 4. Non-goals

- Not a model registry (interlocks with existing).
- Not a feature store (consumes hashes from existing).
- Not a HITL workflow tool (interlocks with Project 07).
- Not a drift monitor (interlocks with Project 01).
- Not a SIEM (interlocks with security telemetry; this is decision-grain, not packet-grain).

## 5. User stories

- **As Head of MRM**, I want a single query interface that returns the full lineage of any decision in under a minute, so I answer the regulator's first question without a fire drill.
- **As Compliance Counsel**, I want a one-click audit-pack export (PDF + JSON, immutable, hash-chained) so dispute defense is a 15-minute task, not a 6-week project.
- **As an AI Ops Lead**, I want to see lineage gaps on my fleet (decisions with missing version pins, missing retrieval-set hashes, missing reviewer IDs) so I close them before audit.
- **As Internal Audit**, I want to sample 100 random decisions per quarter and walk their lineage end-to-end to attest the surface itself.
- **As a Customer Disputes Agent**, I want to pull the customer's last 12 months of AI-touched decisions in one view so resolution time drops.

## 6. Solution

### Capture plane

A thin SDK + sidecar pattern. Every model-serving stack writes one structured record per decision to an append-only event bus. Schema is enforced at write — incomplete records are rejected at the edge, not silently absorbed.

**Required fields:** decision_id, timestamp, customer_id (or pseudonym), model_name, model_version, vendor_snapshot_hash, system_prompt_hash, prompt_text (or hash for PII), retrieval_set (chunk IDs + content hashes), tool_calls, raw_output, post_processed_action, confidence, downstream_action, reviewer_id (if HITL), customer_communication_id, business_outcome (lazy-joined), parent_decision_ids, training_run_id, attestation_id.

### Storage plane

- Append-only, hash-chained ledger (Merkle-anchored, daily root anchored to a write-once store for immutability).
- Hot tier: 90 days, sub-second retrieval.
- Warm tier: 18 months, under 10s retrieval.
- Cold tier: 7 years, under 5 min retrieval (regulator-defensible).
- Customer-pseudonym index for dispute defense workflows.

### Query plane

- Streamlit / internal console for ops + governance.
- API for downstream tools (Project 01, 07, MRM workflows, customer disputes).
- One-click audit pack: PDF (human readable) + JSON (machine readable, hash-chained, signed).

### Governance plane

- Schema versioning with backward-compat enforcement.
- Field-level sensitivity tags (PII / non-PII / regulated).
- Quarterly internal-audit sample of 100 random decisions, end-to-end walk.
- Per-model lineage-completeness scorecard.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PII captured in raw prompts violates retention policy | High | High | Hash-or-redact at edge; never store raw if model contract permits hash |
| Storage cost balloons | High | Med | Tiered storage; aggressive cold-tier compression; 7-yr retention only on regulated decisions |
| Vendors can't emit version snapshot | High | High | Wrap calls in our own gateway (Project 06 interlock); pin server-side |
| Schema drift across teams | High | High | Schema-as-code, contract tests in CI/CD, write-time enforcement |
| Decision-volume scaling (10⁹/yr) | Med | High | Append-only event bus + columnar warm tier; benchmarked at 10⁹ before GA |
| Regulator wants raw, not hash | Med | High | Negotiate at policy level; default = both, with access-controlled raw |

## 8. KPIs

**North star:** Median time-to-audit-evidence for any production AI decision under 15 minutes.

**Inputs (leading):**
- % of Tier-1 models emitting complete records (target 100%)
- Schema-completeness score per model (target at least 99.5%)
- Hash-chain anchor freshness (daily)
- Retrieval-set capture rate on GenAI (target at least 99%)

**Outputs (lagging):**
- Median + p99 time-to-audit-evidence (by tier)
- Reg-exam findings on traceability (target 0)
- Settled-dispute volume on AI decisions (target −38%)
- Forensic-engineering FTE-hours/quarter (target at least −85%)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Schema & ledger | 8w | Schema-as-code, append-only ledger, daily Merkle anchor, 5 pilot models |
| 1 — Tier-1 capture | 12w | All Tier-1 ML and GenAI on capture SDK; gateway-side version pin |
| 2 — Query console | 8w | Ops + Governance UI; customer-pseudonym index; dispute-defense flow |
| 3 — Audit pack | 6w | One-click PDF + JSON export; signing pipeline; legal sign-off |
| 4 — Tier-2/3 + interlocks | 12w | Long tail; hooks into Project 01 (drift) and Project 07 (HITL) |
| 5 — Continuous-exam mode | 6w | Standing regulator-share view; quarterly internal-audit sample loop |

## 10. Open questions

1. Hash-vs-raw default for prompts containing PII — does Compliance accept hash + just-in-time un-hash on subpoena? (Recommend yes.)
2. Cross-line-of-business pseudonym scheme — single bank-wide pseudonym, or per-LOB? (Recommend bank-wide for dispute defense.)
3. Vendor-side capture vs. gateway-side capture — gateway gives uniformity, vendor-side gives fidelity. (Recommend gateway primary, vendor secondary where available.)
4. Retention beyond 7 years for litigation hold — workflow lives where? (Recommend: legal hold flag on record, never expires until cleared.)

## 11. Build & Scale Notes

**Reference architecture (vendor-named):**
- Capture SDK: Python and Go libraries embedded in every model-serving stack. Sidecar variant (Fargate / Cloud Run container) for vendor-served endpoints we can't instrument directly.
- Event spine: Kafka (Confluent Cloud or MSK). One topic per LOB, partitioned on customer-pseudonym.
- Hot tier: Postgres 15 + ClickHouse Cloud. Postgres holds the 90-day decision_id index and pseudonym B-tree; ClickHouse holds the analytical surface.
- Warm tier: ClickHouse on S3-backed storage, 18 months.
- Cold tier: Parquet on S3, Glacier escalation, indexed via AWS Athena and a Postgres-resident pseudonym-to-S3-prefix map. Under 5-minute retrieval.
- Hash-chained ledger: AWS QLDB for the Merkle root anchor (immutable). Per-record hashes computed at write; daily roots anchored.
- Query console: internal React app talking to a Go API that fans out to Postgres / ClickHouse / Athena depending on time range. Streamlit prototype for the demo.
- Natural-language search (optional, v2): Claude Sonnet via Bedrock with retrieval-grounded answers. Hard "cite or refuse" rule — no hallucinated audit results, ever.
- Audit-pack export pipeline: Step Functions orchestrating PDF render (WeasyPrint), JSON sign (AWS KMS), hash, deliver to a regulator-share S3 bucket with object-lock.
- Observability: OpenTelemetry into Datadog. Langfuse traces on the natural-language search path.
- Schema governance: schema-as-code in a dedicated repo, owned by Compliance Counsel with merge rights. CI runs contract tests against every model-serving stack PR.
- Security: SOC 2 Type II, PCI-DSS, GLBA, FedRAMP Moderate where federal-counterparty data lands. **EU AI Act Article 12 logging is the explicit design target.**

**Throughput envelope and latency budget:**
- Designed for 1B decisions/year (32 events/sec steady, 200/sec peak). Kafka and Postgres handle this comfortably.
- Capture-write latency target: under 10ms p99 in-process (SDK). Network write to Kafka is fire-and-forget with local-disk buffering on the producer side.
- Hot-tier query: under 1s p99 for single-decision lookup, under 5s p99 for customer-history pull (last 12 months).
- Warm-tier query: under 10s p99.
- Cold-tier query: under 5min p99 (Athena).
- Audit-pack export: under 60s end-to-end.

**Failure modes:**
- Vendor model ships a silent update without bumping vendor_snapshot_hash. Mitigation: gateway-side wrapper computes the hash from the response signature; vendor doesn't have to cooperate.
- Schema drift across teams. Mitigation: schema-as-code, write-time enforcement, CI gates.
- Cold-tier query slower than 5min on large customer-history pulls. Mitigation: pre-materialized customer-history Parquets refreshed nightly.
- Hash-chain root corruption. Mitigation: daily anchor to QLDB; weekly anchor to a second write-once store; Merkle proof verification on every audit-pack export.
- PII in raw prompts. Mitigation: edge-side redaction with field-level sensitivity tags; raw never persisted unless policy explicitly allows.

**Migration path:**
- Phase 0: schema-as-code repo, ledger stand-up, 5 pilot models with the capture SDK.
- Phase 1: all Tier-1 ML and GenAI on capture. Gateway-side version pinning live for vendor models. Lineage-completeness scorecard in Datadog.
- Phase 2: query console GA for line-2 governance and customer-disputes ops.
- Phase 3: one-click audit pack with KMS signing and legal sign-off.
- Phase 4: Tier-2/3 long tail. Project 01 drift events become first-class lineage events. Project 07 reviewer decisions ditto.
- Phase 5: continuous-exam mode — standing read-only view for regulators, quarterly internal-audit sample loop.

**Org dependencies:**
- Compliance Counsel owns the schema and has merge rights on the schema-as-code repo. This is non-negotiable. Compliance will resist the audit-trail unless you let them own the schema.
- MRM / AI Governance owns the surface and the KPI dashboard.
- Line 1 AI Ops owns capture-completeness per model.
- Internal Audit owns the quarterly walk-through sample.
- Customer Disputes Ops is a key v2 user — their adoption is how you justify the customer-pseudonym index investment.
- Project 01 (drift), Project 06 (inference economics gateway), and Project 07 (HITL) are all upstream emitters.

---

*This PRD interlocks with Projects 01 (DriftSentinel), 06 (Inference Economics gateway), and 07 (HITL Decision Surface).*
