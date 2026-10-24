# Architecture: AI ops operating model review

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: `src/ops_model_review.py` reads a checklist, a programs file and an evidence register, finds the stage the evidence reaches and compares it with the stage the owner claims, over 60 synthetic programs, 23 checklist items and 677 evidence rows, plus a staged Agent Skill that collects the evidence. The skill has not been installed in any agent or run by anyone. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![ai-ops-operating-model flow](./assets/ai-ops-operating-model-flow.svg)

---

## 1. Logical architecture

The review sits between a register of evidence and a status deck: three files and a review date in, a stage and a decision out. It does not open an artifact, compute a tier, approve a program or call a model.

Eight components: five decide the outcome, three collect, record or audit.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `om-skill` | Walks the eight stages, asks for a reference, producer and date per owed item, writes no row without a reference, names one artifact per OK stage to open. | A staged Agent Skill: `skill/ai-ops-review/SKILL.md` | No, it collects; no reference, no row | No |
| `om-ingest` | Loads the three files and the review date. Refuses bad input with a one-line message. | Python 3.9+, standard library. Prototype: `load_checklist`, `load_programs`, `load_evidence`, `parse_date` in `src/ops_model_review.py` | Yes, by refusing: exit 2 | No |
| `om-checklist` | Items, stage, lowest tier that owes each, cycle in days, independence, first-90-days window. | A reviewed CSV in the repo. Prototype: `data/checklist.csv` | Yes, it sets what is owed | Stateful, in git |
| `om-judge` | Judges one owed item: no row, placeholder reference, future date, older than 1.5 cycles, or produced by the builder. | Python. Prototype: `judge` | Yes | No |
| `om-stage` | Skips what the tier does not owe, finds the last stage whose owed items all pass, returns the decision. | Python. Prototype: `review_program` | Yes | No |
| `om-report` | Prints gaps, the first-90-days count and the decision, or annotations; escapes strings; sets the exit code. | Python. Prototype: `render_text`, `render_github`, `one_line`, `escape_annotation`, `run_review` | Yes, the exit code | No |
| `om-register` | System of record with history, and a record per review (design). Prototype: `data/evidence.csv`. | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |
| `om-audit` | Queues the audit sample for a second reader; records whether the sentence held (design). | A small web service (design) | No, it carries the human confirmation | Stateful |

**What decides the outcome.** The input check, the checklist, the item test, the stage rule and the exit code. The skill, register and audit queue collect or record. The command reads rows, not artifacts: a complete-looking row for an empty artifact passes, which is why `om-audit` exists. It trusts the tier, builder id and dates as filed.

**Repo structure** (production shape):

