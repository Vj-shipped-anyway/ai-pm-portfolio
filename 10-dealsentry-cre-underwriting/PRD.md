# PRD · CRE AI Underwriting Reliability Sentinel

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-IC-steering read in a real engagement
**Date:** 2026-Q2

> **Framing:** This PRD applies the PM rigor I bring to enterprise AI to a domain I follow as a personal study interest. I am not an LP in a CRE portfolio; CRE is something I read deeply on. The architecture, the three-check sentinel design, and the rollout plan are mine; the production validation is what the next role does.

---

## 1. Problem

Acquisitions teams now use AI copilots to draft underwriting memos: comp pulls, market reads, T-12 normalization, rent-roll math, IRR/cash-on-cash projections. Outputs reach IC with hallucinated comps, fabricated submarket stats, and arithmetic errors that compound through the model. Analysts trust them because the writing is fluent. The result: bad bids, blown deals, mispriced acquisitions, and a reputational tax with brokers and committee.

**Primary user:** Senior Acquisitions Analyst / VP Acquisitions (line 1).
**Secondary user:** Investment Committee chair (governance).
**Tertiary user:** Asset Management (post-close handoff), CFO (capital deployment), External brokers (counterparty trust).

## 2. Why now

- AI underwriting copilots are deployed at every institutional CRE shop. Almost none QA the output.
- Capital markets are tight; mispricing on a single acquisition is now real money.
- Source-of-truth databases (CoStar, Reonomy, Cherre, proprietary) are API-accessible — citation verification is technically feasible and cost-cheap.
- LLM hallucination on numerical and citation-heavy work is a *known property*, not a bug. Mitigation has to be a product.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Cut comp-hallucination rate | % of cited comps that fail verification | 18% to under 2% |
| Cut underwriting rework | Re-draft cycles per IC memo | Baseline to −60% |
| Avoid bad bids | Deals priced on verified inputs | Baseline to +100% |
| Modeled value preserved | $/yr from avoided mispricings | $7.2M/yr |
| IC trust signal | Senior survey: "I trust AI-drafted memos" | +30 pts |

## 4. Non-goals

- Not an underwriting copilot (this verifies one).
- Not a comp database (consumes one or many).
- Not an IC workflow tool (interlocks with existing).
- Not a deal-screening engine.

## 5. User stories

- **As a Senior Analyst**, I want a verification report on my AI-drafted memo before IC, so I'm never the one defending a hallucinated comp in front of committee.
- **As VP Acquisitions**, I want a portfolio-level reliability dashboard, so I know which analysts and which submarkets carry the highest hallucination risk.
- **As IC chair**, I want every memo to carry a verification stamp with sectional pass/fail, so committee time goes to judgment, not arithmetic checking.
- **As Asset Management** (post-close), I want the verified underwriting attached to the property file, so post-close performance is benchmarked against truth, not the marketing memo.
- **As an External Broker**, I want our offers to be based on verifiable numbers, so the relationship survives a missed bid.

## 6. Solution

### Three-check sentinel

#### Check 1 — Comp citation verification
Every comp cited (sale comp, lease comp) is dereferenced against the source-of-truth database. Verification:
- Asset address matches → exists.
- Transaction date within stated window.
- Price/sf, cap rate, NOI within tolerance of source-of-truth.
- Asset class and submarket match.

Failure modes flagged: not-found, stale, off-class, off-submarket, value mismatch.

#### Check 2 — Symbolic arithmetic re-validation
Re-compute deterministically:
- T-12 NOI from rent roll × effective rent × occupancy − operating expenses.
- Effective rent on stepped leases (correct escalation period).
- Expense ratios vs. trailing periods.
- IRR / cash-on-cash from cashflow projections (re-run as code, not LLM).

Divergence beyond tolerance flagged with the offending line item.

#### Check 3 — Submarket stat cross-check
For every quoted vacancy / asking rent / cap rate / absorption stat, pull from at least 2 source-of-truth feeds. Divergence beyond tolerance is flagged. "Source: training data" or unattributed stats are auto-flagged.

### Confidence dashboard

