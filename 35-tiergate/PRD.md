# PRD: TierGate Intake Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an AI governance review. It is not a record of a PRD landed at a named bank. The rubric points and cut-offs, the planted forms and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the skill is staged and has not been loaded into an agent runtime.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | TierGate Intake Check: a command-line check, with a staged Agent Skill, that recomputes the risk tier a sponsor declared on an AI use-case intake form and lists every form declared below its recomputed tier |
| **Owner** | The AI governance lead who triages intake forms, with the model risk reviewer as co-owner of the rubric |
| **Stage** | Portfolio prototype on synthetic data; the skill is staged and unpublished |
| **Primary user** | The AI governance lead who triages intake forms |
| **Secondary users** | The model risk reviewer who receives the ones sent to full review; the data steward and the vendor manager who own the two second sources; the sponsor who gets a question back |
| **Problem** | A sponsor fills in an intake form and writes the risk tier on it. That tier decides how deep the review goes. Nobody recomputes it, and the answers behind it come from the same person who benefits from a light review. In the synthetic set, 🟢 the declared tier equals the reference tier on 137 of 200 forms, and 30 of the 93 forms the reference sends to full review get the light review (`step_01_declared_tier.py`). |
| **Solution** | Applies a written rubric (six inputs, summed, four tiers) to each form. Cross-checks the data class against the data catalog, the vendor model against the vendor registry, and the customer-facing answer against the words in the title and description. Prints every form whose declared tier is below the recomputed tier, with the reason, and exits non-zero so a pipeline step can stop. Ships as a command line, GitHub annotations on request, and a staged Agent Skill that runs the command and reports what it printed. |
| **North-star metric** | Share of intake forms routed on a recomputed tier, with every cross-check that could run having run, and every UNDER-DECLARED form answered by a person. Target 🔴 100% of forms. Today in this model: the declared tier is the only evidence. |
| **Measured metrics (synthetic)** | 🟢 170 of 200 forms recomputed to the reference tier, against 137 for the declared tier; 87 of 93 full-review forms reach full review, against 63; forms below the reference fall from 57 to 11 (`step_04_with_tiergate.py`, `step_01_declared_tier.py`). |
| **Modeled metrics** | 🟡 Utility (87/93 − 71/93) × 150 = 25.8 full-review forms a year routed to full review that the rubric on the form as written would send to the light review, assuming 150 full-review forms reach the front door each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real intake export and report the planted numbers and the real numbers apart. |
| **Risk #2** | The recompute is only as good as the catalog and the registry. 🟢 9 of 200 forms have a wrong class and no second source that disagrees, and 11 of 200 stay below the reference (`step_03_deficiencies_exposed.py`, `step_04_with_tiergate.py`). Mitigation: a named owner and a refresh date for each source, and the notes the command prints when a cross-check could not run. |
| **Risk #3** | The conservative rules raise some internal tools. 🟢 Forms above the reference rise from 6 to 19, and 15 of those 19 carry a planted hard negative (`step_04_with_tiergate.py`). Mitigation: UNDER-DECLARED is a question to the sponsor and OVER-DECLARED is a notice; neither rejects a form. |
| **Out of scope** | Duplicate linking, the evidence gate and the review queue (project 11); any model call; reading descriptions for meaning beyond a keyword; a registry or catalog integration; publishing the skill. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is intake forms, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Rubric recompute** (six inputs, summed, four tiers; declared against recomputed) | 200 forms | 3 | 0.9 | 1 | 540.0 | Built in prototype |
| 2 | **Input validation** (empty, truncated, wrong-type, duplicate or out-of-range input exits 2, never a traceback) | 200 forms | 2 | 0.9 | 1 | 360.0 | Built in prototype |
| 3 | **Catalog cross-check on the data class** (the higher of the form and the catalog) | 200 forms | 3 | 0.8 | 2 | 240.0 | Built in prototype |
| 4 | **Registry cross-check on the vendor model** (the higher of the form and the registry) | 200 forms | 3 | 0.8 | 2 | 240.0 | Built in prototype |
| 5 | **Output** (text, GitHub annotations, a result CSV with formula-safe cells, notes when a check did not run) | 200 forms | 2 | 0.9 | 2 | 180.0 | Built in prototype |
| 6 | **Text rules for the customer-facing answer** (blank or unsure counts as yes; a cue word overrides no) | 200 forms | 2 | 0.5 | 2 | 100.0 | Built in prototype |
| 7 | **Reviewed rubric config** (points and cut-offs changed by pull request, a different approver) | 200 forms | 2 | 0.7 | 3 | 93.3 | Sequenced for v0.2 |
| 8 | **Scheduled catalog and registry feed** (with a refresh date on each row) | 200 forms | 3 | 0.6 | 4 | 90.0 | Sequenced for v0.2 |
| 9 | **Decision ledger** (form hash, source versions, rubric version, result) | 200 forms | 2 | 0.6 | 4 | 60.0 | Sequenced for v0.2 |
| 10 | **Staged Agent Skill** (runs the command and reports what it printed) | 200 forms | 1 | 0.5 | 2 | 50.0 | Built in prototype; staged, not published |
| 11 | **Second source for autonomy, regulatory scope and exposure** (the forms here never get these wrong) | 200 forms | 3 | 0.4 | 5 | 48.0 | Sequenced for v0.3 |
| 12 | **Sponsor reply workflow** (a question back, and the answer recorded) | 93 forms | 2 | 0.5 | 3 | 31.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from TierGate Intake Check | What they fear |
| --- | --- | --- | --- |
| **AI governance lead** | Owner | A short list of forms to question, each with the reason, and a clear note when a cross-check did not run. | A list so long that nobody reads it, or a clean result read as proof that a tier is right. |
| **Sponsor** | Submitter | A fast route for a use case that is tiered correctly, and a plain question when it is not. | Being told the tier is wrong by a rule they cannot read. |
| **Model risk reviewer** | Receives full-review forms | That the forms reaching full review are the ones that belong there. | Reviewing forms that did not need it because a keyword rule fired. |
| **Data steward** | Owner of the data catalog | A flag when the catalog and a form disagree, so a stale entry is found. | A stale catalog entry used as the reason a sponsor's form is overruled. |
| **Vendor manager** | Owner of the vendor registry | The registry used as the source for the vendor dependency. | A registry that is incomplete being treated as complete. |
| **Security / CISO** | Approver | Sponsor-written text treated as data; nothing leaving the boundary; no key in the path. | A description that instructs the skill or forges a line of output. |
| **Internal audit** | Reader | A path from a result to the form, the sources and the rubric version it used. | Rubric points changed silently between two runs. |

