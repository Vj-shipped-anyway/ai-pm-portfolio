# Architecture: TierGate Skill

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/tiergate.py`, that reads an intake CSV, a data catalog and a vendor registry, recomputes the tier with a written rubric and lists every form declared below its recomputed tier, run here over 200 synthetic intake forms. An Agent Skill is staged in `skill/` and has not been published or loaded into an agent runtime. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![TierGate flow](./assets/tiergate-flow.svg)

---

## 1. Logical architecture

TierGate Intake Check is a function at the front door of intake: an export of forms and two second sources in, a result per form out. It does not route a form or call a model.

Eight components: four decide the outcome, four support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `tg-ingest` | Reads the intake CSV, catalog and registry. Rejects bad input with a one-line message. | Python 3.9+, standard library. Prototype: `read_table`, `read_intake`, `read_catalog`, `read_registry`, `check_choice` in `src/tiergate.py` | Yes, by refusing: exit 2 | No |
| `tg-rubric` | Points per input and tier cut-offs. In production, a reviewed config file. | Prototype: the `PTS_*` tables, `rubric_score`, `tier_from_score` | Yes, config | Stateful, in git (design) |
| `tg-recompute` | Takes the higher of form and catalog for the data class, and of form and registry for the vendor model; resolves the customer-facing answer from its value and the text; then scores. | Python. Prototype: `recompute`, `CUE_RE` | Yes | No |
| `tg-verdict` | Compares declared with recomputed tier: UNDER-DECLARED, OVER-DECLARED or MATCH. Exit 1 if any is under-declared. | Python. Prototype: `status_of`, `run_check`, `check_command` | Yes | No |
| `tg-report` | Prints text, annotations or a CSV. Notes when a cross-check could not run. Escapes untrusted strings. | Python. Prototype: `render_text`, `render_github`, `write_results`, `notes_for`, `clean`, `gh_escape`, `csv_safe` | No | No |
| `tg-skill` | Tells an agent to run the command, report what it printed and state the limits. | `skill/tiergate-intake-check/SKILL.md`, staged, not published | No | No |
| `tg-feed` | Exports the catalog and registry on a schedule, with a refresh date per row (design). | A scheduled export job | No | Stateful |
| `tg-ledger` | Appends one record per form per run; counts to monitoring, off the decision path (design). Prototype analog: `src/out/step_04_results.csv`. | PostgreSQL, object storage with a retention lock, OpenTelemetry (design) | No | Stateful |

**What decides the outcome.** The input check, the rubric, the three cross-checks and the comparison. The rest carry or record the result. The recompute can disagree with the form only where a second source exists; autonomy, regulatory scope and exposure have none here.

**Repo structure** (production shape):

```
tiergate/
├── check/      # ingest, rubric, recompute, verdict, report
├── skill/      # the Agent Skill file
├── config/     # rubric points and cut-offs, changed by pull request
├── feed/       # catalog and registry export
├── ledger/     # result record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile
```

---

## 2. Physical and deployment architecture

The check is one short-lived batch job run when an intake export lands or on a schedule.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check job | Cloud Run job or Cloud Build step | ECS Fargate task or CodeBuild step | Container Apps job or Azure Pipelines step | Stateless, one pass over three files |
| `tg-feed` exports | Scheduled export to Cloud Storage, versioned | Export to S3, versioned | Export to Blob Storage, versioned | The job reads one version of each source, and the version is recorded |
| `tg-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass. A malformed input does not become MATCH: it ends the run with exit 2 and a one-line reason. A cross-check that could not run says so on the output.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A file missing, empty, header only, not UTF-8, not CSV or truncated; a missing or repeated column; a blank or repeated key; a value outside the allowed set; `self_declared_tier` not 1 to 4; `--out` unwritable | Exit 2, one line on stderr naming the file, row and column | P3; P2 if repeated |
| No catalog or registry given, or one that matches no form in the file | A `note:` line says the cross-check did not run; the run continues | P2 in the design: the feed is probably wrong |
| A dataset not in the catalog | Flag `DATASET_NOT_IN_CATALOG`; the form's class stands | P4 digest |
| Ledger or feed unavailable (design) | The result stands; the record queues locally | P3 |

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Intake form | `use_case_id` | What the sponsor wrote, including the declared tier | `data/intake_submissions.csv`: `use_case_id`, `title`, `description`, `dataset_name`, `customer_facing`, `decision_autonomy`, `data_class`, `vendor_model`, `regulatory_scope`, `financial_exposure_band`, `self_declared_tier`. Other columns are ignored |
| Dataset class | `dataset_name` | The class the catalog records | `data/data_catalog.csv`: `dataset_name`, `catalog_class` |
| Vendor dependency | `use_case_id` | The vendor model the registry lists | `data/vendor_registry.csv`: `use_case_id`, `vendor_model` |
| Result | `use_case_id`, run | Declared and recomputed tier, points, status and flag codes | `--out` file: `use_case_id`, `declared_tier`, `recomputed_tier`, `score`, `status`, `flag_codes` |
| Result record | `record_id` | Design: form hash, source versions, rubric version, result, flags | Prototype: `src/out/step_04_results.csv` |
| Planted truth | `use_case_id` | The true inputs, reference tier and planted situation | Hidden columns of `data/intake_submissions.csv`, such as `reference_tier`. Synthetic only; a test confirms the output is the same without them |