Per-section confidence + drill-in. Sectional pass/fail required to forward to IC. Override path requires senior sign-off and writes to audit trail.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Source-of-truth database is itself wrong | Med | High | Multi-source for stats; tolerance bands; human-override on confirmed source-of-truth error |
| Tolerance bands too tight → analyst friction | High | Med | Per-field tunable bands; track override-and-was-right rate as input |
| Tolerance bands too loose → hallucinations slip | Med | High | Quarterly recalibration against IC outcomes |
| Symbolic re-val diverges due to AI normalization choices | Med | Med | Surface assumption diffs (e.g., "AI applied 5% mgmt fee, source OM shows 4%"); don't hide |
| Cost of source-of-truth API calls per memo | Med | Med | Cache + batch; budget per memo capped; degrade gracefully |
| Analyst learns to "write around" the sentinel | Med | High | Audit trail of every override; manager review of high-override analysts |

## 8. KPIs

**North star:** % of IC memos with a clean three-check pass before submission at least 95%.

**Inputs (leading):**
- Comp-citation verification pass rate (target at least 98%)
- Symbolic-arithmetic divergence rate (target under 3%)
- Submarket-stat cross-check pass rate (target at least 95%)
- Sentinel runtime per memo (target under 90s)
- Source-of-truth API uptime (target at least 99.5%)

**Outputs (lagging):**
- Modeled bad-bid avoidance ($/yr)
- IC rework cycles per memo (target −60%)
- Senior-survey trust score (target +30 pts)
- Post-close NOI variance vs. underwriting (information signal)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Source-of-truth integration | 8w | CoStar / Reonomy / Cherre / proprietary; comp + stat APIs; rate-limit and cache |
| 1 — Comp verification check | 6w | Citation parse → dereference → flag; 1 region pilot |
| 2 — Symbolic arithmetic | 8w | T-12, rent roll, expense, IRR re-run; divergence flagging |
| 3 — Submarket stat cross-check | 6w | Multi-source pull; divergence tolerance; flag-or-pass |
| 4 — IC integration | 6w | Verification stamp on memos; override workflow; sectional pass/fail UX |
| 5 — Portfolio rollout | 12w | All acquisitions teams; dashboard for VP Acquisitions and IC |
| 6 — Continuous calibration | ongoing | Quarterly tolerance recalibration vs. IC outcomes |

## 10. Open questions

1. How prescriptive on "no AI memo to IC without a clean pass"? (Recommend: hard rule on Tier-1 deal size, soft rule below threshold.)
2. Tolerance authority — who tunes? (Recommend: VP Acquisitions in concert with IC chair; calibration logs go to audit trail.)
3. When source-of-truth feeds disagree with each other, default? (Recommend: surface both, do not pick.)
4. How does this interlock with broker-supplied OM packets? (Recommend: separate truth track; sentinel verifies AI claims, not broker claims, but flags broker claims that AI ingested without source.)

## 11. Build & Scale Notes

**Reference architecture (vendor-named):**
- Memo parser: Claude Sonnet via Bedrock or direct Anthropic API. Extracts structured claims from the AI-drafted memo (comps, stats, T-12 line items, IRR assumptions). Hard "cite or refuse" prompt — the parser doesn't infer; it extracts what's literally there.
- Comp citation verification: API integrations to CoStar (CompStak for sale comps), Reonomy, and Cherre. Address normalization via a Python-side library (libpostal or USAddress); transaction-date match within stated window; price/sf, cap rate, NOI within tolerance.
- Symbolic re-validator: plain Python with pandas. Re-runs T-12, rent roll, effective-rent-on-stepped-leases, expense ratios, IRR / cash-on-cash. **No LLM in this path.** Outputs a divergence table with offending line items.
- Submarket stat cross-check: parallel calls to CoStar, Reonomy, Cherre, plus internal proprietary feed if available. Tolerance bands per stat type. Disagreement surfaced, never resolved by the sentinel.
- Orchestration: Temporal for the per-memo workflow (parse → three checks in parallel → aggregate → route). Airflow for the nightly source-of-truth API cache refresh.
- Retrieval/vector layer: pgvector on Postgres for prior-IC-memo retrieval (context for the senior reviewer). 768-dim embeddings.
- Cache: Postgres + Redis. Source-of-truth API responses cached 24-72h depending on stat freshness requirements. Cache strategy materially affects cost.
- Storage: Postgres for verification reports, override audit trail, source-of-truth cache. Snowflake for analytics (per-analyst, per-submarket, per-broker hallucination rate over time).
- Observability: OpenTelemetry into Datadog. Langfuse for parser LLM traces. Per-broker hallucination dashboard is a load-bearing feature.
- Verification stamp: PDF stamp generated server-side with sectional pass/fail badges, signed (KMS), embedded in the IC packet.
- Override workflow: senior sign-off UI with audit-trail write to Project 08's ledger.
- Post-close integration: verified underwriting feeds Argus deal model; asset onboarding to Yardi or MRI; leasing handoff to VTS; debt-side workflow to Lev when applicable.
- Security: SOC 2 Type II. CoStar / Reonomy / Cherre license terms govern data RBAC. Broker NDA redaction policy explicit before launch.

