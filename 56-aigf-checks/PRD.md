# PRD: aigf-checks

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a governance review. It is not a record of a PRD landed at a named bank. The rules, the planted crosswalk and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the issue and pull request are drafted and not opened.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | aigf-checks: a command-line tool that reads a crosswalk of framework risks to runnable checks, the registry of those checks and the text each one printed, and reports the rows that no longer hold. It also lints a commit message for a sign-off line and a short subject |
| **Owner** | The contributor who offers the risk-to-check mapping, with the maintainer or reviewer who accepts it as co-owner of the aspects each risk needs |
| **Stage** | Portfolio prototype on synthetic data; the tool runs no check |
| **Primary user** | A contributor who wants to offer a risk-to-check mapping to a public framework |
| **Secondary users** | The maintainer or reviewer who decides whether to trust it; the owner of each check; internal audit |
| **Problem** | A governance framework lists risks. A team that wants to show it has dealt with one writes a crosswalk row: this check covers this risk, and this line of its output shows it. The row is typed once. When the check changes, nothing re-reads the row, so the crosswalk keeps saying what was true on the day it was written. In the planted set, 🟢 the sheet flags 0 of 73 rows while 45 of 73 carry a defect (`step_01_no_recheck.py`). |
| **Solution** | Resolves the risk and the check in every row and reports duplicates. Binds each claim to the labelled line of the check's printed output and compares the value, setting aside case, spacing and thousands separators. Reports a row whose check has no captured output instead of skipping it. Compares the aspects a risk needs with the aspects the check declares, and reports a row marked full that is not. Reads the note for the words compliant, certified and guarantee. Gives each risk a status: CHECKED, PARTIAL, UNVERIFIED or GAP. Lints a commit message for a `Signed-off-by` line and a subject of 72 characters or fewer. |
| **North-star metric** | Share of crosswalk rows that were re-read against a freshly captured output in the last run of the checks. Target 🔴 100%. Today in this model: no row is re-read. |
| **Measured metrics (synthetic)** | 🟢 38 of 45 defective rows found; 0 of 28 harmless rows flagged; 23 of 24 risk statuses right; a person reads 38 of 73 rows (`step_04_with_checks.py`). |
| **Modeled metrics** | 🟡 Utility (38/45 − 11/45) × 30 = 18.0 defective rows a year caught that a link-and-grep pass would miss, assuming 30 defective rows arise in the crosswalk each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling. Mitigation: run it on one real crosswalk the owner can share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The aspects a check declares are taken as written. 🟢 7 of 45 defective rows pass, 4 of them registry entries that declare an aspect the check does not exercise (`step_04_with_checks.py`). Mitigation: a reviewer reads the aspects of each check against its output once, and again when the check changes. |
| **Risk #3** | A captured output that is out of date gives an out-of-date pass. Mitigation: capture the output in the same CI job that runs the tool and store its hash with the result. |
| **Out of scope** | Running the checks; reading a check's code; deciding what a real framework entry requires; any model call; opening the issue or the pull request. The contribution is drafted in `contribution/` and waits for the author. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is rows, risks or commits, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Resolve risk and check ids; report duplicate rows** | 73 rows | 2 | 0.9 | 1 | 131.4 | Built in prototype |
| 2 | **Label-bound claim comparison** (stale value, missing label, no captured output) | 73 rows | 3 | 0.8 | 2 | 87.6 | Built in prototype |
| 3 | **CI output and input validation** (text and GitHub annotations, `--fail-on`, escaped strings, malformed files exit 2) | 73 rows | 2 | 0.9 | 2 | 65.7 | Built in prototype |
| 4 | **Capture step in the CI job** that runs the checks and saves their output beside the crosswalk | 73 rows | 3 | 0.6 | 2 | 65.7 | Sequenced for v0.2 |
| 5 | **Note wording rule** (compliant, certified, certification, guarantee) | 73 rows | 1 | 0.8 | 1 | 58.4 | Built in prototype |
| 6 | **Risk status per risk** (CHECKED, PARTIAL, UNVERIFIED, GAP) | 24 risks | 3 | 0.8 | 1 | 57.6 | Built in prototype |
| 7 | **Aspect check** (a row marked full needs every aspect of the risk) | 73 rows | 3 | 0.7 | 3 | 51.1 | Built in prototype |
| 8 | **Aspects as a reviewed field of each risk entry** (the maintainers' call) | 24 risks | 3 | 0.4 | 3 | 9.6 | Sequenced for v0.2 |
| 9 | **Commit sign-off lint** (a `Signed-off-by` line, a subject of 72 characters or fewer) | 5 commits | 2 | 0.9 | 1 | 9.0 | Built in prototype |
| 10 | **Status record** (risk statuses, file hashes, tool version) | 24 risks | 2 | 0.7 | 4 | 8.4 | Sequenced for v0.3 |
| 11 | **Wording rule beyond a word list** (paraphrased overclaims) | 73 rows | 1 | 0.3 | 3 | 7.3 | Queued |
| 12 | **Run the check and read its code** | 20 checks | 3 | 0.4 | 8 | 3.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from aigf-checks | What they fear |
| --- | --- | --- | --- |
| **Contributor** | Owner | A mapping that stays true, and a finding that names the row and the rule when it stops. | A mapping that ages quietly and costs them credibility with the maintainers. |
| **Framework maintainer** | Reviewer and co-owner of the aspects | A small, checkable table, with what each check does not cover stated beside what it does. | A table of claims no one re-reads, or a crosswalk that reads as an endorsement. |
| **Check owner** | Consulted | To hear when a label or a number in their check's output is something a row depends on. | A rename in their output breaking a crosswalk they did not know existed. |
| **Risk or compliance reader** | Consumer | One status per risk, with the rows behind it. | A CHECKED status that rests on a stale capture. |
| **Platform / CI owner** | Owner of the capture job | A step that runs the checks, saves the output and fails with a reason. | A slow step that blocks a build for a documentation row. |
| **Security / CISO** | Approver | Strings from files kept out of logs and workflow commands, and no check run by the tool. | A tool that executes a command named in a registry. |
| **Internal audit** | Reader | A path from a status to the rows, the capture and the hashes it used. | A capture edited by hand to match a claim. |

---

## User stories (top 4)

1. **As a contributor**, I want the crosswalk to fail when a check's printed number no longer matches the claim, so the mapping stays true after the check changes.
2. **As a maintainer**, I want a row marked full to name every aspect of the risk the check exercises, so a partial check is not presented as full coverage.
3. **As a reader of the crosswalk**, I want one status per risk, so I can see which risks are CHECKED, which are PARTIAL and which have no row.
4. **As internal audit**, I want each status tied to the captured output and the registry it was read against, so I can reproduce it later.

---

## KPIs

**North star:** share of crosswalk rows that were re-read against a freshly captured output in the last run of the checks. Target 🔴 100%.

**Inputs (leading):**
- Risks in the catalogue with their aspects stated (the prototype set has 🟢 24 risks and 20 checks, `data/README.md`).
- Checks with a captured output from the same CI job (target: every check; the prototype set has captured output for 17 of the 20 on purpose).
- Rows that name a labelled printed line, not a free-text claim (target: every row).
- Aspects reviewed against each check's output (target: every check).

**Outputs (lagging):** prototype baselines from the planted set.
- Defective rows found. 🟢 38 of 45 with the tool, against 11 of 45 for link-and-grep (`step_04_with_checks.py`, `step_02_link_and_grep.py`).
- Harmless rows flagged. 🟢 0 of 28 (`step_04_with_checks.py`).
- Risk statuses right. 🟢 23 of 24 (`step_04_with_checks.py`).
- Rows a person reads. 🟢 38 of 73 (`step_04_with_checks.py`).
- Known miss. 🟢 7 of 45 defective rows pass: wording_paraphrase 3 and false_declaration 4 (`step_04_with_checks.py`).
- Findings overturned after a maintainer's reply: not measured; the planted set has no maintainer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one real crosswalk with `--fail-on never`. Print the findings, change nothing, and compare with what the owner already knew. |
| 1: Calibration | 4w | Agree the aspects of each risk with a reviewer. Fix the labels in each check's output that a row depends on. |
| 2: Capture in CI | 4w | Run the checks and save their output in the same job as the tool. Store the hash of each capture. |
| 3: Enforced | 6w | Fail the step on any finding. Crosswalk changes go through a pull request with a different approver. |
| 4: Status record | 8w | Write a status record per run. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Where does a table of checks belong in a public framework?** That is the maintainers' call, and the pull request waits for their answer. Recommendation: send the issue draft first, wait for a reply, and open nothing until a maintainer says where such a table should live.
2. **Who decides the aspects a risk needs?** For the synthetic risks I wrote them. Recommendation: the contributor drafts them from each risk entry and a reviewer signs them, because the tool takes them as written.
3. **How is the captured output kept fresh?** The tool compares a claim with a capture the contributor supplies. Recommendation: regenerate the capture in the same CI job that runs the tool, and store its hash.
4. **How far should the wording rule go?** It knows a short list of words, so 3 paraphrased overclaims pass. Recommendation: keep the list short and exact, extend it from review, and accept that a person reads the rest.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the CI job.** The tool is stateless: it reads four files and returns findings and statuses. Production adds a capture step, a reviewed crosswalk repo and a status record, all designed and none built.
- **Never silent.** A missing, empty, truncated or mistyped input exits 2. A row whose check has no captured output is a finding, and a run in which no claim could be compared says so.
- **Strings from files are data.** Text and annotations are cut to one printable line or escaped, so a hostile note or label cannot forge a line or a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the found count shows in the diff.

**What is next.** Send the issue draft to the framework's maintainers and wait for an answer on where a table of checks belongs; then open the pull request with a sign-off on every commit. Run the tool on one real crosswalk the owner may share.

**What would have to be true before a pilot.**
- A named owner regenerates the captured output in the same job that runs the tool.
- A reviewer has read the aspects of each risk and each check.
- Each row names a labelled line that the check prints.
- One real crosswalk can be shared, so the rules are tried on real defects and not mine.
- The team agrees that a pass means the claim matches the capture, not that the risk is treated.

---

*This PRD names [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), [39 Claims Check](../39-claims-check/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The status words come from 16 and are changed to fit a risk and a check; nothing is imported from it.*
