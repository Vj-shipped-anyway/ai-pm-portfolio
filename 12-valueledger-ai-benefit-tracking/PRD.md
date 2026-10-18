# PRD · ValueLedger — Benefit Realization Tracking for AI Copilots

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-finance-review read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI program review in the seat. It is not a record of a PRD landed at a named bank. The deficiency taxonomy, the estimators, the architecture, and the rollout plan are mine; every figure marked 🟢 comes from a script on synthetic data, and the production validation (a real holdout, a finance sign-off) is what the next role does.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ValueLedger — benefit realization tracking for AI copilots in a regulated bank |
| **Owner** | AI Program Lead (line-1), with the Finance Business Partner as co-owner of the hard column |
| **Stage** | Portfolio prototype; pre-finance-review |
| **Primary user** | The AI program lead who reports copilot benefit to leadership |
| **Secondary users** | Finance business partner; copilot product owners; the CRO; internal audit and model validators |
| **Problem** | A copilot business case multiplies usage events by an assumed minutes-saved figure. Leadership sees a large number, finance cannot find it in a budget line, and nobody nets out rework, novelty decay, or two tools claiming the same task. 🟢 On the synthetic data the claim is 2.52x the true net (+152%; `step_04_with_valueledger.py`), and the cash a budget line can absorb is 9% of the claimed value (`step_03_deficiencies_exposed.py`). |
| **Solution** | A holdout cohort with difference-in-differences (pre-trend check and placebo), net of rework, a weekly effect curve with decay, overlap deduplication, a hard-versus-soft ledger tied to the budget table, and seeded team-level bootstrap intervals. Interlocks with 11 TierGate (use-case IDs and approval), 07 InferenceLens (the cost side), and 04 EvalForge (a quality guardrail). |
| **North-star metric** | % of copilot benefit claims that reach leadership as a ledger statement: interval, cohort rule on file, hard-versus-soft split, known limit. Design target: 100%. Today in this repo's scenario: the claim alone. |
| **Measured on synthetic data** | 🟢 Error against the answer key: claim +152%, pre/post +111%, ValueLedger +5% (`step_04_with_valueledger.py`). 🟢 Hard cash is 22% of ledger value (`step_04_with_valueledger.py`). 🟢 Quality guardrail holds CC-104 at 57% rework (`step_04_with_valueledger.py`). |
| **Modeled** | 🟡 About 94,200 h of phantom benefit removed per 14-week window at 5,000 eligible staff. Assumption: the same adoption, overlap, rework, and seasonal pattern hold at a bank's mix. |
| **Cost** | Not estimated here. The prototype has no cost model for a real build. The costs that matter are organizational: a holdout cohort that waits for the tool, and an export from the work system. |
| **Risk #1** | The holdout is not a fair counterfactual, and nothing in the data can prove it is. Mitigation: the assignment rule is recorded before the first number is read; the pre-trend check and placebo launch run on every statement; a staggered or randomized rollout is the real fix. |
| **Risk #2** | The ledger is read as more precise than it is. 🟢 On the synthetic data the realized error (+5%) understates the bias the method carries by construction (+15%), because sampling noise offset part of it. Mitigation: every statement prints its interval and its known limit, and finance signs the hard column, not the hours. |
| **Risk #3** | Measuring work at person level becomes employee monitoring. Mitigation: team-level aggregation, hashed identifiers, no individual rows in the console, and a legal and works-council read before any real data is used. |
| **Out of scope** | Pre-deploy evaluation (04 EvalForge), cost attribution (07 InferenceLens), use-case approval (11 TierGate), and the finance ledger itself. ValueLedger reads from them; it does not replace them. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R, use cases or owners covered) × Impact (I) × Confidence (C) / Effort (E, PM-weeks). The scores are my judgment, 🔴 never tested, and are not measurements. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Holdout cohort registry** with the assignment rule on file | 8 | 3 | 0.9 | 3 | 7.2 | Stand-in in `teams.csv`; registry designed |
| 2 | **Team-level bootstrap intervals**, seeded | 8 | 2 | 0.9 | 2 | 7.2 | Prototyped in `step_04` |
| 3 | **Use-case ID join and approval gate** (11 TierGate) | 8 | 2 | 0.8 | 2 | 6.4 | Stand-in column; link designed |
| 4 | **Cost join** (07 InferenceLens) | 8 | 2 | 0.8 | 2 | 6.4 | Stand-in seat prices; link designed |
| 5 | **Difference-in-differences** with pre-trend gap slope and placebo launch | 8 | 3 | 0.8 | 4 | 4.8 | Prototyped in `step_04` |
| 6 | **Net of rework** from the work system's correction records | 8 | 2 | 0.8 | 3 | 4.3 | Prototyped in `step_04` |
| 7 | **Weekly effect curve** with decay fit | 8 | 2 | 0.7 | 3 | 3.7 | Prototyped in `step_04` |
| 8 | **Hard-versus-soft ledger** joined to budget lines | 8 | 3 | 0.7 | 5 | 3.4 | Prototyped in `step_04` |
| 9 | **Benefit statement with finance sign-off** | 4 | 3 | 0.8 | 4 | 2.4 | Designed |
| 10 | **Staggered or randomized rollout planner** | 8 | 3 | 0.5 | 6 | 2.0 | Queued |
| 11 | **Quality guardrail** (04 EvalForge pass rate) | 4 | 2 | 0.7 | 3 | 1.9 | Stand-in using rework share; link designed |
| 12 | **Overlap deduplication** with a shared task key across copilot logs | 4 | 2 | 0.7 | 4 | 1.4 | Prototyped on a given column; the key join is designed |
| 13 | **Holdout spillover check** | 4 | 1 | 0.5 | 3 | 0.7 | Queued |
| 14 | **Covariate-adjusted and synthetic-control estimators** | 4 | 1 | 0.4 | 8 | 0.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from ValueLedger | What they fear |
| --- | --- | --- | --- |
| **AI Program Lead** (L1) | Owner | One benefit number per copilot that survives a finance question. | A number that leadership repeats and finance later disproves. |
| **Finance Business Partner** | Co-owner of the hard column | A statement that says which budget line moves, by how much, and with what range. | Hours booked as savings that never reach a line; being asked to sign capacity as cash. |
| **Copilot Product Owners** | Direct users | Credit for what their tool really did, with the overlap split stated. | Losing a flattering number; a split between two tools that looks arbitrary. |
| **CRO** | Approver | Evidence that speed was not bought with errors, and a held line where it was. | A benefit statement that hides a quality problem behind a time saving. |
| **Cost-center managers** | Consulted | A clear rule for when freed time becomes a budget reduction. | Headcount or budget cuts taken on a number they cannot check. |
| **Model Validators** (line 2 MRM) | Auditors | The cohort rule, the checks, the interval, and the known limit on file with each statement. | A benefit model that informs investment decisions with no validation record. |
| **HR and Employee Relations** | Consulted | Aggregation at team level and no individual scoring. | Work data used to rank people. |
| **Data and Platform Engineering** | Consulted | A small number of batch exports with stable keys, including a shared task ID across copilot logs. | A new always-on service they must support. |

