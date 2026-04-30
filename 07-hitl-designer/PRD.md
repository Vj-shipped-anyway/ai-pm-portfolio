# PRD · Human-in-the-Loop Workflow Designer

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.1 — pre-Risk + Ops joint read
**Date:** 2026-Q2

---

## 1. Problem

BFSI bolts "human approval" onto AI workflows as a checkbox to clear the audit memo. The bolt-on doesn't measure review quality, doesn't enforce a review SLA, and doesn't balance reviewer load against confidence. Under volume, reviewers rubber-stamp at sub-10-second dwell and the control becomes ceremonial. Frontier guidance — Anthropic's model spec, OpenAI's usage policies, Lilian Weng's safety writing — is unanimous that human oversight is the safety lever; the lever fails when nobody designed it. The bank ends up with a control that's attestable but not effective, and the gap shows up only after a loss event or a reg finding.

**Primary user:** AI Workflow Owner (line 1, the PM/ops lead deploying the agent).
**Secondary user:** Operations Reviewer (line 1, the human in the loop).
**Tertiary user:** Model Validator / Audit (line 2, attesting the control operates as designed).

## 2. Why now

- Agentic systems with high-blast-radius tool use (Project 05 Layer 3) are landing in production. They need designed human checkpoints, not bolted-on ones.
- Regulator expectations on AI explainability and human override are tightening (CFPB, OCC, NYDFS).
- AI-decision volume per day is past the point where unmeasured human review is even nominally credible.
- Frontier model providers explicitly disclaim that oversight is the deployer's responsibility.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Review SLA enforcement | p95 review latency across workflows | 24h to 35min |
| Oversight-gap closure | % of high-stakes decisions reaching a reviewer | baseline to 96% |
| Review-quality measurement | Kappa vs ground-truth audit | unmeasured to at least 0.75 |
| Rubber-stamp suppression | % approvals with dwell under 15s | unmeasured to under 4% |
| Reviewer load balance | Gini coefficient on case assignment | 0.42 to under 0.20 |

## 4. Non-goals