**Throughput envelope and latency budget:**
- Designed envelope: 800 IC memos / year for an institutional shop. Peak 6 memos in the same week.
- Sentinel runtime per memo: under 90s p95. The three checks run in parallel; the bottleneck is the source-of-truth API latency on cache miss.
- Comp verification: under 30s for a memo with 12 comps cited (cache hits dominate after warm-up).
- Symbolic re-val: under 5s. It's just pandas.
- Submarket stat cross-check: under 20s.
- Verification stamp render: under 10s.

**Failure modes:**
- Source-of-truth feed disagrees with itself (CoStar updated mid-day vs morning pull). Mitigation: cache TTL tuned per stat type; force-refresh on Tier-1 deals.
- Cache poisoning from a stale CoStar response. Mitigation: source-of-truth response includes vendor-side timestamp; cache invalidates on staleness.
- Analyst writes "around" the sentinel by paraphrasing comps to avoid citation match. Mitigation: override audit trail; manager review of high-override analysts; quarterly tolerance recalibration against IC outcomes.
- Broker OM packet contains numbers the AI ingested without source. Mitigation: sentinel flags any unattributed stat in the AI memo; broker claims are a separate truth track.
- Tolerance bands miscalibrated (too tight = analyst friction; too loose = hallucinations slip). Mitigation: per-field tunable bands; quarterly recalibration; track override-and-was-right rate.

**Migration path:**
- Phase 0: source-of-truth integration. Stand up the CoStar / Reonomy / Cherre clients. Cache layer. Rate-limit governance (vendor contracts often cap calls per day).
- Phase 1: comp verification only. Run shadow on 20 memos. Measure precision/recall of "fail" flags against IC outcomes.
- Phase 2: symbolic arithmetic re-val live. Most divergences will be assumption diffs (mgmt fee %, vacancy assumption) rather than fabrications — surface them, don't hide.
- Phase 3: submarket stat cross-check live. Tolerance bands tuned with VP Acquisitions and IC chair.
- Phase 4: IC integration. Verification stamp on every memo. Override workflow. Sectional pass/fail in the IC packet.
- Phase 5: full portfolio. Per-analyst, per-broker dashboards live.
- Phase 6: continuous calibration loop. Quarterly tolerance recalibration vs. post-close NOI variance.

**Org dependencies:**
- VP Acquisitions owns the override decision and the tolerance-tuning authority. Must be co-author of the rollout, not a stakeholder.
- IC chair owns the "no memo to IC without a clean pass" rule for Tier-1 deals. Without this rule, the sentinel becomes optional and adoption stalls.
- Senior Analysts are the daily users. Frame the sentinel as "defends the analyst in front of IC," never "checks the analyst."
- Asset Management consumes the verified underwriting at post-close handoff.
- Tech is builder. They don't own.
- Project 08 (audit trail) consumes every override and verification as a lineage event.
- Project 09 (lease abstraction detector) feeds the corrected lease abstractions into Check 2's rent-roll arithmetic. Without Project 09, Check 2 is materially weaker on portfolios with non-standard leases.

---

*This PRD interlocks with Project 08 (Audit Trail) — every override and verification is a lineage event — and Project 09 (Lease Abstraction Detector) — corrected lease abstractions feed Check 2's rent-roll arithmetic.*
