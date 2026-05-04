# 🧪 EvalForge — Eval-First Console for Regulated AI

**Status:** Roadmap · Targeted Q3 2026 · See [HalluGuard](../01-halluguard-bank-chatbot-safety/) for the format this folder will follow when built.

---

## The bleed

Most BFSI AI orgs ship GenAI to production with a 10-prompt regression test written by the on-call engineer at midnight. That isn't an eval. Karpathy and Hamel Husain have been arguing this for two years — *evals are the moat* — and enterprise AI keeps treating evals as a launch artifact instead of a continuously-running quality signal. Silent quality regressions reach customers because nobody owns the eval system as a product.

## The model deficiency it probes

Eval coverage gaps and silent regression — when a vendor model snapshot changes, an eval set doesn't refresh, or a slice (commercial vs. retail, English vs. Spanish, Tier-1 customer vs. mass-market) silently degrades while aggregate F1 looks fine.

## What this will be when built

Mirroring the HalluGuard walkthrough format:

- **Use case:** A bank running 14 customer-facing GenAI features needs a single eval surface that catches regressions across vendor versions, slices, and rubrics.
- **Sample data:** Eval results across 3 deployed use cases, multiple model snapshots, slice-level scoring.
- **Step 1:** Before evals — vibes-based regression checks.
- **Step 2:** With basic evals — a 10-prompt test set; show why aggregate F1 hides slice disasters.
- **Step 3:** Six named eval-system deficiencies (rubric drift, judge calibration loss, slice blindness, vendor-version invisibility, eval-set staleness, false-pass on paraphrastic variants).
- **Step 4:** The fix — EvalForge with rubric authoring UI for SMEs, slice-aware regression detection, version-pinned eval runs, judge-agreement monitoring.

## Utility math (modeled — priced when built)

- SOTA: ~14% silent regression rate detected after deployment (industry baseline)
- EvalForge: < 2% post-deployment regression
- Affected: ~12-20 GenAI features per Tier-1 BFSI shop, each averaging tens of thousands of customer interactions per day
- Annual utility: thousands of bad responses caught before customer impact, plus the audit-readiness uplift

## Status

Roadmap. When built, it'll follow the [HalluGuard](../01-halluguard-bank-chatbot-safety/) format — walkthrough README, sample data, four step scripts, Streamlit demo, utility math, CHANGELOG, PRD.

---

**Author:** Vijay Saharan · [LinkedIn](https://www.linkedin.com/in/vijaysaharan/)

<!-- @description 2026-05-04-090412 : EvalForge: eval-first console for regulated AI - catches GenAI regressions before deployment with versioned probe sets and CI gates -->