---

## User stories (top 4)

1. **As an AI program lead**, I want every copilot benefit statement to carry a comparison group, an interval, and a known limit, so that I can repeat the number to leadership without a footnote I did not write.
2. **As a finance business partner**, I want hours split into hard cash and soft capacity by budget line, so that I only sign the part a line can absorb.
3. **As a copilot product owner**, I want overlapping tools counted once with the split stated, so that two business cases do not claim the same hour.
4. **As the CRO**, I want a quality guardrail on every statement, so that a cost center where rework eats most of the saving is held and not booked.

---

## KPIs

**North star:** % of copilot benefit claims that reach leadership as a ledger statement. Target: 100% (design target).

**Inputs (leading):**
- Holdout coverage: share of copilot use cases with a recorded cohort and assignment rule (target 100%).
- Pre-trend check pass rate: share of statements where the holdout reads as parallel before launch.
- Registered use-case IDs: share of benefit lines carrying a TierGate use-case ID (target 100%).
- Rework logging coverage: share of copilot tasks with a correction record.

**Outputs (lagging):**
- Claim-to-ledger gap: 🟢 +152% for the claim against +5% for the ledger on the synthetic data (`step_04_with_valueledger.py`). The live target is a gap that does not grow.
- Hard cash found per claimed dollar: 🟢 9% on the synthetic data (`step_03_deficiencies_exposed.py`).
- Budget lines actually reduced against signed hard benefit: 🔴 not measurable until a real pilot runs.
- Statements revised after finance review: a count, trending down.

