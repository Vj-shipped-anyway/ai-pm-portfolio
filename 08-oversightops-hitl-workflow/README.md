# 👥 OversightOps — Human-in-the-Loop Workflow Designer

**Status:** Roadmap · Targeted Q4 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

---

## The bleed

Anthropic's Constitutional AI work and OpenAI's usage policy both name human oversight as the safety lever for high-stakes AI decisions. BFSI bolts a "human review" step on top of AI workflows as an afterthought — no SLA on review, no review-quality measurement, reviewers rubber-stamp under load. The oversight is theater. The first time anyone measures it is during an OCC exam or a complaint escalation.

## The model deficiency it probes

The deficiency isn't in the model — it's in the *system around the model*. AI systems with theatrical HITL fail predictably in three ways: confidence-blind routing (everything goes to a reviewer), no SLA on review (reviewers rubber-stamp under queue pressure), and no quality measurement (you can't tell whether reviewers improve outcomes).

## What this will be when built

- **Use case:** A bank's ML-driven dispute-decision pipeline routes 100% of contested disputes to a reviewer queue. Reviewers rubber-stamp at 94% under load. The "human oversight" line in the model risk attestation is meaningless.
- **Sample data:** Synthetic AI decisions with confidence scores, reviewer outcomes, ground-truth labels, queue depths over time.
- **Step 1:** Before HITL design — uniform routing, no SLA.
- **Step 2:** With basic confidence-tier routing — show that this still doesn't measure reviewer quality.
- **Step 3:** Five named deficiencies (uniform routing, no SLA enforcement, rubber-stamping under load, no kappa scoring, no escalation tier).
- **Step 4:** The fix — OversightOps designer that composes confidence-tier routing, reviewer load balancing, SLA enforcement, kappa-based reviewer-quality scoring, escalation paths.

## 🏛️ Reference architecture: HITL as a confirmation primitive, not a checkbox

Google Cloud's *Building secure multi-agent systems on Google Cloud* (Kannan, Sizemore, Herriford et al.) treats HITL as a runtime safety primitive. OversightOps is what BFSI builds when it wants real oversight — not the rubber-stamp queue most banks ship.

**The Warranty Claim System pattern.** The Logistics Liaison Agent (running on Cloud Run, scoped Workload Identity, Secure Web Proxy egress to pre-approved vendors only) executes fulfillment. Before any shipping label fires, it pauses on an asynchronous HITL "Approve" gate. Branches:

- **Branch A — "Covered."** Generate shipping label, draft confirmation email, queue for one-click HITL approval by a support rep reviewing a pre-validated summary.
- **Branch B — "Expired."** Auto-trigger a discount-offer MCP tool. No HITL because the action is bounded and reversible.
- **Branch C — "Suspicious."** Bypass automated fulfillment entirely. Route to a Fraud & Alerts queue for immediate human review.

The architectural primitive that makes this work is the **ADK confirmation primitive**:

```python
# Example from the Google Cloud paper
logistics_agent = adk.Agent(
    name="logistics-liaison",
    tools=[shipping_label_mcp_tool],
    require_human_approval=["generate_shipping_label"],
)
```

The high-stakes action is **paused for explicit user approval**, the agent process can resume on confirmation (long-running ops up to seven days), and the gate is enforced at the runtime layer — not as a post-hoc workflow bolt-on.

**Where OversightOps maps to the paper's controls:**

| OversightOps deficiency | What the Google paper provides | What OversightOps adds |
| --- | --- | --- |
| Confidence-blind routing | ADK confirmation primitives + per-tool `require_human_approval` | Per-use-case confidence-tier routing logic, calibrated against historical reviewer-vs-ground-truth divergence |
| No SLA on review | ADK supports long-running ops up to 7 days | Reviewer load balancer + queue-depth-aware SLA enforcement |
| Rubber-stamping under load | Not addressed by the paper | Kappa-based reviewer-quality scoring; surfaces rubber-stamp rate as a tracked metric |
| No quality measurement | Cloud Logging captures actions, not review quality | Reviewer-quality dashboard with kappa, agreement rate, and decision-flip outcomes |
| No escalation tier | Branch C "Suspicious" is hardcoded per workflow | Configurable escalation tiers per use-case archetype |

**The product opinion.** The paper's `require_human_approval=["generate_shipping_label"]` line is correct but insufficient. It guarantees the *gate* exists; it does not guarantee the *review* is real. OversightOps is the layer that measures whether the human in the loop is actually loop-closing or just clicking Approve. Most banks I've worked with ship the gate without the measurement and call it oversight. It's theater until you measure it.

**Crawl/walk/run alignment.** Crawl: the bank can use ADK confirmation primitives directly today, with manual SLA tracking. Walk: OversightOps adds confidence-tier routing and reviewer load balancing on top. Run: kappa scoring, queue-depth-aware escalation, and the rubber-stamp-rate dashboard wired into the MRM workbench.

> Source: Anirudh Kannan, Christine Sizemore, Connor Herriford, et al., *Building secure multi-agent systems on Google Cloud*, Google Cloud (2025). Aligned to Anthropic's Constitutional AI and Google's Secure AI Framework (SAIF).

## Utility math (modeled — priced when built)

- SOTA: ~94% rubber-stamp rate on uniform-routing HITL; review SLA p95 24h+
- OversightOps: rubber-stamp rate ≤ 4% (measured by reviewer-vs-ground-truth divergence); review SLA p95 35 minutes
- Affected: every regulated AI workflow with a human-in-the-loop step (typical Tier-1: 6-15 such pipelines)
- Annual utility: actual oversight (not theatrical) on tens of thousands of high-stakes decisions per year

## Status

Roadmap. [HalluGuard](../01-halluguard-bank-chatbot-safety/) is the format reference for when this gets built.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)


<!-- @description 2026-05-04-083534 : OversightOps: human-in-the-loop workflow designer - replaces rubber-stamp review with calibrated, role-aware oversight -->
