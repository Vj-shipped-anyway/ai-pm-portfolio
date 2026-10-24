# PRD: Credit Policy Needle

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model-risk review of a policy-grounded assistant. It is not a record of a PRD landed at a named bank. The manuals, the stub readers, the audit rules and the gate floors are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Credit Policy Needle: a small command-line tool that lists the clauses of a credit policy that read as exceptions, scores an assistant's answers by form of exception and depth, and prints PASS or FAIL, with four stub readers to try it against |
| **Owner** | The owner of a policy-grounded assistant for credit staff, with the policy owner as co-owner of the question set |
| **Stage** | Portfolio prototype on synthetic data; not deployed, no model call |
| **Primary user** | The owner of a policy-grounded assistant for credit staff, and the model risk or policy reviewer who signs off its test set |
| **Secondary users** | The policy owner who writes the questions; the engineer who runs the sweep in a pipeline; internal audit |
| **Problem** | A credit policy states a limit in one clause and changes it for some applicants in another. The change can sit in the same clause, in the next one, in another section that cites the clause number, in a register at the back, or in a clause that cancels it for one case. An assistant that answers from a long policy can state the limit confidently and leave out the exception. A short test set does not show it. In the planted set, 🟢 a plain-rule set of 30 questions catches 1 of 3 faulty readers and touches none of the 105 planted exception clauses (`step_01_plain_rule_questions.py`). |
| **Solution** | Lists the clauses in a manual that read as exceptions, and says which of them do not name the rule they change. Scores an assistant's answers against exact expected answers, flags the form-by-length-by-depth cells that fail, and prints PASS or FAIL with an exit code. Ships four stub readers (a control and three with a planted fault) and a synthetic set of three manuals, so the checks can be tried against faults that are known to be there. |
| **North-star metric** | Share of releases of an in-scope policy assistant that pass the exception sweep before release, with a recorded result. Target 🔴 100%. Today in this model: a plain-rule set catches 🟢 1 of 3 faulty readers (`step_01_plain_rule_questions.py`). |
| **Measured metrics (synthetic)** | 🟢 The gate fails 3 of 3 faulty readers and passes the control with 0 cells flagged; the cells flagged match the cells predicted from the planted offsets: 84 of 84, 90 of 90 and 60 of 60, with 0 other flags (`step_04_with_gate.py`). |
| **Modeled metrics** | 🟡 Utility (3/3 − 1/3) × 6 = 4 faulty releases caught that a plain-rule set would pass, assuming 6 such releases reach the test. 🟡 The 98.0% and 90% floors and the 60,000-character view of the truncating reader are my assumptions. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of running a sweep against a real assistant has not been sized. |
| **Risk #1** | Data, readers and rules share an author, so the numbers are a ceiling. Mitigation: run the sweep on one real manual with questions the policy owner wrote, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The retrieval stub is blunter than a real retriever, and exact match scores a wrapped answer as wrong. Mitigation: require the assistant to return the value in a fixed field, and compare the stub's misses with a real assistant's in shadow mode. |
| **Risk #3** | A score on answers alone passes a reader that never opens an exception whenever the exception does not apply: 🟢 90 of 90 questions pass (`step_03_deficiencies_exposed.py`). Mitigation: write every exception question as a pair, so the question where the exception applies fails it. |
| **Out of scope** | Any model call; scoring free-text answers; exceptions that tighten a limit or stack on one rule; tables and amendments; real policy text; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is questions or clauses, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (empty, wrong-type, truncated or mismatched files exit 2, never a traceback) | 210 questions | 2 | 0.9 | 1 | 378.0 | Built in prototype |
| 2 | **Paired exception questions across seven forms** (the exception applies, and it does not) | 210 questions | 3 | 0.9 | 2 | 283.5 | Built in prototype |
| 3 | **Gate with cell flags and floors** (overall, per slice, per depth band) | 210 questions | 3 | 0.8 | 2 | 252.0 | Built in prototype |
| 4 | **CI output** (text and annotations with every value escaped, `--fail-on`) | 210 questions | 1 | 0.9 | 1 | 189.0 | Built in prototype |
| 5 | **Stub readers with planted faults** (a control, truncating, base-only, retrieval) | 210 questions | 2 | 0.8 | 2 | 168.0 | Built in prototype |
| 6 | **Harness that asks the assistant under test** and writes the answers file | 210 questions | 3 | 0.6 | 3 | 126.0 | Sequenced for v0.2 |
| 7 | **Audit of exception clauses** (which read as exceptions, which do not name their rule) | 105 clauses | 2 | 0.7 | 2 | 73.5 | Built in prototype |
| 8 | **Sweep record per release** (inputs, floors, cells, result) | 210 questions | 2 | 0.7 | 4 | 73.5 | Sequenced for v0.2 |
| 9 | **Check that expected answers still match after an amendment** | 210 questions | 2 | 0.4 | 5 | 33.6 | Queued |
| 10 | **A second exception per rule, and an exception that tightens a limit** | 105 clauses | 3 | 0.5 | 5 | 31.5 | Sequenced for v0.3 |
| 11 | **Scoring of free-text answers** | 210 questions | 2 | 0.4 | 6 | 28.0 | Queued |
| 12 | **Audit patterns for other clause numbering** | 105 clauses | 1 | 0.6 | 3 | 21.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Credit Policy Needle | What they fear |
| --- | --- | --- | --- |
| **Assistant owner** | Owner | A release test that fails when the assistant loses an exception, and says where. | A gate that fails on noise and gets switched off. |
| **Policy owner** | Writes the questions | Questions written from real exceptions, with exact answers they can sign. | Tests that paraphrase the policy and drift from it. |
| **Model risk reviewer** | Approver of the test set | A test set that covers the places an exception can sit, and a record of what each release scored. | A pass rate that hides a fault behind questions where no exception applies. |
| **Credit staff** | Consumers of the assistant | The right limit for the applicant in front of them. | A confident wrong limit on a case that has an exception. |
| **Platform engineer** | Runs the sweep | A command that reads two files, exits with a clear code and runs in the pipeline they have. | A sweep that is slow or needs a key it should not hold. |
| **Security / CISO** | Approver | Nothing leaving the boundary, strings from files kept out of logs, no model key in the tool. | Policy text or customer data copied into a test artifact. |
| **Internal audit** | Reader | A path from a release to the questions, the answers and the floors it was judged by. | Floors changed silently between two releases. |