Flag codes: `DATA_CLASS_BELOW_CATALOG`, `DATA_CLASS_ABOVE_CATALOG`, `DATASET_NOT_IN_CATALOG`, `VENDOR_NOT_DECLARED`, `CUSTOMER_FACING_CUE`, `CUSTOMER_FACING_AMBIGUOUS`, `TIER_DECLARED_BELOW`, `TIER_DECLARED_ABOVE`. `sponsor_unit` is not read.

**Retention** is a design choice; confirm it against the bank's own schedule. 🔴 Design default: result records for 7 years in PostgreSQL, archived with a retention lock, and the input versions a result used for as long.

**Lineage.** A result traces back in three hops: the record names the form hash, the source versions and the rubric version; the versioned store returns those bytes; and the recompute is deterministic, so re-running `recompute` reproduces the flags and the tier.

**Deliberately not stored.** The description text beyond the form hash, and any customer data.

---

## 4. Security architecture

**Identity and roles.** The job runs under the platform's workload identity. `tg:runner` reads the exports and config and writes a result record. `tg:approver` (governance lead and model risk reviewer) approves a change to the rubric points. `tg:auditor` reads results and config history. `tg:admin` manages roles and the ledger.

**Secrets.** None. The command never calls a model and holds no key.

**Data classification and what leaves the boundary.** Titles and descriptions are sponsor-written and may carry confidential detail; treat them as confidential. In the prototype nothing leaves the machine. In the design the exit code, annotations and ledger write leave the job.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a title or description echoed into a log, annotation or CSV | A title with a newline and text that looks like a workflow command, or a cell that starts with `=` | `clean` blanks control characters; `gh_escape` rewrites `%`, carriage return and newline; `csv_safe` guards formula cells. Every text line starts with the status. `tests/test_cli.py` covers each |
| Text addressed to the agent that runs the skill | A description that says to ignore the rubric | The skill says to treat titles and descriptions as data. I have not tested that on a model, so it is an intent and not a control |
| The rubric points are changed to lower a tier | Points for a data class lowered | Pull request with a different approver; every result stores the rubric version |
| A stale catalog entry agrees with a wrong form | The class is wrong on the form and in the catalog | The check cannot see this: 🟢 9 of 200 forms (`step_03_deficiencies_exposed.py`). The feed carries a refresh date, and the data steward owns it |

---

## 5. Operational architecture

