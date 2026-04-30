# Evaluation & KPI Tree — AI Audit Trail & Decision Lineage

## North-star

**Median time-to-audit-evidence for any production AI decision ≤ 15 minutes.**

Why this north star: it composes coverage (capture breadth), schema completeness (depth), and retrieval performance (timeliness) into one number Compliance Counsel can answer in front of a regulator. Anything else is an input.

## KPI tree

```
North star: Median time-to-audit-evidence ≤ 15 min
│
├── INPUTS (leading, daily/weekly)
│   ├── % of Tier-1 models emitting complete records (target 100%)
│   ├── Schema-completeness score per model (target ≥ 99.5%)
│   ├── Retrieval-set capture rate on GenAI (target ≥ 99%)
│   ├── Vendor-version pin rate on GenAI (target 100%)
│   └── Daily Merkle-anchor freshness (target: anchored < 24h)
│
├── PROCESS (mid, monthly)
│   ├── Median time-to-audit-evidence (Tier-1)
│   ├── p99 time-to-audit-evidence (Tier-1)
│   ├── Audit-pack assembly success rate (target ≥ 99.9%)
│   └── Internal-audit sample pass rate (target ≥ 98%)
│
└── OUTPUTS (lagging, quarterly)
    ├── Reg-exam findings on AI traceability (target: 0)
    ├── Settled-dispute volume on AI-touched decisions ($ and count)
    ├── Forensic-engineering FTE-hours saved
    └── Continuous-exam-readiness posture (binary)
```

## Eval harness

The prototype loads 50,000 synthetic decisions. The eval harness benchmarks:

| Metric | Formula | Target |
|--------|---------|--------|
| Single-decision lineage retrieval (p50) | end-to-end query → bundle assembled | ≤ 60 s |
| Single-decision lineage retrieval (p99) | end-to-end query → bundle assembled | ≤ 5 min |
| Schema completeness | % of records with all required fields populated | ≥ 99.5% |
| Hash-chain integrity | random-sample audit walks 100% intact | 100% |
| Pseudonym join correctness | customer-grain re-join across LOBs | ≥ 99.99% |

## Test scenarios (production replay)

1. **Exam request, 9-month-old denied credit decision.** Expected: bundle assembled ≤ 12 min; full lineage incl. feature snapshot, model version, training run, retrieval set if applicable.
2. **Customer dispute on GenAI advisor output.** Expected: full prompt hash, retrieval chunks, tool calls, model version, and downstream customer-comm ID returned in one bundle.
3. **Vendor silent-update window.** Expected: every GenAI decision before/after the snapshot change is differentiable by `model_version` field; zero ambiguous records.
4. **HITL-overridden decision under litigation.** Expected: reviewer_id, dwell time, and the exact UI state the reviewer saw (interlock with Project 07) are reconstructable.
5. **Schema-completeness regression.** Expected: a deliberately-malformed write is rejected at the edge, never stored.
6. **Continuous-exam-readiness drill.** Expected: 100 random decisions sampled per quarter, all walked end-to-end in < 1 day total.

## Ongoing eval cadence

- **Continuous:** schema-completeness scoring on every write; rejection rate alerted in real time.
- **Daily:** Merkle anchor freshness check; hash-chain integrity sample.
- **Weekly:** retrieval p50/p99 review; vendor-version pin coverage.
- **Monthly:** synthetic exam drill — pull a random Tier-1 decision and time end-to-end.
- **Quarterly:** internal-audit sample of 100 decisions, full walk; per-model lineage scorecard published to AI Governance Council.

## Exit criteria for v1 GA

- 100% Tier-1 model coverage on the capture SDK
- ≥ 99.5% schema completeness sustained for 30 days
- p99 time-to-audit-evidence ≤ 5 min for 30 consecutive days
- Hash-chain integrity = 100% across full sample audit
- Compliance Counsel sign-off on audit-pack format
- Internal Audit (line 3) attestation of the surface itself
