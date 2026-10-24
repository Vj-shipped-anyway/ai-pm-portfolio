# PRD: Intake Tier Action

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an AI governance intake review. It is not a record of a PRD landed at a named bank. The rubric, the planted intake set and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the Action has not run on GitHub.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Intake Tier Action: a command-line tool, with a staged GitHub Action, that reads an AI intake issue body by its form headings, recomputes the risk tier from six answers and two cross-checks, and says which labels to add and remove |
| **Owner** | The person who runs AI intake for a regulated team, with the second-line reviewer as co-owner of the rubric |
| **Stage** | Portfolio prototype on synthetic data; the Action is staged and unpublished |
| **Primary user** | The person who runs AI intake for a regulated team |
| **Secondary users** | The reviewer who picks the next issue from a label; the sponsor who fills in the form; the data steward who owns the catalog; the vendor manager who owns the registry; internal audit |
| **Problem** | AI use cases arrive as issues. The sponsor fills in a form and declares a tier, and that declaration becomes the label. It is the answer most likely to be low for the use cases that matter. A workflow that reads the form with a regex fixes the arithmetic but not the inputs, and it labels bodies it cannot read, adds a second tier label when an issue is edited, and echoes issue text into logs. In the planted set, 🟢 21 of 55 tier 3-4 issues are declared at tier 1-2 (`step_01_declared_label.py`). |
| **Solution** | Reads the issue body by the form's own headings and refuses to guess a missing or ambiguous input. Recomputes the tier from six answers, using the higher of the form and a data catalog for the data class and the higher of the form and a vendor registry for the vendor model, and counting a blank or unsure customer-facing answer as customer-facing until confirmed. Says which labels to add and which of its own labels to remove. Writes one comment with a marker, listing the checks that ran and the evidence the tier asks for. Echoes only text it has made safe. |
| **North-star metric** | Share of AI intake issues that carry a tier label computed from checked inputs, or needs-info, and never a tier taken from the sponsor's word alone. Target 🔴 100%. Today in this model: the declared tier is the label. |
| **Measured metrics (synthetic)** | 🟢 142 of 160 issues tiered and 18 sent to needs-info; 129 of 160 tiers equal the reference (124 for the regex); 46 of 57 tier 3-4 issues found, 4 put at tier 1-2, 7 sent to needs-info; one tier-or-needs-info label on 160 of 160 issues after 24 edits (`step_04_with_action.py`). |
| **Modeled metrics** | 🟡 Utility (18/57 − 4/57) × 40 = 9.8 tier 3-4 issues a year that no longer carry a tier 1-2 label, assuming 40 tier 3-4 issues a year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so the numbers are a ceiling, and the rubric points are my assumption carried over from project 11. Mitigation: replace the rubric with the bank's own and run on a real export. |
| **Risk #2** | The body format is from memory and has not been checked against a real GitHub issue. Mitigation: open one real issue from the form and compare it with what the parser expects; the tool sends an unreadable body to needs-info and names the heading it could not find. |
| **Risk #3** | The cross-checks are only as good as the catalog and the registry, and a strict parser costs a person one look. 🟢 11 issues are tiered with a data class below the true class and the tier is wrong on 2; 4 complete forms go to needs-info only because a pasted block repeats a heading (`step_04_with_action.py`). Mitigation: show the known limit in the comment and send the catalog entry to its steward. |
| **Out of scope** | Approving anything; reading free text with a model; checkboxes and several forms; a hosted service; a Marketplace listing, which is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is intake issues, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Read by headings and refuse to guess** (missing, blank, repeated or out-of-range input gives needs-info) | 160 issues | 3 | 0.9 | 1 | 432.0 | Built in prototype |
| 2 | **Recompute the tier from six answers** (rubric and cut-offs) | 160 issues | 3 | 0.8 | 1 | 384.0 | Built in prototype |
| 3 | **Label reconciliation on edit** (one tier label, only its own labels removed) | 160 issues | 2 | 0.9 | 1 | 288.0 | Built in prototype |
| 4 | **Safe echo** (sponsor text made safe, annotations escaped) | 160 issues | 2 | 0.8 | 1 | 256.0 | Built in prototype |
| 5 | **Data-class cross-check against the catalog** | 160 issues | 3 | 0.7 | 2 | 168.0 | Built in prototype |
| 6 | **One comment with a marker, the checks and the evidence list** | 160 issues | 1 | 0.8 | 1 | 128.0 | Built in prototype |
| 7 | **Vendor-model cross-check against the registry** | 160 issues | 2 | 0.6 | 2 | 96.0 | Built in prototype |
| 8 | **Publish the Action from its own repository, after checking the body format on a real issue** | 160 issues | 3 | 0.5 | 3 | 80.0 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Reviewer approval tied to the issue version** (an edit after approval reopens it) | 160 issues | 3 | 0.5 | 4 | 60.0 | Sequenced for v0.2 |
| 10 | **Decision ledger** (inputs hash, rubric version, tier, flags, per edit) | 160 issues | 2 | 0.6 | 4 | 48.0 | Sequenced for v0.2 |
| 11 | **The bank's own rubric in place of mine** | 160 issues | 3 | 0.4 | 5 | 38.4 | Sequenced for v0.3 |
| 12 | **Close the known limit** (data class understated on both the form and the catalog) | 11 issues | 3 | 0.3 | 3 | 3.3 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Intake Tier Action | What they fear |
| --- | --- | --- | --- |
| **AI intake lead** | Owner | A label they can trust to order the queue, and a needs-info that says what to fix. | A workflow that labels what it cannot read and gets ignored. |
| **Second-line reviewer** | Co-owner of the rubric | Every tier tied to the checks that ran, so a tier is a starting point for review and not a verdict. | A tier treated as an approval. |
| **Sponsor** | Fills in the form | Fast feedback on what is missing, in plain words, on the issue itself. | Being sent back for a formatting slip on a complete form. |
| **Data steward** | Owns the catalog | A flag when a form declares a class below the catalog, and one when the catalog looks too high. | Being blamed for a stale entry the tool exposed. |
| **Vendor manager** | Owns the registry | A flag when the form says no vendor and the registry says otherwise. | A registry keyed on something procurement does not file against. |
| **Security / CISO** | Approver | Issue text kept out of logs and comments, a token with only issue permissions, no value interpolated into a shell command. | A public form that lets a stranger inject a workflow command. |
| **Internal audit** | Reader | A path from a label to the body, the rubric version and the checks. | A tier relabeled by an edit with no record. |

