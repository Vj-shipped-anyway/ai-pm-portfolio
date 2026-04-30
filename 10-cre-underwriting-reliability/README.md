# 🏗️ DealSentry — CRE AI Underwriting Reliability

**Status:** Roadmap · Targeted Q4 2026 · See [HalluGuard](../03-hallucination-containment/) for the format this folder will follow when built.

> **Framing:** This is a roadmap placeholder for a portfolio prototype. CRE is a personal study interest for me, not an active investment practice — I am not an LP in any CRE portfolio. The deficiency framing and utility math below reflect how I'd apply PM rigor to a domain I follow as a learner.

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

- SOTA: ~12-18% of AI-generated comp citations are fabricated (CRE-AI vendor independent audits)
- DealSentry: < 1% fabrication reaches IC
- Affected: a typical national CRE operator screens 800-1,200 deals/yr through AI underwriting
- Annual utility: prevents 3-5 bad bids per year (modeled at average $1.8M each in misallocated capital), plus the bigger uncounted benefit of trust restoration in the AI underwriting tool itself

## Status

Roadmap. [HalluGuard](../03-hallucination-containment/) is the format reference for when this gets built.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)
