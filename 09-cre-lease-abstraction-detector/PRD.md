# PRD · CRE Lease Abstraction Error Detector

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.1 — pre-Asset Management leadership read
**Date:** 2026-Q2

---

## 1. Problem

Deployed lease-abstraction NLP is materially wrong on non-standard, redlined, and older leases. Errors are silent: a missed escalation, a fabricated CAM cap, a dropped exclusivity. They surface months later in operating numbers, tenant disputes, or buyer-side diligence findings — by which point the operator has already underwritten on bad data.

**Primary user:** Asset Manager (line 1) on a 30–60 asset portfolio.
**Secondary user:** Lease Administrator running the abstraction pipeline.
**Tertiary user:** Acquisitions / Diligence (during onboarding); Disposition (during marketing); Legal (during dispute).

## 2. Why now

- Vendor lease-NLP is in production at most institutional owner/operators. Almost none QA against ground truth at scale.
- Acquisition cycles compress diligence to 21–28 days; abstraction has to be *trusted* or the deal isn't underwritable on time.
- 8–10 yr lease vintage is now coming up for renewal and disposition; the older the lease, the more non-standard the language, the worse the abstraction.
- LLM ensemble inference cost is now low enough that running 2–3 extractors per lease is unit-economic.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Cut abstraction error rate | Field-level error rate vs. ground truth | 12.4% to under 2% |
| Recover rent | Modeled $/yr from caught escalation + CAM errors | $4.2M/yr |
| Cut reviewer load | Hours per lease post-deployment | 3.5h to under 30 min |
| Cut buyer-side surprise findings | Post-close abstraction findings, count/yr | Baseline to −60% |
| Reduce missed-clause litigation exposure | Modeled $ exposure | −70% |

## 4. Non-goals

- Not a lease-abstraction engine (this is a QA layer over the existing one).
- Not OCR (consumes already-extracted text).
- Not a property-management system.
- Not a lease negotiation tool.

## 5. User stories

- **As an Asset Manager**, I want a triage queue of suspect fields across my portfolio, sorted by $-impact, so I touch the leases that move NOI first.
- **As a Lease Administrator**, I want field-level disagreement flags with the source clause highlighted, so I correct in 2 minutes instead of re-reading the lease.
- **As a Diligence Analyst** (acquisitions), I want a portfolio-level confidence scorecard during the diligence window, so the offer reflects abstraction risk, not assumes it away.
- **As Legal**, I want an audit trail of every overridden field — who, when, why, source clause — so dispute defense is documented.
- **As a Disposition Lead**, I want assets re-QA'd before marketing, so the buyer's findings don't reprice the deal.

## 6. Solution

### Three-checker ensemble

For each canonical field — `base_rent`, `escalation_type`, `escalation_pct`, `term_start`, `term_end`, `cam_cap_controllable`, `cam_cap_noncontrollable`, `exclusivity`, `kick_out`, `rofr_rofo`, `tenant_rights`, `use_clause` — run:

1. **Primary extractor** (deployed vendor or in-house).
2. **Re-extract** with a different LLM / prompt / chunking strategy.
3. **Rule-based extractor** for high-precision patterns (regex + structured templates for escalations, dates, base rent).

### Disagreement scoring

- **Hard disagreement:** values differ — triage to human.
- **Soft disagreement:** one extractor null, another non-null — triage with "missing-but-likely-present" tag.
- **Confidence floor:** primary returns under threshold confidence — triage regardless.

### Missing-but-likely-present detector

A clause-class classifier predicts whether a tenant type / asset class / lease vintage *should* have a given clause. If the abstraction returns null but the prior is high, route to human.

### Reviewer triage UX

- Field-level disagreement view, side-by-side.
- Source-clause highlight rendered over the original PDF.
- One-click accept / override / "needs lease counsel."
- Override writes audit trail (interlocks with Project 08).

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reviewer fatigue from too many flags | High | High | Tunable thresholds per field; surface $-impact ranking; suppress low-$ low-confidence flags |
| Ensemble agrees and is still wrong | Med | High | Ground-truth audit on a 5% sample monthly; calibrate; surface "agreement-but-low-prior" cases |
| Source-clause highlight misaligns to PDF | Med | Med | Two-tier highlighting: char-offset primary, embedding-search fallback |
| Cost of running 2-3 extractors per lease | Med | Med | Tier extractors by suspicion; run full ensemble only when primary confidence under threshold |
| Missing-but-likely classifier biased by vintage | Med | High | Explicit fairness audit by vintage and asset class; reviewer-feedback retraining loop |
| Vendor lease-NLP is contractually opaque | Med | Med | QA against output, not model internals; vendor doesn't need to cooperate |

## 8. KPIs

**North star:** Abstraction error rate (field-level, vs. ground truth) under 2%.

**Inputs (leading):**
- % of portfolio leases run through QA layer (target 100%)
- Median ensemble cost per lease
- Reviewer-flag precision (target at least 0.85)
- Reviewer-flag recall on injected errors (target at least 0.95)

**Outputs (lagging):**
- Modeled recovered rent ($/yr)
- Buyer-side surprise findings post-close (count, $)
- Missed-clause litigation exposure ($ modeled)
- Reviewer hours per lease (target under 30 min)

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Field schema + ground-truth set | 6w | Canonical field list; ground-truth sample (300 leases); error-rate baseline |
| 1 — Ensemble & rules | 8w | Re-extractor + rule extractor + disagreement scoring; 1 pilot region |
| 2 — Reviewer UX | 6w | Triage queue, source-clause highlight, override workflow, audit trail |
| 3 — Missing-but-likely | 8w | Clause-class classifier; vintage/asset-class fairness audit |
| 4 — Portfolio rollout | 12w | All 220 assets; integration with diligence + disposition workflows |
| 5 — Continuous QA | ongoing | Monthly ground-truth audit; reviewer-feedback retraining |