- Not a case-management system (interlocks with the existing one).
- Not a reviewer-hire-or-fire system (signals quality, doesn't make HR decisions).
- Not a model that decides in place of the human (router, not decider).

## 5. User stories

- **As a Workflow Owner**, I want to compose a HITL workflow visually — confidence tiers, reviewer pools, SLAs, escalation paths — so I ship oversight that's actually designed, not retrofitted.
- **As a Reviewer**, I want a sized queue with case context, suggested verdict, and time budget, so I'm calibrated, not drowning.
- **As a Validator**, I want a workflow design artifact and reviewer-quality time-series, so I can attest the control is operating as designed.
- **As an Auditor**, I want every reviewer decision in a signed event chain (Project 08), so I can replay any case end-to-end.

## 6. Solution

A three-loop product: visual designer, runtime router, quality-measurement surface.

### Loop 1 — Design
- **Confidence-tier router:** decisions above tier-1 threshold auto-approve, tier-2 sample-route to review, tier-3 always-route, tier-4 abstain or escalate.
- **Reviewer-pool composer:** pools by skill (AML, credit, KYC), with capacity and shift coverage.
- **SLA dial:** per-tier SLA, with auto-reroute on miss.
- **Abstention/escalation paths:** explicit dead-ends for "neither approve nor deny — escalate to senior reviewer or specialist."
- **Preview:** run a synthetic batch through the design before deploying.

### Loop 2 — Operate
- **Runtime router** consumes decisions from upstream agents (often via Project 05 Layer 3 high-blast-radius funnel).
- **Queue manager** balances load across reviewers with capacity, skill, and freshness signals.
- **SLA monitor** reroutes if a queue is about to breach.
- **Reviewer UI** shows case, AI suggested verdict, confidence, and time budget; enforces minimum dwell on tier-3 cases.

### Loop 3 — Measure
- **Reviewer-quality kappa** vs sampled ground-truth audit cases blended into the live queue.
- **Rubber-stamp metric:** % approvals at sub-15s dwell (with case-difficulty normalization).
- **Calibration drift:** reviewer-by-reviewer agreement vs panel consensus over time.
- **Routing health:** distribution by tier, abstention rate, escalation rate, SLA compliance.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reviewer over-trust of AI suggested verdict | High | High | Hide AI suggestion on a 10% blind sample per reviewer per week; measure agreement |
| Rubber-stamp metric gamed by holding mouse | Med | Med | Composite signal: dwell + scroll + cursor + active window |
| Confidence calibration drift on upstream model | High | High | Recalibrate tier thresholds quarterly (interlocks with Project 01) |
| HR consequences from quality metric | Med | High | Quality is for calibration + coaching; explicit no-direct-HR policy in v1 |
| Reviewer fatigue under high volume | High | Med | Capacity caps; rotate; cross-train pools |
| Workflow-design complexity scares Workflow Owners | Med | Med | Templates per use case (AML, credit, KYC, GenAI moderation) |

## 8. KPIs

**North star:** % of high-stakes AI decisions reviewed within SLA, at reviewer-quality kappa at or above 0.75, with rubber-stamp rate under 4%.

**Inputs (leading):**
- Coverage: % of AI workflows on the designer
- % of workflows with PM-signed reviewer-pool capacity model
- Quality-audit blend rate (target 5–10% of live queue)

**Outputs (lagging):**
- Review SLA p95 (target under 35min)
- Reviewer-quality kappa (target at or above 0.75)
- Rubber-stamp rate (target under 4%)
- Oversight-gap closure on high-stakes decisions
- Reg-exam findings on AI oversight (target: 0)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Designer GA; one pilot workflow (AML alert review) |
| 1 — Pilot expand | 8w | Add credit-exception review; reviewer-quality blending live |
| 2 — Confidence tiers GA | 6w | All pilot workflows on tiered routing; SLA monitor enforcing reroute |
| 3 — Quality measurement GA | 8w | Kappa + rubber-stamp metric live; calibration coaching loop established |
| 4 — Tool-gate funnel | 8w | Project 05 Layer 3 high-blast tools route here by default |
| 5 — All workflows | 12w | Cover all production AI decision workflows |

## 10. Open questions

1. Reviewer-quality metric — feedback to reviewer (yes), feedback to manager (yes, aggregated), feedback to HR (no in v1, revisit in v2 with policy).
2. Abstention isn't a "no-decision" — it's a decision. Where does an abstained case go? (Recommend: senior-reviewer queue, with audit.)
3. Auto-approve floor — what confidence threshold makes auto-approve defensible? (Recommend: per-workflow, with eval evidence and Validator co-sign.)
4. Multi-reviewer consensus — for Tier-1 high-stakes (e.g., over $500k credit), require 2-of-2 reviewers? (Recommend yes for top tier; cost is real but defensible.)

## 11. Build & Scale Notes

**Reference architecture (vendor-named):**
- Inbound decision events from upstream agents land on Kafka (Confluent Cloud or self-hosted MSK). One topic per workflow.
- Router service is a deterministic policy engine in Go, packaged as a container, deployed on EKS. Not an LLM. Decisions about routing must be auditable line-by-line.
- Confidence calibration uses Platt scaling / isotonic regression on the upstream model's raw scores, retrained quarterly via Airflow against a held-out validation set in Snowflake.
- Reviewer queue and SLA orchestration on Temporal Cloud. Long-running workflows with deterministic retry and timeout semantics.
- Case-context summarizer for the reviewer UI is Claude Sonnet via the Anthropic API or Bedrock for shops with that BAA. Azure OpenAI gpt-4o is the alternate where the bank's BAA already covers it. The summarizer never decides — it only assists.
- Case-similarity retrieval on Postgres with pgvector. Volumes are well within pgvector's envelope at BFSI HITL scale.
- Reviewer-decision events written to an append-only event store (the Project 08 ledger) with hash-chaining.
- Observability: OpenTelemetry into Datadog for runtime; Langfuse for LLM summarization spans.
- Analytics: Snowflake, with Unity Catalog or Lake Formation for lineage on the reviewer-decision table.

**Throughput envelope and latency budget:**
- Designed for 2M decisions/day across a Tier-1 bank's portfolio. ~94% auto-clear above tier-1 threshold; ~6% reach a human.
- Routing decision: under 50ms p99. This is non-negotiable — the router can't be a bottleneck.
- Case-context summarization: 1.2s p50, 3.5s p99 (Claude Sonnet, 6-bullet summary, ~1.5K input tokens). Reviewer doesn't wait — the summary is generated at enqueue time.
- Reviewer dwell budget: enforced minimum on tier-3 cases (15s). p95 review latency target: 35 min.

**Failure modes:**
- Upstream model recalibrates and tier thresholds become stale. Mitigation: drift signal from Project 01 forces a recalibration window.
- Kafka backpressure during a peak ingestion event. Mitigation: bounded queue depth per reviewer, overflow to senior pool with explicit "overload" tag.
- LLM summarizer hallucinates context. Mitigation: every summary cites which case-payload fields it used; reviewer can collapse the summary and read raw.
- Temporal cluster failure during an in-flight review. Mitigation: workflow state is durable; on recovery, review resumes; SLA clock paused during outage and audit-logged.

**Migration path:**
- Phase 0–1 stand up the designer alongside the existing review queue with read-only mirroring. No production routing yet.
- Phase 2 takes one workflow (AML alert) live with shadow routing for 2 weeks, then cutover.
- Phase 3 adds credit-exception with the same shadow-then-cutover pattern.
- Phase 4–5 expand. Each workflow needs a fresh capacity model from the workflow owner before cutover.
- Existing case-management system remains the reviewer's primary UI; this designer drives routing and SLA, not the case UX.

**Org dependencies:**
- Line 1 workflow owner (PM/ops) signs the design.
- Line 2 model risk / compliance signs the design's fitness before cutover.
- Line 3 internal audit tests quarterly.
- HR + employee relations co-sign the "no direct HR consequence in v1" policy on reviewer-quality metrics. This is the political path-dependency — without it, you don't ship.
- Project 01 (drift) feeds calibration triggers. Project 08 (audit trail) consumes reviewer-decision events.

---

*This PRD interlocks with Projects 01 (confidence calibration drift), 05 (high-blast-radius tool calls funnel here), and 08 (every reviewer decision is a signed audit event).*
