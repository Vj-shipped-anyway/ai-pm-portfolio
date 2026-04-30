# PRD · Production Model DriftSentinel

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.2 — pre-MRM committee read
**Date:** 2026-Q2

---

## 1. Problem

Production ML and GenAI models silently decay. Across the BFSI fleet — credit, fraud, AML, customer-facing GenAI — ground truth is delayed 30 to 180 days, vendor models update without notice, and the SR 11-7 ongoing-monitoring requirement is met today with quarterly Word docs. The result is structural blindness. By the time decay surfaces in a business KPI, two quarters of value have leaked.

I've watched this happen. The credit model that drifted for 11 weeks before anyone noticed. The fraud model that lost two recall points across a tactic shift and got blamed on "campaign noise." The GenAI Q&A use case where the vendor pushed a minor update and the refusal rate doubled overnight. None of these were exotic. All of them were invisible to the existing tooling.

**Primary user:** Production ML/AI Operations Lead (line 1).
**Secondary user:** Model Validator (line 2).
**Tertiary user:** CRO / Head of MRM (line 2 oversight) and the Business Owner of the model (line 1 accountability).

## 2. Why now

- GenAI is in production at every Tier-1 US bank. None I've seen have a unified drift surface that covers it.
- OCC, Fed, and CFPB are signaling sharper expectations on ongoing monitoring of AI/ML. The next exam cycle is when this becomes a finding.
- Vendor model silent updates from Anthropic, Azure OpenAI, and AWS Bedrock are now a quarterly occurrence. Legacy MRM tooling does not see them.
- The open-source drift primitives (Evidently, NannyML, Whylogs) are mature enough that the build is now about diagnosis and routing, not detection math.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Reduce drift MTTD | Median days to detection across Tier-1 models | 78d to 9d |
| Increase coverage | % of Tier-1 models on continuous monitoring | 22% to 100% |
| Reduce MRM cycle | Evidence-bundle assembly time | 3 weeks to under 1 hour, with human edit before sign-off |
| Prevent loss | Modeled fraud/credit loss prevented | $14M/yr (modeled, not measured) |

## 4. Non-goals

- Not a model registry. Reads from the existing one (MLflow or SageMaker Model Registry).
- Not a feature store. Consumes from the existing one (Tecton or Databricks Feature Store).
- Not a retraining engine. Recommends. Does not execute.
- Not a fourth line of defense. The product is line-1 instrumentation with line-2 attestation rights.

## 5. User stories

- **As an Ops Lead**, I want every Tier-1 model on one screen with a drift health score and a root-cause hint, so I can triage before the business calls me.
- **As a Validator**, I want the evidence pack auto-assembled — PSI/KS, segment slices, lineage, attestation history — so I spend my time on judgment and not collation.
- **As a CRO**, I want a one-page exam-ready view of fleet health by tier, so the regulator's first three questions don't trigger a fire drill.
- **As a Business Owner**, I want a recommendation (retain/retrain/shadow/rollback) with a bounded risk envelope, so I make a call without a 14-week MRM round trip.

## 6. Solution

A three-loop product.

### Loop 1 — Detect
- Population Stability Index and Kolmogorov-Smirnov on every feature against a training reference window. Implemented on Evidently AI primitives.
- Prediction-distribution drift, categorical and continuous.
- Performance proxy when ground truth is delayed. NannyML for the estimator. Confidence-distribution drift, abstention rate, and vendor-version delta for GenAI use cases.
- For GenAI specifically: groundedness, refusal rate, citation accuracy, response-length distribution, and judge-score drift. Interlocks with Project 02.

### Loop 2 — Diagnose
- Feature-contribution bisect on a tripped alert.
- Segment slicer by geography, channel, product, and customer cohort.
- Upstream correlation: did a feature pipeline change land in the 48 hours before drift? Reads from Unity Catalog or Lake Formation lineage.
- Vendor-version diff for GenAI: which Anthropic or Azure OpenAI snapshot was in flight when behavior changed?

### Loop 3 — Decide
- Action recommendation engine with a bounded risk envelope:
  - Retain if drift stays within the attested envelope.
  - Shadow a candidate alongside if drift crosses the threshold but performance proxy holds.
  - Rollback to N-1 if performance regression is over X% on a monitored slice.
  - Retrain with an attached candidate spec.
- Auto-routes the evidence bundle to MRM. Validator can attest in roughly a day instead of three weeks. The bundle is human-edited, never auto-attested.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Alert fatigue (PSI false positives) | High | High | Segment-aware noise floor; 2-of-3 signal rule before paging; tunable thresholds per use-case archetype |
| Validator rejects auto-bundle | Med | High | Co-design rubric with MRM L2 from week one; bundle is editable, not auto-attested |
| GenAI ground-truth latency | High | Med | Proxy metric portfolio (groundedness, refusal, length, judge drift); calibrate offline |
| Vendor model silent updates | High | High | Vendor-version pinning; canary diff on snapshot change; treat snapshot ID as a model attribute |
| Performance regression on shadow rollout | Med | High | Always shadow first; never auto-promote |
| Internal political loss to existing MRM team | Med | High | Embed in their workbench; do not build a parallel UI |