```
ai-ops-review/
├── review/     # ingest.py, judge.py, stage.py, report.py
├── checklist/  # items, tiers, cycles; changed by pull request
├── skill/      # SKILL.md and the question set
├── audit/      # audit sample service
├── register/   # register and review record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

The command is one short-lived job per review cycle, or per pull request that changes the register. The skill is a text file an agent reads; it is not hosted.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Review job (`om-ingest` to `om-report`) | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass over files |
| Register and exports | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Keeps the exact bytes a decision used |
| `om-audit` | Cloud Run service behind the identity proxy | Fargate service behind a load balancer | Container Apps with the identity provider | Reviewers sign in; the confirmation names the person |
| Review record | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing or malformed input ends the run with exit 2 and a one-line reason. An owed item with no row is MISSING, not skipped, and a program with no rows at all says so and marks every owed item MISSING.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A file missing, empty, header only, not text, a column missing, a wrong field count, a tier, stage or cycle out of range, `independent` other than yes or no, or a claimed stage above the last stage | Exit 2, one line naming the file and line | P2 if repeated in one cycle, else P3 |
| An evidence row for an unknown program or item, or a second row for one pair | Exit 2, not ignored | P3 |
| A review date that is not a real date, `--program` that matches nothing, `--window` other than 30, 60 or 90 | Exit 2 | P4 |
| A program with no evidence rows | Every owed item MISSING, with a line saying so | P4 digest |
| Register or audit queue unavailable (design) | The decision and exit code stand; the record queues locally; the audit gap is listed | P3 |

**Latency.** I have not timed the prototype. 🔴 Design target: a decision for one program within 10 seconds of the files landing.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Checklist item | `item_id` | Stage, lowest tier, cycle, independence, window, the sentence to confirm | `data/checklist.csv`: `item_id`, `stage`, `stage_name`, `item`, `evidence`, `min_tier`, `cycle_days`, `independent`, `day_window`, `must_show`, `source` |
| Program | `program_id` | Tier, builder, claimed stage | `data/programs.csv`: `program_id`, `program_name`, `tier`, `builder`, `claimed_stage` |
| Evidence row | `program_id`, `item_id` | Reference, producer and date; one row per pair | `data/evidence.csv`: `program_id`, `item_id`, `artifact_ref`, `produced_by`, `date` |
| Review | `program_id`, review date | Stage reached, decision, gaps, first-90-days count | `src/out/step_04_programs.csv` |
| Planted truth | `program_id`, `item_id` | True stage and the planted state; synthetic data only | `data/program_truth.csv`, `data/item_truth.csv` |

**Retention** is a design choice, not a measurement; confirm it against the bank's own schedule. 🔴 Design default: reviews, register rows and the checklist version used for 7 years, in PostgreSQL archived with a retention lock, so a decision can be reproduced.

**Lineage.** A decision traces back in three hops: the record names the program, review date, checklist version and register hash; the versioned store returns those bytes; and the rules never read the clock, so `review_program` reproduces the decision. In the prototype the trace is a row of `step_04_programs.csv`.

**Deliberately not stored.** The artifacts themselves. The register holds a reference a second person can open, not the document.

---

## 4. Security architecture

**Identity and roles.** The job runs under the platform's workload identity and has no account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `om:filer` | Add evidence rows for their own program | Program owner |
| `om:reviewer` | Run the review; approve a checklist or cycle change, never for their own program | AI program office, second line |
| `om:second-reader` | Open an artifact and record whether the sentence held | Independent reviewer |
| `om:auditor` | Read reviews, register history and config history | Internal audit |

**Secrets.** None, and no model call. The job reaches storage and the record store through workload identity, with no static keys. The skill asks a person for a reference and holds no credential.

**Data classification and what leaves the boundary.** Program names, builder ids and artifact references are internal; a reference is a pointer, and the document keeps its own classification. In the prototype nothing leaves the machine. In the design the decision, the annotations and the record write leave the job.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a program name or reference echoed into a log or workflow command | A reference holding a newline and text that looks like `::error::` | `escape_annotation` rewrites `%`, carriage return and newline; `one_line` turns control characters into spaces; `tests/test_cli.py` covers both |
| A reference to an empty or unrelated document | A complete-looking row for a hollow artifact | The command cannot see this. 🟢 It rejects 0 of 19 hollow artifacts (`step_04_evidence_review.py`). The audit sample is the control |
| The agent running the skill invents a reference | A made-up document id to keep the walk moving | The skill forbids it. The audit sample opens the artifact; the register stores who filed the row |
| The builder files evidence under another name | `produced_by` set to a colleague | The tool compares names only. In the design the producer comes from the identity provider, not a typed field |
| The register is edited after a review | A stale date changed to a fresh one | Versioned register; the record stores its hash and the review date |

---

## 5. Operational architecture

**SLIs.** Decisions per run (CONFIRMED, OVERCLAIM, UNDERCLAIM); owed items by status; programs with a first-90-days item open; input rejections; audit samples opened and how many fail; age of the oldest OVERCLAIM. Prototype baseline: 🟢 CONFIRMED 19, OVERCLAIM 30 and UNDERCLAIM 11 across 60 programs (`step_04_evidence_review.py`).

**SLOs (all 🔴 design targets, none measured).**
- A decision for one program within 10 seconds of the files landing.
- Every OVERCLAIM read by a named person within one business day (planning estimate).
- An audit sample opened for every OK stage before the stage is relied on.
- 99.9 percent of reviews written to the register.

**Alerts.** P2: repeated input rejections, or the register down for more than a day (low-urgency page). P3: an OVERCLAIM on a tier 3 or 4 program, or a failed audit sample (chat). P4: a weekly digest of MISSING or STALE items (email).

**Runbooks** (one page each, in `docs/runbooks/`):
- `overclaim.md`: read the gaps; the owner files the evidence or restates the stage.
- `stale-or-late.md`: tell a lapsed cycle from a late one; record the reason.
- `audit-sample.md`: open one artifact per OK stage and confirm one sentence.
- `changing-the-checklist.md`: propose, re-run the planted set, compare, approve.

**On-call and ownership.** The program office lead owns the job, the register and the runbooks. Item owners own the cycle days. The second line approves checklist changes. Nobody is paged for a single OVERCLAIM on a low tier.

**Change control.** The checklist, tiers and cycles are versioned; a change needs a proposer and a different approver. Before merge the planted set is re-run against the pinned numbers in `tests/test_golden.py`, and a test checks that the skill's table still matches `data/checklist.csv`.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites two sources, restated with the same wording about what was read.

- The Financial Stability Board's [Sound Practices for Responsible Adoption of Artificial Intelligence](https://www.fsb.org/uploads/P151026-1.pdf) (final report, 15 October 2026; I read the full text on 24 October 2026). Sound Practice 3 asks institutions to document AI use and to assess materiality and risk; Sound Practice 5 asks for that assessment at inception and after; Sound Practice 9 asks for performance evaluation in proportion to materiality and risk, including ongoing monitoring.
- [SR 26-2, Revised Guidance on Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (Federal Reserve, OCC and FDIC, 17 April 2026; I read the attached guidance on 24 October 2026). It says it sets no enforceable standards or prescriptive requirements, and says in a footnote that generative AI and agentic AI models are outside its scope while a bank's own risk management and governance practices should guide their controls.

- **What the design does.** The tier that sets what is owed, the evidence register and the renewal cycle are one way to make the three practices concrete, as a design for a bank's own governance.
- **What it does not claim.** It does not map to the FSB report's section on stages or to SR 26-2 clause by clause, makes no claim of conformity to either, holds no certification, and I have read and mapped no other source.

---

## 7. What is deliberately not here

- **Reading the artifacts.** 🟢 The review rejects 0 of 19 hollow artifacts, and 6 of the 36 overclaims still pass (`step_04_evidence_review.py`). The audit sample is designed and not measured.
- **Lapsed evidence inside the grace.** Lapsed evidence younger than 1.5 times its cycle passes: 🟢 5 of the 24 lapsed items did (`step_03_deficiencies_exposed.py`).
- **Late cycles.** 🟢 8 items planted as fine are rejected as stale, and one program lands below its true stage (`step_03_deficiencies_exposed.py`).
- **The tier.** The tool takes the tier as given and does not compute it.
- **History.** The register holds one row per program and item, so it shows the latest artifact only.
- **Thresholds from a real register.** Tiers, cycles, the 1.5 times factor and the first-90-days window are assumptions, and the planted set and the rules share an author.

---

## Appendix: sample contract

```bash
python3 ops_model_review.py review --checklist C.csv --programs P.csv --evidence E.csv --as-of 2026-09-30 --window 90
```

An evidence row reads `program_id,item_id,artifact_ref,produced_by,date`. Exit status: 0 when no claim is above its evidence (or `--fail-on never`), 1 when one is, 2 for bad input. The `--demo` output is under "Run one now" in the README.
