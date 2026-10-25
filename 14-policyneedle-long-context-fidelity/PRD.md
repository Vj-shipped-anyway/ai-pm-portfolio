# PRD · PolicyNeedle — Long-Context Fidelity Probes for Policy-Manual Assistants

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for a pre-model-risk-committee read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI platform engineering review in the seat. It is not a record of a PRD landed at a named bank. The failure taxonomy, the probe design, the gate rules and the rollout plan are mine; the production validation is what the next role does. Every number tagged 🟢 comes from synthetic manuals and four stub readers (not models) in this folder; each names its script. 🟡 is modeled with the assumption named. 🔴 is designed, never tested.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | PolicyNeedle — long-context fidelity probes for assistants that answer from policy manuals |
| **Owner** | AI Platform Lead (line 1), with the Policy Owner as co-owner of the probe set and its expected answers |
| **Stage** | Portfolio prototype; pre-model-risk-committee read |
| **Primary users** | AI platform lead; policy owner; model risk reviewer; assistant product owner |
| **Secondary users** | Compliance and legal (consulted on gold answers); information security (manuals leave the building only to approved endpoints) |
| **Problem** | A bank's assistant answers from 100 to 300 page policy manuals. A clause in the middle, a superseded version, an exception in a footnote or a table value gets missed or mixed up, and the answer still reads confidently. Teams test on short documents, so the failure never shows before launch. (Design premise; no real incident is cited.) |
| **Solution** | A generator for synthetic or real-manual probes (facts planted at controlled depth in six forms), a question set with exact expected answers, a harness that takes any `reader(document_text, question) -> answer_text` function, a per-slice pass matrix, fault localization and a CI-style gate that blocks a release. |
| **North-star metric** | % of policy-grounded assistant releases that pass the PolicyNeedle gate before launch. Target: 100% (🔴 design). Current state of the art in the modeled bank: no long-document gate exists. |
| **Measured on the prototype** | 🟢 190 of 190 known fault cells flagged, 0 missed, 0 false flags on the control (`step_04_with_policyneedle.py`). 🟢 Short-document spot test flags 0 of 190 (`step_01`). 🟢 Fixed-needle test flags 2 of 190 (`step_02`). All on stub readers with known faults; not a result for any real model. |
| **Modeled metrics** | 🟡 8 policy-grounded assistants launched or re-launched per year at a large bank (my assumption, range 4-12). 🟡 Utility: (100% − 0%) × 8 = 8 launches a year with long-document faults caught before launch, if each carries at least one such fault. |
| **Cost** | 🟢 One sweep of one reader at prototype size is 270 reader calls and 64,894,140 characters of manual text, because each probe sends its whole manual (`step_04`). 🟡 About 16 million tokens at 4 characters per token (rule of thumb). A dollar figure needs the bank's reader and price; not estimated here. |
| **Risk #1** | Exact-match scoring flags a correct but wordy assistant as broken (🟢 the control wrapped in one sentence scores 0 of 270). Mitigation: a tolerant scorer with every tolerant pass logged, before the gate is allowed to block. |
| **Risk #2** | The probe set tests what its author imagined. A fault outside the six forms is invisible. Mitigation: policy owner and model risk reviewer add forms from real incidents and complaints; the form list is versioned. |
| **Risk #3** | The gate becomes a speed bump and gets bypassed. Mitigation: bypass needs a named approver, a reason and an audit entry, and the override list is reviewed monthly. |
| **Out of scope** | Runtime grounding of answers (HalluGuard, Project 01); the general probe registry and CI gate (EvalForge, Project 04); lease and contract extraction (LeaseGuard, Project 03); retrieval quality; answer tone and style. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R, assistant launches per year affected) × Impact (I, 1-3) × Confidence (C) / Effort (E, PM-weeks). R uses the 🟡 assumption of 8 launches a year. All scores are my estimates (🔴), not measurements. Rows are grouped by the release that carries them (v0.1, v0.2, v0.3, then queued) and ordered by RICE within each group, so the evidence bundle export (7.2) sits in v0.3 because it needs the items before it.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Reader adapter** (wraps the assistant under test in the one-function interface) | 8 | 3 | 0.9 | 3 | 7.2 | Sequenced for v0.1 |
| 2 | **Probe-set versioning** (content-addressed; the gate verdict names the version) | 8 | 2 | 0.9 | 2 | 7.2 | Sequenced for v0.1 |
| 3 | **CI gate hook** (hands the verdict to the EvalForge gate) | 8 | 3 | 0.85 | 3 | 6.8 | Sequenced for v0.1 |
| 4 | **Manual re-ingest trigger** (new manual version or new amendment starts a sweep) | 8 | 2 | 0.8 | 2 | 6.4 | Sequenced for v0.2 |
| 5 | **More probes per cell** (statistical power: 3 per cell today means one miss flags) | 8 | 2 | 0.8 | 2 | 6.4 | Sequenced for v0.2 |
| 6 | **Tolerant scorer** (paraphrase, verbosity, unit conversion; closes the known limit) | 8 | 3 | 0.8 | 5 | 3.8 | Sequenced for v0.2 |
| 7 | **Probes from the bank's real manuals** with policy-owner-signed gold answers | 8 | 3 | 0.9 | 6 | 3.6 | Sequenced for v0.2 |
| 8 | **Evidence bundle export** (probe-set version, reader version, matrix, flagged cells) to the model risk workflow | 8 | 2 | 0.9 | 2 | 7.2 | Sequenced for v0.3 |
| 9 | **Results console** (slice list, manual viewer with the planted clause highlighted) | 4 | 2 | 0.8 | 4 | 1.6 | Sequenced for v0.3 |
| 10 | **Finer depth grid** (more than five depths, to place a limit more tightly) | 8 | 1 | 0.8 | 2 | 3.2 | Queued |
| 11 | **Retriever-versus-reader split** (probe the retrieval step and the reading step separately) | 8 | 2 | 0.7 | 5 | 2.2 | Queued |
| 12 | **Multi-turn and follow-up probes** | 8 | 2 | 0.6 | 6 | 1.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from PolicyNeedle | What they fear |
| --- | --- | --- | --- |
| **AI Platform Lead** | Owner | A pre-release gate that catches long-document faults without slowing every release; a slice list an engineer can act on. | A gate that blocks on noise; a tool nobody owns after launch. |
| **Policy Owner** | Co-owner of probes and gold answers | Questions that state their policy correctly; a say in what counts as the right answer, including after an amendment. | Probes that misstate a policy and train the team on the wrong answer; being asked to sign 270 answers a quarter. |
| **Model Risk Reviewer** (line 2) | Validator | An evidence bundle that shows what was tested, at which depth, and what failed. Ongoing monitoring that names a slice, not an average. | A parallel attestation surface that competes with their own review; a gate verdict with no record of the probe-set version. |
| **Assistant Product Owner** | Direct user | A fail that says which form and depth broke, so the fix is targeted. | A gate that is a wall, not a window. Being blocked by a fault in a form the assistant never faces. |
| **Compliance and Legal** | Consulted | Confidence that a superseded rule and a fee exception are tested before customers see an answer. | Scope creep into general AI governance. |
| **Information Security** | Approver | Manuals sent only to approved endpoints; probe sets and results kept internal. | Policy text leaving the bank inside a test run; probe sets leaking into training data. |
| **Platform and DevEx** | Consulted | A gate that fits the existing release pipeline and says how long it takes. | A sweep that makes the release slower than anyone will accept. |

