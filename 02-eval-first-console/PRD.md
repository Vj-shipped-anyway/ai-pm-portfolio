# PRD · Eval-First Console for Regulated AI

**Author:** Vijay Saharan, Sr PM
**Stage:** Draft v1.1 — pre-AI Council read
**Date:** 2026-Q2

---

## 1. Problem

Production GenAI in BFSI is shipped past evals. A 10-to-30 prompt regression set, hand-authored by engineering, runs once at launch and is never opened again. There's no domain rubric. No slice analysis. No version-pinned baseline. No coverage map of what isn't tested. Vendor models update underneath us. Prompt revisions land without regression. Quality regressions reach customers and surface only as complaints — the most expensive possible detector.

I've watched the engineering team in three different shops show me the same shape of artifact: a markdown file with prompts and expected substrings, last edited the night before launch. That's not an eval. That's the absence of one.

**Primary user:** GenAI Use-Case Owner (line 1, business).
**Secondary user:** SME author — credit officer, fraud analyst, compliance specialist.
**Tertiary user:** AI Platform Lead and Model Validator (line 2).

## 2. Why now

- Karpathy's "evals are the moat" framing is consensus among practitioners now. Hamel Husain's eval consultancy is one of the most-cited references in the field. Eugene Yan and Lilian Weng publish weekly on slice cuts and judge calibration.
- Every Tier-1 US bank now has 5 to 30 GenAI use cases in production. None I've seen have a unified eval surface across vendors.
- Vendor silent updates from Anthropic, Azure OpenAI, and AWS Bedrock are now a quarterly event. Current eval posture is structurally blind to them.
- OCC and Fed examiner guidance is moving toward evidence-of-ongoing-quality-monitoring. Launch-only eval will not survive the next exam cycle.

## 3. Goals (12-month horizon)

| Goal | Metric | Target |
|------|--------|--------|
| Eval coverage | % of deployed GenAI use cases on a domain rubric | 6% to 88% |
| Catch regressions before customers do | Silent regressions caught / quarter | 2 to 26 |
| Compress launch cycle | Pre-deploy eval cycle (median) | 4w to 2d |
| Prevent loss | Modeled prevented loss (modeled, not measured) | $9M/yr |

## 4. Non-goals

- Not a prompt IDE. Interlocks with the existing prompt registry.
- Not a model-serving layer.
- Not a synthetic-data generator beyond eval-set seeding (interlocks with Project 05).
- Not a labeling tool for training. Eval-only.

## 5. User stories

- **As a Use-Case Owner**, I want a single dashboard showing rubric scores, slice cuts, and vendor-version diffs for my use case, so I can attest to quality without a 4-week working group.
- **As an SME author**, I want to write eval rubrics in my own language — credit policy, fraud typology, AML SAR triggers — without filing a Jira to engineering. My judgment lives in the system, not in a doc.
- **As an AI Platform Lead**, I want every deployed GenAI use case to inherit a baseline eval suite by default, so coverage isn't a heroic effort.
- **As a Validator**, I want eval runs version-pinned to vendor model snapshot, prompt hash, and rubric version, so "what was attested" is unambiguous.

## 6. Solution

A three-loop product.

### Loop 1 — Author
- SME-facing eval-set editor. Rubric, reference answers, slice tags (commercial vs retail, tier-1 vs tier-2 customer, geography, product line), pass-fail criteria.
- Versioned rubric — every edit is a Git-backed event with attestation (interlocks with Project 08).
- AI-assisted draft using Claude Sonnet, with the SME as editor.
- Coverage map by use case: which slices are tested, which are missing.

### Loop 2 — Run
- Scheduled runs (nightly, on-prompt-change, on-vendor-snapshot-change).
- Vendor model snapshots pinned. Prompt hash pinned. Rubric version pinned.
- LLM-as-judge with two vendor judges (Claude Sonnet + Azure OpenAI gpt-4o) and an on-prem fine-tuned Mistral 7B fallback for confidential workloads.
- Weekly recalibration against a 100-example SME-graded gold set. Trigger judge re-pinning when correlation drops below 0.85.
- Cost-bounded — per-use-case eval budgets enforced. Interlocks with Project 06.

### Loop 3 — Detect
- Regression flagger across (use case × slice × rubric × vendor version).
- Coverage-gap surfacing — which use cases lack a rubric, which slices lack tests, which rubrics haven't been refreshed in 90 days.
- Silent-update sentinel — when a pinned vendor snapshot changes underneath us, the eval suite re-runs automatically and diffs are surfaced.

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM-as-judge drift | High | High | Weekly SME-graded calibration; trigger judge re-pinning at correlation < 0.85; two-judge cross-check |
| SME authoring burnout | Med | High | Rubric templates per use-case archetype; AI-assisted draft with SME as editor |
| Eval cost runaway | Med | Med | Per-use-case eval budgets; tiered cadence (hot/warm/cold); guardrails enforced at orchestrator |
| False sense of coverage | Med | High | Coverage gaps surfaced as loud as failures; never report only the green |
| Rubric-regulatory mismatch | Low | High | Compliance co-signs every rubric for regulated workflows |
| Engineering team feels displaced | Med | Med | Co-own the platform; promote the existing prompt set into the rubric registry as the v0 baseline |

## 8. KPIs

**North star:** % of deployed GenAI use cases on a continuously-running domain rubric with eval staleness under 14 days.

