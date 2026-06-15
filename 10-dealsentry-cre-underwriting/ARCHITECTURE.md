# Architecture · DealSentry CRE Underwriting Reliability Sentinel

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-IC-steering read in a real engagement
**Date:** 2026-Q2

> This document describes the reference architecture for DealSentry. The prototype in `src/app.py` proves the product mechanic. This is what the production build looks like when it ships to a national CRE operator.

---

## 1. Reference architecture (one-page view)

```
                          ┌─────────────────────────────────────┐
                          │  AI Underwriting Copilot            │
                          │  (Claude Sonnet / GPT-4o agent over │
                          │   CoStar + Reonomy + Cherre + OM)   │
                          └──────────────┬──────────────────────┘
                                         │  draft memo (PDF/JSON)
                                         ▼
                          ┌─────────────────────────────────────┐
                          │  1. INGESTION                       │
                          │  - PDF parse (pdfplumber/Textract)  │
                          │  - Claim extraction (Claude Sonnet, │
                          │    "cite-or-refuse" prompt)         │
                          │  - Normalize to structured schema   │
                          └──────────────┬──────────────────────┘
                                         │ {comps, t12_rows, stats,
                                         │  cap_rate, occupancy,
                                         │  exit_cap, IRR_assumptions}
                                         ▼
                ┌────────────────────────┴───────────────────────┐
                │       2. THREE INDEPENDENT VERIFIER PATHS      │
                │              (Temporal workflow, parallel)     │
                ├──────────────────────────────────────────────  │
                │                                                │
                │  Path 1: Comp existence              Path 2:   │
                │  - CoStar Real Estate Mgr API        Symbolic  │
                │  - Reonomy Properties API            math      │
                │  - Cherre Property API            ◀─re-run     │
                │  - RCA / MSCI                        - pandas  │
                │  - pgvector address embedding        - sympy   │
                │  Tolerance bands per                 - no LLM  │
                │  (asset_class, region)               in this   │
                │                                      path      │
                │  Path 3: Submarket stat cross-feed             │
                │  - CoStar + REIS + Reonomy quarterly cache     │
                │  - Stat-versioning detects staleness           │
                │  - Tolerance band per stat type                │
                └────────────────────────┬───────────────────────┘
                                         │ aggregated findings
                                         ▼
                          ┌─────────────────────────────────────┐
                          │  3. RECONCILIATION                  │
                          │  - Severity-weighted verdict        │
                          │    (PASS / REVIEW / FAIL)           │
                          │  - Bid-risk dollar model            │
                          │  - Override audit trail             │
                          └──────────────┬──────────────────────┘
                                         │
                          ┌──────────────┴──────────────────────┐
                          │  4. IC-READY WORKPAPER EXPORT       │
                          │  - PDF stamped with verifier badges │
                          │  - JSON evidence bundle             │
                          │  - Linked into Dealpath /           │
                          │    Juniper Square / Salesforce CRE  │
                          │  - Yardi / Argus post-close handoff │
                          └─────────────────────────────────────┘
```

See [`assets/dealsentry-flow.svg`](./assets/dealsentry-flow.svg) for the visual rendering.

---

## 2. Component-by-component

### 2.1 Ingestion layer

**Purpose:** turn a memo (PDF, Google Doc, or pasted text) into a structured claim graph the verifier paths can act on.

| Component | Choice | Why |
| --- | --- | --- |
| PDF parser | `pdfplumber` + AWS Textract fallback for scans | Most AI-drafted memos are emitted as PDF; pdfplumber preserves table structure; Textract handles the broker-OM scans the copilot ingests upstream |
| Claim extractor | Claude Sonnet 4 via Anthropic API, "cite-or-refuse" prompt | The extractor does not infer; it extracts what is literally there. Hard prompt rule prevents the verification path from being polluted by the same hallucination pattern it's trying to detect |
| Schema | Pydantic models in Python | Structured output ensures the three verifier paths receive deterministic inputs |
| Storage | Postgres (raw memo + extracted claims), S3 (PDF object) | Memo audit retention for the hold period |

### 2.2 Verifier path 1 — Comp existence

**Purpose:** dereference every cited comparable trade against a source-of-truth comp database.