## 8. KPIs

**North star:** % of Tier-1 production models with drift MTTD under 14 days.

**Inputs (leading):**
- Coverage: % of Tier-1, Tier-2, and GenAI models instrumented.
- Time-to-evidence-bundle (median, by tier).
- False-positive rate on alerts. Target at or under 8%.

**Outputs (lagging):**
- Modeled prevented loss ($).
- MRM cycle-time reduction (days).
- Reg-exam findings related to ongoing monitoring. Target zero.

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Wire to model registry, feature store, eval logs; instrument 5 pilot models (3 fraud, 1 credit, 1 GenAI Q&A) |
| 1 — Tier-1 ML | 12w | All Tier-1 classical ML on continuous monitoring |
| 2 — GenAI fleet | 12w | All customer-facing GenAI; proxy metric portfolio live |
| 3 — Tier-2/3 | 12w | Long tail; lighter-touch monitoring |
| 4 — Auto-bundle | 6w | MRM evidence-bundle automation; co-sign with L2 |

## 10. Open questions

1. Attestation cadence on GenAI. Do we treat each vendor minor version as a new model under MRM, or amend the parent attestation? My recommendation is new-model treatment for any customer-facing or credit-decisioning use case.
2. Where does the eval-first console (Project 02) end and the drift sentinel begin? Likely shared eval-set storage and shared rubric registry; separate UX.
3. Auto-rollback authority. Does the product execute, or always require a human? Recommend require human for Tier-1; auto on Tier-2/3 with audit trail.

## 11. Build & Scale Notes

**Reference architecture.**
- Drift compute: Spark on Snowflake (or Databricks if the bank's on Databricks) for the heavy aggregations. Python on a sidecar for diagnosis logic. Evidently AI for the open-source drift primitives. NannyML for performance estimation under delayed ground truth.
- LLM-as-judge (GenAI portion only): Anthropic Claude Sonnet primary, Azure OpenAI gpt-4o secondary for cross-judge reliability, fine-tuned Mistral 7B on Triton for fully-isolated workloads. Two judges, two vendors, by design — so one shifting under us is itself a detected event.
- Storage: Snowflake for model output history and reference windows. Feature snapshots from existing feature store. Drift events on ClickHouse (high-cardinality, cheap-to-store).
- Orchestration: Airflow for scheduled jobs. Temporal for the multi-day human-approval retraining workflow. Kafka or Kinesis for the model-output event spine — pick the one already in the bank.
- Observability: OpenTelemetry as the substrate. Datadog for SOC. Langfuse for GenAI traces.
- Compute: CPU-only for drift math. T4/L4 batch for LLM-as-judge. No A100s. The GPU spend belongs to the models being monitored, not the monitor.
- Data plane: Unity Catalog (Databricks) or Lake Formation (AWS) for lineage — non-negotiable for the diagnose loop.
- Security: SOC 2 Type II, GLBA, PCI-DSS where in scope. SR 11-7 alignment is the existence proof.

**Throughput envelope and latency budget.**
- Roughly 800 to 1,500 monitored models at a $50B-asset bank. 50,000 to 200,000 drift evaluations per day at full coverage.
- Latency: drift is not in the request path. End-to-end alert SLO is 15 minutes for hot use cases (fraud), 24 hours for cold. We are not optimizing tail latency; we are optimizing diagnosis-to-decision time.

**Failure modes and degradation strategy.**
- Feature pipeline outage: drift compute degrades to last-known-good reference. Alert is suppressed (with a flag) until upstream is healthy, to avoid spurious drift attribution.
- LLM-as-judge unavailability: fall back to the secondary judge. If both judges are down, the GenAI proxy metric portfolio carries the signal until they recover.
- Snowflake warehouse contention: drift jobs are queued at low priority. Worst case: 24-hour delay on Tier-3 models, which is within tolerance.
- Vendor silent update: detected as a snapshot-ID change event, treated as a drift event in its own right.

**Migration path from current state.**
- If the bank is already running Evidently AI in pockets: this product is the orchestration, diagnosis, and routing layer on top. Don't rip out what's working. Adopt the existing PSI/KS instrumentation, add the diagnose loop, route into the existing MRM workbench.
- If they're already on Arize or Fiddler: same wedge — bring our diagnosis and bundle-routing layer; let the vendor own detection until we have a real reason to swap.
- If they're on quarterly Word docs only: greenfield. The 5-pilot foundation phase is non-negotiable. Don't try to boil the fleet.

**Org dependencies.**
- MRM L2 co-signs the diagnosis rubric, the bundle template, and the recommendation thresholds. Without this, the product is dead on arrival.
- Model owners (line 1) sign the per-model attestation envelope.
- Internal Audit (line 3) gets read-only access and an audit-trail interlock with Project 08.
- The data platform team owns the feature-store and lineage interfaces. Get this commitment in writing before phase 0.
- The existing GRC tool owner (Archer, ServiceNow GRC, or MetricStream) needs to agree to ingest events. This is usually a 3-month conversation. Start it on day one.

---

*This PRD interlocks with Projects 02 (Eval-First Console), 06 (Inference Economics), and 08 (AI Audit Trail).*