**Inputs (leading):**
- Coverage: % of use cases with a rubric, % with slice tags, % with vendor-version pinning.
- Rubric freshness: median days since last SME edit.
- LLM-judge to SME correlation. Target at or above 0.85.

**Outputs (lagging):**
- Silent regressions caught per quarter.
- Pre-deploy eval cycle time.
- Modeled prevented loss.
- Reg-exam findings on AI quality monitoring. Target zero.

## 9. Rollout

| Phase | Duration | Scope |
|-------|----------|-------|
| 0 — Foundation | 6w | Wire to model registry + prompt registry; ingest one pilot use case (loan-officer Q&A) with a recent regression incident |
| 1 — SME authoring | 8w | Rubric editor GA; onboard credit, fraud, compliance SMEs |
| 2 — Vendor pinning | 6w | Vendor-snapshot pin + silent-update sentinel; integrate Project 01 |
| 3 — Fleet rollout | 14w | All customer-facing GenAI use cases |
| 4 — Coverage UX | 4w | Coverage-gap dashboard; eval-budget guardrails |

## 10. Open questions

1. Do we treat the rubric as a regulated artifact (formal MRM attestation) or a quality artifact (line-1 attestation)? Recommend regulated for customer-facing, quality for internal.
2. Where does the eval-first console end and the drift sentinel (Project 01) begin? Likely shared eval-set storage; the sentinel reads from this console's artifacts.
3. Vendor-snapshot cadence — re-eval on every minor vendor update, or batch weekly? Cost-vs-timeliness trade. My lean: every snapshot for customer-facing, batch weekly for internal.
4. Authoring authority — single SME or pairs (maker-checker)? Recommend pairs for customer-facing.

## 11. Build & Scale Notes

**Reference architecture.**
- LLM judges: Anthropic Claude Sonnet primary, Azure OpenAI gpt-4o secondary, fine-tuned Mistral 7B on Triton for on-prem confidential workloads. Two-vendor cross-check is a feature, not a redundancy.
- Eval runner: Promptfoo for declarative suites, Inspect (the Anthropic-published framework) for heavier multi-turn evals, custom Python where neither fits.
- Vector / retrieval (for grounded eval scenarios): Postgres + pgvector. Most BFSI use cases land at 1M to 50M embeddings, well inside what pgvector handles. Skip Pinecone here unless you have a hard sub-50ms retrieval budget; if you do, fall back to Weaviate or OpenSearch with hybrid lexical+semantic.
- Prompt and rubric registry: homegrown service on Postgres, Git-backed for version history, signed commits per SME edit.
- Orchestration: Temporal for the eval-run workflow (durable, retryable, hours-long). Airflow for nightly scheduled sweeps. Kafka for vendor-snapshot-change events.
- Observability: Langfuse as the trace store for eval runs. OpenTelemetry as substrate. ClickHouse for high-cardinality eval-result store. Datadog for SOC.
- Compute: T4 or L4 GPUs for the on-prem Mistral judge. Serverless (Lambda or Cloud Run) for orchestration glue. No A100s — heavy models are vendor-hosted.
- Data plane: Snowflake or Databricks for the eval result warehouse. Unity Catalog or Lake Formation for lineage between rubric, prompt, snapshot, result, and model.
- Security: SOC 2 Type II, GLBA for customer-data eval sets, PCI-DSS where in scope, FedRAMP Moderate for the on-prem judge path if there's federal counterparty work.

**Throughput envelope and latency budget.**
- 30 to 80 customer-facing GenAI use cases at the $50B-asset bank shape.
- Roughly 3 to 10 million eval inferences per month at full coverage. Most served by vendor APIs, judge inferences mixed.
- Latency: eval is offline. End-to-end SLO from snapshot-change-detected to regression-flag-fired is 6 hours for hot use cases, 24 hours for cold.

**Failure modes and degradation strategy.**
- Vendor API outage on the judge side: fall back to the secondary judge. If both vendors are out, the on-prem Mistral judge carries the signal until they recover.
- Vendor silent update: detected as a snapshot-ID change, re-run triggered automatically, regression diffed.
- Judge-to-SME correlation drift: weekly recalibration; if correlation drops under 0.85, the suite is paused and a notification fires before any line-2 attestation reads the result.
- Eval-budget exhaustion: per-use-case soft caps enforce graceful degradation — drop to a smaller eval set, flag the gap, alert the use-case owner.

**Migration path from current state.**
- If the bank is already running Promptfoo or LangSmith in pockets: this product is the rubric layer, the SME-authoring UI, the cross-vendor judge, and the routing into MRM. We adopt the existing runner where it fits.
- If they're already on Braintrust or Arize: similar story — bring our rubric registry and MRM-routing layer; let the vendor own execution until there's a real reason to swap.
- If they're on a markdown file: greenfield. The 6-week foundation phase is non-negotiable. Pick a use case with a known regression incident as the wedge.

**Org dependencies.**
- SME owners (credit, fraud, compliance) sign and recalibrate rubrics. This is the dependency that makes or breaks the product. Get it in writing before phase 1.
- MRM L2 co-signs every rubric for regulated workflows.
- Engineering team that wrote the original prompt set: invited as co-owners. Don't make this product feel like a vote of no-confidence.
- Existing prompt-registry owner: needs to expose a webhook for prompt-change events. Usually a 4-week conversation.
- Internal Audit (line 3): read access plus an interlock with Project 08.

---

*This PRD interlocks with Projects 01 (DriftSentinel), 05 (Synthetic Eval Data), 06 (Inference Economics), and 08 (Audit Trail).*
