# PRD · PromptShield — Prompt-Injection & Egress Defense

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype, designed for engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I would bring to a Tier-1 BFSI shop's CISO and Head of AI Platform in the seat. It is not a record of a PRD landed at a named bank. The six-class taxonomy, the five-layer architecture, the OPA policy pattern, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD stub

| Field | Value |
| --- | --- |
| **Product** | PromptShield — five-layer defense-in-depth gateway in front of internal BFSI copilots. |
| **Owner** | Vijay Saharan, Sr PM (BFSI AI Platform). |
| **Stage** | Portfolio prototype, designed for engagement. Synthetic data, no production deployment. |
| **Users** | Primary: CISO, Head of Security, Head of AI Platform. Secondary: MRM committee chairs (the line-2 validators who sign off on the gateway as a model-risk control), Internal Copilot product owner, InfoSec audit. Tertiary: line-1 RM / KYC / claims engineers whose copilots route through the gateway. |
| **Problem** | Every BFSI shop has deployed at least one internal copilot over confidential customer data. [OWASP LLM01](https://genai.owasp.org/llm-top-10/) is the #1 listed LLM risk. Current state: zero gateway in production at many shops; a regex blocklist at the rest. Catch rate on novel attacks: 30-50%. FP rate on legit banker queries: 10-15%. Single successful exfil = customer-data breach + [GLBA](https://www.ftc.gov/business-guidance/privacy-security/gramm-leach-bliley-act) notification + state breach-disclosure law + brand event. Modeled loss: $4-15M per confirmed event. |
| **Solution** | Five-layer defense-in-depth gateway. **L1** input classifier ([Llama Guard 3](https://huggingface.co/meta-llama/Llama-Guard-3-8B) / fine-tuned DeBERTa) catches direct injection + jailbreak. **L2** retrieval scanner catches indirect injection in retrieved RAG content. **L3** tool-call gate (OPA / Rego policy on every outbound tool) refuses non-allowlisted destinations + bulk extracts. **L4** egress filter (DLP-style regex on response) catches PII + known-bad URLs + markdown tracking pixels. **L5** per-session memory boundary (Redis + SPIFFE) refuses cross-session probes. Every block / allow decision lineage-logged via [LineageLog](../09-lineagelog-ai-decision-audit/) for audit. |
| **North-star metric** | (catch_rate × queries_protected) − (FP_rate × queries_protected). Target steady-state: catch ≥ 96%, FP ≤ 4%, on every deployed internal copilot. |
| **Modeled metrics (12-month horizon)** | 🟢 **Catch rate: 99%** on the shipped 100-attack suite (measured). 🟢 **FP rate: 1%** on the 200-prompt legitimate corpus (measured). 🟢 **Tool-gate accuracy: 100%** on 50-call ground-truth set (measured). 🟡 **Modeled production catch: 96%+** — assumes fine-tuned DeBERTa / Llama Guard 3 replaces the deterministic regex pack. 🟡 **Modeled production FP: ~4%** — assumes calibration against the bank's actual legitimate-query corpus. 🔴 **Data-exfiltration incidents → 0** at fleet scale (designed). |
| **Modeled cost** | 🔴 ~$380k for a 90-day engagement in a real deployment (compute on existing K8s/EKS footprint + 1 PM + 1.5 FTE engineers + 0.5 FTE InfoSec partner + fine-tuned classifier inference on T4 / L4 GPUs + WORM bucket for the `attack_log` archive) — designed, not yet executed. |
| **Risk #1** | Classifier latency. The fine-tuned DeBERTa / Llama Guard 3 on T4 / L4 GPUs adds ~50-100ms P99 to every prompt. Solution: batch inference at the gateway; cache by prompt hash; degrade to deterministic-only mode under load (catch rate drops to ~85% but FP stays low). |
| **Risk #2** | False-positive rate hurts banker productivity. Even 4% FP across 200k+ queries/yr per copilot = thousands of legitimate queries blocked. Solution: continuous calibration against the bank's own legitimate-query corpus; per-tenant tuning; soft-block / explain-and-retry UX on borderline cases. |
| **Risk #3** | Vendor classifier silent updates. If Meta or the fine-tuned-classifier vendor silently rolls a snapshot, behavior changes. Solution: interlock with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5 vendor-pin detector; daily diff job; auto-rollback on catch-rate regression. |
| **Risk #4** | Adversarial drift. Attackers adapt to the classifier's patterns. Solution: continuous red-team probe runs; quarterly retraining; integration with [HuggingFace prompt-injection datasets](https://huggingface.co/datasets/deepset/prompt-injections) for community-fresh examples. |
| **Out of scope** | (1) Hallucination containment — covered by [HalluGuard](../01-halluguard-bank-chatbot-safety/). (2) Decision-grain lineage of every block — covered by [LineageLog](../09-lineagelog-ai-decision-audit/). (3) Model drift detection — covered by [DriftSentinel](../02-driftsentinel-model-drift-monitoring/). (4) Building a new foundation model. (5) Customer-facing copilots (different threat model — public abuse, not insider exfil). |

---

## 2. Stakeholder map

| Role | Line | Stake | What they want from PromptShield |
| --- | --- | --- | --- |
| **CISO** | L2 | Owns the bank's data-handling posture | A single auditable control point for "is the internal copilot leaking customer data." Audit-grade trail of every block / allow decision. SOC 2 / ISO 27001 alignment. |
| **Head of Security / SOC** | L2 | Owns active-defense posture | Real-time fire-rate dashboards; PagerDuty on classifier-catch-rate regression; runbook for the "attack just slipped through" case. |
| **Head of AI Platform** | Platform | Owns the substrate the copilots ship on | A platform service (not per-copilot bolt-on) that every internal copilot can route through with one config flag. |
| **MRM committee chair (L2 validator)** | L2 | Owns model-risk attestation | PromptShield itself is a "model" under SR 11-7 — needs its own attestation pack. North-star metric on a quarterly review cadence. Documented assumptions + adversarial-drift retraining schedule. |
| **InfoSec Audit (L3)** | L3 | Owns the effective-challenge function | Read-only access to the immutable `attack_log` table; sample-pull workflow that does not require pulling six log surfaces. Audit-on-audit trail. |
| **Internal Copilot product owner (RM / KYC / claims)** | L1 | Owns the copilot product | Low FP rate — does not impede the banker's actual work. Soft-block / explain-and-retry UX on borderline cases. |
| **Legal / E&G** | L2 | Owns disclosure + consent posture | Trail of which customer data was blocked from leaving + which user attempted the action. GLBA / state-breach-law evidence chain. |
| **Privacy Office / DPO** | L2 | Owns GDPR / CCPA / customer-consent posture | Per-region deployment (EU instance, India RBI-compliant instance, US instance). No cross-region replication of the `attack_log`. |
| **Engineering (L1)** | L1 | Owns the gateway deployment | Standard FastAPI on K8s; OPA bundle distribution via Argo CD; observability into Datadog. Low ops overhead. |
| **Procurement** | Function | Owns vendor selection | Open-weight classifiers (Llama Guard 3) preferred over proprietary; on-prem DLP (BigID / Nightfall) preferred over SaaS-only; bank's existing OPA / Datadog / Argo CD footprint preferred over new vendors. |

---

## 3. RICE-prioritized backlog

> RICE = (Reach × Impact × Confidence) ÷ Effort.
> Status: "Sequenced for v0.x" = committed to a release. "Queued" = will be sequenced after v0.5.

| # | Item | Reach | Impact | Confidence | Effort | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | **L1 Input Classifier (v0.1)** — Llama Guard 3 deployed on T4 / L4 GPUs; FastAPI service; sub-100ms P99. | 100M | 3 | 0.9 | 13 | 20.8 | Sequenced for v0.1 |
| 02 | **L2 Retrieval Scanner (v0.1)** — same classifier applied to retrieved chunks; FP-tolerant calibration. | 80M | 3 | 0.85 | 8 | 25.5 | Sequenced for v0.1 |
| 03 | **L3 Tool-Call Gate (v0.1)** — OPA + Rego policy bundle; one bundle per tool; allow-list of destinations. | 100M | 3 | 0.9 | 8 | 33.8 | Sequenced for v0.2 |
| 04 | **L4 Egress Filter (v0.1)** — DLP regex pack + Cloud DLP / Nightfall integration; markdown-pixel detection. | 100M | 3 | 0.85 | 8 | 31.9 | Sequenced for v0.2 |
| 05 | **L5 Per-Session Memory Boundary** — Redis Cluster + per-session SPIFFE ID; session state keyed by `(spiffe_id, session_id)`. | 60M | 2 | 0.8 | 8 | 12.0 | Sequenced for v0.3 |
| 06 | **`attack_log` immutable table** — Postgres CREATE TABLE; row-hash HSM-signed; partitioned by month; 7-year retention. | 100M | 2 | 0.9 | 5 | 36.0 | Sequenced for v0.1 |
| 07 | **Streamlit prototype** — config/observability panel; per-layer fire-rate; scenario walkthrough. | 1k | 2 | 1.0 | 5 | 0.4 | Sequenced for v0.1 (this repo) |
| 08 | **Argo CD pipeline for OPA bundles** — one bundle per tool, distributed continuously, no application restart. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.2 |
| 09 | **Continuous red-team probe runs** — quarterly cycle against the [HuggingFace prompt-injection datasets](https://huggingface.co/datasets/deepset/prompt-injections) + the bank's red team. | 100M | 3 | 0.7 | 13 | 16.2 | Sequenced for v0.3 |
| 10 | **Vendor-pin verifier for classifier snapshot** — interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5; daily diff. | 50M | 2 | 0.7 | 5 | 14.0 | Sequenced for v0.4 |
| 11 | **LineageLog integration** — every block / allow decision writes a lineage record indexed by `(session_id, request_id, timestamp)`. | 100M | 2 | 0.8 | 8 | 20.0 | Sequenced for v0.4 |
| 12 | **Per-tenant calibration** — each copilot tunes its FP-vs-catch curve on its own legitimate-query corpus. | 80M | 3 | 0.65 | 21 | 7.4 | Sequenced for v0.5 |
| 13 | **Multi-region EU + India instances** — separate KMS rings, no cross-region replication, RBI + GDPR alignment. | 60M | 2 | 0.6 | 21 | 3.4 | Queued (post v0.5) |
| 14 | **Soft-block / explain-and-retry UX** — borderline cases route to a "did you mean..." UX, not a hard refusal. | 100M | 2 | 0.6 | 13 | 9.2 | Queued (post v0.5) |

---

## 4. Why now

- **[OWASP LLM01](https://genai.owasp.org/llm-top-10/)** has named Prompt Injection as the #1 LLM risk since 2023. The published industry threshold for "the problem is mature enough to invest in" — that's it.
- **[MITRE ATLAS](https://atlas.mitre.org/)** is the now-stable attacker-techniques catalog. Every BFSI red team uses it. The gateway needs to be calibrated against the same catalog.
- **[EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)** is in effect. High-risk AI systems (BFSI internal copilots over confidential customer data qualify) must meet record-keeping + risk-management standards. The gateway is the implementation surface for "did our copilot do the safe thing on this request."
- **The substrate is finally there.** [Llama Guard 3](https://huggingface.co/meta-llama/Llama-Guard-3-8B) is open-weight, fine-tunable, and deployable on T4 / L4. [Meta Prompt Guard](https://huggingface.co/meta-llama/Prompt-Guard-86M) is 86M params and runs sub-50ms on CPU. [OPA](https://www.openpolicyagent.org/) is in production at every Tier-1 bank already. [Cloud DLP](https://cloud.google.com/security/products/dlp) / [Nightfall](https://nightfall.ai/) / [BigID](https://bigid.com/) cover the L4 egress regex layer.
- **Vendor copilots are now everywhere.** Every BFSI shop has Microsoft Copilot for M365, an OpenAI / Anthropic / Bedrock-backed internal RM copilot, and at least one KYC / claims-triage agent. The attack surface is not theoretical.

## 5. Goals (12-month horizon)

| Goal | Metric | Target | Tier |
| --- | --- | --- | --- |
| Increase catch rate on novel attacks | Catch rate on quarterly red-team probe set | 30-50% → ≥96% | 🟡 (modeled — assumes fine-tuned classifier + continuous retraining) |
| Hold false-positive rate | FP rate on legitimate-banker corpus | 10-15% → ≤4% | 🟡 (modeled — assumes per-tenant calibration) |
| Zero confirmed exfil incidents | Confirmed customer-data exfil via internal copilot | unknown → 0 | 🔴 (designed against OWASP-LLM01 attack pattern) |
| Tool-gate accuracy | Block / allow accuracy on red-team tool-call set | unknown → ≥99% | 🟡 (modeled — measured 100% on the 50-call synthetic set) |
| MRM attestation pack auto-generated | % of quarterly MRM cycle that requires manual collation | 100% → 5% | 🔴 (designed — interlocks with LineageLog) |

## 6. Non-goals

- Not a foundation-model vendor — we route to the bank's existing vendor stack.
- Not a customer-facing safety layer — that is a different threat model (public abuse, not insider exfil). Different product.
- Not in the model registry / MRM workbench — we integrate with whichever the bank already runs (Archer, ServiceNow GRC, MetricStream).
- Not a replacement for Bedrock Guardrails / Azure Prompt Shields / Google Model Armor — we sit on top, add the BFSI-specific corpus + policy + tool-registry knowledge.
- Not a hallucination containment system — covered by [HalluGuard](../01-halluguard-bank-chatbot-safety/).

## 7. User stories

- **As CISO**, I want a single auditable control point for "is the internal copilot leaking customer data" so I can answer the board's question with one screenshot and one query.
- **As Head of Security**, I want real-time fire-rate dashboards and PagerDuty alerts on catch-rate regression so I know within minutes when an attack pattern is slipping through.
- **As Head of AI Platform**, I want a one-config-flag enablement story so every new copilot ships behind PromptShield by default.
- **As MRM committee chair**, I want a quarterly attestation pack auto-assembled so I can sign off without spending three weeks on data collation.
- **As InfoSec Audit (L3)**, I want read-only access to the immutable `attack_log` so I can validate the effective-challenge function without pulling six log surfaces.
- **As an Internal Copilot product owner**, I want low FP rate and soft-block UX on borderline cases so my bankers do not abandon the tool.

## 8. Solution detail — the five-layer composition

The product is a five-layer gateway. Each layer is one of the six deficiency-class fixes.

| # | Deficiency class | Primary layer | Catch action |
| --- | --- | --- | --- |
| 1 | Direct injection in user input | L1 (Input classifier) | Llama Guard 3 / fine-tuned DeBERTa scores the user prompt against the injection / jailbreak corpus; refuses on score > threshold. |
| 2 | Indirect injection in retrieved docs | L2 (Retrieval scanner) | Same classifier scores every retrieved RAG chunk; sanitizes (FP-tolerant) before the chunk reaches the model. |
| 3 | Tool-call abuse | L3 (Tool-call gate) | OPA / Rego policy evaluates every tool invocation; allow-list of destinations + tools; refuses bulk extracts and cross-book reads. |
| 4 | Egress channel | L4 (Egress filter) | DLP regex pack scans the model's response payload; refuses on PII match / known-bad URL / markdown tracking pixel. |
| 5 | Cross-session leak | L5 (Per-session memory boundary) | Redis + SPIFFE; session state keyed by `(spiffe_id, session_id)`; cross-session prompts refused. |
| 6 | Jailbreak via role-play | L1 (Input classifier) | Same L1 classifier — generalizes past the hand-tuned blocklist to the long tail of jailbreak phrasings. |

## 9. Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 6w | L1 + L5 deployed; `attack_log` schema; integration with the bank's IdP + Datadog + Argo CD; 1 pilot copilot (RM Copilot). |
| 1 — Tier-1 copilots | 12w | All Tier-1 internal copilots routed through L1 + L5; L2 enabled for the RAG-backed copilots. |
| 2 — Tool gate | 8w | L3 enabled for every routed copilot; OPA bundle per tool; allow-list calibrated against 60 days of legit traffic. |
| 3 — Egress filter | 8w | L4 enabled; Cloud DLP / Nightfall / BigID integration; bank-specific PII regex pack. |
| 4 — Continuous red team | 8w | Quarterly red-team probe runs; LineageLog integration; vendor-pin verifier (interlocks with DriftSentinel). |
| 5 — Multi-region | 12w | EU instance (Frankfurt) + India instance (Mumbai); independent KMS rings. |

## 10. Open questions

1. **Classifier vendor.** Llama Guard 3 (open-weight, self-hosted) vs. Meta Prompt Guard (smaller, faster, narrower coverage) vs. a fine-tuned DeBERTa on the bank's red-team corpus. Default: Llama Guard 3 for L1/L2; fine-tuned DeBERTa as the fallback for FP-sensitive copilots.
2. **DLP vendor.** Cloud DLP (GCP-native, cheap), Nightfall (SaaS, BFSI-tuned), or BigID (on-prem, broader coverage). Depends on the bank's existing footprint. Default: build the L4 service as a generic DLP-vendor-agnostic shim; let procurement pick.
3. **Soft-block UX.** Hard refusal vs. soft-block-and-explain. Banker-productivity argument says explain; security argument says refuse. Default: soft-block on borderline (probability 0.5-0.7), hard refusal above 0.7; logged either way.
4. **Latency budget under load.** Sub-100ms P99 in the classifier inference; degrade to deterministic-only under burst. Default: catch rate drops to ~85% under degraded mode but FP stays low; alert L2 on every degrade.

## 11. Build & scale notes

**Reference architecture.** Five stateless FastAPI services, one per layer, deployed on the bank's existing K8s/EKS footprint. OPA bundle distribution via Argo CD. Postgres for the `attack_log` table. Redis Cluster for session memory. ClickHouse for per-layer fire-rate observability. GCS / S3 Object Lock for the 7-year audit archive. Interlocks with [LineageLog](../09-lineagelog-ai-decision-audit/) for the audit-grade lineage layer.

**Throughput envelope.** A Tier-1 BFSI shop typically runs 4-12 internal copilots, each handling 200-800k internal queries/yr. Aggregate: ~1-10M queries/yr per shop = ~0.5-3 queries/second average, ~5-30 queries/second peak. L1/L2 classifier inference is the bottleneck (sub-100ms P99 on T4 / L4 GPUs); L3/L4/L5 are sub-millisecond.

**Failure modes.**
- *Classifier service down.* Degrade to L1=deterministic-regex-only mode. Catch rate drops ~14 points; FP stays low. Alert L2.
- *OPA bundle deploy fails.* Roll back to the last-known-good bundle in <60s. Allow path open in the meantime.
- *Vendor classifier silent update.* Vendor-pin verifier (interlocks with [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) v0.5) catches via daily diff job. Auto-rollback on catch-rate regression.
- *Adversarial drift.* Quarterly retraining cycle. New patterns added to L1 corpus; OPA bundle updated.

**Migration path.** If the bank is already running a regex-only filter: PromptShield ingests the bank's existing blocklist as the L1 fallback regex pack, then progressively replaces with the fine-tuned classifier over 90 days. If the bank is on no gateway at all: 6-week foundation phase to deploy L1 + L5 on the highest-risk copilot first; expand to the rest.

**Org dependencies.** CISO signs off on the `attack_log` immutability properties + the threat model. Head of AI Platform owns the gateway service. InfoSec Audit (L3) audits the L1 classifier accuracy on a quarterly cycle. Procurement owns the DLP-vendor + classifier-vendor selection (typically a 2-month conversation; start on day one).

---

*This PRD interlocks with [HalluGuard](../01-halluguard-bank-chatbot-safety/) (hallucination containment), [DriftSentinel](../02-driftsentinel-model-drift-monitoring/) (vendor-pin detection), [AgentWatch](../05-agentwatch-agent-observability/) (multi-agent reliability), and [LineageLog](../09-lineagelog-ai-decision-audit/) (immutable audit log of every block / allow decision).*
