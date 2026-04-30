# PRD · Prompt-Injection & Egress Defense

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.1 — pre-CISO and Model Risk joint read
**Date:** 2026-Q2

---

## 1. Problem

Banks are putting LLM-backed copilots and agents over confidential and regulated data without a defense layer between the model and the user, the model and its tools, or the model and its retrieved context. The dominant threat is no longer the jailbreak crafted by a curious user — it is *indirect injection*: instructions embedded in retrieved documents, customer-supplied text, tool outputs, or third-party content that the model executes as if they were system intent. OWASP LLM01 names this. Simon Willison has cataloged it weekly for three years. BFSI security tooling does not see it because the AI traffic doesn't pass through the WAF/DLP plane.

**Primary user:** AI Platform Security Lead (line 1 controls).
**Secondary user:** CISO / DPO (line 2).
**Tertiary user:** Application Owner of each deployed copilot/agent.

## 2. Why now

- Every Tier-1 US bank now has at least one customer-facing or internal-confidential GenAI app in production.
- Indirect-injection attacks moved from research papers to documented incidents in 2024–2025.
- Regulators (OCC, NYDFS, FFIEC) are signaling explicit AI-security expectations; safe-harbor will require a defensible control plane.
- Vendor model providers consistently disclaim that prompt-injection defense is the application owner's responsibility — in writing, in their MSAs.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Detect direct injection | OWASP LLM01 test-suite block rate | 100% |
| Detect novel injection | Red-team novel-attack block rate | ≥ 96% |
| Eliminate egress incidents | Confirmed data-egress events | 0 |
| Hold latency budget | p95 added latency at gateway | ≤ 250ms |
| Hold false-block rate | Benign-traffic block rate | ≤ 0.4% |

These are modeled targets calibrated against red-team suites I've seen at three Tier-1 BFSI shops. Vendor model behavior shifts mean these need re-validation each model-version pin (interlocks with Project 01).

## 4. Non-goals

- Not a model-safety RLHF tuning effort. Consumes from vendor; layers on top.
- Not a CASB/DLP replacement. Interlocks; complementary.
- Not the audit log of record. Writes events into Project 08.

## 5. User stories

- **As a Platform Security Lead**, I want every LLM call routed through one gate with one policy language, so a single change propagates to all copilots.
- **As a CISO**, I want a one-page weekly view of attempted-injection volume, classifier hit-rate, and egress events, so I can speak to the board without a war room.
- **As an Application Owner**, I want a per-app policy I can tune (strict for customer-facing, looser for internal research), so I'm not gated by the most paranoid app in the portfolio.
- **As a Validator (line 2)**, I want every block decision to carry an evidence record (input, classifier, score, policy version) so I can attest the control is operating as designed.

## 6. Solution

A three-layer gateway, deployed as a sidecar/proxy in front of every LLM application.

### Layer 1 — Input classifier
- **Direct-injection signals**: known jailbreak patterns, role-play override, system-prompt extraction probes, multilingual obfuscation, encoding tricks.
- **Indirect-injection signals**: instruction-shaped content in retrieved documents, tool outputs, and customer text; trust-tag every input segment by provenance.
- **Score fusion** across multiple detectors (rules + Llama Guard 3 + fine-tuned DeBERTa + Claude Haiku LLM-judge for hard cases) with calibrated thresholds per app tier.

### Layer 2 — Egress filter
- **PII / credential scrub**: SSN, account, card, secret, token, internal URL.
- **System-prompt leak detector**: model output that reproduces > N tokens of system prompt — block + alert.
- **Cross-tenant bleed detector**: per-session tenant tag; egress carrying off-tenant identifiers is blocked.
- **Model-card / red-team-known-bad pattern matcher**.

### Layer 3 — Tool-call permission gate
- Every tool call is evaluated against (a) which app is calling, (b) whether any input segment was untrusted-provenance, (c) whether the tool's blast radius is within the app's allow-list.
- Untrusted-provenance instructions can never trigger a write/transfer/external-call tool.
- High-blast-radius tools always require human-in-the-loop (interlocks with Project 07).

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| False-block on benign traffic frustrates users | High | Med | Per-app tunable thresholds; shadow-mode rollout for 30 days per app |
| Classifier evaded by novel attack | High | High | Layered defense; weekly red-team replay; rapid signature push |
| Latency hit kills UX | Med | High | Streaming-friendly architecture; cheap-first short-circuit; classifier under 80ms p95 inline; cache benign verdicts |
| Tool-permission policy too strict, blocks real workflows | Med | Med | Co-author per-app policy with App Owner; require dual sign-off to relax |
| Vendor model upgrade changes egress patterns | High | Med | Pin vendor version (interlocks with Project 01); regression-test on upgrade |
| Audit-bundle gaps trigger reg findings | Low | High | Project 08 lineage + signed event chain |

## 8. KPIs

**North star:** % of production LLM traffic routed through the gateway with verified detection on OWASP LLM01 + monthly red-team suite.

**Inputs (leading):**
- Coverage: % of deployed LLM apps behind gateway
- Per-app shadow-mode-to-block transition rate
- Time to push a new injection signature (target ≤ 24h)

