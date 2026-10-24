# Architecture: ISO 20022 Map Check

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/iso20022_map_check.py`, that reads a legacy-to-ISO field mapping and, optionally, pairs of a legacy message and the ISO message a converter produced, checks the mapping and each pair, and prints PASS or FAIL, run here over 230 synthetic pairs from 10 converter builds. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![Map Check flow](./assets/map-check-flow.svg)

---

## 1. Logical architecture

Map Check is a function between a mapping review and a release: four mapping files and, for a converter build, a pairs file in; a decision out. It does not convert a message, parse XML or judge whether the mapping means the right thing.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `mc-ingest` | Loads the mapping files and the pairs file. Rejects empty, wrong-column, duplicate or dangling input in one line. | Python 3.9+, standard library. Prototype: `load_bundle`, `build_bundle`, `load_pairs` in `src/iso20022_map_check.py` | Yes, by refusing: exit 2 | No |
| `mc-registry` | The mapping files, versioned with the converter. A change needs a reviewer other than its author. | Files in the converter repo (design). Prototype: the four files in `data/` | Yes, config | Stateful, in git |
| `mc-mapping` | Checks the mapping alone: a field with no row, a mandatory element nothing fills, a code with no table entry, a field that cannot fit; the reverse is a warning. | Python. Prototype: `check_mapping`, `capacity` | Yes | No |
| `mc-pairs` | Rebuilds the ISO value the mapping implies, compares it with the converter's output, finds values with no source. | Python. Prototype: `expected_target`, `compare`, `schema_issues`, `check_pair` | Yes | No |
| `mc-verdict` | Turns errors into FAIL and an exit code: 0 clean, 1 an error found, 2 bad input. | Python. Prototype: `run_check`, `main` | Yes | No |
| `mc-probe` | Prints legacy messages with every field at its limit, and lists the code values and combinations no message exercised. | Python. Prototype: `probe_messages`, `coverage` | No: it sets what the pairs can reach | No |
| `mc-report` | Prints findings by kind and element with counts and the first pair. Escapes untrusted strings. Never prints a value. | Python. Prototype: `render`, `_group`, `safe` | No | No |
| `mc-ledger` | One record per decision, and counts off the decision path (design). Prototype analog: the files step 4 writes to `src/out/`. | PostgreSQL plus object storage with a retention lock, OpenTelemetry (design) | No | Stateful |

**What decides the outcome.** The input check, the mapping files, the two rule sets and the verdict. The probe step sets what the pairs can reach: a defect no message exercises cannot be found, and the coverage line shows that gap. The check shows a converter follows the mapping on the messages it sees, not that the mapping is right. A converter test job, outside Map Check, runs the probe messages through the converter and writes the pairs file.

**Repo structure** (production shape):

```
map-check/
├── check/      # ingest, mapping_rules, pair_rules, probe, verdict, report
├── registry/   # the four mapping files, changed by pull request
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
└── tests/      # unit, golden (planted-set numbers), hostile (injection strings)
```

---

## 2. Physical and deployment architecture

The check is one short-lived process in the pipeline that already builds the converter. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check process | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the converter builds |
| Pairs store | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Versioning keeps the bytes a decision used |
| `mc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass. A missing, empty, truncated or mistyped input does not become PASS: it ends the run with exit 2 and a one-line reason. A run with no pairs says so and checks only the mapping. A gap in what the messages exercised is printed, not dropped.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A mapping file is missing, empty, has the wrong columns, a duplicate id, an unknown field, element or code table, an element written by two rows, or `code_tables.json` is invalid | Exit 2, one line on stderr naming the file or row | P2 if repeated on one mapping, else P3 |
| The pairs file is missing, not JSON, has an empty list, or a pair without a string `pair_id` and string-to-string `source` and `target` | Exit 2 with the reason | P3 |
| No pairs given | Output says "only the mapping was checked"; mapping errors still fail | P3 if a converter build ran with no pairs (design) |
| A source field not in the catalogue, an amount that is not digits, or an element the mapping does not explain | Finding (`unknown_source_field`, `source_invalid`, `untraced`), exit 1 | P3 |
| A probe message was sent and no pair came back | The check sees only the pairs it is given. The design has the test job compare messages sent with pairs returned | P3 |

**Latency.** The prototype is one pass over small files; I have not timed it. 🔴 Design target: findings on a mapping change within 5 minutes of the pull request, converter test job included (planning estimate).

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Mapping files | `field`, `path`, `row_id` | Legacy fields, ISO elements, mapping rows, code tables | `legacy_fields.csv`: `field`, `max_len`, `kind`, `codes`. `iso_elements.csv`: `path`, `max_len`, `kind`, `mandatory`, `codes`. `mapping.csv`: `row_id`, `legacy_fields`, `iso_path`, `transform`, `param`. `code_tables.json` |
| Message pair | `pair_id` | The legacy message and the converter's output, as flat maps | `example_pairs.json`: `pair_id`, `source`, `target`; the full 230 are in `legacy_messages.json` and `iso_outputs.json` |
| Decision record | `decision_id` | Design: mapping version, SHA-256 of the mapping files and the pairs file, tool version, counts per finding kind, decision, time | Prototype: the files step 4 writes under `src/out/` |

**Retention** is a design choice, not a measurement: 🔴 7 years by default for decision records, findings, and the mapping version and pairs file a decision used, in PostgreSQL archived to object storage with a retention lock. Confirm it against the bank's own schedule.

**Lineage.** A finding names the element, the count and the first pair; the pairs file returns that pair's source and target; the mapping row that writes the element is in the mapping version the record names. The rules are deterministic (no clock, locale or random draw, and findings are sorted), so re-running on the same hashes reproduces the findings.

