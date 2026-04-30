# PRD · AI Inference Economics Dashboard

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.0 — pre-CFO + CTO joint read
**Date:** 2026-Q2

---

## 1. Problem

The bank has GenAI features in production but no per-feature cost visibility. Vendor invoices arrive monthly, in aggregate. Finance can't answer "what does this feature cost per user, per call, per segment?" Product can't answer "is this feature paying for itself?" Engineering can't answer "would the cheaper model do for this slice?" The information vacuum produces a predictable failure: discovery of overspend three weeks after it started, decisions on model selection made by folklore not data, and dead features that bleed budget because no one has the authority or the signal to kill them.

**Primary user:** AI Feature PM / Product Owner (line 1).
**Secondary user:** AI Platform FinOps lead (line 1, central).
**Tertiary user:** CFO / Finance Business Partner (line 2 oversight on AI spend).

## 2. Why now

- Every Tier-1 US bank has multiple GenAI features in production by 2026; spend is no longer rounding error.
- Vendor pricing is volatile. Vendor changes price. New models released quarterly. Without per-feature metering, the bank can't respond.
- Multi-vendor (OpenAI, Anthropic, Bedrock, Azure OpenAI, in-house GPU) makes invoice aggregation manual and error-prone.
- Cost-quality trade-off has shifted: cheaper open-weight models now match GPT-4-class on many BFSI slices. Without measurement, the bank pays the premium tax forever.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Per-feature cost visibility | % of features with $/call attribution | 0% → 100% |
| Reduce spend on wrong-model defaulting | Modeled saving via substitution | ≥ 18% |
| Prune dead features | $ pruned from features below adoption floor | ≥ 9% of total spend |
| Prevent budget blowouts | Confirmed envelope breaches without alert | 0 |
| Vendor-invoice reconciliation | Days from invoice to attribution | 14d → same day |

Targets are modeled against five-feature synthetic traffic with cost shapes I've seen at Tier-1 BFSI shops. The 27% combined headline (substitution + dead-feature pruning) is not a guarantee; it's the order of magnitude.

## 4. Non-goals

- Not a model-serving platform. Consumes meter signals from existing.
- Not a finance ledger. Writes a daily feed into the existing cost-allocation system (SAP, Workday, or homegrown).
- Not a model-selection engine. Recommends; PM decides.

## 5. User stories

- **As a Feature PM**, I want to see my feature's $/call broken by user cohort and segment, so I can answer "is this paying for itself?" without a finance ticket.
- **As a Platform FinOps lead**, I want a single dashboard across all vendors and features, so I can spot a runaway in hours, not weeks.
- **As a CFO**, I want a monthly view of AI spend by business line, with a forecasted next-month envelope, so AI cost stops being a surprise on the P&L.
- **As a Validator**, I want every cost-driven model-selection decision logged with the eval evidence, so model risk has a record.

## 6. Solution

A three-loop surface metering every inference and rolling spend up to feature, user, segment, and business line.

### Loop 1 — Meter
- Token-level metering at the gateway (interlocks with Project 05 — same gateway dataplane).
- Attribution: feature_id, user_id, customer_segment, vendor, model, region.
- Vendor-invoice reconciliation: vendor invoice line items mapped to internal feature_id same-day.

### Loop 2 — Compare
- **Cost-quality frontier** per feature and per slice. X-axis $/call, Y-axis quality score from eval harness (interlocks with Project 02 if present, otherwise own eval).
- **Model-mix** view: traffic share by model, by feature, by segment.
- **Substitution simulator**: "if we ran segment X on cheaper model, modeled $ saved with quality delta within tolerance."

### Loop 3 — Govern
- **Monthly envelope per feature**, signed by Feature PM.
- **Alerts at 60 / 80 / 100%** of envelope; auto-throttle at 100%, kill-switch authority to PM.
- **Dead-feature monitor**: features below adoption floor flagged for kill review at 30 / 60 / 90 days.
- **Audit event** to Project 08 for every kill / model-swap / envelope change.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Cheaper-model swap silently degrades quality | High | High | Cost-quality frontier requires eval evidence (Project 02); shadow-mode swap before promote |
| Throttle harms customer-facing UX during a spike | Med | High | Customer-facing features get soft-throttle (model downgrade) not hard-throttle; envelope set at 1.4x P50 |
| Per-user attribution conflicts with privacy | Med | Med | Aggregate above k=20 cohorts for any reporting outside engineering; works-council review in EU |
| Vendor invoice format changes break reconciliation | High | Med | Schema-on-read ingestion + canary on each vendor close-out cycle |
| Feature PM lacks kill authority | High | High | Governance gate: kill authority delegated by name; CFO co-sign on > $250k/yr features |

## 8. KPIs

**North star:** % of AI feature spend with attribution down to feature × segment, with 100% reconciled to vendor invoice within 24 hours.

**Inputs (leading):**
- Coverage: % of features metered at the gateway
- % of vendor invoices reconciled same-day
- Cost-quality frontier refresh cadence (target: weekly)

**Outputs (lagging):**
- Modeled spend reduction (cheaper-model substitution + dead-feature pruning)
- Budget-envelope breach incidents (target: 0)
- $ saved per quarter per feature
- Time from cost anomaly to PM-aware (target ≤ 1 day)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Gateway metering on; feature catalog tagged; ingestion of one vendor invoice |
| 1 — All vendors | 6w | Schema-on-read for OpenAI / Anthropic / Bedrock / Azure / internal GPU |
| 2 — Frontier + simulator | 8w | Cost-quality frontier per feature; substitution simulator |
| 3 — Envelopes + alerts | 6w | Per-feature envelopes signed; alerting wired |
| 4 — Auto-throttle / kill | 8w | Throttle and kill-switch authority delegated; first dead-feature pruning |
| 5 — CFO monthly close | ongoing | Same-day reconciliation; CFO close-out pack auto-generated |