---

## User stories (top 4)

1. **As the AI intake lead**, I want an issue the workflow cannot read to say so and get no tier, so the queue is not ordered by a guess.
2. **As a reviewer**, I want the data class and vendor model checked against the catalog and registry, so the use cases most likely to be under-declared are not labeled lowest.
3. **As a sponsor**, I want to edit the form and get one correct tier label and the same comment updated, so I do not end up with two tier labels.
4. **As internal audit**, I want hostile text in an issue kept out of the log and the comment, so an intake form cannot be used to forge a workflow command.

---

## KPIs

**North star:** share of AI intake issues that carry a tier label computed from checked inputs, or needs-info, and never a tier taken from the sponsor's word alone. Target 🔴 100%.

**Inputs (leading):**
- Issues that carry every required heading with an allowed value (the prototype set has 🟢 142 of 160 readable bodies, from `step_04_with_action.py`).
- Datasets named on the form that are in the catalog (the prototype catalog has 🟢 23 datasets, from `data/README.md`).
- Issues the vendor registry has an entry for (the prototype registry has 🟢 83 rows, from `data/README.md`).
- Reviewers who read the comment before approving (target: every one).

**Outputs (lagging):** prototype baselines from the planted set.
- Tiers equal to the reference. 🟢 129 of 160 with the tool, against 124 of 160 with a regex (`step_04_with_action.py`, `step_02_form_and_regex.py`).
- Tier 3-4 issues put at tier 1-2. 🟢 4 of 57, against 18 of 57 with a regex (`step_04_with_action.py`, `step_02_form_and_regex.py`).
- Unreadable bodies named and not tiered. 🟢 18 of 160 (`step_04_with_action.py`).
- One tier-or-needs-info label after edits. 🟢 160 of 160 issues, with the unrelated label kept on 160 of 160 (`step_04_with_action.py`).
- Hostile text. 🟢 0 workflow commands forged and 0 of 160 comments echoing a mention, tag, link or command (`step_04_with_action.py`).
- Known limit. 🟢 11 issues tiered with a data class below the true class, the tier wrong on 2 (`step_04_with_action.py`).
- Tiers a reviewer later changed: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Verify and shadow | 4w | Open one real issue from the form and compare its body with what the parser expects. Run the command on exported issues with `--fail-on never` and apply nothing. |
| 1: Advisory labels | 4w | Apply labels and the comment on a throwaway repository, then on one pilot intake repository. A reviewer still sets the tier of record. |
| 2: Cross-checks wired | 4w | Connect the catalog and registry exports, and send the flags to their stewards. |
| 3: Strict reading enforced | 6w | Let needs-info hold an issue out of the queue. Publish the Action from its own repository. |
| 4: Ledger and the bank's rubric | 8w | Record a decision per edit, replace my rubric with the bank's own, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should an unreadable body hold the issue out of the queue or only warn?** In the prototype it gets needs-info and no tier. 🟢 That is 18 of 160 issues, 4 of them complete forms with a pasted heading (`step_04_with_action.py`). Recommendation: hold it, and say in the comment exactly which heading to fix.
2. **Whose rubric?** The points per answer and the cut-offs are mine. Recommendation: replace them with the bank's own before the tier is used for anything but ordering.
3. **Is the body format right?** I wrote the parser from memory of how an issue form renders. Recommendation: verify on one real issue before anything else.
4. **Who corrects a catalog entry the tool contradicts?** 🟢 DATA_CLASS_ABOVE_CATALOG is raised 12 times and the tier stays at the form's class (`step_04_with_action.py`). Recommendation: send each flag to the data steward and keep the tier unchanged until the entry is reviewed.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One step in a workflow.** The tool is stateless: it reads one issue body, two optional registers and the current labels, and writes two label lists and a comment. Production adds live feeds and a decision ledger, both designed and none built.
- **Never silent.** A body it cannot read gets needs-info, not a tier; a file it cannot read exits 2. A stale tier label is removed when the issue is edited.
- **Strings from input are data.** Sponsor text is reduced to safe characters before it reaches a comment, and annotations are escaped, so an issue body cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rubric change that moves a count shows in the diff.

**What is next.** Open one real issue from the form and compare its body with what the parser expects; run it on a throwaway repository; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The form renders as the parser expects, checked on a real issue.
- A named person owns the rubric and the label set, and a different person owns the catalog.
- The registry is keyed on something procurement files against the intake issue.
- The workflow token has issue permissions only.
- A reviewer still sets the tier of record.

---

*This PRD names [11 TierGate](../11-tiergate-ai-usecase-intake/), [35 TierGate](../35-tiergate/), [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/) and [44 Inventory Check](../44-inventory-check/) as designed interlocks (🔴 designed, none built). The rubric is carried over from 11 as an assumption, not read from its files.*
