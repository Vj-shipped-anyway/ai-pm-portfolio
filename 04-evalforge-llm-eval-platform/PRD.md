# PRD · EvalForge — Eval-First Console for Regulated AI

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-MRM-committee read in a real engagement
**Date:** 2026-Q2

> **Framing:** This PRD is the product I'd bring to an AI platform engineering review in the seat. It is not a record of a PRD landed at a named bank. The deficiency taxonomy, the architecture, and the rollout plan are mine; the production validation is what the next role does.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | EvalForge — eval-first console for regulated AI (GenAI customer-facing features) |
| **Owner** | AI Platform Engineering Lead (line-1) + L2 Trust-and-Safety (co-owner on rubrics) |
| **Stage** | Portfolio prototype; pre-MRM-committee read |
| **Primary user** | AI Platform engineer shipping prompt edits or model updates |
| **Secondary users** | L2 Trust-and-Safety reviewers; L3 Compliance; the model owner (PM) |
| **Problem** | Tier-1 BFSI shops deploy 12-20 GenAI features per year. ~14% of deploys produce silent post-deploy regressions. Customer complaints surface the regression 8-12 weeks later. The legacy eval ("spreadsheet a senior engineer maintains") cannot represent the failure modes that actually hit customers. |
| **Solution** | Versioned probe sets + calibrated rubrics + cross-vendor LLM-as-judge + CI gate (GitHub Actions / Argo CD pre-deploy hook) that blocks deploys on regression. |
| **North-star metric** | % of customer-facing GenAI deploys with EvalForge PASS verdict before production traffic. Target: 100%. Current SOTA: ~0% (no gate exists). |
| **Modeled metrics** | 🟡 Silent post-deploy regression rate 14% → <2%; 🟡 time-to-detect 8-12 weeks → first eval run; 🟡 CI gate FP rate <5%; 🟢 inter-judge kappa 0.78+ on the calibrated rubric set. |
| **Cost** | 🔴 ~$220K for a 90-day pilot in a real engagement (compute + 1 PM + 0.5 FTE platform engineer + L2 partner time). Per-feature ongoing: ~$1.5K/month in judge compute. |
| **Risk #1** | Engineering treats the CI gate as a speed bump, finds the bypass switch. Mitigation: gate is owned by L2, bypass requires named approver + audit log entry. |
| **Risk #2** | Judge model itself drifts silently (the very failure mode the product targets). Mitigation: judge snapshot pinning + cross-vendor agreement floor + periodic re-anchor against held-out set. |
| **Risk #3** | Rubric calibration is hard; reviewers diverge over time. Mitigation: quarterly recalibration with held-out anchor set; override-audit log surfaces drift. |
| **Out of scope** | Production observability (covered by DriftSentinel); prompt-injection defense (PromptShield); agent reliability (AgentWatch); audit lineage (LineageLog). |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Effort in PM-weeks. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Versioned probe registry** (Postgres + Git-style commits) | 12 features | 3 | 0.9 | 4 | 8.1 | Sequenced for v0.1 |
| 2 | **Cross-vendor LLM-as-judge with kappa floor** (Claude + GPT-4o) | 12 features | 3 | 0.85 | 6 | 5.1 | Sequenced for v0.1 |
| 3 | **Calibrated rubric authoring UI** (L2 owns the criteria) | 8 L2 reviewers | 3 | 0.8 | 5 | 3.8 | Sequenced for v0.2 |
| 4 | **CI gate as GitHub Action / Argo CD pre-deploy hook** | 12 features | 3 | 0.9 | 3 | 10.8 | Sequenced for v0.1 |
| 5 | **Vendor snapshot pin + diff job** (interlocks with DriftSentinel) | 12 features | 3 | 0.85 | 3 | 10.2 | Sequenced for v0.2 |
| 6 | **Slice-aware pass-rate breakdown** (refusal-edge, fraud-workflow, pii-refusal) | 12 features | 2 | 0.85 | 2 | 10.2 | Sequenced for v0.2 |
| 7 | **Human override audit log** (every override has a reason + reviewer ID) | 8 L2 reviewers | 2 | 0.9 | 2 | 7.2 | Sequenced for v0.2 |
| 8 | **Inter-judge kappa monitor + auto-recalibration trigger** | 12 features | 2 | 0.75 | 3 | 6.0 | Sequenced for v0.3 |
| 9 | **Paraphrase variant generator** (catch the paraphrastic-false-pass class) | 12 features | 2 | 0.7 | 4 | 4.2 | Queued |
| 10 | **Behavioral regression suite** (probe-level diff between runs) | 12 features | 3 | 0.8 | 4 | 7.2 | Sequenced for v0.3 |
| 11 | **Long-context fidelity probes** (Greg Kamradt's needle-in-haystack) | 4 features | 2 | 0.7 | 5 | 2.2 | Queued |
| 12 | **Evidence bundle exporter** (PDF + JSON to GRC tool) | 4 GRC owners | 2 | 0.9 | 2 | 7.2 | Sequenced for v0.3 |
| 13 | **MCP server** (lets agents query eval status as a tool — Project 05 interlock) | 4 agents | 2 | 0.7 | 3 | 3.7 | Queued |
| 14 | **Multilingual probe coverage** (Spanish, then Mandarin for BFSI in CA / Asia regions) | 6 features | 2 | 0.65 | 8 | 1.9 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from EvalForge | What they fear |
| --- | --- | --- | --- |
| **AI Platform Engineering Lead** (L1) | Owner | A pre-deploy gate that catches regressions without slowing velocity to a crawl. | False positives that block deploys for benign changes; an unowned tool that becomes their problem. |
| **L2 Trust-and-Safety** | Co-owner of rubrics | A calibrated, auditable rubric set they can defend to L3 and the regulator. Authority to set the bar. | Engineering bypassing the gate; getting blamed when a regression slips through. |
| **L3 Compliance** | Sign-off authority | Evidence the bank's GenAI deploys are evaluated against a documented bar before customer impact. | A scope creep into general "AI governance" that overshadows their existing controls. |
| **Model Validators** (line 2 MRM) | Auditors | The evidence bundle as an artifact for the SR 11-7 ongoing-monitoring story for GenAI use cases. | EvalForge becoming a parallel attestation surface that competes with MRM. |
| **Foundation-model PM** (the L1 product owner of the GenAI feature) | Direct user | A signal they can act on (which probe regressed, on which slice) — not just a fail flag. | The CI gate becoming a 'wall' rather than a 'window' into what's wrong. |
| **CISO / Information Security** | Approver | Snapshot-pinned judges, in-VPC or HIPAA-eligible compute, no customer PII in probe payloads. | Vendor-judge data egress; insider-threat path via the override log. |
| **Engineering Velocity / DevEx Lead** | Consulted | A gate that runs in <10 minutes p95 against any PR. | Eval runs that take 45 minutes and become the slowest CI step. |
| **Customer Service Ops** | Consulted | A signal when a regression is going to make their queue explode, before it does. | Discovering the regression themselves via the complaint backlog. |

---

## User stories (top 4)

1. **As an AI Platform engineer**, I want the EvalForge CI gate to run on every PR that touches a prompt or a model snapshot, so I find out about a regression before customers do.
2. **As an L2 Trust-and-Safety reviewer**, I want every judge-vs-human override I make to be logged with my reason, so calibration drift is auditable and I can defend my interpretation.
3. **As an L3 Compliance officer**, I want a pre-deploy evidence bundle per GenAI feature, so the bank's GenAI deploy story under SR 11-7 and the NIST AI RMF 'Measure' function is documented continuously and not just at attestation time.
4. **As a Foundation-model PM**, I want slice-level pass-rate breakdowns, not just aggregate, so I can prioritize fixes against the slice that actually carries customer pain (fraud-workflow > rate-disclosure).

---

## KPIs

**North star:** % of customer-facing GenAI deploys that pass through EvalForge before production traffic. Target: 100%.

**Inputs (leading):**
- Probe set coverage: probes-per-deficiency-class (target ≥ 10 per class).
- Inter-judge kappa: rolling 7-day average (target ≥ 0.78).
- CI gate latency p95 (target ≤ 10 minutes per run).
- Human override count per run (target: trending down as rubric calibrates).

**Outputs (lagging):**
- Silent post-deploy regression rate (target < 2%).
- Time-to-detect-regression (target: first eval run).
- Customer complaint volume tied to GenAI features (proxy for regressions that slip through).
- Reg exam findings related to GenAI ongoing monitoring (target zero).

---

## Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 6w | Wire to one GenAI feature (the customer-service assistant); ship probe registry + judge orchestrator + CI gate skeleton |
| 1 — Calibrated rubrics | 6w | L2 co-design 12 calibration anchors; kappa monitor live |
| 2 — Cross-vendor judge | 6w | GPT-4o secondary judge; in-VPC Llama tertiary; cross-vendor kappa floor enforced |
| 3 — Fleet onboarding | 12w | Onboard remaining 11-19 customer-facing GenAI features; per-feature owner sign-off |
| 4 — Evidence bundle + GRC | 6w | Auto-route to Archer / ServiceNow GRC; LineageLog interlock |

---

## Open questions

1. **Gate authority.** Does L2 Trust-and-Safety have *blocking* authority on the CI gate, or only *advisory*? Recommendation: L2 blocks on high-severity slice regressions; L1 product owner can override for low-severity, with audit log entry and an SLA to re-test.
2. **Probe set ownership.** L1 product owner writes; L2 reviews and approves. What if they disagree? Recommendation: 24-hour escalation to AI Platform Lead, then to CRO.
3. **In-VPC vs hosted judge.** For features that touch PCI / HIPAA data, do we mandate in-VPC judge? Recommendation: yes, mandated; the tertiary in-VPC Llama judge becomes primary for those features.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Probe registry:** Postgres with row-level versioning; each probe is one row with a SHA pin.
- **Rubric calibration:** Snowflake for historical scoring; Postgres for current anchor set.
- **Judge orchestrator:** FastAPI on K8s; fan-out to Anthropic Claude (primary) + Azure OpenAI GPT-4o (secondary) + in-VPC Llama 3.1 8B (tertiary).
- **CI gate:** GitHub Actions or Argo CD pre-deploy hook; verdict posted as a PR check.
- **Storage:** Postgres for metadata; ClickHouse for high-cardinality per-probe scores; GCS / S3 Object Lock for immutable evidence bundles.

**Throughput envelope and latency budget.**
- 60 probes × 3 judges × 12-20 features × 5-10 runs per feature per week ≈ 40K-80K judge calls per week at fleet scale.
- CI gate latency budget: 10 minutes p95 per run. Parallelize probe execution across the 3 judges.

**Failure modes and degradation strategy.**
- Judge unavailability: fall back to next available judge; flag kappa-incomplete on the run; do not auto-pass.
- Probe registry corruption: every probe is content-addressed by SHA; tamper detection at read time.
- Vendor snapshot silent update on the judge: detected as a snapshot-ID change event; trigger judge re-anchor against held-out set.

**Migration path from current state.**
- If the team is running ad-hoc evals: greenfield. The 6-week foundation phase is non-negotiable.
- If the team is running LangSmith / Braintrust / Helicone: this product is the orchestration + CI gate + cross-vendor judge layer on top. Don't rip out the existing eval logging; adopt it and add the gate.

**Org dependencies.**
- L2 Trust-and-Safety co-owns the rubric authoring. Without their sign-off, the calibration is unowned and the gate has no authority.
- The bank's CI/CD platform team needs to land the GitHub Action / Argo CD hook. This is usually a 2-month conversation; start on day one.
- The MRM team (line 2) needs to accept the EvalForge evidence bundle as part of their attestation surface. Without that interlock, the L3 compliance story is incomplete.

---

*This PRD interlocks with [Project 02 (DriftSentinel)](../02-driftsentinel-model-drift-monitoring/), [Project 05 (AgentWatch)](../05-agentwatch-agent-observability/), [Project 06 (PromptShield)](../06-promptshield-prompt-injection-defense/), and [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/). Acknowledgement: [Hamel Husain's eval-first thesis](https://hamel.dev/blog/posts/evals/) is the intellectual anchor of this product.*
