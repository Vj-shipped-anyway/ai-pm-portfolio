# PRD: Feature Contract gate

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a model-risk and data-ownership review. It is not a record of a PRD landed at a named bank. The contracts, the planted deliveries and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Feature Contract: a command-line gate, with a staged GitHub Action, that checks one delivery of a feature table against a contract the model owner wrote and prints PASS, WARN or FAIL |
| **Owner** | The engineer who owns the feature table behind a model, with the model owner as co-owner of the contract |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | The engineer who owns a feature table behind a model |
| **Secondary users** | The owner of the model, who wants the inputs stated in one file; the team that owns the upstream feed; the second-line reviewer; internal audit |
| **Problem** | A model reads fields that another team owns. When one of them changes (a column renamed, a ratio sent as a percent, a null rate that jumps) the pipeline still runs and the model still scores. The first sign is a score that moved. In the planted set, 🟢 a pipeline with no input check stops 0 of 90 batches while 47 of 90 carry a changed field (`step_01_no_check.py`). |
| **Solution** | Reads a contract (per field a type, a range or allowed values, and a null allowance; per file a tolerance for isolated bad rows and a policy for columns it does not list) and checks one delivery of data, CSV or JSON lines with their JSON types, against it. Prints PASS, WARN or FAIL with the share of rows behind each finding, exits non-zero at a chosen level, and writes GitHub annotations on request. |
| **North-star metric** | Share of scoring runs of in-scope models that pass through the gate with a recorded decision against a current contract. Target 🔴 100%. Today in this model: nothing checks the data. |
| **Measured metrics (synthetic)** | 🟢 37 of 47 bad batches stopped; 0 of 43 harmless batches blocked and 5 of 43 warned; the decision is right on 80 of 90; 10 of 47 bad batches still pass (`step_04_with_contract.py`). |
| **Modeled metrics** | 🟡 Utility (37/47 − 16/47) × 20 = 8.9 bad batches a year stopped that a header and type check would pass, assuming 20 bad batches reach the gate each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the contracts share an author, so the numbers are a ceiling. Mitigation: run it on one real feature table the owner can share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | A range wide enough to hold the wrong scale cannot see it. 🟢 2 of the 4 unit_cents batches pass on `txn_total_30d_usd`, whose declared maximum is 10,000,000 (`data/README.md`, `step_04_with_contract.py`). Mitigation: review each range with the feed owner against the field's real scale, and keep the tightest range clean deliveries allow. |
| **Risk #3** | The 2.0% tolerance and the 5.0% null allowance are my assumptions and decide which isolated problems count as harmless. A contract written by hand also drifts from the feed it describes. Mitigation: set both against the clean deliveries of the real feed, and review the contract whenever the feed's owner announces a change. |
| **Out of scope** | Distribution drift and any shift inside the declared range; cross-field rules; dates and patterns; row-count and freshness checks; drafting a contract from data; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is deliveries or batches, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Structure check** (a listed column missing, a value that does not parse as the declared type, an unlisted column by policy) | 90 batches | 3 | 0.9 | 1 | 243.0 | Built in prototype |
| 2 | **Input validation** (empty, truncated, wrong-type input or an unknown contract key exits 2, never a traceback) | 90 batches | 2 | 0.9 | 1 | 162.0 | Built in prototype |
| 3 | **Value rules** (null rate, minimum and maximum, allowed list, with a bad-row tolerance) | 90 batches | 3 | 0.8 | 2 | 108.0 | Built in prototype |
| 4 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 90 batches | 2 | 0.9 | 2 | 81.0 | Built in prototype |
| 5 | **Publish the Action from its own repository** | 90 batches | 2 | 0.6 | 2 | 54.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 6 | **Contract change workflow** (pull request, a different approver, the feed owner consulted) | 90 batches | 3 | 0.6 | 3 | 54.0 | Sequenced for v0.2 |
| 7 | **Tolerance calibration from clean deliveries** (set `max_bad_rate` and null allowances from the feed's own history) | 90 batches | 2 | 0.6 | 2 | 54.0 | Sequenced for v0.2 |
| 8 | **Decision ledger** (contract version, file hash, findings) | 90 batches | 2 | 0.7 | 4 | 31.5 | Sequenced for v0.2 |
| 9 | **Draft a contract from a reference batch** | 90 batches | 2 | 0.5 | 3 | 30.0 | Sequenced for v0.3 |
| 10 | **Row-count and freshness checks** (a clean delivery of one row passes today) | 90 batches | 2 | 0.5 | 3 | 30.0 | Sequenced for v0.3 |
| 11 | **Cross-field, date and pattern rules** | 90 batches | 1 | 0.4 | 4 | 9.0 | Queued |
| 12 | **Hand-off to a distribution monitor** for the changes that stay inside the range | 10 batches | 3 | 0.4 | 4 | 3.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Feature Contract | What they fear |
| --- | --- | --- | --- |
| **Feature table owner** | Owner | A step that fails with a reason a person can act on: the field, the share of rows and the first value seen. | A gate that blocks good deliveries on a typo and gets switched off. |
| **Model owner** | Co-owner of the contract | The model's inputs stated in one file, reviewed, with a version. | A contract that is out of date and gives false comfort. |
| **Upstream feed team** | Consulted | To hear of a contract before it fails their delivery, and to see which field and which rule. | A new gate that turns every schema change into a ticket against them. |
| **Second-line reviewer** | Approver of contract and tolerance changes | A record of which contract version checked which delivery, and who loosened a range. | A range widened to make a FAIL go away. |
| **Business operations lead** | Informed | Fewer scores that quietly moved, and a short list of deliveries held. | Deliveries held for noise, so the day's work is late. |
| **Security / CISO** | Approver | No customer data copied out of the boundary, nothing leaving the job, strings from input kept out of logs. | Another tool in the pipeline holding credentials or copying rows. |
| **Internal audit** | Reader | A path from a decision to the exact delivery and the contract version it used. | Thresholds changed silently between two runs. |

---

## User stories (top 4)

1. **As the owner of a feature table**, I want the pipeline to stop when a ratio arrives as a percent, so the model does not score a batch in which every value is out of range.
2. **As the owner of a model**, I want the inputs stated in one contract with a type, a range, an allowed list and a null allowance, so a reviewer can read what the model is allowed to see.
3. **As the owner of a feature table**, I want one or two stray rows to pass and a null surge to fail, so the gate is not switched off the first week.
4. **As internal audit**, I want each decision tied to the contract version and the delivery it checked, so I can reproduce it later.

---

## KPIs

**North star:** share of scoring runs of in-scope models that pass through the gate with a recorded decision against a current contract. Target 🔴 100%.

**Inputs (leading):**
- Feature tables with a contract that names every field the model reads (the prototype has 🟢 3 contracts of 7 fields each, from `data/README.md`).
- Ranges reviewed with the feed owner against the field's real scale (target: every range).
- Tolerance and null allowances set from clean deliveries (prototype assumption: 🟢 2.0% bad rows and 5.0% nulls on four fields, from `data/README.md`).
- Contracts with a named approver and a version (target: every contract).

**Outputs (lagging):** prototype baselines from the planted set.
- Bad batches stopped. 🟢 37 of 47 with the contract, against 0 of 90 batches stopped with no check (`step_04_with_contract.py`, `step_01_no_check.py`).
- Harmless batches blocked. 🟢 0 of 43; 5 of 43 warned (`step_04_with_contract.py`).
- Batches a person has to read. 🟢 42 of 90, against 30 blocked by the header and type check (`step_04_with_contract.py`).
- Decision is right (bad stopped, harmless not blocked). 🟢 80 of 90 (`step_04_with_contract.py`).
- Known miss. 🟢 10 of 47 bad batches pass: null_zero_fill 3, unit_cents 2, unit_in_range 5 (`step_04_with_contract.py`).
- FAILs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one feature table with `--fail-on never`. Print the decision, hold nothing, and compare with what the model owner saw. |
| 1: Calibration | 4w | Read the clean deliveries. Set the tolerance, the null allowances and each range against the feed's own history, with the feed owner. |
| 2: Structure enforced | 4w | Fail the step on a missing column or a type mismatch. Contract changes go through a pull request with a different approver. |
| 3: Values enforced | 6w | Fail the step on a FAIL from every rule. WARN stays advisory. Publish the Action from its own repository. |
| 4: Ledger and monitor hand-off | 8w | Write a decision record per delivery. Test the designed hand-off to a distribution monitor named in the ARCHITECTURE doc. |

---

## Open questions

1. **How many bad rows should a delivery be allowed before a field fails?** In the prototype it is 2.0%, which is my assumption. Recommendation: start there, then set it against the stray-row rate on the real feed's clean deliveries; a stricter team will label the five harmless batches with isolated bad rows differently.
2. **Should an unlisted column warn or fail?** The prototype warns. Recommendation: keep WARN, and move a feed to fail only where the model reads columns by position or name and an extra column could shift them.
3. **Who writes a range, and who may loosen it?** Recommendation: the model owner writes it with the feed owner, and a person other than the author approves any change that widens it, with the reason recorded in the contract history.
4. **What covers the changes that stay inside the range?** A zero-filled null or a unit change that keeps its range passes today. Recommendation: pair the contract with a distribution monitor and do not tighten ranges blindly to chase them.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The check is stateless: it reads a contract and a delivery and returns a decision. Production adds a reviewed contract repo and a decision ledger with counts, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped input, or an unknown contract key, exits 2 and fails the step, even with `--fail-on never`. A listed column that is absent is a finding.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile column name or cell cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the stopped count shows in the diff.

**What is next.** Run it against one real feature table whose owner can share an export; add a command that drafts a contract from a reference batch; pair it with a distribution monitor for the changes a range cannot see; publish the Action from its own repository.

**What would have to be true before a pilot.**
- A named owner writes the contract and a different person approves changes to a range.
- The feed owner has read each range against the field's real scale.
- One real export can be shared, so the tolerance and null allowances are set against real noise and not mine.
- The team agrees which level holds the scoring job.
- A way to see the in-range changes exists, or the team accepts that they pass.

---

*This PRD names [28 Tool Schema Drift](../28-tool-schema-drift/), [15 SchemaWatch](../15-schemawatch-tool-schema-drift/), [02 DriftSentinel](../02-driftsentinel-model-drift-monitoring/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The validator style and exit-code convention follow 28; no code or file is imported from it.*
