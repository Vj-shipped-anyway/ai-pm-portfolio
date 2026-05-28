# PRD · AgentWatch — Agent Reliability & Tool-Use Observability

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype, designed for engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I would bring to a Tier-1 BFSI shop's Head of AI Platform and CRO in the seat. It is not a record of a PRD landed at a named bank. The six-deficiency taxonomy, the sidecar architecture, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD stub

| Field | Value |
| --- | --- |
| **Product** | AgentWatch — agent reliability and tool-use observability sidecar for deployed multi-step agents (LangGraph / AutoGen / Bedrock Agents / OpenAI Assistants). Six-deficiency taxonomy + per-incident dollar cap + immutable incident pack. |
| **Owner** | Vijay Saharan, Sr PM (BFSI AI Platform). |
| **Stage** | Portfolio prototype, designed for engagement. Synthetic data, no production deployment. |
| **Users** | Primary: Head of AI Platform, Site Reliability (SRE on-call). Secondary: FinOps, MRM (line-2 validators), Internal Audit (L3). Tertiary: line-1 agent owners (claims ops, KYC ops, payments ops). |
| **Problem** | Deployed agents fail in ways pre-LLM apps never did: runaway tool loops ($5–50k per incident), hallucinated tool arguments (PII leak risk), silent agent drift (regressed planning), unbounded blast radius (compounding side-effects), missing reasoning trace (un-defensible failures), cost detached from outcomes (FinOps can't prioritize). Today: 3-week MTTR via FinOps review. Bank pays for the incident AND the post-mortem. |
| **Solution** | Sidecar that ingests the agent framework's OpenTelemetry export, classifies failure under a six-deficiency taxonomy, and enforces a per-incident dollar cap. Six-deficiency taxonomy closed by design: runaway-loop detector, schema validator on tool-call args, tool-call-mix diff vs baseline, blast-radius circuit breaker, long-term reasoning-trace replay store, cost-attribution to downstream business outcome. Per-run incident pack assembled in sub-second on the prototype. |
| **North-star metric** | % of detected agent incidents bounded by AgentWatch's per-incident cap, with a complete six-deficiency incident pack composed within 5 minutes of incident detection time. |
| **Modeled metrics (12-month horizon)** | 🟡 Detection rate of agent-shaped incidents: **0% → 100%** (assumes the synthetic 500-run corpus + Tier-1-style four-agent fleet). 🟡 APM-only detection rate: **~25%** (assumes Datadog with standard p99 thresholds, the other ~75% live and die in the FinOps bill). 🔴 MTTR: **4 hours → &lt;10 minutes** (designed against published BFSI agent-incident review intervals). |
| **Modeled cost** | 🔴 ~$380k for a 90-day engagement in a real deployment (compute on existing OpenTelemetry / Datadog / Langfuse infra + 1 PM + 1.5 FTE engineers + 0.5 FTE SRE partner + 0.25 FTE FinOps partner) — designed, not executed. |
| **Risk #1** | Sidecar back-pressure on the agent runtime. If the OTel export channel saturates, the agent's planner stalls. Solution: stateless sidecar consumers backed by Pub/Sub with at-least-once semantics; agent fails open (continues without observability rather than blocking). |
| **Risk #2** | False-positive cap-tripping on legitimately long-running agents (loan-package assembly can legitimately take 20 minutes). Solution: per-agent dollar cap configurable at deploy time; cap audited under SR 11-7 change control; allow-list flow for known-long-running plans. |
| **Risk #3** | LLM proxy trace TTL outpaces the post-mortem cycle. The vendor's trace store (Langfuse / Helicone) loses traces after 7-15 days; an incident reviewed at week 4 has no chain-of-thought to replay. Solution: AgentWatch's own long-term replay store, indexed by `run_id`, retained for 7 years under SR 11-7. |
| **Out of scope** | (1) Replacing the agent framework — we sidecar, we do not orchestrate. (2) Replacing Datadog / Langfuse — we read from them, we do not collect. (3) Adjudicating disputed agent decisions — we provide reliability, not adjudication. (4) On the request path — sidecar is off the hot path, with a 5-minute compose SLO. (5) Customer-facing surfaces — internal AI-platform tool only. (6) Building a new IdP — we integrate with the bank's existing Okta / Entra ID / Ping. |

---

## 2. Stakeholder map

| Role | Line | Stake | What they want from AgentWatch |
| --- | --- | --- | --- |
| **Head of AI Platform** | Platform | Owns the agent-platform substrate | One pane that classifies agent failure across LangGraph / AutoGen / Bedrock / OpenAI Assistants under a single taxonomy. No new vendor introduced. |
| **Site Reliability (SRE on-call)** | Platform / Ops | Owns the pager rotation | Agent-shaped pages (not "service slow") with the chain-of-thought trace replay attached. Compose-to-page in &lt; 10 minutes. |
| **FinOps** | Platform / Finance | Owns the inference + tool spend | Per-incident dollar cap enforced before the bleed reaches the AWS bill. Cost attributed to downstream business outcome (cost-per-resolved-customer-action). |
| **MRM (Line-2 Validators)** | L2 | Owns model attestation | Reasoning-trace replay store queryable past the LLM proxy's 7-15-day TTL. Effective challenge becomes possible. |
| **Internal Audit (L3)** | L3 | Owns the bank's effective-challenge function | Read-only access to immutable agent_incidents records; sample-pull workflow that does not require pulling 4 log surfaces by hand. |
| **CRO** | L2 oversight | Owns model risk at the portfolio level | Fleet-level reliability metric (incidents bounded per agent per quarter); aging-runs-without-attribution report. |
| **Cloud Security (CISO)** | Platform | Owns the bank's data-handling posture | Workload-identity-based sidecar; no long-lived service-account keys; egress restricted to the bank's VPC; aligns with Google's *Building secure multi-agent systems* pattern. |
| **Line-1 Agent Owners** | L1 | Owns the deployed agent | Incident pack routed to their queue; replay UI showing the chain-of-thought that produced the failure. Retraining feedback loop closed. |
| **Compliance** | L2 | Owns regulator response posture | Incident retention (7 years under SR 11-7); EU AI Act Article 14 (human oversight) audit evidence pulled on demand. |
| **Legal (E&G)** | L2 | Owns disclosure and consent posture | Legal-hold cascade on incidents when a customer complaint is filed; GDPR right-to-erasure cascades to hash deletion. |

---

## 3. RICE-prioritized backlog

> RICE = (Reach × Impact × Confidence) ÷ Effort.
> Status: "Sequenced for v0.x" = committed to a release. "Queued" = will be sequenced after v0.5.

| # | Item | Reach | Impact | Confidence | Effort | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | **OpenTelemetry ingester (v0.1)** — fan-in subscription on the framework OTel export; commit offsets via Pub/Sub. | 100M | 3 | 0.9 | 13 | 20.8 | Sequenced for v0.1 |
| 02 | **agent_incidents schema (v0.1)** — Postgres CREATE TABLE with JSONB columns for the six deficiencies; immutability trigger; HSM-signed row_hash. | 100M | 3 | 0.9 | 5 | 54.0 | Sequenced for v0.1 |
| 03 | **Runaway-loop detector (v0.1)** — per-run tool-call counter; threshold-based + signature-based (same tool, arg-variation) detection. | 100M | 3 | 0.85 | 8 | 31.9 | Sequenced for v0.1 |
| 04 | **Per-agent dollar cap enforcer (v0.2)** — Workload Identity-scoped budget; pre-flight check before each tool call; auto-terminate on breach. | 100M | 3 | 0.8 | 13 | 18.5 | Sequenced for v0.2 |
| 05 | **Schema validator on tool-call args (v0.2)** — pre-flight check against SOT (BigQuery / Snowflake / mainframe DB2); reject fabricated IDs. | 80M | 3 | 0.75 | 13 | 13.8 | Sequenced for v0.2 |
| 06 | **Tool-call mix baseline + drift detector (v0.3)** — 30-day rolling baseline per agent; alert when any tool's share deviates &gt; 20 pp. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.3 |
| 07 | **Blast-radius circuit breaker (v0.3)** — per-incident distinct-tool cap + per-agent dollar ceiling; trip before downstream side-effects fire. | 100M | 3 | 0.8 | 8 | 30.0 | Sequenced for v0.3 |
| 08 | **Long-term reasoning-trace replay store (v0.4)** — ClickHouse-backed event store; query by `run_id` past the LLM proxy's 7-15-day TTL. | 100M | 3 | 0.7 | 21 | 10.0 | Sequenced for v0.4 |
| 09 | **Cost attribution to outcome (v0.4)** — daily ETL joining run cost to downstream business event via `outcome_id`. | 100M | 3 | 0.65 | 13 | 15.0 | Sequenced for v0.4 |
| 10 | **Streamlit prototype (v0.1)** — single-run drill-down, six-deficiency verdict card, incident-pack download. | 1k | 2 | 1.0 | 5 | 0.4 | Sequenced for v0.1 (this repo) |
| 11 | **MRM workbench integration (v0.5)** — push incident_id to Archer / ServiceNow GRC / MetricStream; bidirectional sync on attestation. | 100M | 2 | 0.6 | 13 | 9.2 | Sequenced for v0.5 |
| 12 | **OPA policy gates (v0.5)** — RBAC matrix scoped per region; OPA evaluates every incident-pack export. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.5 |
| 13 | **PagerDuty / Slack routing (v0.5)** — incident-pack delivery to SRE on-call + line-1 owner queues; auto-deduplication by `(agent_id, deficiency_class)` within 1h window. | 100M | 2 | 0.85 | 5 | 34.0 | Sequenced for v0.5 |
| 14 | **GDPR right-to-erasure cascade** — customer_id_hash deletion cascades to incident records (with legal-hold override). | 30M | 2 | 0.7 | 8 | 5.2 | Queued (post v0.6) |

---

## 4. Why now

- **Agent deployment is moving from PoC to production at every Tier-1 BFSI shop.** LangGraph, AutoGen, Bedrock Agents, and OpenAI Assistants are all GA. Banks are wiring 6-11 internal tools to each agent. Failure modes that didn't exist 18 months ago are now live.
- **Anthropic, OpenAI, and Microsoft all publish agent guidance that says the same thing.** Agents fail unpredictably in production. The remediation is per-incident cost bounding + reasoning-trace capture. AgentWatch is the implementation surface.
- **[OpenTelemetry](https://opentelemetry.io/) on agent frameworks is now native.** LangGraph emits OTel spans by default. AutoGen exposes a logging hook. Bedrock Agents and OpenAI Assistants expose vendor-native trace tails. The substrate exists.
- **Vendor model silent updates** make the cost-per-incident question harder every quarter. A silent Anthropic snapshot roll changes the agent's planning behavior; AgentWatch's tool-call-mix drift detector surfaces it.
- **[SR 11-7](https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html) and [EU AI Act Article 14](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)** apply to deployed agents the same way they apply to deployed models. The ongoing-monitoring requirement is the same; the surface AgentWatch implements is the same.

## 5. Goals (12-month horizon)

| Goal | Metric | Target | Tier |
| --- | --- | --- | --- |
| Bound per-incident cost | $ at cutoff per detected incident | unbounded → per-agent cap ($150–$300) | 🟢 |
| Reduce MTTR | Median minutes from incident to mitigation routed | 4h+ → &lt;10min | 🔴 |
| Increase detection coverage | % of agent-shaped incidents detected | ~25% (APM) → 100% (AgentWatch) | 🟡 |
| Zero finding rate | SR 11-7 + EU AI Act Article 14 audit findings related to deployed agents | unknown → zero (designed target) | 🔴 |

## 6. Non-goals

- Not an agent orchestrator — we sidecar, we do not orchestrate. LangGraph / AutoGen / Bedrock / OpenAI Assistants stay the runtime.
- Not an APM replacement — we read from Datadog / OTel, we do not collect.
- Not an adjudication engine — we provide reliability; we do not decide whether the agent's plan was correct.
- Not in the request path — sidecar is off the hot path, with a 5-minute compose SLO.
- Not a customer-facing surface — internal-only.

## 7. User stories

- **As Head of AI Platform**, I want a single pane that classifies agent failure across LangGraph / AutoGen / Bedrock / OpenAI Assistants under a single taxonomy, so I do not have to integrate four vendor consoles.
- **As SRE on-call**, I want the agent-shaped page to arrive with the chain-of-thought trace replay already attached, so I can triage in 6 minutes instead of 60.
- **As FinOps**, I want the per-incident dollar cap enforced before the bleed reaches the AWS bill, so the monthly review is "agent spend was $X" not "agent spend was $X plus $40k of post-mortem."
- **As MRM (Line-2 Validator)**, I want the reasoning-trace replay queryable past the LLM proxy's 7-15-day TTL, so effective challenge becomes possible.
- **As Internal Audit (L3)**, I want read-only access to immutable agent_incidents records, so I can validate effective challenge without pulling four log surfaces by hand.

## 8. Solution detail — the six-deficiency composition

The product is a composition layer. Each deficiency maps to a specific source signal and a specific sidecar action.

| # | Deficiency | Source signal | Sidecar action |
| --- | --- | --- | --- |
| 1 | Runaway tool loops | Framework OpenTelemetry export (per-tool-call span) | Counter; threshold-based + signature-based detection; auto-terminate on cap. |
| 2 | Hallucinated tool arguments | Tool-call args payload from OTel | Pre-flight schema validator against SOT; reject before tool fires. |
| 3 | Silent agent drift | 30-day rolling tool-call-mix per agent | Daily diff vs baseline; alert when any tool's share deviates &gt; 20 pp. |
| 4 | Blast-radius unbounded | Per-run distinct-tool count + accumulated cost | Circuit breaker: per-incident tool-call cap + per-agent dollar ceiling. |
| 5 | No reasoning trace capture | LLM proxy trace tail (Langfuse / Helicone / vendor-native) | Long-term ClickHouse-backed replay store; query by `run_id`. |
| 6 | Cost telemetry detached from outcomes | Daily ETL from downstream business systems (claims platform, KYC case database, etc.) | Join run cost to downstream business event via `outcome_id`. |

## 9. Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 6w | Postgres `agent_incidents` schema; OpenTelemetry ingester; 1 pilot agent (claims_triage_v3). |
| 1 — Runaway + cap | 8w | Runaway-loop detector + per-agent dollar cap enforcer; PagerDuty integration; SRE on-call playbook. |
| 2 — Schema validator | 6w | Pre-flight tool-arg validator; SOT integration (BigQuery / Snowflake / mainframe DB2); allow-list flow. |
| 3 — Drift + blast | 8w | Tool-call mix baseline + drift detector; blast-radius circuit breaker; per-agent allow-list for known-long-running plans. |
| 4 — Reasoning trace + cost | 12w | Long-term ClickHouse-backed replay store; cost-attribution ETL; FinOps integration. |
| 5 — MRM integration | 6w | MRM workbench integration (Archer / ServiceNow GRC); legal-hold workflow. |
| 6 — Multi-region | 12w | EU instance (Frankfurt) + India instance (Mumbai); independent KMS rings. |

## 10. Open questions

1. **Cap-tripping severity.** Should the cap be a hard kill or a graduated throttle? Default: hard kill at the per-agent cap, with a `cap_override` token for line-1 owners with line-2 attestation. Audited.
2. **OTel ingester at-least-once vs exactly-once.** Composition tolerates duplicates (idempotent on `(run_id, deficiency_class)`); ingester is at-least-once for simplicity. Default: at-least-once.
3. **Sidecar location.** Sidecar process on the same K8s pod as the agent (for lowest latency) or separate consumer of the OTel topic (for fault isolation)? Default: separate consumer; the agent fails open if the sidecar is down.
4. **MRM workbench primary integration.** Archer, ServiceNow GRC, or MetricStream first? Depends on the bank's existing license. Default: build the integration as a generic OIDC-based push so the third one isn't a rewrite.

## 11. Build & scale notes

**Reference architecture.** Sidecar runs on Cloud Run (stateless) or as a K8s deployment. Postgres (Cloud SQL with HA + read replicas) holds the immutable `agent_incidents` table; ClickHouse holds the high-cardinality reasoning-trace event stream; GCS Object Lock + cross-region replication holds the WORM archive. The incident pack is generated on-demand from the immutable Postgres row + reasoning-trace replay + cached vendor-snapshot diff.

**Throughput envelope.** At Tier-1 BFSI fleet scale (8-20 deployed agents, ~10-50k runs per agent per day), the sidecar sees ~80-1000 incidents per day. Compose SLO is 5 minutes; the constraint is fan-in latency, not durability.

**Failure modes.**
- *OTel ingester saturation.* Pub/Sub partition-sharded by `agent_id`; consumer autoscales. Backpressure on the producer side is avoided by the at-least-once contract — the agent fails open.
- *SOT lookup latency for schema validator.* Cached point-in-time lookups for 60s; fall back to "validate later" with a `validation_pending` flag if the SOT is slow.
- *LLM proxy trace TTL expired.* AgentWatch's own replay store synthesizes the trace from the OTel + Cloud Logging surfaces; flag `trace_source: synthesized`.

**Migration path.** If the bank is already running an SRE on-call rotation with PagerDuty + Datadog + a FinOps dashboard: AgentWatch ingests into the existing tooling; it does NOT replace the bank's pager or APM. If the bank is on quarterly model attestation only: 6-week foundation phase to wire up the OTel ingester first; incidents get composed as a side-effect; the quarterly attestation gets replaced by continuous monitoring over a 12-month transition.

**Org dependencies.** Internal Audit (L3) signs off on the immutability properties of the `agent_incidents` table. CISO signs off on the field-level encryption + KMS key handling. AI Platform team owns the OTel ingester feed. The MRM workbench owner owns the GRC tool integration (typically a 3-month vendor conversation; start on day one).

---

*This PRD interlocks with [HalluGuard](../01-halluguard-bank-chatbot-safety/) (chat-surface hallucination), [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) (model-snapshot drift), [PromptShield](../06-promptshield-prompt-injection-defense/) (prompt-injection defense at the agent gateway), [OversightOps](../08-oversightops-hitl-workflow/) (HITL workflow for cap-override), and [LineageLog](../09-lineagelog-ai-decision-audit/) (decision-grain lineage on individual agent decisions).*
