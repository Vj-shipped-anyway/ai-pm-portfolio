# Evaluation & KPI Tree — Production Model DriftSentinel

## North-star

**% of Tier-1 production models with drift MTTD ≤ 14 days.**

Why this north star: it composes coverage (instrumentation breadth) and detection latency (timeliness) into one number a CRO can answer in a board pack. Anything else is an input.

## KPI tree

```
North star: Tier-1 models with MTTD ≤ 14d
│
├── INPUTS (leading, weekly)
│   ├── Coverage: % of Tier-1 models instrumented
│   ├── Coverage: % of GenAI models on proxy-metric portfolio
│   ├── Eval-set freshness: median days since last refresh
│   └── False-positive rate on PSI alerts (target ≤ 8%)
│
├── PROCESS (mid, monthly)
│   ├── Time-to-evidence-bundle (median, by tier)
│   ├── Validator throughput (Tier-1 attestations / FTE-week)
│   └── Drift events triaged within SLA
│
└── OUTPUTS (lagging, quarterly)
    ├── Modeled prevented loss ($)
    ├── MRM cycle time (drift event → attestation)
    └── Reg-exam findings related to ongoing monitoring (target: 0)
```

## Eval harness

The prototype induces a known drift event on day 60. The eval harness runs four detector configurations against this ground truth and scores them on:

| Metric | Formula | Target |
|--------|---------|--------|
| Detection delay (days) | `t_alert - t_drift_actual` | ≤ 9 |
| Precision @ alert | `TP / (TP + FP)` | ≥ 0.92 |
| Recall on injected drift | `TP / (TP + FN)` | ≥ 0.95 |
| Diagnosis hit-rate | did diagnosis name the actual drifted feature? | ≥ 0.90 |

## Test scenarios (production replay)

1. **Credit DTI shift** — rate-cycle change shifts DTI distribution. Expected: PSI on `dti` trips Day 64; recommendation = SHADOW.
2. **Fraud velocity decline** — adversaries slow velocity to evade. Expected: PSI on `velocity` + KS on `txn_amt` trip Day 67; recommendation = RETRAIN.
3. **GenAI vendor silent update** — refusal rate doubles, response length grows. Expected: refusal_rate alarm Day 62; recommendation = ROLLBACK to pinned vendor version.
4. **No-drift control** — quiet 90-day window. Expected: zero alerts. (False-positive control.)

## Ongoing eval cadence

- **Daily:** PSI/KS sweep across all instrumented models.
- **Weekly:** False-positive review with model owners; threshold recalibration.
- **Monthly:** Counterfactual replay — inject synthetic drift, measure detection delay.
- **Quarterly:** Line-2 (MRM) sign-off on drift envelopes per tier.

## Exit criteria for v1 GA

- 100% Tier-1 ML coverage
- ≥ 80% of GenAI fleet on proxy portfolio
- False-positive rate ≤ 8% sustained for 30 days
- Validator NPS ≥ 40 on auto-bundle UX
