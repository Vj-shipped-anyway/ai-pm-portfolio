# PRD · Hallucination Containment for Bank Chatbots

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.0 — pre-Trust & Safety Council read
**Date:** 2026-Q2

---

## 1. Problem

Bank chatbots in production confidently misstate rates, fees, account terms, and regulations. The model is not the lever. Vendor models change underneath us, hallucination is structurally unsolved, and BFSI cannot wait on the research frontier. The lever is a containment layer that wraps the deployed chatbot and refuses to pass an ungrounded claim to a customer. Today, that layer is a thin disclaimer in the footer. The result is incident-after-incident, each handled as a one-off remediation while the underlying posture stays unchanged.

I've watched this pattern at three different shops. The remediation cost adds up. The brand cost adds up faster.

**Primary user:** Head of Digital Customer Experience (line 1, business owner).
**Secondary user:** Trust & Safety / AI Risk lead (line 2).
**Tertiary user:** Compliance, with mappings to Reg DD, Reg E, Reg Z, and Reg B.

## 2. Why now

- Anthropic, OpenAI, and the broader research community have publicly stated factuality is unsolved. The frontier is not arriving in time for a 2026 chatbot launch.
- Public bank-chatbot hallucination incidents are now quarterly news. CFPB attention is rising.
- Knowledge-graph and retrieval-grounded approaches are mature enough to deploy as a containment layer without model retraining.
- The cost asymmetry is clear: a single rate-hallucination remediation cycle costs more than a year of containment-layer operation.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Cut hallucination rate | Hallucinations / 1k turns on probe set | -71% |
| Hold deflection | End-to-end self-service deflection | At or above 64%, vs 67% baseline |
| Lift customer trust | NPS on chatbot interactions | +14 |
| Prevent loss | Modeled prevented loss (modeled, not measured) | $11M/yr |

## 4. Non-goals

- Not a chatbot. Wraps existing chatbots — vendor or in-house.
- Not a model fine-tuner. No retraining.
- Not a knowledge-graph platform. Consumes the existing product, rate, and reg KG.
- Not the eval-first console (Project 02), but interlocks for probe authoring.

## 5. User stories

- **As Head of Digital CX**, I want every rate, fee, and reg claim grounded against the product source of truth before it reaches a customer, so I'm not in the next CFPB headline.
- **As Trust & Safety**, I want abstention with warm handoff (not a refusal wall) when confidence is below threshold, so the customer is served and the regulator is satisfied.
- **As Compliance**, I want a probe schedule that hits Reg DD, Reg E, Reg Z, and Reg B claims continuously, with auto-quarantine on regression, so I learn about a problem from the system, not from a complaint.
- **As an AI Platform Lead**, I want the containment layer to be model-agnostic, so it survives vendor model swaps without re-architecting.

## 6. Solution

A three-guard containment layer.

### Guard 1 — Ground
- Atomic-claim extractor (Anthropic Claude Sonnet with constrained JSON output) parses every response candidate for rate, fee, term, regulation reference, and account-behavior claims.
- Each atomic claim is checked against the authoritative knowledge graph: product catalog and rate sheet in Postgres, reg-claim graph in Neo4j.
- Ungroundable or contradicted claims trigger rewrite-or-refuse.
- Source citations attached to every response with a grounded claim.

### Guard 2 — Abstain
- Calibrated confidence score per response (interlocks with Project 02 evals).
- Below threshold: escalate to a live agent with full conversation context, intent classification, and pre-extracted account context.
- Threshold is per-intent, not global. Owned by Head of CX with quarterly Compliance co-sign.
- Abstention is treated as a successful interaction, not a failure metric.

### Guard 3 — Probe
- Continuous red-team probe schedule. Hourly on hot intents, daily on cold.
- Probes derived from incident history, regulatory reference, and adversarial prompt mining.
- Auto-quarantine: on probe-set regression over X%, the use case is taken out of customer flow within 5 minutes; routed to handoff until cleared.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| KG stale | High | High | Hourly Kafka sync from rate/fee/product source-of-record; staleness SLO of 60 min with auto-degrade to higher abstention |
| Over-abstention (deflection collapse) | Med | High | Calibration set; per-intent threshold tuning; 3-point give-back budget |
| Probe set captures wrong adversaries | Med | Med | Rotate probes monthly; mine from incident log; co-author with Compliance |
| Vendor model change breaks grounding | High | High | Model-agnostic claim extractor; re-baseline on every vendor pin change (Project 02) |
| Handoff capacity insufficient | Med | High | Capacity planning by intent forecast; abstention rate is a real input to staffing |
| Prompt-injection bypasses ground guard | Med | High | Treat customer turn as untrusted input; interlock with Project 05 |

## 8. KPIs

**North star:** Hallucinations per 1k customer-facing turns on the live probe set.

**Inputs (leading):**
- Grounding rate: % of atomic claims verified against the KG.
- KG freshness: median minutes since last sync.
- Abstention precision: % of abstentions that were correctly out-of-zone.
- Probe coverage: % of regulated claim types under probe.

**Outputs (lagging):**
- Hallucination rate, probe and live.
- Deflection rate (must hold within 3 points of baseline).
- Customer trust NPS.
- Compliance incidents related to chatbot statements. Target zero.

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Wire to product/rate/fee KG; baseline hallucination rate on probe set; pick the intent with the most recent public incident |
| 1 — Ground guard | 8w | Atomic-claim extractor + KG check; rewrite-or-refuse |
| 2 — Abstain guard | 6w | Confidence calibration + warm handoff with context; per-intent threshold |
| 3 — Probe guard | 8w | Continuous probe scheduler + auto-flag (auto-quarantine deferred to v2) |
| 4 — Fleet rollout | 12w | All customer-facing chatbot intents |