---

## User stories (top 4)

1. **As an AI platform lead**, I want the sweep to run on every release candidate and return a form-by-length-by-depth matrix, so I find out which slice broke before the release goes out.
2. **As a policy owner**, I want each probe's expected answer to carry my sign-off and the manual version it was written against, so a changed policy updates the gold answer and not the test.
3. **As a model risk reviewer**, I want an evidence bundle per release (probe-set version, reader version, matrix, flagged cells, overrides), so ongoing monitoring is documented continuously and not only at attestation time (SR 11-7 is the model-risk guidance the work is compared with).
4. **As an assistant product owner**, I want the kind of wrong answer named (old version, missed exception, wrong column, one clause of two, sibling product), so I can tell a retrieval fix from a prompt fix.

---

## KPIs

**North star:** % of policy-grounded assistant releases that pass the PolicyNeedle gate before launch. Target: 100% (🔴 design).

**Inputs (leading):**
- Probe coverage: cells (form × length × depth) with at least 3 signed probes. Prototype: 🟢 90 of 90 cells have 3 probes each, none signed because the probes are synthetic (`data/probes.csv`).
- Probe-set audit: questions that match more or fewer blocks than their form allows. Prototype: 🟢 0 of 280 (`step_04`).
- Harness validity on the stub control set, re-run on every release of the harness: true flags, misses, false flags. Prototype: 🟢 190, 0, 0.
- Policy-owner sign-off rate on gold answers (target 100% before a probe counts; 🔴 design).
- Tolerant-scorer agreement with a human reviewer on a sample (target set once the scorer exists; not built).

