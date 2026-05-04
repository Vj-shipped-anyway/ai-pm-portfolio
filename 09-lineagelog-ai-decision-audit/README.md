# 📜 LineageLog — AI Audit Trail & Decision Lineage

**Status:** Roadmap · Targeted Q4 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

---

## The bleed

Every regulator from the OCC to the Fed to the EU AI Act says the same thing: explain every AI decision, on demand, for a specific customer at a specific time. NIST AI RMF is explicit about it. EU AI Act Article 12 codifies it. Despite this, decision logs are scattered across 6 vendors, 4 cloud accounts, and 3 logging stacks. Pulling a single decision's lineage for an exam takes 14 days and a paralegal.

## The model deficiency it probes

Most LLM/ML logging captures inputs and outputs but not the *decision-grain lineage*: which prompt, which retrieval set, which model snapshot, which tools called, which features at decision time, which downstream action, which reviewer, which customer, which outcome. Reconstructing one decision after the fact is the hard part.

## What this will be when built

- **Use case:** OCC exam asks "show me how this AI denied this loan to this customer on this date." Today: 14 days of paralegal collation. With LineageLog: 12 minutes.
- **Sample data:** 50,000 synthetic AI decisions across 4 deployed models with full lineage records.
- **Step 1:** Before lineage — inputs/outputs only, scattered across vendors.
- **Step 2:** With basic logging — request/response pairs but no decision context.
- **Step 3:** Six named deficiencies (no prompt versioning, no retrieval-set capture, no model-snapshot pin, no feature-at-decision-time, no reviewer attribution, no outcome backlink).
- **Step 4:** The fix — LineageLog immutable decision-grain lineage layer with sub-minute query, audit-pack export, drill-into-decision view.

## 🏛️ Reference architecture: Agent Identity Logs + Cloud Audit + OpenTelemetry from ADK

Google Cloud's *Building secure multi-agent systems on Google Cloud* (Kannan, Sizemore, Herriford et al.) describes the lineage substrate that LineageLog is built on top of. The paper specifies the data sources; LineageLog composes them into the decision-grain lineage that regulators actually ask for.

**The four lineage signals the paper defines:**

1. **Cloud Logging — system interactions.** As the Case Manager Agent completes a workflow cycle, every system interaction, A2A call, and fulfillment action is captured in Cloud Logging.
2. **Cloud Audit Logs — sensitive resource access.** Specific interactions with Google Cloud services (e.g., BigQuery data access by the Data Vault Agent) are recorded in Cloud Audit Logs separately. This is the "who looked at what data, when" trail.
3. **Agent Identity Logs.** Cryptographically auditable record of when an agent acquired credentials to act autonomously vs. when it used user-delegated tokens (via Agent Identity Auth Manager). The single most underrated trail in regulated AI.
4. **OpenTelemetry traces from ADK.** Send default ADK telemetry to **Cloud Trace** to visualize the agent's chain-of-thought as a waterfall — internal reasoning linked directly to tool executions. The exact shape of "explain this AI decision."

**The decision-grain composition.** A single regulated decision (e.g., "AI denied this loan to this customer on this date") spans all four sources. Pulling it from raw logs is the 14-day-paralegal problem. LineageLog **composes the four sources into a single immutable decision record** indexed by customer/decision/timestamp, with sub-minute query.

**Where LineageLog maps to the paper's controls:**

| LineageLog deficiency | Paper's source signal | LineageLog's composition |
| --- | --- | --- |
| No prompt versioning | ADK session_id + user_id primitives | Prompt + system-instruction snapshot per decision |
| No retrieval-set capture | Cloud Logging on Memory Bank reads | The exact retrieval set bound to the decision |
| No model-snapshot pin | Vendor snapshot ID logged at A2A boundary | Model snapshot pinned per decision (interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5) |
| No feature-at-decision-time | Data Vault's BigQuery MCP audit log | Features fetched, with timestamp and lineage to feature pipeline version |
| No reviewer attribution | Agent Identity Auth Manager (user-delegation) | When user-delegated, the human user ID; when autonomous, the Agent Identity |
| No outcome backlink | Cloud Storage summary report (paper's pattern) | Decision → action → downstream outcome (claim approved, customer complaint filed, charge-off, etc.) |

**The crawl/walk/run alignment.** Crawl: enable ADK telemetry → Cloud Trace, get chain-of-thought visibility on day one. Walk: turn on Cloud Audit Logs for BigQuery + Agent Identity Logs; LineageLog ingests both. Run: full decision-grain composition with sub-minute query, exam-pack export, and integration with the MRM workbench (Archer, ServiceNow GRC, MetricStream — pick what your CRO already pays for).

**The unsexy point.** Most banks have most of these signals. They're scattered across 4 cloud accounts, 6 logging stacks, 3 vendor APIs. The product is not "collect more logs." The product is the **composition layer** that turns log fragments into the decision-grain view a regulator can read in 12 minutes instead of 14 days.

> Source: Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., *Building secure multi-agent systems on Google Cloud*, Google Cloud (2025). Aligned to NIST AI RMF, EU AI Act Article 12, and Google's Secure AI Framework (SAIF).

## Utility math (modeled — priced when built)

- SOTA: 14 days, paralegal-led, fragmented across vendors
- LineageLog: 12 minutes, self-serve, complete lineage in one record
- Affected: every regulated AI decision the bank produces — for a Tier-1 retail bank that's 50-200M decisions per year
- Annual utility: continuous exam-readiness instead of annual fire drills, plus the second-order benefit of internal model improvement when teams can trace bad outcomes to specific contributing decisions

## Status

Roadmap. [HalluGuard](../01-halluguard-bank-chatbot-safety/) is the format reference for when this gets built.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)

<!-- @description 2026-05-04-083532 : LineageLog: AI decision audit trail - every regulated AI decision traced to its inputs, model snapshot, and reviewer -->