---

## User stories (top 4)

1. **As the assistant owner**, I want the release test to include exception questions at several depths, so a fault in how the assistant finds exceptions shows before credit staff see it.
2. **As the policy owner**, I want to write each exception question as a pair, one applicant who meets the condition and one who does not, so a reader that never opens the exception fails.
3. **As the model risk reviewer**, I want the failing cells named by form, length and depth, so I can tell a truncation fault from a retrieval fault.
4. **As internal audit**, I want each result tied to the questions, the answers and the floors it used, so I can reproduce it later.

---

## KPIs

**North star:** share of releases of an in-scope policy assistant that pass the exception sweep before release, with a recorded result. Target 🔴 100%.

**Inputs (leading):**
- Manuals with a question set signed off by the policy owner (the prototype has 🟢 3 manuals and 210 questions, from `data/README.md`).
- Exception questions written as pairs (target: every exception).
- Forms and depths covered (the prototype covers seven forms at five depths; not a measured rate on a real policy).
- Floors set against a clean run of the control (the prototype's 98.0% and 90% are assumptions).

**Outputs (lagging):** prototype baselines from the planted set.
- Faulty readers failed by the gate. 🟢 3 of 3, and the control passes with 0 cells flagged (`step_04_with_gate.py`).
- Flagged cells that match the planted offsets. 🟢 84 of 84, 90 of 90 and 60 of 60, with 0 other flags (`step_04_with_gate.py`).
- Faulty readers a plain-rule set catches. 🟢 1 of 3 (`step_01_plain_rule_questions.py`).
- Exception clauses the audit lists. 🟢 90 of 105 (`step_04_with_gate.py`).
- Known misses. 🟢 15 of 15 restated limits unlisted and 12 of 36 look-alikes listed by mistake (`step_04_with_gate.py`).
- Faults found in a real assistant: not measured; no real assistant was run.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the sweep against one real assistant and one real manual with `--fail-on never`. Print the cells, fail nothing, and compare with what staff report. |
| 1: Calibration | 4w | Have the policy owner write paired questions from real exceptions. Set the floors against the control's clean run. Require a fixed answer field. |
| 2: Advisory in release | 4w | Run the sweep on every release candidate and show the result to the release owner, without blocking. |
| 3: Enforced | 6w | Fail the release step on FAIL. A change to a floor needs a second approver. |
| 4: Record and coverage | 8w | Write a sweep record per release. Add a second exception per rule and an exception that tightens a limit, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Where should the floors sit?** The 98.0% overall floor and the 90% slice, depth and cell floors are mine. Recommendation: run advisory first, then set them against the control reader's clean run on the real manual.
2. **Who writes the questions?** Recommendation: the policy owner, from real exceptions, one pair per exception, with the exact answer stated.
3. **Is exact match too strict?** A correct answer wrapped in a sentence scores as wrong, and I have not measured how many answers that would affect. Recommendation: keep exact match, and have the assistant return the value in a fixed field.
4. **How do we cover exception forms the sweep lacks?** The set has seven forms, and each loosens a limit with one numeric condition. Recommendation: add a form to the set when the policy owner finds it in the real manual, starting with an exception that tightens a limit.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the release pipeline.** The tool is stateless: it reads a manual, a probe file and an answers file and returns a list, cells and PASS or FAIL. Production adds a harness that asks the assistant, a sweep record and telemetry, all designed and none built.
- **Never silent.** An empty, truncated, mismatched or mistyped file exits 2. An answers file that matches none of the probes is an error, not a pass.
- **Strings from input are data.** Output and annotations strip or escape control characters, so a hostile form name or clause text cannot forge a line or a workflow command.
- **Changes to a floor are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a pass count shows in the diff.

**What is next.** Run the sweep on one real manual the owner can share, with questions the policy owner wrote; add the harness; add an exception that tightens a limit.

**What would have to be true before a pilot.**
- The policy owner writes the questions from real exceptions, in pairs, with exact answers.
- The assistant returns the value in a fixed field.
- One real manual can be shared, so the floors are set against real noise and not mine.
- A named person owns the floors and the question set.
- The team agrees which result blocks a release.

---

*This PRD names [14 PolicyNeedle](../14-policyneedle-long-context-fidelity/), [04 EvalForge](../04-evalforge-llm-eval-platform/) and [40 Eval Gate](../40-eval-gate/) as designed interlocks (🔴 designed, none built). The prototype reuses the approach of 14 and imports no code or data from it.*
