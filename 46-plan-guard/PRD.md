# PRD: plan-guard

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a cloud change-control review. It is not a record of a PRD landed at a named bank. The rules, the planted plans and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and no plan in the data came from a Terraform run.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | plan-guard: a command-line check, with a staged GitHub Action, that reads the JSON form of a Terraform plan and prints ALLOW, REVIEW or BLOCK before apply |
| **Owner** | The engineer who owns the pipeline that applies infrastructure changes, with a cloud security reviewer as co-owner of the rules, port lists and severities |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | An engineer who owns the pipeline that applies infrastructure changes |
| **Secondary users** | The reviewer who approves those changes; the author of an infrastructure change; internal audit |
| **Problem** | A Terraform plan can create a public bucket, open a database port to the internet or leave storage unencrypted, and every one of those is valid Terraform. `terraform validate` and the plan itself pass. The first time anyone looks is a scanner after apply, or a person reading plan text under time pressure. In the planted set, 🟢 a pipeline with no check stops 0 of 86 plans and 42 of 86 apply a risky resource unchecked (`step_01_no_gate.py`). |
| **Solution** | Reads the JSON form of a plan (`terraform show -json`) and keeps resources the plan creates or updates. Applies ten rules chosen by the exact `type` field: public bucket ACL, public access block off, bucket policy open to everyone, world-open admin and database ports, unencrypted volume, database and file system, public database, plain HTTP listener. Says "unverified" and sends the plan to review when a value is only known after apply. Prints ALLOW, REVIEW or BLOCK, exits non-zero at a chosen level, and prints GitHub annotations on request. |
| **North-star metric** | Share of production Terraform plans that pass through the gate with a recorded decision before apply. Target 🔴 100%. Today in this model: nothing reads the plan, and 🟢 0 of 86 plans are stopped (`step_01_no_gate.py`). |
| **Measured metrics (synthetic)** | 🟢 33 of 42 risky plans blocked, each on the planted resource with the expected rule; 10 of 10 need-a-look plans sent to review; 0 of 34 harmless plans blocked and 3 of 34 sent to review; the decision matches the planted truth on 74 of 86 (`step_04_with_guard.py`). |
| **Modeled metrics** | 🟡 Utility (17/52 − 9/52) × 50 = 7.7 plans a year that a text search would pass and the guard stops or sends to review, assuming 50 plans a year that should be blocked or reviewed reach the gate. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real plan stream and report the planted numbers and the real numbers apart. |
| **Risk #2** | No plan here came from a Terraform run, so field names and the handling of unset attributes are unverified against real output. Mitigation: a contract test on real `terraform show -json` output before any pilot, covering an attribute that is absent, null and unknown. |
| **Risk #3** | Port lists and severities are my assumptions, and some plans pass. 🟢 9 of 42 risky plans pass: a split CIDR, a permissive condition and a queue policy with no rule (`step_04_with_guard.py`). Mitigation: rules and lists live in a reviewed config, and the golden numbers show every change. |
| **Out of scope** | Other providers; module configuration; `planned_values`; sensitive values; anything about resources already deployed and untouched by the plan; joins between resources; any model call; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is plans or listener plans, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Action-aware scope** (only create and update are read; deletes, no-ops and data sources are skipped) | 86 plans | 3 | 0.9 | 1 | 232.2 | Built in prototype |
| 2 | **Input validation** (empty, truncated, wrong-type or deeply nested input exits 2, never a traceback) | 86 plans | 2 | 0.9 | 1 | 154.8 | Built in prototype |
| 3 | **CI output** (text and GitHub annotations, `--fail-on` levels, escaped strings) | 86 plans | 2 | 0.9 | 2 | 77.4 | Built in prototype |
| 4 | **Publish the Action from its own repository** | 86 plans | 2 | 0.6 | 2 | 51.6 | Sequenced for v0.2 (staged in `action/`, not published) |
| 5 | **Reviewed policy config** (ports, ACLs, severities and a dated exception list) | 86 plans | 2 | 0.6 | 3 | 34.4 | Sequenced for v0.2 |
| 6 | **Nine blocking rules by exact type** (public ACL, public access block, open policy, admin port, database port, unencrypted volume, database and file system, public database) | 42 risky plans | 3 | 0.8 | 3 | 33.6 | Built in prototype |
| 7 | **Decision ledger** (plan hash, rules version, findings) | 86 plans | 2 | 0.7 | 4 | 30.1 | Sequenced for v0.2 |
| 8 | **Unknown-value handling** (a value known only after apply sends the plan to review) | 10 need-a-look plans | 3 | 0.8 | 1 | 24.0 | Built in prototype |
| 9 | **Other providers and module configuration** | 86 plans | 2 | 0.3 | 7 | 7.4 | Queued |
| 10 | **Close the three planted hard misses** (split CIDR, a condition that matches everything, a queue policy) | 9 risky plans | 3 | 0.5 | 3 | 4.5 | Sequenced for v0.3 |
| 11 | **Plain HTTP listener rule** (medium, REVIEW) | 6 listener plans | 1 | 0.7 | 1 | 4.2 | Built in prototype |
| 12 | **Cross-resource join** (a listener joined to its load balancer, so an internal one is not flagged) | 6 listener plans | 2 | 0.6 | 4 | 1.8 | Sequenced for v0.3 |

---

## Stakeholder map

