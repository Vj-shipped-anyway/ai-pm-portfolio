# Evaluation & KPI Tree — AI Inference Economics Dashboard

## North-star

**% of AI feature spend with attribution down to feature × segment, with 100% reconciled to vendor invoice within 24 hours.**

Why this north star: it composes coverage (every dollar accounted to a feature), granularity (segment-level, not just feature), and timeliness (same-day reconciliation kills the surprise-invoice failure mode). Anything else is an input.

## KPI tree

```
North star: % feature spend attributed × reconciled in 24h
│
├── INPUTS (leading, weekly)
│   ├── Coverage: % of features metered at gateway
│   ├── Coverage: % of vendors with schema-on-read ingestion live
│   ├── Frontier refresh cadence (target: weekly per feature)
│   └── Envelopes signed: % of features with PM-signed monthly envelope
│
├── PROCESS (mid, monthly)
│   ├── Days from invoice receipt to attribution (target ≤ 1)
│   ├── Time from cost anomaly to PM-aware (target ≤ 24h)
│   ├── Substitution-test cycle time (eval → shadow → promote)
│   └── Dead-feature kill-review SLA (30/60/90 day cadence held)
│
└── OUTPUTS (lagging, quarterly)
    ├── Modeled spend reduction via substitution + pruning ($)
    ├── Budget-envelope breach incidents (target: 0)
    ├── Forecast accuracy: planned vs actual monthly spend (target ±8%)
    └── CFO close-out pack auto-generated (target: every cycle)
```

## Eval harness

The prototype runs a known synthetic ledger with an injected runaway on day 55 (support_copilot) and a known dead feature (rm_prep_brief). The eval harness scores:

| Metric | Formula | Target |
|--------|---------|--------|
| Anomaly detection delay | `t_alert - t_anomaly` | ≤ 24h |
| Anomaly precision | `TP / (TP + FP)` | ≥ 0.95 |
| Substitution recommendation accuracy | `swaps that hold ≥ tolerance / total` | ≥ 0.90 |
| Dead-feature recall | features below floor flagged | 100% |
| Envelope-breach catch | breaches caught at 100% threshold | 100% |
| Vendor reconciliation accuracy | matched line items / total | ≥ 0.99 |

## Test scenarios (synthetic ledger replay)

1. **Runaway prompt** — support_copilot doubles per-call tokens day 55. Expected: alert within 24h, PM-aware same day, soft-throttle on day 60 if envelope breached.
2. **Cheaper-model substitution** — fraud_narrative on segment "ops" candidate-swapped to gpt-3.5-class. Expected: simulator shows $X saved; shadow test gates promote until eval evidence holds.
3. **Dead feature** — rm_prep_brief at 18% adoption. Expected: flagged on day-30 review; kill-review queued; if not justified, prune by day 60.
4. **Vendor invoice mismatch** — VendorA invoice line-item $X exceeds metered $Y. Expected: variance flagged same day; root cause traced (clock skew, model name mismatch, etc.).
5. **Multi-vendor view** — show full spend by vendor; ensure no orphaned spend (must equal sum of feature attribution within 1%).

## Ongoing eval cadence

- **Continuous:** gateway meters every inference; daily aggregation to attribution table.
- **Daily:** anomaly scan vs. trailing 14-day baseline per feature × segment.
- **Weekly:** cost-quality frontier refresh; PM review meeting on top-3 features by spend.
- **Monthly:** PM-signed envelope reset; CFO close-out pack auto-generated; vendor invoice full reconciliation.
- **Quarterly:** dead-feature kill review; cross-vendor benchmarking re-run.

## Exit criteria for v1 GA

- 100% of production AI features metered at gateway
- All vendors on schema-on-read ingestion (≥ 99% line-item match)
- ≥ 95% of monthly invoices reconciled within 24h
- Forecast accuracy within ±8% sustained for two cycles
- Modeled spend reduction ≥ 18% in pilot quarter from substitution + pruning
- Zero ungoverned envelope breaches in pilot quarter
