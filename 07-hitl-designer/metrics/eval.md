# Evaluation & KPI Tree — HITL Workflow Designer

## North-star

**% of high-stakes AI decisions reviewed within SLA, at reviewer-quality kappa ≥ 0.75, with rubber-stamp rate ≤ 4%.**

Why this north star: it composes timeliness (SLA), competence (kappa), and engagement (rubber-stamp ceiling) into one number. Hitting any two is theater; hitting all three is operational oversight that survives a regulator review.

## KPI tree

```
North star: % high-stakes decisions reviewed (in-SLA, kappa ≥ 0.75, rubber-stamp ≤ 4%)
│
├── INPUTS (leading, weekly)
│   ├── Coverage: % of AI workflows on the designer
│   ├── Workflow design completeness (tiers, pools, SLA, abstention) signed
│   ├── Quality-audit blend rate (5–10% of live queue)
│   └── Reviewer capacity vs forecasted volume per pool
│
├── PROCESS (mid, monthly)
│   ├── SLA p95 by tier (target ≤ 35min on tier-3)
│   ├── Reroute-on-breach rate (target ≤ 5%)
│   ├── Reviewer load Gini (target ≤ 0.20)
│   └── Calibration drift per reviewer (recalibrate at > 0.10 kappa drop)
│
└── OUTPUTS (lagging, quarterly)
    ├── Reviewer-quality kappa fleet-wide (target ≥ 0.75)
    ├── Rubber-stamp rate (target ≤ 4%)
    ├── Oversight-gap closure on high-stakes decisions
    ├── Reg-exam findings on AI human-oversight (target: 0)
    └── Loss events traceable to oversight gap (target: 0)
```

## Eval harness

The prototype runs a synthetic batch of 200 decisions with known ground truth through a configurable design and scores:

| Metric | Formula | Target |
|--------|---------|--------|
| End-to-end correctness | reviewer/auto-verdict == ground truth | ≥ 0.92 on high-stakes |
| Reviewer kappa | Cohen's κ vs ground truth on reviewed cases | ≥ 0.75 |
| SLA p95 | 95th percentile review latency | ≤ 35 min on tier-3 |
| SLA compliance | 1 − breach rate | ≥ 0.95 |
| Rubber-stamp rate | approvals at dwell < 15s on non-easy | ≤ 0.04 |
| Reviewer load Gini | inequality across reviewer pool | ≤ 0.20 |
| Auto-approve precision | auto-approved correct / auto-approved total | ≥ 0.98 |
| Abstention recall | hard cases routed to escalation / hard cases total | ≥ 0.90 |

## Test scenarios

1. **High-volume AML triage** — 80% sample-review, tight SLA. Expected: SLA met, kappa ≥ 0.75, no rubber-stamp spike.
2. **Credit exception, 2-of-2 high-tier** — top-tier cases require dual reviewer. Expected: dual sign-off, latency higher but bounded.
3. **Confidence-calibration drift** — upstream model post-vendor-update over-reports confidence. Expected: more cases auto-approved than warranted; quality-audit blend catches accuracy drop within 14 days; thresholds recalibrated (interlocks with Project 01).
4. **Reviewer load shock** — one pool loses 30% capacity overnight. Expected: SLA monitor reroutes to cross-trained pool; Gini holds.
5. **Adversarial rubber-stamp** — synthetic reviewer holds mouse and clicks fast. Expected: composite signal (dwell + scroll + cursor + active window) flags within first 50 cases; calibration coaching triggered.
6. **Escalation path** — abstention queue handled by senior reviewer with bounded SLA. Expected: no abstained case stalls > 4h.

## Ongoing eval cadence

- **Continuous:** every reviewer decision logged with dwell, scroll, cursor, latency, verdict.
- **Daily:** SLA monitor + rubber-stamp scan per pool.
- **Weekly:** kappa refresh per reviewer; calibration coaching scheduled for outliers.
- **Monthly:** workflow-design review; threshold recalibration if upstream confidence drifted.
- **Quarterly:** Validator + Audit joint sign-off on workflow design and quality posture.

## Exit criteria for v1 GA

- 100% of pilot workflows on designer with PM-signed reviewer capacity model
- Fleet-wide reviewer kappa ≥ 0.75 sustained for 30 days
- Rubber-stamp rate ≤ 4% sustained for 30 days
- SLA p95 ≤ 35min on tier-3 sustained for 30 days
- Audit-bundle signed for every reviewer decision (Project 08 verified)
- Zero loss events traceable to oversight gap during pilot quarter