**Outputs (lagging):**
- Confirmed data-egress incidents (target: 0)
- Red-team novel-attack catch-rate (≥ 96%)
- False-block rate on benign traffic (≤ 0.4%)
- p95 added latency (≤ 250ms)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Gateway deploy in shadow mode; instrumentation only; no blocks |
| 1 — Internal copilots | 8w | Switch to enforce mode for internal-confidential apps; tier-1 policy |
| 2 — Egress filter GA | 6w | PII/secret/system-prompt egress controls enforced fleet-wide |
| 3 — Tool gate GA | 8w | Tool-permission policy live for all agent workflows |
| 4 — Customer-facing | 12w | Customer chat / public-facing apps moved to enforce; tightest policy |
| 5 — Continuous red-team | ongoing | Weekly novel-attack replay; signature pipeline |

## 10. Open questions

1. Where does the gateway live — sidecar, central proxy, or both? Recommend hybrid: central for policy and audit, sidecar for latency-critical apps.
2. Build vs buy on the input classifier? Recommend ensemble: open-weight detector (Llama Guard 3) + lightweight in-house (fine-tuned DeBERTa) + Claude Haiku LLM-judge for hard cases.
3. What is the model owner's accountability when gateway blocks a benign request? Recommend: app-tier SLO, app-owner co-signs threshold.
4. How do we share signatures across the industry without revealing customer data? Engage with FS-ISAC and BITS as the venue.

## 11. Build & Scale Notes

**Reference architecture (vendor-named).**

- **Gateway dataplane:** Envoy or Istio with a custom WASM filter for lightweight checks; falls through to a Python service for classifier inference.
- **Classifiers (layered):** Llama Guard 3 (cheap first-pass, ~30ms on L4), fine-tuned DeBERTa (indirect-injection signal), Anthropic Claude Haiku (LLM-judge on hard-case escalation only).
- **Egress filter:** Microsoft Presidio + custom regex pack for BFSI-specific identifiers (account numbers, internal URLs, model-card snippets); same Llama Guard 3 model running in egress mode.
- **Pattern store:** Postgres + pgvector for known-bad signatures and red-team artifacts.
- **Tenant identifier registry:** DynamoDB or Cosmos DB depending on cloud — sub-5ms lookup is the requirement.
- **Signature push:** Kafka topic into hot config — sub-five-minute fleet propagation when an active novel attack lands.
- **Async pipeline:** Temporal for red-team replay, signature curation, eval batches.
- **Observability:** Datadog (gateway service health), Langfuse (LLM-judge traces), ClickHouse (high-cardinality block/allow events). Splunk receives a curated stream for the SOC pane.
- **Audit chain:** signed event chain into Project 08 — every block decision carries input hash, classifier ID, score, policy version, app tier.
- **Compute:** L4 GPU fleet for inline classifier inference; CPU for Envoy/Istio; A100 only if bringing classifiers in-house at high QPS.
- **Data plane:** Snowflake or Databricks for evidence-record warehouse; Unity Catalog or AWS Lake Formation for tagging by tenant, app, severity, policy version.

**Throughput envelope and latency budget.**

- Pilot: 200k to 500k LLM calls/day across three internal copilots.
- Steady-state: 5M to 15M LLM calls/day including customer-facing chat.
- Sustained RPS at peak: 1,500.
- Block-decisions/sec at peak: ~60.
- Inline added latency budget: 250ms p95. Cheap first-pass under 80ms; LLM-judge only on the gray-zone short-circuit (~5% of traffic).
- Audit event durability: zero drop; Kafka committed before user response.

**Failure modes and degradation strategy.**

- Classifier service degraded: cheap first-pass continues, heavier classifiers fall to advisory-only (logged, not enforced); CISO alerted within 60 seconds.
- Vendor LLM upgrade detected: gateway auto-flags via Project 01 vendor-pin signal; policy in shadow until red-team replay confirms detection rate.
- Active novel attack landed: signature push pipeline targets sub-five-minute propagation; manual override path with 2-of-2 sign-off (CISO + Platform Security Lead).
- Gateway dataplane down: hard-fail closed for customer-facing, hard-fail open for internal research with explicit log + post-hoc review (configurable per app tier).

**Migration path from current state.**

- Phase 0: deploy in shadow mode on one pilot copilot. No enforce. Two weeks of telemetry to size the egress filter signal-to-noise.
- Phase 1: enforce direct-injection blocks on internal-confidential copilot. Egress filter still shadow.
- Phase 2: enforce egress on PII / credentials. App Owner co-signs threshold per app.
- Phase 3: tool-call permission gate live for any agent workflow consuming customer text.
- Phase 4: customer-facing apps moved to enforce; tightest policy tier; weekly red-team continues.

**Org dependencies.**

- AI Platform Security Lead: build owner.
- CISO / DPO: policy floor and board narrative; signs off on enforce-mode promotion per tier.
- App Owner (per copilot): per-app threshold; co-signs UX trade-offs.
- Model Risk (line 2): MRM L2 sign-off on the classifier ensemble before enforce-mode.
- Internal Audit (line 3): quarterly attestation pack from Project 08.
- InfoSec / SOC: their existing detection rules run in Layer 0 (pre-classifier); fight this fight early.
- Procurement: net-new Langfuse contract; Llama Guard 3 inference cost; Claude Haiku tokens.
- Vendor counsel: confirm MSA disclaimer language doesn't preclude the control set.

---

*This PRD interlocks with Projects 01 (DriftSentinel — vendor pin), 04 (Agent Reliability — gateway events feed reliability surface), 06 (Inference Economics — gateway is the metering point), 07 (HITL — high-blast-radius tools), and 08 (Audit Trail — every gateway event is a lineage record).*