| Component | Choice | Why |
| --- | --- | --- |
| Primary SOT | [CoStar Real Estate Manager API](https://www.costar.com/products) | Largest comp database; most operators have a CoStar license already |
| Secondary SOT | [Reonomy Properties API](https://www.reonomy.com/) | Stronger ownership data + private-trade coverage |
| Tertiary SOT | [Cherre Property API](https://cherre.com/) | Integration layer that joins many vendors; useful for cross-checks |
| Address normalization | `libpostal` (Python) + USAddress | CoStar / Reonomy / Cherre disagree on address strings; normalization is load-bearing |
| Match logic | Property name fuzzy match → address match → transaction-date window match → $/sf within tolerance band | Each layer narrows; mismatch at any layer flags |
| Tolerance bands | Per `(asset_class, region, market_cycle)` | An LA industrial trade today has tighter $/sf bands than a Sunbelt office in a recovering market |
| Cache | Postgres + Redis, 24-72h TTL per stat type | Source-of-truth API responses cached; force-refresh on Tier-1 deals |

### 2.3 Verifier path 2 — Symbolic math re-run

**Purpose:** re-compute the memo's NOI / cap rate / occupancy / exit cap math deterministically. No LLM in this path.

| Component | Choice | Why |
| --- | --- | --- |
| T-12 NOI re-summation | pandas | Reads the 12 monthly rows from the extracted claim graph, sums them, compares to the memo's stated sum |
| Effective-rent computation | pandas + lease abstraction join (from Project 03 LeaseGuard) | Effective rent on stepped leases requires the correct escalation period; LeaseGuard's corrected abstractions feed this path |
| Cap-rate validation | sympy for symbolic identity check | Stated cap = NOI / value; recompute and diff against tolerance |
| Occupancy reconciliation | pandas | Recompute from rent-roll lines; compare to memo's stated occupancy |
| Exit-cap spread validator | pure Python | Spread = exit cap - going-in cap; tolerance enforced from industry-standard +25-50 bps for office / industrial |
| IRR / cash-on-cash re-run | `numpy_financial` | Replay full 5-10 year cashflow; flag divergence beyond tolerance |

### 2.4 Verifier path 3 — Submarket stat cross-feed

**Purpose:** every cited submarket stat (vacancy, asking rent, cap rate) is cross-checked against ≥2 independent feeds at the latest available quarter.

| Component | Choice | Why |
| --- | --- | --- |
| Stat feed 1 | CoStar submarket stats API | Most-cited |
| Stat feed 2 | REIS / Moody's CRE | Independent methodology |
| Stat feed 3 | Reonomy submarket aggregates | Tertiary cross-check |
| Stat versioning | Quarterly snapshot table with `(submarket, asset_class, quarter, feed, as_of_date)` | Staleness detection requires versioning — without it, the verifier can't tell a Q3 stat from a Q4 stat |
| Disagreement handling | Surface both, do not pick | The verifier never resolves a vendor disagreement silently; senior analyst reviews |
| Staleness threshold | 90 days from current quarter | Anything older than 90 days flagged as "verify currency" |

### 2.5 Reconciliation layer

**Purpose:** aggregate the findings from all three verifier paths and render a sectional verdict.

| Component | Choice | Why |
| --- | --- | --- |
| Severity weighting | per-deficiency-class weights tuned with VP Acquisitions + IC chair | High-severity (fabricated comp, T-12 drift, cap math) auto-FAIL; medium (occupancy, exit-cap, stale stat) → REVIEW |
| Bid-risk dollar model | per-deficiency dollar impact × severity | Modeled tightly to operator's deal-size distribution; recalibrated quarterly against IC outcomes |
| Override workflow | senior-analyst sign-off UI; write to audit ledger (Project 08 OversightOps) | Override-and-was-right rate is a recalibration input |
| Tolerance recalibration | Quarterly review of override outcomes; tighten / loosen bands per-field | Tolerance bands too tight → analyst friction; too loose → hallucinations slip; recalibration is a load-bearing operating loop |

### 2.6 IC-ready workpaper export

**Purpose:** assemble the verifier evidence into an IC-ready PDF + JSON evidence bundle.

| Component | Choice | Why |
| --- | --- | --- |
| PDF stamp | server-side reportlab generation, signed (AWS KMS) | Verifier evidence is cryptographically signed; IC chair can verify on-the-fly |
| Sectional pass/fail badges | per-deficiency-class badges in the PDF margin | At-a-glance comprehension for the IC chair |
| JSON evidence bundle | full claim graph + verifier findings + SOT pointers per accepted/rejected comp | Audit trail; consumed by Project 09 LineageLog at the decision-id grain |
| Integration | Dealpath / Juniper Square / Salesforce CRE Cloud webhook for verification status | Verified memos surface as "DealSentry verified" in the existing deal-pipeline UI |
| Post-close handoff | Yardi Voyager / MRI / Argus Enterprise write-back | Verified underwriting feeds the post-close asset onboarding |

---

## 3. Orchestration and runtime

| Layer | Choice | Why |
| --- | --- | --- |
| Workflow engine | Temporal | Per-memo workflow: parse → 3 verifier paths in parallel → aggregate → route. Durable, retry-safe, auditable |
| Batch refresh | Airflow | Nightly SOT cache refresh; quarterly tolerance recalibration jobs |
| Event spine | Kafka | Verifier findings published to internal topics for Project 08 OversightOps + Project 09 LineageLog |
| Cache | Postgres + Redis | SOT API response cache; 24-72h TTL tuned per stat-freshness requirement |
| Compute | EKS (most CRE shops are AWS) | Microservice per verifier path; horizontal scale during peak weeks |

**Throughput envelope:**
- Designed envelope: 1,200 IC memos / year. Peak 12 memos in the same week (Q1 / Q4 deal flow).
- Per-memo verifier runtime: under 90s p95.
- Comp verification: under 30s with warm cache (12 cited comps per memo on average).
- Symbolic math re-run: under 5s (pure pandas).
- Submarket stat cross-check: under 20s (3 feeds, parallel).
- Workpaper PDF render: under 10s.

---

## 4. Stakeholder map (production)

| Role | Owns | Consumes |
| --- | --- | --- |
| **Head of Acquisitions** | Tolerance authority; override-and-was-right rate; "no IC memo without clean pass" rule for Tier-1 deals | Per-analyst, per-broker, per-submarket hallucination dashboard |
| **IC Chair** | Verification-stamp-required policy; high-severity-finding escalation routing | DealSentry verdict on every memo before IC packet seals |
| **Senior Analyst** (line 1) | Override workflow; manual-clear of REVIEW findings | Verifier evidence bundle alongside primary memo |
| **Asset Management** (post-close) | Verified underwriting alongside the property file | Verified inputs feed the post-close performance benchmark |
| **Audit / Compliance** | SOC 2 + LP retention policy; override audit trail | Per-memo verification stamp + JSON evidence bundle |
| **Acquisitions Tech / IT** | EKS deployment; SOT API contracts; cache + rate-limit governance | Verifier-runtime SLO + uptime metrics |

DealSentry interlocks with:
- **Project 08 OversightOps** — every override and verification is a decision-lineage event
- **Project 09 LineageLog** — verifier evidence bundle is consumed at the `(decision_id, customer_id_hash, timestamp)` grain
- **Project 03 LeaseGuard** — corrected lease abstractions feed Path 2's rent-roll arithmetic. Without LeaseGuard, Path 2 is materially weaker on portfolios with non-standard leases.

---

## 5. Failure modes and mitigations

| Failure mode | Mitigation |
| --- | --- |
| SOT feed disagrees with itself (CoStar updated mid-day vs morning pull) | Cache TTL tuned per stat type; force-refresh on Tier-1 deals |
| Cache poisoning from stale SOT response | Vendor-side timestamp embedded in cache; invalidate on staleness |
| Analyst paraphrases comp to avoid citation match | Override audit trail; manager review of high-override analysts; quarterly tolerance recalibration vs IC outcomes |
| Broker OM packet contains numbers the copilot ingested without source | Verifier flags any unattributed stat in the AI memo; broker claims tracked separately |
| Tolerance bands miscalibrated | Per-field tunable bands; quarterly recalibration; track override-and-was-right rate as input |
| Symbolic re-val diverges due to AI normalization choices (mgmt fee %, vacancy assumption) | Surface assumption diffs explicitly ("AI applied 5% mgmt fee, source OM shows 4%"); don't hide |

---

## 6. Migration path

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 | 8w | SOT integration: CoStar / Reonomy / Cherre client libraries, address normalization, cache + rate-limit governance |
| 1 | 6w | Path 1 (comp verification) live; shadow on 20 memos; measure precision/recall of "fail" flags against IC outcomes |
| 2 | 8w | Path 2 (symbolic math) live; surface assumption diffs, don't hide |
| 3 | 6w | Path 3 (submarket stat cross-check) live; tolerance bands tuned with Head of Acquisitions + IC chair |
| 4 | 6w | IC integration: verification stamp on every memo, override workflow, sectional pass/fail in IC packet |
| 5 | 12w | Portfolio rollout: all acquisitions teams; per-analyst, per-broker, per-submarket dashboards live |
| 6 | ongoing | Continuous calibration loop: quarterly tolerance recalibration vs post-close NOI variance |

---

*This document is part of the [DealSentry README walkthrough](./README.md). For the full product spec, see [PRD.md](./PRD.md). For the runnable prototype, see [src/app.py](./src/app.py).*
