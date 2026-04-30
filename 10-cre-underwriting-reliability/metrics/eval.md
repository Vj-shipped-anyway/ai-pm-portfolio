# Evaluation & KPI Tree — CRE AI Underwriting Reliability Sentinel

## North-star

**% of IC memos with a clean three-check pass before submission ≥ 95%.**

Why this north star: it composes citation accuracy (truth), arithmetic integrity (math), and stat sourcing (market) into one IC-readable number. Pass rate is the only metric a CIO cares about; everything else is an input.

## KPI tree

```
North star: % IC memos with clean three-check pass ≥ 95%
│
├── INPUTS (leading, weekly)
│   ├── Comp-citation verification pass rate (target ≥ 98%)
│   ├── Symbolic-arithmetic divergence rate (target ≤ 3%)
│   ├── Submarket-stat cross-check pass rate (target ≥ 95%)
│   ├── Sentinel runtime per memo (target ≤ 90s)
│   └── Source-of-truth API uptime (target ≥ 99.5%)
│
├── PROCESS (mid, monthly)
│   ├── IC rework cycles per memo (target -60%)
│   ├── Override-and-was-right rate (calibration signal)
│   ├── Per-analyst override rate (manager-review trigger)
│   └── Per-submarket hallucination rate (heatmap)
│
└── OUTPUTS (lagging, quarterly)
    ├── Modeled bad-bid avoidance ($/yr, target $7.2M)
    ├── Senior-survey trust score (target +30 pts)
    ├── Post-close NOI variance vs. underwriting (information signal)
    └── Broker counterparty trust (qualitative)
```

## Eval harness

The prototype runs the three-check sentinel on a synthetic AI-drafted memo with deliberately injected failure modes. The eval harness scores:

| Metric | Formula | Target |
|--------|---------|--------|
| Comp-fabrication detection | TP on injected fake comps / total fakes | ≥ 0.98 |
| Comp-stale detection (off-date) | TP on stale comps / total stale | ≥ 0.95 |
| Comp-class mismatch detection | TP on wrong-class comps / total | ≥ 0.95 |
| Arithmetic divergence detection (>5%) | TP / total injected | ≥ 0.99 |
| Submarket stat fabrication detection | TP on injected fake stats / total | ≥ 0.95 |
| False-positive rate (clean memo) | flags-on-clean / clean-fields | ≤ 3% |
| Sentinel runtime | end-to-end seconds per memo | ≤ 90 |

## Test scenarios (memo replay)

1. **Clean memo, all comps verifiable, math clean.** Expected: 100% pass, forward to IC.
2. **Fabricated comp address.** "1200 Hollywood Blvd" not in source-of-truth. Expected: NOT FOUND flag, sectional fail on comp check.
3. **Stale comp.** 2019 transaction cited as "recent." Expected: stale flag, divergence on date.
4. **Off-class comp.** Multifamily comp cited as office. Expected: class-mismatch flag.
5. **Value-mismatch comp.** "$535/sf" claimed; truth $612/sf. Expected: VALUE MISMATCH flag if outside tolerance.
6. **Arithmetic NOI divergence.** Implied NOI ≠ recomputed effective rent × (1 − opex_ratio). Expected: DIVERGENCE on the line item.
7. **Submarket stat divergence.** "Vacancy 6.1%" vs. CoStar 12.4% / Reonomy 12.1%. Expected: DIVERGENCE on both feeds.
8. **Two-feed disagreement.** CoStar 9.7% vs. Reonomy 10.0% (within 5% tolerance). Expected: surface both, no flag.
9. **Tolerance-band tightness probe.** Sweep tolerance bands; record FN/FP curve; pick operating point.

## Ongoing eval cadence

- **Per memo:** sentinel runs and stamps. No memo to IC without a recorded result.
- **Daily:** comp-verification volume + pass rate dashboard.
- **Weekly:** per-analyst override-and-was-right rate; high-override analysts surface to manager.
- **Monthly:** tolerance-band review; per-submarket hallucination heatmap; per-feed disagreement tracking.
- **Quarterly:** post-close NOI variance review for last quarter's closed deals; senior-survey pulse.

## Exit criteria for v1 GA

- 100% of acquisitions teams using the sentinel
- Clean-pass rate ≥ 95% sustained for 60 days
- Comp-fabrication detection ≥ 98% on monthly synthetic injection test
- Arithmetic-divergence detection ≥ 99% on monthly synthetic injection test
- IC chair sign-off on verification stamp UX
- VP Acquisitions sign-off on portfolio dashboard
