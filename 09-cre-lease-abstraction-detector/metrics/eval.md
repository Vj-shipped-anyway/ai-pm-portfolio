# Evaluation & KPI Tree — CRE Lease Abstraction Error Detector

## North-star

**Field-level abstraction error rate vs. ground truth ≤ 2%.**

Why this north star: it is the single number that translates directly into recovered rent, dispute defensibility, and underwriting truth. Reviewer hours and flag counts are inputs.

## KPI tree

```
North star: Field-level abstraction error rate ≤ 2%
│
├── INPUTS (leading, weekly)
│   ├── % of portfolio leases through QA layer (target 100%)
│   ├── Flag precision (target ≥ 0.85)
│   ├── Flag recall on injected errors (target ≥ 0.95)
│   ├── Median ensemble cost per lease ($)
│   └── Reviewer SLA: hours to clear a flagged lease (target ≤ 1 day)
│
├── PROCESS (mid, monthly)
│   ├── Reviewer hours per lease (target ≤ 30 min)
│   ├── Override rate by field (sanity check on flag tuning)
│   ├── Ground-truth audit pass rate on 5% sample (target ≥ 98%)
│   └── Vintage-stratified error rate (Older ≤ 2024 vs. ≥ 2024)
│
└── OUTPUTS (lagging, quarterly)
    ├── Modeled recovered rent ($/yr, target $4.2M)
    ├── Buyer-side surprise findings post-close (count, $, target -60%)
    ├── Missed-clause litigation exposure ($, target -70%)
    └── Acquisition diligence cycle days (information signal)
```

## Eval harness

The prototype runs the three-extractor ensemble against a 6-lease corpus with hand-labeled ground truth. The eval harness scores:

| Metric | Formula | Target |
|--------|---------|--------|
| Field-level error rate | wrong / total field-extractions | ≤ 2% |
| Flag precision | flagged-and-actually-wrong / flagged | ≥ 0.85 |
| Flag recall | flagged-and-wrong / total-wrong | ≥ 0.95 |
| Missing-but-likely true-positive | clauses correctly identified as missing | ≥ 0.80 |
| Cost per lease ($) | LLM + infra | ≤ $1.10 |

## Test scenarios (corpus replay)

1. **Standard ICSC retail (L-001).** Expected: zero hard disagreements, primary matches ground truth on all fields.
2. **Redlined coffee operator (L-002).** Expected: hard disagreement on `cam_cap_noncontrollable` (primary drops it), `escalation_pct` flagged.
3. **Older non-standard big-box (L-003).** Expected: missing-but-likely on `escalation_pct`, hard disagreement on `use_clause` (primary over-normalizes to "retail").
4. **BOMA office standard (L-004).** Expected: zero or one soft flag.
5. **Redlined specialty grocer (L-005).** Expected: hard disagreement on `cam_cap_noncontrollable` and `kick_out`.
6. **Non-standard industrial (L-006).** Expected: rule extractor wins on `base_rent_psf` and `escalation_pct`; primary aligned.
7. **Reviewer-flag false-positive control.** Inject 50 leases with no errors. Expected: ≤ 8% false-positive flag rate.
8. **Vintage stratification.** Expected: pre-2015 leases show 4x baseline error vs. 2020+; QA layer normalizes both to ≤ 2%.

## Ongoing eval cadence

- **Daily:** ensemble run on new leases; flag-rate dashboard.
- **Weekly:** reviewer-feedback summary; flag precision/recall recompute.
- **Monthly:** ground-truth audit on 5% sample (~10–20 leases on a 220-asset portfolio); per-field error rate published.
- **Quarterly:** vintage and asset-class fairness audit on the missing-but-likely classifier; retrain trigger.
- **Annual:** modeled recovered-rent recomputation against actuals; buyer-side findings reconciliation.

## Exit criteria for v1 GA

- 100% portfolio coverage on the QA layer
- Field-level error rate ≤ 2% sustained for 90 days
- Reviewer hours per lease ≤ 30 min sustained for 60 days
- Flag precision ≥ 0.85, recall ≥ 0.95 on monthly audit
- Asset Management leadership sign-off on $-impact ranking UX
- Legal sign-off on override audit trail