**Outputs (lagging):**
- Long-document faults found before launch versus after (target: after = 0; 🔴 design).
- Gate overrides per quarter, each with a named approver.
- Model-risk findings tied to document-grounded assistants (target zero; 🔴 design).

---

## Rollout

All durations are design targets (🔴), not commitments.

| Phase | Duration | Scope |
| --- | --- | --- |
| 0 — Foundation | 4w | Reader adapter for one assistant; the synthetic sweep and the stub control run in the release pipeline in shadow; no blocking |
| 1 — Real manual, signed probes | 6w | One real manual; probes written with the policy owner; gold answers signed and tied to the manual version |
| 2 — Tolerant scorer | 6w | Paraphrase, verbosity and unit conversion scored; every tolerant pass logged and sampled by a human |
| 3 — Blocking gate | 4w | Gate returns FAIL on a release; override needs a named approver and an audit entry; verdict handed to the EvalForge gate |
| 4 — Fleet and evidence | 8w | Remaining policy-grounded assistants onboarded; evidence bundle filed to the model risk workflow; re-ingest trigger on new manual versions |

---

## Open questions

1. **Gate authority.** Does the model risk reviewer have blocking authority, or only advisory? Recommendation: the reviewer blocks on any superseded-clause or exception-form fault (customer-visible wrong answers); the product owner can override a position-only fault with an audit entry and a retest date.
2. **Who signs the gold answer.** The policy owner, against a named manual version. What happens when policy changes between sweeps? Recommendation: a changed clause or a new amendment invalidates the probes that cite it until re-signed.
3. **How many probes per cell.** Three per cell means one miss flags the cell. Is that the right sensitivity for a real assistant, whose answers vary run to run? Recommendation: repeat each probe several times and gate on the rate, once a real reader is in the loop.
4. **Where the sweep runs.** Sending whole manuals to a hosted endpoint is a data-handling decision for information security. Recommendation: in-boundary endpoints only for real manuals; synthetic manuals for anything outside.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Planter:** builds probes by inserting synthetic needles into a copy of a real manual at controlled depth, and by pairing real clauses with policy-owner-signed questions.
- **Probe registry:** Postgres, content-addressed versions; the gate verdict names the probe-set version.
- **Runner and reader adapter:** the assistant under test sits behind the one-function interface; the runner records the manual version and the reader version with every result.
- **Scorer:** exact match first, a tolerant scorer second, every tolerant pass logged.
- **Gate:** a pre-release check; the verdict goes to the EvalForge CI gate.

**Throughput envelope.**
- 🟢 One sweep of one reader at prototype size: 270 calls, 64,894,140 characters of manual text (`step_04`).
- Each probe sends the whole manual, so cost scales with manual length × probe count. Design levers (🔴 not measured): ask the questions for one manual in one cached session; sweep a sample on every commit and the full grid on every release candidate.

**Failure modes and degradation strategy.**
- Reader endpoint unavailable: the sweep is incomplete, the gate returns REVIEW and never PASS.
- Manual changed since the probes were signed: probes citing changed clauses are held out and reported, not scored.
- Scorer disagreement with the human sample above a threshold: the tolerant scorer is switched off and the gate falls back to exact match with a note.

**Migration path from current state.**
- If the team tests on short excerpts: greenfield. Start in shadow with the synthetic sweep and the stub control.
- If the team already runs an eval platform: adopt it. PolicyNeedle adds a probe set and slice vocabulary; it does not replace the platform's logging or its gate.

**Org dependencies.**
- The policy owner signs the gold answers. Without that, the probes are unowned and the gate has no authority.
- The release pipeline team lands the gate hook.
- The model risk team agrees to take the evidence bundle as part of its monitoring record.

---

*This PRD interlocks with [Project 01 (HalluGuard)](../01-halluguard-bank-chatbot-safety/), [Project 03 (LeaseGuard)](../03-leaseguard-cre-lease-verification/) and [Project 04 (EvalForge)](../04-evalforge-llm-eval-platform/). Acknowledgement: [Greg Kamradt's needle-in-a-haystack test](https://github.com/gkamradt/LLMTest_NeedleInAHaystack) is the starting point for the single-needle idea this product extends.*