## 10. Open questions

1. Threshold authority — who owns the abstention threshold? Recommend Head of CX with quarterly Compliance co-sign.
2. Auto-quarantine authority — does the system pull a use case from customer flow without human approval? Recommend deferred to v2 with a 4-hour exec notification SLO; v1 is auto-flag and recommend.
3. Source of truth for regulations — internal compliance KB or external feed? Recommend internal, attested quarterly.
4. Handoff staffing model — is abstention forecast an input to call-center planning? Recommend yes, with monthly recon.
5. Vendor chatbots that don't expose intermediate logits — do we ground post-hoc on output text, or block deployment? Recommend post-hoc grounding as a fallback, with a roadmap to require logit access.

## 11. Build & Scale Notes

**Reference architecture.**
- Wrapped chatbot model: vendor's choice. Could be Anthropic Claude Sonnet via AWS Bedrock, Azure OpenAI gpt-4o, or an in-house fine-tuned Llama-3 70B on Triton. The containment layer is model-agnostic by design.
- Atomic-claim extractor: Claude Sonnet with a tightly-constrained JSON schema. Rewrite-or-refuse generator: same Claude Sonnet with a constraint that it can only emit grounded content or a refusal.
- Vector / retrieval: Postgres + pgvector for the rate, fee, and product KG embeddings. Catalog at a typical retail bank lands at 50K to 200K chunked entries — pgvector handles that at sub-30ms p95. Skip Pinecone here; the operational cost isn't worth it under 5M entries.
- Knowledge graph: Neo4j for the reg-claim graph (Reg DD, Reg E, Reg Z, Reg B nodes with conditional relationships). Postgres for relational claims (rates, fees, product attributes).
- Source-of-record sync: Kafka spine. Hourly sync from the product catalog, rate sheet, and fee schedule into the KG. 60-minute staleness SLO with auto-degrade.
- Orchestration: Temporal for the multi-step claim-extract → ground-check → rewrite-or-refuse → log workflow. LangGraph for conversational state across turns.
- Observability: OpenTelemetry as substrate. Datadog for SOC and CX SLOs. Langfuse for conversation traces. ClickHouse for the high-cardinality per-claim grounding event store.
- Compute: Sub-200ms latency budget on the containment layer end-to-end. T4 or L4 GPUs in-region for claim extraction and grounding. Serverless (Lambda or Cloud Run) for the lighter routing.
- Data plane: Snowflake or Databricks for the audit and analytics warehouse. Unity Catalog or Lake Formation for lineage. Every grounded claim, abstention, and refusal logged with rubric version, KG snapshot, and model snapshot.
- Security: SOC 2 Type II, GLBA, PCI-DSS where in scope. Containment layer is treated as untrusted-input-handling code. Interlocks with Project 05 for prompt-injection defense.

**Throughput envelope and latency budget.**
- 200K to 800K customer turns per day at the $50B-asset retail bank shape.
- Containment layer adds 100 to 200ms per turn. Peak around 100 to 400 claim-extractor inferences per second.
- T4/L4 GPU pool with auto-scaling. End-to-end (chatbot + containment) p95 under 1.5 seconds.

**Failure modes and degradation strategy.**
- KG staleness over the 60-minute SLO: auto-degrade to a higher abstention threshold; flag the use case as degraded; notify ops.
- Claim extractor unavailable: fall back to a more conservative grounding heuristic (block any response containing a numeric rate or fee until restored).
- Vendor model snapshot change: re-baseline the extractor prompt on the new snapshot before customer traffic resumes; coordinated with Project 02.
- Probe-set regression: in v1, auto-flag and exec-notify; in v2, auto-quarantine within 5 minutes.
- Abstention spike beyond contact-center capacity: degrade gracefully to a softer threshold; alert ops.

**Migration path from current state.**
- If the bot is on Kore.ai, Cognigy, LivePerson, or Microsoft Bot Framework: the containment layer integrates as a webhook between the model output and the customer surface. We do not replace the chatbot platform.
- If the bank already has a product catalog API and a rate-sheet API: the wedge is the KG schema and the Kafka sync; the rest is greenfield.
- If the bot is a vendor black box that doesn't expose the response candidate before send: we ground post-hoc on the output text. It works, but with a roadmap to require pre-send hook access by the next vendor renewal.

**Org dependencies.**
- Head of CX co-owns the abstention threshold and signs off on the deflection trade.
- Trust & Safety owns the probe set, the auto-flag thresholds, and the eventual auto-quarantine authority.
- Compliance attests to the KG content quarterly and co-signs every probe added under Reg DD, Reg E, Reg Z, or Reg B.
- Contact center owns the handoff SLO and the staffing model. Get the abstention-rate forecast into their planning cycle from day one.
- Source-of-record owners (rate sheet, fee schedule, product catalog) commit to the 60-minute Kafka sync SLO. This is the dependency that breaks the product if it slips.
- Internal Audit (line 3): read-only and an interlock with Project 08.

---

*This PRD interlocks with Projects 01 (DriftSentinel), 02 (Eval-First Console), 05 (Prompt-Injection Defense), 07 (LLM Red Team) and 08 (Audit Trail).*