---

## Rollout

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Shadow | design target: 6w | One copilot use case. Record the cohort and the assignment rule. Run ValueLedger beside the existing business case; finance compares, nothing is replaced. |
| 1 — Hard column | design target: 6w | Join budget lines and cash levers. Finance signs the hard column on one use case. |
| 2 — Guardrail and cost | design target: 6w | Read the eval pass rate (04 EvalForge) and the cost record (07 InferenceLens). Held lines appear on the statement. |
| 3 — Fleet | design target: 12w | Onboard the remaining copilot use cases with their TierGate IDs. Staggered rollout planned per team for new launches. |
| 4 — Quarterly cycle | design target: 6w | Scheduled statements, version history, and a sign-off record per quarter. |

These durations are design targets, not estimates from a pilot.

---

## Open questions

1. **Who waits.** A holdout means some teams do not get the tool yet. Does the business accept a staggered rollout, and who decides the order? Recommendation: stagger by team, record the order, and tell teams the order in advance.
2. **Hold authority.** Does the CRO's guardrail block a line from booking hard cash, or only flag it? Recommendation: block hard cash, allow the hours to stay visible as soft, and require a named reviewer to release it.
3. **Cash conversion.** Who decides that freed time becomes a budget reduction: finance or the line manager? Recommendation: the line manager proposes against a named cash lever, finance signs, and the signed amount is capped at the addressable spend.
4. **Overlap split.** Shared tasks are split 50/50 in the prototype. Recommendation: keep the split as an explicit, versioned policy and show the alternative split beside it.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines (design, not deployed):

- **Panel:** a person-by-week table in a columnar store; the prototype's panel is 160 treated plus 160 holdout people × 26 weeks = 8,320 rows.
- **Cohorts and estimates:** Postgres, with an append-only cohort registry and one row per estimate with its interval.
- **Estimators:** batch jobs per cohort and per quarter. Nothing is in a request path.
- **Ledger:** hard-versus-soft lines joined to budget lines from the finance ledger, with a sign-off record.

**Throughput envelope.**
- A bank with 5,000 people in scope produces 260,000 person-weeks a year (5,000 × 52). That is a single-table workload; the bootstrap resamples teams, not rows, so it works on team-by-week aggregates.
- The prototype resamples whole teams 1,000 times with a fixed seed (`step_04_with_valueledger.py`). Resampling teams keeps the cost independent of how many people sit in each team.

**Failure modes and degradation strategy.**
- Missing work-system export: the statement is marked incomplete and not published; the last signed statement stays current.
- Pre-trend check fails: the statement prints a range and a "not credible as a point estimate" flag instead of a single number.
- A copilot use case with no registered ID: its benefit is not booked.

**Migration path from current state.**
- If the program only has usage logs: start with Phase 0. A usage log alone can only produce the claim; the work log and the cohort record are the new inputs.
- If product owners already report savings in a spreadsheet: keep it as a column, and put the ledger beside it. Do not rip it out.

**Org dependencies.**
- Finance must agree that only the hard column is signed as savings. Without that, the ledger is a better-looking claim.
- The business must accept a holdout or a staggered rollout. Without a comparison group the method reduces to Step 2.
- HR and legal must read the data use before any person-level work data leaves the work system.

---

*This PRD interlocks with [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/) for the quality guardrail, [Project 07 (InferenceLens)](../07-inferencelens-inference-finops/) for the cost side, and [Project 11 (TierGate)](../11-tiergate-ai-usecase-intake/) for use-case IDs and approval.*