**SLIs.** Results per status per week (prototype baseline: 🟢 63 forms under-declared, 4 over-declared and 133 unchanged, `step_04_with_tiergate.py`); input rejections; runs where a cross-check did not run; datasets not in the catalog; age of the exports; UNDER-DECLARED forms answered by a sponsor.

**SLOs (all 🔴 design targets, none measured).**
- A result within 60 seconds of an intake export landing (I have not timed the prototype).
- Every production run has both a catalog and a registry (no `note:` line about a skipped check).
- Every UNDER-DECLARED form has a question sent within one business day (planning estimate).

**Alerts.** P2: repeated input rejections, a source that matches no form, or the ledger down over a day (low-urgency page to the governance lead). P3: a production run without a catalog or registry, or a changed hash for a finished result (chat). P4: a daily digest of datasets not in the catalog (email).

**Runbooks** (one page each, in `docs/runbooks/`):
- `under-declared.md`: read the flag, ask the sponsor, record the answer.
- `input-rejected.md`: find which export broke and re-run.
- `changing-the-rubric.md`: propose, re-run the planted set, compare with the golden numbers, approve.
- `stale-source.md`: find why a source disagrees with a form, and fix it there.

**On-call and ownership.** The governance lead owns the rubric, runbooks and result list, the data steward the catalog, the vendor manager the registry, the platform team the job. Nobody is paged for an UNDER-DECLARED form.

**Change control for the rubric.** Points and cut-offs are versioned in the repo; a change needs a proposer and a different approver. The generator keeps its own copy of the rubric to score the truth, so a change goes to both, the data is regenerated, and the planted set is compared with `tests/test_golden.py`.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) (v2, 20 October 2025). I read its page [A heuristic approach to identifying GenAI risks](https://air-governance-framework.finos.org/heuristic-assessment.html) on 2026-10-23. It asks a team to assess a use case on factors such as internal or customer-facing users, data sensitivity, third-party or in-house models, and advisory or automated decisions, and it covers applicable regulation.

- **What the design does.** Five of the six rubric inputs map onto those factors; the financial exposure band is my own addition. It recomputes a tier from them where a second source exists.
- **What it does not claim.** The page defines no numeric tiers or scores and gives its Low, Medium or High rating in its last step, after controls; this design tiers at intake, before any control, so its tier is not that rating, and the points and cut-offs are my assumption and not a reading of that text. It makes no claim of conformity to that guidance or any other standard, holds no certification, and I have not read any other source.

---

## 7. What is deliberately not here

- **A second source for three inputs.** Autonomy, regulatory scope and exposure are taken from the form; the planted forms never get them wrong, so the prototype cannot show what a wrong one costs.
- **Wrong in both places.** 🟢 9 of 200 forms have a wrong class and no second source that disagrees: a stale catalog entry that understates the class too, or a dataset with no entry (`step_03_deficiencies_exposed.py`).
- **Vendor dependencies nobody wrote down.** 🟢 8 of the 11 forms still below the reference have one missing from the form and the registry (`step_04_with_tiergate.py`).
- **Reading descriptions for meaning.** The customer-facing rule is a keyword match; it reads "client-side" as a client and cannot see a tool whose text names nobody.
- **A low false-alarm rate.** 🟢 Forms above the reference rise from 6 to 19 (`step_04_with_tiergate.py`). Blank and `unsure` answers count as customer-facing until the sponsor confirms; that is my policy.
- **Tiers from a standard.** The points, the cut-offs and the choice of tiers 3 and 4 as full review are assumptions.
- **Duplicate linking, the evidence gate, the review queue, hosting, or a published skill.**

---

## Appendix: sample contract

```bash
python3 tiergate.py check intake.csv --catalog catalog.csv --registry registry.csv --format github --out tier_result.csv
```

Exit status: 0 when no form is declared below its recomputed tier, 1 when at least one is, 2 for bad input.