| Stakeholder | Role | What they want from plan-guard | What they fear |
| --- | --- | --- | --- |
| **Pipeline owner** | Owner | A step that fails with a rule and a resource a person can act on, and a non-zero exit only when something is wrong. | A gate that blocks good changes on a look-alike and gets switched off. |
| **Infrastructure change author** | Consulted | A finding that names the resource and the attribute, early, before review. | A BLOCK on a plan that was fine, with no way to say why. |
| **Cloud security reviewer** | Approver of rules and exceptions | Rules tied to exact resource types, and a record of who approved each exception. | A rule list that drifts, or an exception that never expires. |
| **Cloud platform lead** | Consulted | One check across teams that reads the plan the way it will be applied. | Another tool in the pipeline that reads secrets out of a plan. |
| **Security / CISO** | Approver | Nothing leaving the boundary, no cloud credentials in the gate, strings from the plan kept out of logs. | A plan file, which can carry sensitive values, ending up in a build artifact. |
| **Internal audit** | Reader | A path from a decision to the plan hash, rules version and findings it used. | Rules changed silently between two runs. |

---

## User stories (top 4)

1. **As the pipeline owner**, I want the pipeline to fail when a plan creates a world-open port or an unencrypted store, so the first reader is not a scanner after apply.
2. **As a reviewer who approves a change**, I want each finding to name the rule, the resource and the attribute, so I can decide without opening the whole plan.
3. **As an infrastructure change author**, I want a deleted or unchanged risky resource to be ignored, so the gate does not block a cleanup.
4. **As internal audit**, I want each decision tied to the plan hash and the rules version it used, so I can reproduce it later.

---

## KPIs

**North star:** share of production Terraform plans that pass through the gate with a recorded decision before apply. Target 🔴 100%.

**Inputs (leading):**
- Plans that reach apply without passing the gate (prototype: 🟢 0 of 86 plans are stopped today, `step_01_no_gate.py`).
- Plans with a value known only after apply (prototype: 🟢 10 plans need a person to look, `step_01_no_gate.py`).
- Resource types with a rule: the prototype covers 12 types behind ten rules; target is every type the platform applies.
- Pull requests that change a rule, a port list or a severity with a different approver (target: every one).
- Real `terraform show -json` plans checked against the contract test (target: before any pilot).

**Outputs (lagging):** prototype baselines from the planted set.
- Risky plans blocked. 🟢 33 of 42 with the gate, against 0 of 86 plans stopped with no check (`step_04_with_guard.py`, `step_01_no_gate.py`).
- Harmless plans blocked. 🟢 0 of 34; 3 of 34 sent to review (`step_04_with_guard.py`).
- Need-a-look plans flagged. 🟢 10 of 10 (`step_04_with_guard.py`).
- Plans a person reads. 🟢 46 of 86, where the text search sent 58 (`step_04_with_guard.py`).
- Known miss. 🟢 9 of 42 risky plans pass (`step_04_with_guard.py`).
- Findings overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the command on one plan stream with `--fail-on never`. Print the decision, fail nothing, and compare with what the scanner after apply finds. |
| 1: Calibration | 4w | Check the plan shape against real output. Set the port lists, public ACLs and severities against the cloud standard. Write the first exception list. |
| 2: Blocking rules enforced | 4w | Fail the step on BLOCK from the nine high rules. Rule and exception changes go through a pull request with a different approver. |
| 3: Review enforced, Action published | 6w | Add the unknown-value and plain HTTP listener reviews to the enforced set. Publish the Action from its own repository. |
| 4: Ledger and join rule | 8w | Write a decision record per run. Add the listener join and the closed misses, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a value known only after apply send the plan to review?** In the prototype it does; that is my policy. Recommendation: keep REVIEW, not BLOCK. 🟢 A parser that lets unknowns pass flags only 3 of 10 need-a-look plans, so 7 would reach apply with no reader (`step_03_deficiencies_exposed.py`).
2. **Where should the port lists and severities come from?** They are my assumptions, taken from no standard. Recommendation: start from the bank's cloud security standard, record each difference from mine, and have the reviewer sign the list.
3. **How are known exceptions handled?** A bastion may legitimately open one port. Recommendation: a reviewed exception list keyed to the resource address, with an approver and an expiry, and no bypass flag on the command.
4. **Should the plan file be kept?** A plan can carry values you would not want in a log. Recommendation: do not retain it; keep the plan hash, the rules version and the findings, and keep the file out of uploaded build artifacts.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The gate is stateless: it reads one plan file and returns a decision. Production adds a reviewed policy config, a decision ledger and a published Action, all designed and none built.
- **Never silent.** A missing, empty or malformed plan exits 2 and fails the step, even with `--fail-on never`. A plan with no resource change, or none of a type that has a rule, says nothing was checked.
- **Strings from the plan are data.** Text output shows control characters as escapes and annotations are escaped, so a hostile resource address cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the blocked count shows in the diff.

**What is next.** Run it on one real plan the owner is allowed to share; add a cross-resource join for listeners and load balancers; publish the Action from its own repository.

**What would have to be true before a pilot.**
- One real `terraform show -json` plan has been checked against the shape the rules read, including an unset attribute.
- A named reviewer owns the port lists, the severities and the exception list.
- The team agrees which level fails the step.
- The plan file stays out of uploaded build artifacts and logs.
- The pipeline applies the plan that was checked, not a new one.

---

*This PRD names [28 Tool Schema Drift](../28-tool-schema-drift/), [40 Eval Gate](../40-eval-gate/) and [34 Audit Chain](../34-audit-chain/) as designed interlocks (🔴 designed, none built). No file from those projects is read here.*
