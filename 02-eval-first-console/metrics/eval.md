# Evaluation & KPI Tree — Eval-First Console for Regulated AI

## North-star

**% of deployed GenAI use cases on a continuously-running domain rubric with ≤ 14-day staleness.**

Why this north star: it composes coverage (do we have a rubric?), authorship (is it SME-owned?), and timeliness (is it actually running?) into one number. Anything else is an input.

## KPI tree

```
North star: GenAI use cases on continuous, fresh domain rubric
│
├── INPUTS (leading, weekly)
│   ├── Coverage: % of use cases with a rubric
│   ├── Coverage: % of use cases with slice tags
│   ├── Coverage: % of use cases with vendor-version pinning
│   ├── Rubric freshness: median days since last SME edit
│   └── LLM-judge <-> SME correlation (target >= 0.85)
│
├── PROCESS (mid, monthly)
│   ├── Pre-deploy eval cycle time (median, by use case)
│   ├── SME authoring throughput (rubrics edited / FTE-week)
│   └── Vendor-update-to-eval lag (silent-update -> diff posted)
│
└── OUTPUTS (lagging, quarterly)
    ├── Silent regressions caught per quarter
    ├── Modeled prevented loss ($)
    ├── Customer complaints attributed to GenAI quality (target: declining)
    └── Reg-exam findings on AI quality monitoring (target: 0)
```

## Eval harness (eval-on-eval)

The product itself must be eval'd. The harness runs five scenarios against the regression flagger and judge calibration:

| Metric | Formula | Target |
|--------|---------|--------|
| Regression precision | `TP / (TP + FP)` on silent-update injection | ≥ 0.92 |
| Regression recall | `TP / (TP + FN)` on silent-update injection | ≥ 0.95 |
| Slice-cut coverage | (slices tested) / (slices declared) | 1.00 |
| LLM-judge correlation | Pearson r vs. SME gold set | ≥ 0.85 |
| Time to first eval after vendor update | wall-clock minutes | ≤ 30 |

## Test scenarios (production replay)

1. **Vendor silent update — citation regression.** Vendor v2 drops citation accuracy 12 points on the loan-officer Q&A. Expected: regression flagged within 30 minutes; recommendation = ROLLBACK to pinned version.
2. **Slice failure — commercial vs retail.** Aggregate score 88%, commercial slice 71%. Expected: slice cut surfaces gap; routes to use-case owner with commercial-specific eval-set expansion.
3. **Coverage gap — KYC narrative use case.** No rubric authored. Expected: surfaces in coverage-gap dashboard at the same loudness as a failed run; routes to SME authoring queue.
4. **Stale rubric — advisor research at day 92.** Expected: marked STALE; routes to SME for refresh attestation.
5. **No-regression control.** Vendor minor update; no rubric crosses threshold. Expected: zero alerts. (False-positive control.)

## Ongoing eval cadence

- **Per-prompt-change:** eval suite re-runs on every prompt-registry commit before promotion.
- **Per-vendor-version-change:** automatic re-run; diff posted within 30 min.
- **Nightly:** full sweep across hot use cases (customer-facing).
- **Weekly:** judge ↔ SME calibration set; threshold recalibration; coverage-gap review with use-case owners.
- **Monthly:** rubric review with compliance L2 for regulated workflows.
- **Quarterly:** AI Council sign-off on rubric inventory; retired/added use cases reconciled.

## Exit criteria for v1 GA

- ≥ 80% of customer-facing GenAI use cases on a domain rubric
- ≥ 90% of use cases with vendor-version pinning
- LLM-judge ↔ SME correlation ≥ 0.85 sustained for 30 days
- Median pre-deploy eval cycle ≤ 2 days
- Zero regressions > 10 points reach customers in a 30-day window
- SME-author NPS ≥ 35 on rubric-editor UX
