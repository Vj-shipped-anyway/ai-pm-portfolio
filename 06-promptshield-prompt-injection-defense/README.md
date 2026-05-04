# 🛡️ PromptShield — Prompt-Injection & Egress Defense

**Status:** Roadmap · Targeted Q3 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

---

## The bleed

OWASP's LLM Top 10 has listed Prompt Injection as LLM01 since 2023. Simon Willison has written about it on his blog roughly weekly. Every BFSI shop has now deployed at least one internal copilot — frequently over confidential customer data — with **zero gateway in front of it**. Indirect injection via fetched web content and tool outputs is the live attack surface, not the theoretical one.

## The model deficiency it probes

Foundation models follow instructions found in their context window regardless of source. Direct injection from user input is one class. Indirect injection from retrieved content, tool outputs, email, calendar invites, PDFs, and web pages is the harder class — and the one no enterprise has actually solved.

## What this will be when built

- **Use case:** A bank's internal RM copilot with access to CRM, deal pipeline, and customer email — a customer-supplied PDF contains hidden instructions that exfiltrate other customer data.
- **Sample data:** Direct-injection prompts (jailbreaks, role-play attacks), indirect-injection content (poisoned web pages, malicious PDFs, hostile tool outputs), benign control set.
- **Step 1:** Before defense — copilot deployed with system prompt only.
- **Step 2:** With basic input filtering — keyword/regex blocklist; show why this breaks on novel attacks.
- **Step 3:** Six named deficiencies (direct jailbreak, indirect via tool output, role-play attack, ASCII-art bypass, multi-turn drift, output-egress without filtering).
- **Step 4:** The fix — PromptShield gateway with input classifier (fine-tuned DeBERTa for direct, separate model for indirect), output egress filter (PII, credentials, customer data), tool-call permission gate.

## 🏛️ Reference architecture: Model Armor + Agent Gateway + the double-guardrail pattern

Google Cloud's *Building secure multi-agent systems on Google Cloud* (Kannan, Sizemore, Herriford et al.) lays out the canonical defensible-LLM stack. PromptShield is what an enterprise builds when it doesn't yet have all of this in production — and what it integrates with when it does.

**The four layers the paper specifies (Warranty Claim System reference):**

1. **Inline ingress sanitization at the gateway.** Before any user prompt reaches the Case Manager Agent, Agent Gateway routes it through **Model Armor** (integrated with Sensitive Data Protection). Model Armor inspects for prompt injections, jailbreaks, PII leakage, malicious URLs, and policy violations against custom templates. Sanitized prompt only is passed downstream.
2. **Lateral A2A inspection.** Every agent-to-agent (A2A) handoff routes through Agent Gateway with **IAP-enforced zero-trust IAM allow policies**. The Case Manager's SPIFFE ID is verified before it can invoke the Data Vault or the Logistics Liaison. Cloud Next-Gen Firewall applies Layer 7 inspection to A2A and MCP traffic — a compromised orchestrator cannot execute SQL injection against the database.
3. **Deterministic input validation at the tool boundary.** ADK **BeforeToolCallback** fires a deterministic input firewall before any MCP call. Example from the paper: reject any "serial number" that isn't 12 alphanumeric characters before the BigQuery MCP server is invoked. This is the layer that catches indirect injection where untrusted retrieved content tries to slip a malformed argument through.
4. **Egress filtering.** **VPC Service Controls** wraps the entire ecosystem so even hijacked credentials cannot exfiltrate. **Secure Web Proxy** restricts the Logistics Liaison's outbound traffic to pre-approved vendor URLs. Model Armor inspects egress payloads — not just final responses to the user, but every payload sent to downstream agents and external MCPs.

**The double-guardrail pattern (the part most enterprises miss):**

- **IAM boundaries (deterministic).** Agent Gateway + IAP cryptographically verify every A2A call. Controls *which* agent can call *which* downstream agent or MCP. Blocks unauthorized lateral movement before payload processing.
- **Semantic boundaries (intent-aware).** **Semantic Governance Policies** + custom classifiers run on the actual payload in real time. Even if the network connection is technically authorized, the semantic guardrail acts as an intent firewall. The example from the paper: technical IAM lets the Case Manager call the Logistics Liaison; the semantic guardrail blocks payloads that try to trick the Liaison into generating an unauthorized 100% discount code.

PromptShield directly maps to layer 1 (input sanitization), layer 4 (egress filtering), and the **semantic boundary** half of the double guardrail. For enterprises on GCP / Gemini Enterprise Agent Platform, PromptShield slots into Model Armor + Agent Gateway and adds the BFSI-specific probe set, the bank-domain semantic policies, and the OWASP-LLM01 test harness. For enterprises on AWS Bedrock or Azure AI Foundry, the same architecture maps onto Bedrock Guardrails, AWS Network Firewall + PrivateLink, and Azure AI Content Safety + Private Endpoints — primitive names change, the pattern doesn't.

**Crawl/walk/run alignment.** The paper's phased rollout is the right pacing for a BFSI program: **Crawl** (Agent Identity + scoped MCP IAM), **Walk** (Model Armor on inputs + outputs), **Run** (full Agent Gateway with semantic policies + Binary Authorization + VPC Service Controls). PromptShield is delivered in phases that line up — the input classifier ships at Walk, the egress filter and tool-permission gate at Run.

> Source: Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., *Building secure multi-agent systems on Google Cloud*, Google Cloud (2025). Aligned to Google's Secure AI Framework (SAIF) and OWASP LLM Top 10 (LLM01: Prompt Injection).

## Utility math (modeled — priced when built)

- SOTA: ~30-50% catch rate on novel injections with regex/keyword filtering
- PromptShield: 96%+ on OWASP suite + ~85% on novel red-team probes
- Affected: every deployed copilot in the bank — typical Tier-1: 4-12 internal copilots over confidential data
- Annual utility: data-egress incidents → 0; the cost of one prevented exfiltration covers the build many times over

## Status

Roadmap. [HalluGuard](../01-halluguard-bank-chatbot-safety/) is the format reference for when this gets built.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)


<!-- @description 2026-05-04-091013 : PromptShield: prompt-injection and egress defense - catches data exfiltration attacks on internal copilots over confidential data -->
