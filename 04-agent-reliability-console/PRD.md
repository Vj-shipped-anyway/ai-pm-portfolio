# PRD · Agent Reliability & Tool-Use Observability

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.0 — pre-AI Platform + SRE council read
**Date:** 2026-Q2

---

## 1. Problem

BFSI is putting ops agents — reconciliation, dispute, KYC refresh, AML alert triage — into production with no behavioral telemetry. SREs have token-bill dashboards and Slack alerts on agent crashes. They don't have a view of tool-call loops, tool misuse (wrong tool for intent), runaway reasoning chains, schema drift in tool I/O, or blast-radius blowouts. The first signal of failure is a vendor invoice or a downstream complaint. The unit of observation in a traditional SRE stack is the request; for agents, the unit is the trajectory. That gap is the entire product.

**Primary user:** SRE / Platform Reliability Engineer (line 1).
**Secondary user:** Agent Use-Case Owner (business owner of the deployed agent).
**Tertiary user:** AI Risk and Internal Audit (line 2/3).

## 2. Why now

- Anthropic, OpenAI, and the agent-platform community publicly identify tool misuse, loops, and budget blowouts as the dominant production failure modes.
- Every Tier-1 US bank now has 3–10 ops agents in production or pilot. None I've seen have a unified reliability surface.
- Token-bill costs have crossed the threshold where finance is asking why the line item moves.
- Audit committees are starting to ask: "what is your blast-radius limit for an autonomous agent?" Most shops do not have an answer today.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Cut tool misuse | Tool-misuse rate on deployed fleet | -83% |
| Eliminate runaway $/incident | $ lost to single-trajectory runaway | -> 0 |
| Compress incident MTTR | Median wall-clock to resolution | 4h -> 7m |
| Establish reliability SLO | Agent reliability SLO | unmeasured -> 99.4% |
| Prevent loss | Modeled prevented loss | $7M/yr |

Numbers are modeled against synthetic traffic on three pilot agents with shapes I've seen on real BFSI ops deployments. Treat them as the order of magnitude, not the precise hit.

## 4. Non-goals

- Not an agent-building framework. Consumes deployed agents from any framework (LangGraph, Temporal, custom).
- Not a tool registry. Interlocks with the existing one.
- Not an LLM gateway. Interlocks with Project 06 for cost and Project 05 for security.
- Not the audit trail. Writes events into Project 08.

## 5. User stories

- **As an SRE**, I want every deployed agent trajectory captured with tool calls, durations, tokens, and intent classification, so I can triage from behavior, not from a token bill.
- **As a Use-Case Owner**, I want a circuit breaker on my agent (tokens, dollars, wall-clock, tool-call count) so a single bad trajectory cannot cost me a quarter's budget.
- **As Internal Audit**, I want a documented blast-radius limit per agent and evidence the limit is enforced in production, so I have a real answer to "what could go wrong."
- **As an Agent Engineer**, I want failed trajectories replayable in a UI so I can debug a 47-step tool sequence without grepping logs.

## 6. Solution

A three-loop product.

### Loop 1 — Observe
- Trajectory capture: every tool call, duration, token count, schema check, intent classification.
- Failure-mode classifiers running continuously:
  - **Loop detector** — repeated tool calls with similar args within a window.
  - **Misuse classifier** — predicted intent vs. tool taxonomy mismatch.
  - **Runaway detector** — token / wall-clock / step count vs. learned envelope per intent.
  - **Schema-drift sentinel** — tool I/O schema vs. live API contract.
- Per-agent reliability dashboard with SLO and error budget.

### Loop 2 — Contain
- Per-agent budgets in four dimensions: tokens, dollars, wall-clock, tool-call count.
- Blast-radius circuit breaker — fires on classifier hit or budget exceed; halts the trajectory.
- Emergency stop: pull a use case from automation; route to human queue.
- Quarantine: an agent whose classifier-hit rate exceeds threshold is taken out of production until cleared.

### Loop 3 — Replay
- Failed-trajectory replay UI: step through tool calls, intent classifications, prompt state, schema diffs.
- Canonical-trajectory comparison: diff a failed trajectory against the canonical successful trajectory for the same intent.
- Postmortem-as-data: every replay session generates a structured incident artifact for audit.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Telemetry overhead breaks agents | Med | High | Async OTel exporters; sampling for high-throughput agents; circuit breaker on telemetry overhead itself |
| Classifier false positives | High | Med | Per-agent calibration; misuse classifier requires 2-of-3 signals to fire breaker |
| Budget caps too tight | Med | Med | Adaptive budgets per intent class; owner-tunable with audit |
| Replay PII exposure | Med | High | Trajectory data tokenized at capture; replay UI scoped by role |
| Schema sentinel misses silent updates | Med | High | Daily schema diff job + snapshot retention 90 days |

## 8. KPIs

**North star:** Agent reliability SLO — % of trajectories that complete within (intent budget, schema valid, no classifier hit).

**Inputs (leading):**
- Coverage: % of deployed agents instrumented
- Classifier-hit precision (target ≥ 0.90)
- Budget-cap adherence: % of trajectories within four-dim budget
- Schema-drift sentinel freshness