## 10. Open questions

1. Where does this live — under Asset Management, Lease Admin, or Tech? (Recommend product under Asset Management with Tech as builder.)
2. How does this interlock with the abstraction vendor's own confidence scores? (Recommend: ignore vendor confidence as ground signal; treat only as one input.)
3. Diligence-window throughput — can we hit 21-day acquisition close cycles? (Bench: 200 leases / 21 days = 10/day reviewer load. Achievable.)
4. Does the QA layer ever auto-correct? (Recommend: never. Always human-in-loop on overrides.)

## 11. Build & Scale Notes

**Reference architecture (vendor-named):**
- Primary extractor: whatever the firm runs today — Yardi's lease-abstraction module, ProDeal's abstraction product, an in-house Llama 3.1 70B fine-tune, or one of the standalone vendors. We don't replace it.
- Re-extractor: Claude Sonnet via Bedrock (or direct Anthropic API). Different prompt, different chunking strategy than primary. The "different model family" rule is non-negotiable — same family produces correlated errors.
- Second-opinion re-extractor: Azure OpenAI gpt-4o. The two re-extractors plus the primary form the ensemble.
- Rule extractor: Python with regex and spaCy. Templates for dates, base rent, escalation %, CAM cap percentages. Runs in <100ms per lease.
- Clause-class classifier: Llama 3.1 8B fine-tune on a labeled corpus of clause-class examples. Inferred on a single L4 GPU. Powers the missing-but-likely-present detector.
- PDF source-clause highlight: PyMuPDF render with character-offset primary, embedding-search fallback (sentence-transformers / E5).
- Orchestration: Airflow for nightly portfolio QA batch. Temporal for the per-lease reviewer workflow (queue, override, escalate to lease counsel).
- Retrieval/vector layer: pgvector on Postgres for clause-similarity ("show me 12 leases with comparable CAM language"). 768-dim embeddings.
- Reviewer UI: React app with the PDF viewer and side-by-side disagreement panels. Override events POST to Project 08's audit ledger.
- Lease-admin write-back: Yardi Voyager REST API; MRI XML connector (translation layer); Argus rent-roll export; VTS leasing-team-side if used.
- Observability: OpenTelemetry into Datadog. Langfuse for LLM traces — when override rate spikes on a field, you can pull the prompts.
- Security: SOC 2 Type II; encryption at rest; RBAC by asset and role. GDPR for any EU-resident lease.

**Throughput envelope and latency budget:**
- Diligence-window mode: 50K leases in 21 days (a 200-asset platform deal). Parallel workers, full ensemble pass.
- Steady-state portfolio QA: ~5K leases/day across an institutional owner's full book. Nightly batch.
- Per-lease ensemble pass: ~45s p50 (the LLM calls dominate). Acceptable for batch; not interactive.
- Reviewer triage UI: under 1s p99 for queue load and field-level disagreement view.
- Source-clause highlight render: under 3s p99 over a 50-page PDF.

**Failure modes:**
- Ensemble agrees and is still wrong (the correlated-error case). Mitigation: monthly 5% ground-truth audit catches systemic blind spots; surface "agreement-but-low-prior" cases for spot review.
- Source-clause offset misaligns on heavily-redlined PDFs. Mitigation: embedding-search fallback locates the clause by content.
- Vendor lease-admin API rate limit during diligence-window write-back. Mitigation: batched writes, exponential backoff, queueing on a dedicated diligence run.
- Clause-class classifier biased by lease vintage. Mitigation: explicit fairness audit by vintage and asset class; reviewer-feedback retraining loop quarterly.
- Cost spike on a redline-heavy portfolio (full ensemble triggers more often). Mitigation: per-portfolio cost cap; degrade to two-checker mode under pressure with alert.

**Migration path:**
- Phase 0: define the canonical field schema. Ground-truth 300 leases by hand. This is the most important single artifact in the program. Without it you have no baseline.
- Phase 1: stand up re-extractor and rule extractor. Run as shadow alongside the primary on one pilot region (3–5 assets).
- Phase 2: reviewer triage UX live. Override audit trail lit. One asset manager piloting.
- Phase 3: missing-but-likely classifier trained and deployed. Fairness audit before GA.
- Phase 4: full portfolio. Diligence-window integration with Acquisitions. Disposition re-QA before marketing.
- Phase 5: continuous QA loop. Monthly ground-truth sample. Reviewer-feedback retraining.

**Org dependencies:**
- Asset Management owns the product and the override decision. Without their buy-in this dies.
- Lease Administration runs the upstream abstraction. Position the QA layer as making their vendor's output trustworthy, not auditing their vendor.
- Acquisitions consumes the diligence-window scorecard. They become the loudest internal advocates after the first deal saved.
- Disposition consumes the re-QA pack before marketing.
- Legal consumes the override audit trail for dispute defense.
- Tech is builder. They don't own.
- Project 08 (audit trail) consumes every override as a lineage event. Project 10 (underwriting reliability) consumes the corrected abstractions as truth for rent-roll re-validation.

---

*This PRD interlocks with Projects 08 (Audit Trail) and 10 (CRE Underwriting Reliability Sentinel). Reviewer overrides are audit events; corrected abstractions feed underwriting truth.*