## 10. Open questions

1. Soft-throttle (downgrade model) vs hard-throttle (drop traffic) — recommend soft for customer-facing, hard for internal.
2. How do we treat free-tier internal experimentation — count or exclude? Recommend: count, with separate envelope.
3. Multi-tenant chargeback granularity — feature × business line, or feature × cost-center? Recommend the latter; aligns with finance ledger.
4. Vendor lock-in: should the substitution simulator force monthly cross-vendor benchmarking? Recommend yes; it's a control.

## 11. Build & Scale Notes

**Reference architecture (vendor-named).**

- **Metering point:** shared Envoy/Istio gateway with Project 05. Token-level event emission via OpenTelemetry GenAI semconv.
- **Inference targets metered (not run by this product):** Azure OpenAI gpt-4o + gpt-4o-mini, Anthropic Claude Sonnet on Bedrock, Anthropic Claude Haiku, in-house fine-tuned Mistral 7B on H100.
- **Substitution simulator judge:** Anthropic Claude Haiku as the eval-tied LLM-judge.
- **Eval harness embedding store:** Postgres + pgvector — eval set is small, managed vector DB is overkill.
- **Time-series metering store:** ClickHouse. Datadog's at-scale custom-metric pricing makes this product self-defeating; ClickHouse is the only viable path at fleet rollout.
- **Vendor-invoice ingest:** Airflow with schema-on-read parsers per vendor. Snowflake or Databricks as the canonical reconciliation warehouse.
- **Substitution + frontier-refresh orchestration:** Temporal (weekly default, daily for top-spend).
- **CFO close-out pack:** auto-generated PDF/XLSX into the format finance already uses; ledger-of-record feed into the bank's SAP / Workday / homegrown cost-allocation system.
- **Observability of the metering platform itself:** Datadog (service health), Langfuse (LLM-judge traces), Grafana on ClickHouse (PM-facing FinOps dashboard).
- **Compute:** CPU-only at the metering point. Lambda / Cloud Run for the substitution simulator's small judge batches. Eval-set sweeps run on whatever the candidate model serves on (T4 / L4 for open-weight, vendor API otherwise).
- **Data plane:** Unity Catalog or AWS Lake Formation tags every metering event by feature_id, vendor, model, region, customer_segment, business_line. Collibra if already deployed.

**Throughput envelope and latency budget.**

- Pilot: 5 features, ~2M to 5M inferences/month.
- Steady-state: 30 features, ~80M to 150M inferences/month.
- Metering events/sec at peak: ~80.
- Metering added latency: target ≤ 5ms p95 inline (metering must not be felt by the user).
- Reconciliation: same-day for vendors that publish invoice line-items in machine-readable form (most by 2026); 24h-target for the laggards.
- Frontier-refresh cost cap: ≤ $5k/quarter in eval-time API spend per feature (the cure cannot cost more than the disease).

**Failure modes and degradation strategy.**

- ClickHouse degraded: metering events buffer at Kafka; PM-facing dashboards run on last-good cache up to 6 hours; reconciliation pauses with explicit banner.
- Vendor-invoice format breaks: schema-on-read canary fails loudly per vendor; manual reconciliation path stays available; finance receives explicit "stale by X days" status.
- Substitution simulator regresses (judge model behavior changes): freeze auto-recommendations; flag every existing substitution decision for re-validation under Project 02.
- Auto-throttle stuck: customer-facing soft-throttle (model downgrade to gpt-4o-mini or Haiku) holds; PM has manual kill-switch; envelope override gated by 2-of-2 sign-off (PM + Platform FinOps).

**Migration path from current state.**

- Phase 0: deploy metering at the gateway in passive mode for one feature. Reconcile against last month's invoice manually to validate attribution.
- Phase 1: expand to all five pilot features. Ingest all vendor invoices. PMs see per-call cost for the first time.
- Phase 2: build the cost-quality frontier on the eval harness from Project 02 (or a minimal own-eval). Surface, don't enforce.
- Phase 3: per-feature envelopes signed by PMs. Alerts at 60 / 80 / 100%. No auto-throttle yet.
- Phase 4: enable auto-throttle with soft default. First dead-feature kill review at 90-day mark.
- Phase 5: CFO close-out pack live; reconciliation moves to same-day.

**Org dependencies.**

- AI Platform team: build owner; shares the gateway dataplane with Project 05.
- AI Feature PMs: own per-feature envelopes and kill decisions (cultural shift required).
- CFO / Finance Business Partner: signs off on cross-feature envelope; co-signs > $250k/yr features.
- Model Risk (line 2): signs off on cheaper-model substitution affecting any regulated path.
- Internal Audit (line 3): receives evidence chain from Project 08 on every kill / swap / envelope change.
- InfoSec: privacy review on per-user metering tagging.
- Procurement: ClickHouse contract, Claude Haiku judge tokens, eval-time API budget.
- HR / Works Council (EU): review on per-user attribution before EU rollout.

---

*This PRD interlocks with Projects 01 (drift events log $/inference deltas), 02 (eval harness — cost-quality frontier ties to Y-axis), 04 (Agent Reliability — agent trajectories meter through the same gateway), 05 (gateway metering hooks share dataplane), and 08 (audit events on kill / swap / envelope changes).*