**Deliberately not stored.** Payment values from real messages. The check prints names, counts and lengths, and the record keeps the same. Values live only in the pairs file, which the design fills from invented probe messages and test fixtures.

---

## 4. Security architecture

**Identity and roles.** The check runs under the CI platform's workload identity and has no user account of its own.

| Role | Can | Maps to |
| --- | --- | --- |
| `mc:runner` | Read the mapping files and the pairs file; write a decision record | The CI service identity |
| `mc:approver` | Approve a mapping change or an accepted capacity cut, never for their own change | Reviewer who signs the mapping off |
| `mc:auditor` | Read decisions, findings and mapping history | Internal audit |

**Secrets.** None. The check never calls a model or the converter, so no key is in its path; the CI identity reaches the store and ledger by workload identity.

**Data classification and what leaves the boundary.** Mapping files and finding counts are internal. A pairs file holds field values and would carry payment data if built from a real message, so the design forbids that. In the prototype nothing leaves the machine. In the design three things leave the job: the exit code, the finding lines (names and counts) and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an input field echoed into output | A field name or `pair_id` holding a newline and a line that reads `decision: PASS` | `safe` writes control characters as `\uXXXX`, so one input cannot add an output line. `tests/test_cli.py` covers a hostile `pair_id`, field name, element name and catalogue name |
| A capacity finding is made to go away | An element's `max_len` raised with no change in the real specification | Pull request with a different approver; the record stores the mapping hash; lengths come from the bank's specification |
| Production messages end up in a pairs file or a log | A tester copies live traffic into the converter test job | The check prints no value; the test job runs in a test environment on probe messages; the pairs bucket is confidential with its own role |

---

## 5. Operational architecture

**SLIs.** Decisions per outcome per week; input rejections; findings by kind; share of released builds with a pairs run that includes boundary messages; code combinations never exercised; capacity findings without a recorded decision; time to decision. Prototype baseline: 🟢 0 of 162 harmless variations flagged (`step_04_with_check.py`).

**SLOs (all 🔴 design targets, none measured).**
- Findings within 5 minutes of the pull request.
- Every released converter build leaves a decision record that includes a pairs run.
- Every capacity finding carries a recorded decision before release (planning estimate).
- 99.9 percent of decisions written to the ledger.

**Alerts.** P2: repeated input rejections on one mapping. P3: a FAIL on a build marked for release, a build run with no pairs file, or a changed hash for a finished run. P4: a daily digest of coverage gaps.

**Runbooks** (one page each, in `docs/runbooks/`):
- `mapping-error.md`: read the finding, fix the row, length or table, re-run.
- `capacity-overflow.md`: shorten the field, widen the element or record the accepted cut.
- `pair-finding.md`: find the first pair, read the element and its mapping row, fix the converter or the row.
- `changing-the-mapping.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**On-call and ownership.** The mapping owner owns the mapping files, capacity decisions and runbooks. The converter engineer owns the converter and the test job. The reviewer approves mapping changes and accepted cuts. Nobody is paged for a coverage gap.

**Change control.** Rules are versioned in the repo. A change needs a proposer and a different approver. Before merge the planted set is re-run and compared with `tests/test_golden.py`, so a change that moves the found count shows in the diff. Rollout is shadow, calibration, then enforcement, as the PRD lays out.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the Federal Reserve moved the Fedwire Funds Service to ISO 20022, and its press release of July 15, 2025, announces the completed migration ([Federal Reserve Financial Services, read 2026-10-24](https://www.frbservices.org/news/press-releases/071525-iso20022-migration-announcement/)). That release is the only Fed source I read. I did not read the Fedwire message specification or any FedNow format document.

- **What the design does.** It addresses a problem any move to ISO 20022 raises, which the release does not discuss: it checks that a conversion keeps what the mapping says it keeps, and records the decision.
- **What it does not claim.** It states nothing about what Fedwire or FedNow require, and the element lengths are mine. It makes no claim of conformity to the release or to any message specification, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **A judgment on whether the mapping is right.** If the spreadsheet sends the debtor name to the creditor element and the converter obeys it, every pair passes.
- **A defect no message reaches.** 🟢 Build B10 is not found: it drops the beneficiary account only when TYP is 16 and CHGS is S, and 2 of 9 code combinations are in no message (`step_04_with_check.py`). Crossing the coded fields grows as the product of the code counts.
- **Real XML and the real schemas.** The ISO side is a flat path-to-value view; namespaces and structured addresses are out of scope.
- **The ISO-to-legacy direction beyond arithmetic.** The reverse check is a length warning; no converted-back messages are tested.
- **Specification-grade lengths.** The legacy format is invented, and the ISO lengths and mandatory flags are my simplification.
- **Values in the output.** A finding says "differs from character 12", not what the values were. That is deliberate and slower to debug.
- **Rates on real converters.** The data and the rules share an author, so the event-level numbers are a ceiling. Hosting and a CI wrapper are not built.

---

## Appendix: sample contract

The call is the prototype's own; its output for the bundled `--demo` run is under "Run one now" in the README.

```bash
python3 iso20022_map_check.py probe DIR > probes.json
python3 iso20022_map_check.py check DIR --pairs pairs.json
```

`DIR` holds the four mapping files. The pairs file is one object with a list under `pairs`, each pair a string `pair_id` and flat string-to-string `source` and `target` maps, for example a `source` of `{"AMT": "123456789012"}` and a `target` of `{"IntrBkSttlmAmt": "1234567890.12"}`. A finding line reads `[error  ] truncated  Dbtr/Nm  1 of 3 pairs (first B03-P1): kept 33 of 35 characters`. Exit status: 0 when nothing at error level was found, 1 when something was, 2 for bad input.
