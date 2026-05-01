# 🤖 AgentWatch — Agent Reliability & Tool-Use Observability

**Status:** Roadmap · Targeted Q3 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

---

## The bleed

Anthropic's agentic research and OpenAI's agent docs both say the same thing: agents fail unpredictably in production. They loop. They mis-call tools. They blow token budgets. Despite this, BFSI is now deploying ops agents into reconciliation, dispute, and KYC refresh workflows with **zero failure-mode telemetry**. SREs see token bills, not behavior. The first time anyone notices a runaway agent is when FinOps flags the line item.

## The model deficiency it probes

Production agent failure modes that don't show up in traces designed for traditional services: tool-call loops, schema drift on tool arguments, runaway reasoning chains, blast-radius violations, silent tool misuse (right schema, wrong tool for intent).

## What this will be when built

- **Use case:** A bank's deployed reconciliation agent on Anthropic Claude with 6 internal tools (ledger lookup, customer match, dispute file, etc.) — burns its monthly budget in 9 days because something's looping.
- **Sample data:** Synthetic agent trajectories with token counts, tool calls, durations, intent labels. Five named failure modes injected.
- **Step 1:** Before agent observability — token bills as the only signal.
- **Step 2:** With basic LLM tracing (Langfuse / OpenTelemetry) — visible spans but no failure-mode classifier.
- **Step 3:** Five named agent deficiencies (tool-call loops, schema drift, runaway reasoning, blast-radius violation, tool-intent misuse).
- **Step 4:** The fix — AgentWatch console with loop detection, tool-misuse classifier, blast-radius circuit breaker, replay UI for failed trajectories.

## 🏛️ Reference architecture: the secure multi-agent pattern AgentWatch observes

Google Cloud published a reference architecture in *Building secure multi-agent systems on Google Cloud* (Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., Google Cloud) that frames the canonical shape of a defensible multi-agent system. AgentWatch is the observability and reliability layer **on top of** that pattern. The paper specifies the controls; AgentWatch tells you when they break in production.

**The Warranty Claim System reference (Gemini Enterprise Agent Platform).** A claim flows through three agents with strict security boundaries:

- **Case Manager Agent** — orchestrator on Agent Runtime. Goal-bounded to workflow routing only. No direct DB or external-API access.
- **Data Vault Agent** — read-only retrieval on Agent Runtime, exclusive IAM access to a Google Cloud MCP Server for BigQuery, blocked from public egress via VPC Service Controls.
- **Logistics Liaison Agent** — fulfillment executor on Cloud Run, scoped Workload Identity, egress restricted to pre-approved vendor URLs via a Secure Web Proxy. Includes an asynchronous HITL "Approve" interrupt before any shipping label fires.

Defense-in-depth controls: **Model Armor** scrubs prompts at the gateway (prompt injection, PII, jailbreaks). **Agent Identity** (SPIFFE-backed, mTLS, certificate-bound tokens) replaces shared service accounts. **Agent Gateway** + IAP enforces zero-trust IAM allow policies on every A2A and MCP call. **ADK BeforeToolCallback** runs deterministic input validation (e.g., reject non-12-digit serial numbers before the BigQuery MCP fires). The double-guardrail pattern: **IAM boundaries** (deterministic, technical) + **Semantic Governance Policies** (intent-aware — "even if the call is authorized, the payload cannot trick the Liaison into a 100% discount code").

**Where AgentWatch maps to the paper's controls:**

| AgentWatch deficiency | Google paper control / failure mode |
| --- | --- |
| Tool-call loops | Cloud Trace chain-of-thought visibility — AgentWatch alerts when the trace shows looping despite SCC anomaly detection allowing it |
| Schema drift on tool arguments | ADK BeforeToolCallback rejects, but the *rate* of rejects is the AgentWatch signal — silently rising rejects = drift |
| Runaway reasoning chains | Agent Platform anomaly detection ingests OpenTelemetry traces; AgentWatch composes those into a per-agent reliability SLO |
| Blast-radius violation | Workload Identity + PAB policies prevent unauthorized reach; AgentWatch records when an agent *attempts* unauthorized reach (the attempt itself is the signal) |
| Tool-intent misuse | Semantic Governance Policies catch some at the gateway; AgentWatch closes the loop with a tool-call-vs-claimed-intent classifier on the trace |

**The crawl/walk/run alignment.** The paper recommends a phased rollout: **Crawl** (Agent Runtime + Agent Identity) → **Walk** (Model Armor + scoped MCP IAM) → **Run** (Binary Authorization, VPC Service Controls, Agent Registry, full Agent Gateway). AgentWatch is the **observability layer that gets meaningful at Walk** and becomes a CISO-grade dependency at Run. Without AgentWatch, the Run-phase controls fire silently and you don't know whether your agents are actually behaving or just not getting *caught*.

**Three pillars of agent testing** (from the paper, applied to BFSI):

1. **Agent Success & Quality** — LLM-as-a-judge (Pointwise) against a golden dataset of historical claims. AgentWatch records the score per agent, per snapshot.
2. **Process & Trajectory** — chain-of-thought trace verification: did the Case Manager call the Data Vault before the Logistics Liaison? Did the Data Vault actually invoke the BigQuery MCP or hallucinate the answer? AgentWatch is the dashboard for this trajectory analysis.
3. **Trust & Safety** — automated adversarial test suites (virtual red-teaming via SCC AI Protection). AgentWatch is the alerting layer when the red-team suite finds a regression.

**What this means for the BFSI buyer.** If your AI org is on GCP / Gemini Enterprise Agent Platform, AgentWatch slots into the Agent Registry + Agent Gateway + Model Armor + ADK telemetry stack as the reliability surface. If your org is on AWS Bedrock or Azure AI Foundry, the same three-pillar test framework and the same five deficiencies apply — just with different primitive names (Bedrock Guardrails ≈ Model Armor, IAM Identity Center ≈ Agent Identity, AWS PrivateLink + Network Firewall ≈ VPC-Service Controls). The product is cloud-agnostic; the Google paper is the cleanest published spec of what "good" looks like.

> Source: Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., *Building secure multi-agent systems on Google Cloud*, Google Cloud (2025). Aligned to Google's Secure AI Framework (SAIF).

## Utility math (modeled — priced when built)

- SOTA: ~$/incident in runaway token cost = $5-50k per event, MTTR 4+ hours
- AgentWatch: $/incident → 0 via auto-cutoff at blast-radius threshold; MTTR < 10 minutes
- Affected: every deployed agent in the fleet (typical Tier-1 BFSI: 8-20 agents in 18 months)
- Annual utility: tens of prevented runaway incidents + reliability-SLO uplift from "unmeasured" to 99.4%

## Status

Roadmap. [HalluGuard](../01-halluguard-bank-chatbot-safety/) is the format reference for when this gets built.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)

<!-- AgentWatch: AI agent reliability and tool-use observability - catches runaway costs and tool-call failures in deployed agents -->