---

## User stories (top 4)

1. **As the AI governance lead**, I want every form declared below its recomputed tier listed with the reason, so I question the sponsor before the form is routed.
2. **As a model risk reviewer**, I want the share of full-review forms that reach me to rise without my queue filling with internal tools, so the check is worth reading.
3. **As a data steward**, I want a flag when a form's data class is below the catalog, so a stale entry on either side is found.
4. **As internal audit**, I want each result tied to the rubric version and the two sources it used, so I can reproduce it later.

---

## KPIs

**North star:** share of intake forms routed on a recomputed tier, with every cross-check that could run having run, and every UNDER-DECLARED form answered by a person. Target 🔴 100% of forms.

**Inputs (leading):**
- Intake forms with all six rubric fields filled (the prototype set has 🟢 200 forms, `step_01_declared_tier.py`).
- Datasets with a catalog entry (the prototype catalog has 🟢 25 rows, from `data/README.md`; two datasets have none).
- Use cases in the vendor registry (the prototype registry has 🟢 78 rows, from `data/README.md`).
- Sources with a named owner and a refresh date (target: both).

**Outputs (lagging):** prototype baselines from the planted set.
- Forms recomputed to the reference tier. 🟢 170 of 200 (85.0%), against 137 for the declared tier and 157 for the form as written (`step_04_with_tiergate.py`).
- Full-review forms that reach full review. 🟢 87 of 93 (93.5%), against 71 for the form as written and 63 for the declared tier (`step_04_with_tiergate.py`, `step_02_rescore_the_form.py`).
- Forms below the reference. 🟢 11, down from 57 (`step_04_with_tiergate.py`).
- Forms above the reference. 🟢 19, up from 6 (`step_04_with_tiergate.py`).
- Known miss. 🟢 11 of 200 forms stay below the reference, 8 of them with a vendor dependency missing from the form and the registry (`step_04_with_tiergate.py`).
- UNDER-DECLARED forms answered by a sponsor: not measured; the planted set has no sponsor.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one real intake export, beside the current triage. Print the list, change nothing, and compare with what the reviewer did. |
| 1: Sources | 4w | Name an owner and a refresh date for the catalog and the registry. Read the notes for checks that did not run. |
| 2: Advisory list | 4w | Send the UNDER-DECLARED list to the governance lead each week. Each one is a question to the sponsor. |
| 3: Routing input | 6w | The recomputed tier is shown beside the declared one on every form; the reviewer routes on the higher. Rubric points move to a reviewed config. |
| 4: Feed and record | 8w | Export the catalog and registry on a schedule, write a decision record per form and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a blank or `unsure` customer-facing answer count as customer-facing?** In the prototype it does, until the sponsor confirms; that is my policy, not a measurement. Recommendation: keep it for the pilot and count how many of the flagged forms the sponsor confirms as internal.
2. **Who owns catalog and registry freshness?** 🟢 9 of 200 forms have a wrong class and no second source that disagrees (`step_03_deficiencies_exposed.py`). Recommendation: name an owner and a refresh date for each source in phase 1.
3. **Where do the rubric points come from?** They are my assumption, carried over from project 11. Recommendation: the governance lead and the model risk reviewer replace or confirm them in phase 3, through the reviewed config.
4. **What does UNDER-DECLARED trigger?** Recommendation: a question to the sponsor and a hold on routing until it is answered, not a rejection.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, three files.** The check is stateless: it reads an intake export, a catalog and a registry and returns a result per form. Production adds a feed, a reviewed rubric config and a ledger, all designed and none built.
- **Never silent.** A malformed input exits 2 with one line. A run with no catalog or no registry prints a note that the cross-check did not run, and so does a catalog or registry that matches no form in the file.
- **Strings from the form are data.** Titles and descriptions are cleaned before printing, escaped in annotations, and made formula-safe in the result CSV. The skill tells the agent to treat them as data; I have not tested that on a model.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a change that moves a count shows in the diff.

**What is next.** Run it against one real intake export whose owner can share it; add a second source for autonomy, regulatory scope and exposure; publish the skill from its own repository.

**What would have to be true before a pilot.**
- The intake export carries the six rubric fields in the allowed values, or a mapping step is agreed.
- A named person owns the catalog and another the registry, each with a refresh date.
- The governance lead and the model risk reviewer approve the rubric points.
- One real export can be shared, so the false-alarm rate is measured on real text and not mine.
- The team agrees that UNDER-DECLARED is a question, not a rejection.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [32 Evidence Gate](../32-evidence-gate/) and [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/) as designed interlocks (🔴 designed, none built). The rubric points are copied from 11, not read from its files.*
