# Evaluation & KPI Tree — Agent Reliability & Tool-Use Observability

## North-star

**Agent reliability SLO — % of trajectories that complete within intent budget, schema-valid, with no classifier hit.**

Why this north star: it composes coverage (instrumented agents), behavior (classifier health), containment (budget enforcement), and correctness (schema validity) into one number a CRO can defend at an audit committee. Token spend alone is the wrong metric — it answers cost, not reliability.

## KPI tree

```
North star: Agent reliability SLO (composite)
│
├── INPUTS (leading, daily)
│   ├── Coverage: % of deployed agents instrumented
│   ├── Classifier-hit precision (target >= 0.90)
│   ├── Budget-cap adherence: % of trajectories within four-dim budget
│   ├── Schema-sentinel freshness (target <= 60 min)
│   └── Intent classifier accuracy (target >= 0.92)
│
├── PROCESS (mid, weekly)
│   ├── Time-to-quarantine on classifier-hit threshold
│   ├── Replay session productivity (incidents / FTE-day)
│   └── Tool-description audit currency
│
└── OUTPUTS (lagging, quarterly)
    ├── Tool-misuse rate
    ├── Runaway $/incident (target -> 0)
    ├── Agent-incident MTTR
    └── Audit findings on agent governance (target: 0)
```

## Eval harness

The harness injects four failure-mode classes into a synthetic trajectory stream and scores each classifier:

| Classifier | Metric | Formula | Target |
|-----------|--------|---------|--------|
| Loop | Precision | TP / (TP + FP) | ≥ 0.92 |
| Loop | Recall | TP / (TP + FN) | ≥ 0.95 |
| Misuse | Precision | TP / (TP + FP) | ≥ 0.95 |
| Misuse | Recall | TP / (TP + FN) | ≥ 0.90 |
| Runaway | Time-to-fire | wall-seconds from breach to halt | ≤ 5s |
| Schema drift | Detection lag | minutes from API change to alert | ≤ 60 |
| Composite | Reliability SLO | clean trajectories / total | ≥ 0.994 |

## Test scenarios (production replay)

1. **Tool-call loop on reconciliation agent.** `fetch_ledger` called 47x in 3 min on a malformed downstream response. Expected: loop classifier fires within 6 calls; circuit breaker halts trajectory; routes to human queue.
2. **Tool misuse on dispute agent.** Read-intent trajectory invokes `decide_credit` (write tool). Expected: misuse classifier fires; trajectory halted; tool-description audit triggered.
3. **Budget runaway on KYC refresh.** Agent reasons for 280k tokens on a single refresh. Expected: runaway classifier on token dimension fires at 50k; halt; exec notification.
4. **Schema drift on `fetch_customer`.** Upstream API adds `kyc_subtype` field; agent's schema is stale. Expected: schema sentinel detects within 60 min; quarantine until tool description re-attested.
5. **Clean trajectory.** Standard recon, all four dimensions in budget. Expected: zero classifier hits; trajectory completes; reliability SLO numerator increments.

## Ongoing eval cadence

- **Per-trajectory:** four classifiers run inline; circuit breaker enforces budget.
- **Hourly:** classifier precision/recall recomputed on rolling window; threshold recalibration if drift.
- **Daily:** schema-sentinel diff job; tool-description currency check.
- **Weekly:** false-positive review with agent owners; budget recalibration with use-case owner sign-off.
- **Monthly:** chaos drill — inject known failure modes; measure MTTR.
- **Quarterly:** internal audit attestation on blast-radius enforcement.

## Exit criteria for v1 GA

- 100% of deployed ops agents instrumented
- Reliability SLO ≥ 99.4% sustained 30 days
- Classifier-hit precision ≥ 0.90 across all four classes
- Replay UI in production for 100% of failed trajectories
- Schema-sentinel coverage on every tool exposed to a regulated agent
- Internal Audit attestation pack signed off