**Outputs (lagging):**
- Tool-misuse rate
- Runaway $/incident
- Agent-incident MTTR
- Audit findings on agent governance (target: 0)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Trajectory capture; instrument 3 pilot agents (recon, dispute, KYC) |
| 1 — Classifiers | 8w | Loop, misuse, runaway, schema-drift detectors GA |
| 2 — Containment | 6w | Four-dim budgets; circuit breaker; emergency stop |
| 3 — Replay UI | 6w | Trajectory replay; canonical-trajectory diff |
| 4 — Fleet rollout | 12w | All deployed ops agents |
| 5 — SLO + governance | 6w | Reliability SLO published; audit attestation pack |

## 10. Open questions

1. SRE org vs. AI/ML org ownership — recommend SRE owns reliability, AI/ML owns capability. The console is an SRE tool with AI/ML inputs. The political fight is real; SRE wins because they run the pager.
2. Circuit-breaker authority — system halts without human approval, posts a 4-hour exec notification. Confirm with Risk.
3. Tool descriptions as a regulated artifact — does every tool a regulated agent can call require Compliance attestation? Recommend yes for write-tools, no for read-tools.
4. Replay PII handling — how long do we retain trajectories with customer data? Recommend 90 days hot, 365 days cold-with-tokenization.
5. Schema sentinel — pull-based or contract-based? Recommend contract-based (consume API gateway schemas) with pull-based fallback.

## 11. Build & Scale Notes

**Reference architecture (vendor-named).**

- **Agent runtimes (consumed, not built):** LangGraph and Temporal predominantly; some teams on a homegrown harness on top of Anthropic Claude Sonnet or Azure OpenAI gpt-4o-mini.
- **Telemetry substrate:** OpenTelemetry GenAI semantic conventions, OTel collectors fronted by Kafka (or AWS MSK).
- **Trace store:** ClickHouse cluster (12-node baseline). Datadog priced out at this cardinality; Splunk sees only classifier-hit events.
- **LLM-trace surface:** Langfuse for prompt versions, replay, and eval ties.
- **Classifier layer:** fine-tuned Mistral 7B on Bedrock for the misuse classifier; xgboost for the runaway envelope; sliding-window dedup for the loop detector.
- **Tool-taxonomy embedding store:** Postgres + pgvector. Skip Pinecone — corpus is ~10k tool descriptions and pgvector handles it through ~50M.
- **Console workflows:** Temporal for replay-snapshot generation, classifier batch retraining, schema-diff cron.
- **Warehouse and lineage:** Snowflake or Databricks (whichever is the bank standard) with Unity Catalog or AWS Lake Formation for trajectory provenance. Collibra if it's already deployed for the broader catalog.
- **Compute:** T4 / L4 for inline classifier inference (50ms p95 inline budget); A100 for replay sandbox if Claude-class; CPU otherwise.

**Throughput envelope and latency budget.**

- v1 fleet: 200k trajectories/day across 3 pilot agents.
- Steady-state fleet: 2M to 5M trajectories/day across 10 agents.
- Trace pipeline: 30k events/sec at peak (one trajectory = 8 to 40 events).
- Inline classifier budget: 50ms p95. Anything heavier moves to async lane.
- Trace ingest p99 to query: under 5 seconds for SRE triage flows.

**Failure modes and degradation strategy.**

- Telemetry pipeline down: agents continue, traces buffer at OTel collector for 30 minutes, then sampled-fallback (1-in-10) until catch-up.
- Classifier service down: budget caps still enforce (they live at the gateway), but advisory hits go silent. SRE alerted within 60 seconds.
- ClickHouse cluster degraded: writes hit Kafka durable buffer; reads fall back to last 24h hot tier on Postgres for triage.
- Circuit breaker stuck-on (false positive storm): owner-level override gated by 2-of-2 sign-off (use-case owner + SRE).

**Migration path from current state.**

- Phase 0: deploy OTel collector sidecar in shadow alongside existing token-bill dashboard. No behavior change.
- Phase 1: turn on trace capture for one pilot agent in non-prod. Validate cardinality and cost.
- Phase 2: shadow classifiers in prod (alert-only, no enforce). Tune thresholds for 30 days per agent.
- Phase 3: enforce four-dimensional budget caps on pilot agent. First save = first credibility.
- Phase 4: classifier enforcement, then fleet rollout.

**Org dependencies.**

- SRE org: owner. Headcount ask 3 FTE (one PM, two SREs).
- AI/ML platform: provides classifier-training pipeline and model versioning.
- InfoSec: signs off on telemetry data path; expect a fight on the ClickHouse-vs-Splunk question (resolve by feeding Splunk classifier-hit events only).
- Model Risk (line 2): MRM L2 sign-off on classifier validation before enforcement.
- Internal Audit (line 3): receives evidence packs out of Project 08.
- Procurement: net-new ClickHouse + Langfuse contracts, plus existing Datadog / Splunk renegotiation.

---

*This PRD interlocks with Projects 06 (Inference Economics — same gateway meters), 05 (Prompt-Injection — gateway events feed both surfaces), and 08 (Audit Trail — every classifier hit and breaker fire becomes a lineage record).*
