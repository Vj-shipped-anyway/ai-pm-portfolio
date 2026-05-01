# 🏗️ DealSentry — CRE AI Underwriting Reliability

**Status:** Roadmap · Targeted Q4 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

> **Framing:** This is a roadmap placeholder for a portfolio prototype. CRE is a personal study interest for me, not an active investment practice — I am not an LP in any CRE portfolio. The deficiency framing and utility math below reflect how I'd apply PM rigor to a domain I follow as a learner.

> **Reading the numbers — credibility tags inline.** Numbers in this roadmap doc are tagged 🟢 **Measured**, 🟡 **Modeled** (extrapolated from synthetic data + published industry baselines, with the assumption named), or 🔴 **Hypothetical** (designed and reasoned about, never tested in production). Full convention in the [master README's "Reading the numbers" section](../README.md#-reading-the-numbers).

---

## The bleed

PropTech AI founders have publicly warned: deal-screening AI hallucinates comparables, misreads OMs, fabricates submarket statistics. CRE acquisitions teams use these copilots — comp pulls, market reads, T-12 normalization — and ship IC memos built on hallucinated comparables. **Bad bids. Blown deals. Mispriced acquisitions.** And the failure mode is quiet: a fabricated comp set looks plausible because it shares a submarket with real ones.

## The model deficiency it probes

The CRE-specific instance of "confident-and-wrong" — foundation models trained on broad real-estate text learn to produce plausible-shaped outputs (comp records, sub-market rents, cap rates) that have correct *form* but no underlying source. The deficiency is plausible-fabrication in numerically-dense outputs.

## What this will be when built

- **Use case:** A 220-asset acquisitions team uses an AI underwriting copilot. A deal dies at IC because the AI-generated comp set included two assets that didn't exist — same submarket, reasonable price-per-door, just not real.
- **Sample data:** Synthetic AI underwriting summaries with comps, T-12 normalization, submarket statistics; some real (verifiable against CoStar / Reonomy / Cherre / proprietary), some fabricated.
- **Step 1:** Before reliability — AI underwriting summary trusted at face value.
- **Step 2:** With basic spot-checking — analysts spot-check 10% of comps; show what slips through.
- **Step 3:** Six named deficiencies (comp-existence fabrication, T-12 arithmetic drift, submarket-stat fabrication, cap-rate hallucination, exit-assumption staleness, occupancy-fabrication).
- **Step 4:** The fix — DealSentry sentinel that verifies every comp against a source-of-truth DB, re-runs T-12 math symbolically, cross-checks submarket stats across multiple feeds, confidence-flags outputs.

## Utility math (modeled — priced when built)

- 🟡 SOTA: ~12-18% of AI-generated comp citations are fabricated (CRE-AI vendor independent audits)
- 🟡 DealSentry target: < 1% fabrication reaches IC (modeled — depends on the synthetic SOT coverage matching real CoStar/Reonomy/Cherre coverage in the engaged operator's submarkets)
- Affected: a typical national CRE operator screens 800-1,200 deals/yr through AI underwriting
- 🟡 Annual utility (modeled): prevents an estimated 3-5 bad bids per year at ~$1.8M each in modeled misallocated capital, plus the larger uncounted benefit of trust restoration in the AI underwriting tool itself

## Status

Roadmap. The Streamlit prototype in [`src/app.py`](./src/app.py) is the product-mechanic walkthrough; the production-system architecture is below. [HalluGuard](../01-halluguard-bank-chatbot-safety/) is the format reference for the full README when the build wraps.

---

## 🛠️ Why this is a Streamlit prototype, not a production app

Streamlit was the right tool for the prototype that lives in [`src/app.py`](./src/app.py) — it lets a CRE acquisitions lead walk the four-step *cite → verify → flag → workpaper* story without a build. It would be the wrong tool for production.

**Streamlit is right for:** validating the product mechanic with one acquisitions team in 5 days; embedding a no-install demo in a portfolio deploy; single-page narrative flows.

**Streamlit is wrong for:** multi-tenant SaaS (no row-level security per operator); pixel-perfect IC-deliverable UX; hardened SAML/OIDC RBAC; large-corpus comp lookups under sub-second latency.

### What this would look like as a client-facing SaaS

> **Production stack reassessment** — the SaaS shape a CRE operator's procurement team would actually evaluate.

If DealSentry were a real product shipping to a national CRE operator's acquisitions team:

- **Frontend:** Next.js 15 + Tailwind + shadcn/ui — a per-memo verification panel that lives inside the deal pipeline tool the team already uses (Dealpath, Juniper Square, Honest Buildings, or a custom Salesforce CRE Cloud build), not a standalone app.
- **Auth:** SAML / OIDC with the operator's IdP (Okta, Azure AD); RBAC mapping junior analyst / senior analyst / IC member / managing director roles.
- **Backend:** FastAPI on the operator's K8s footprint (most CRE shops standardize on AWS — EKS); microservice per check (comp verifier, T-12 symbolic re-runner, submarket-stat cross-check, fabrication classifier).
- **Source-of-truth data plane:** live integrations with CoStar, Reonomy, Cherre, RCA / MSCI Real Capital Analytics, REIS / Moody's CRE; Postgres + pgvector for the comp embedding index; Snowflake / Databricks as the analytics warehouse.
- **Symbolic math:** sympy-based T-12 normalization re-runner that replays the rent roll → NOI → cap rate chain deterministically and flags any AI-generated number that does not reconcile.
- **Observability:** OpenTelemetry → Datadog; Langfuse for the LLM verifier traces; PagerDuty for IC-eve memo-fail escalations.
- **Compliance:** SOC 2 Type II baseline (LPs increasingly require it for any tool touching investment decisions); audit log of every fabrication decision retained for the holding period.
- **Governance:** Every flagged comp produces a workpaper that the senior analyst signs off on before IC; every cleared memo carries a verification token the IC chair can verify.
- **Deployment:** Blue-green via Argo CD; feature flags via LaunchDarkly; canary rollout starts with one asset class (industrial in the Sunbelt, where the comp coverage is densest) before expanding.

The Streamlit prototype here proves the *product mechanic* — that three independent checks can catch the canonical fabricated-comp / bad-math / submarket-fiction patterns on a 6-memo eval set. The production architecture above is what the seat I'm pursuing actually delivers.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)

<!-- DealSentry: CRE AI underwriting reliability - catches comp fabrications, math errors, and submarket-stat hallucinations in AI-drafted memos -->
