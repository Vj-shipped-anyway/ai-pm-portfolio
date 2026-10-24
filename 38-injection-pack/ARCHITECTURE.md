# Architecture: Injection Pack

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a command, `src/injection_pack.py`, that replays a pack of injection cases on the old and the new rules of a five-layer prompt gateway and fails the check when a case the old rules got right is now wrong. The gateway is a rule file of regular expressions, not a live endpoint. It runs here over 51 synthetic rule changes. A GitHub Action is staged in `action/`, unpublished and not run on GitHub. Nothing below is claimed as deployed or load-tested; a design target says so.

GCP is primary; AWS and Azure sit beside it.

![Injection Pack flow](./assets/injection-pack-flow.svg)

---

## 1. Logical architecture

Injection Pack sits between a rule pull request and a merge: two rule files and a pack in, a decision out. It does not call a gateway or a model.

Eight components: five decide the outcome, three support, report or record.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `ip-ingest` | Loads both rule files and the pack; rejects malformed input and patterns that do not compile | Python 3.9+, standard library. Prototype: `check_rules`, `load_rules`, `load_pack` | Yes, by refusing: exit 2 | No |
| `ip-gateway` | Compiles a rule file into the five layers and decides which rules fire on a case, by channel | Python. Prototype: `build_gateway`, `normalize`, `matches`, `empty_layers` | Yes | No |
| `ip-runner` | Replays the pack on one gateway and counts attacks blocked and benign cases blocked | Python. Prototype: `run_pack`, `summarize` | Yes | No |
| `ip-diff` | Lists changed rules, finds regressions and blind spots, applies optional floors, picks ALLOW or BLOCK | Python. Prototype: `rule_changes`, `compare`, `floor_problems`, `run_compare` | Yes | No |
| `ip-pack` | The pack as a reviewed CSV in the repo | Prototype: `data/pack.csv`. Design: a reviewed repo with technique coverage | Yes: decides what is tested | Stateful, in git |
| `ip-report` | Prints text or annotations; escapes ids and text from the input | Python. Prototype: `render_compare`, `render_run`, `escape_annotation`, `clean` | No | No |
| `ip-action` | Runs the command in a CI job, inputs through environment variables | Composite GitHub Action, staged in `action/action.yml` | No | No |
| `ip-ledger` | One record per decision (design). Prototype analog: `src/out/step_04_decisions.csv` | PostgreSQL plus object storage with a retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the compiled rules, the pack and the comparison. A regression is a case the old rules got right and the new rules get wrong; any regression is a BLOCK. The report, the Action and the ledger carry or record it. ALLOW means no case in the pack got worse, not that the change is safe.

**Repo structure** (production shape):

```
injection-pack/
├── pack/       # ingest, gateway, runner, diff, report
├── cases/      # the pack, changed by pull request with a different approver
├── action/     # composite Action wrapper
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden (planted-set numbers), hostile strings
```

---

## 2. Physical and deployment architecture

One short-lived process in the pipeline that already tests the gateway repository. No server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Check process | Cloud Build step or Cloud Run job | CodeBuild step or ECS Fargate task | Azure Pipelines step or Container Apps job | Stateless, one pass, runs where the rules are tested |
| Rule files and pack | The gateway repo, plus Cloud Storage for archived copies | Same, with S3 | Same, with Blob Storage | The change and its test land in one history |
| `ip-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The check must never silently pass on input it could not read. Malformed input ends the run with exit 2, and that fails the CI step. A rule change the pack cannot see is not an error in the prototype; it is a printed note, and the reviewer has to read it.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A rule file that is not an object, lacks a layer, repeats a rule id, or holds a pattern that does not compile | Exit 2, one line on stderr, CI step fails | P2 if repeated, else P3 |
| A pack that is empty, truncated, missing a column, has a bad `channel` or `expected` value, or a duplicate `case_id` | Exit 2 with the line number | P3 |
| A floor outside 0 to 100 | Rejected before the run | P4 |
| A changed rule matches no case in the pack, or a layer holds no rules | Note printed, decision unchanged | P3 to the pack owner |
| A pattern that hangs the matcher (no timeout in the prototype) | The run hangs; the design adds a job timeout | P2 |
| Ledger unavailable (design) | The decision and exit code stand; the record queues locally | P3 |

**Latency.** I have not timed the prototype. 🔴 Design target: a decision within 60 seconds of a rule pull request opening.

---

## 3. Data architecture

| Entity | Key | Real columns in the prototype |
| --- | --- | --- |
| Rule file | `id` per rule | JSON: `normalize`, `l1_input`, `l2_retrieval`, `l4_egress` (lists of `id`, `pattern`), `l3_tools` (`allowed_domains`, `destination_keys`, `denied_tools`), `l5_session` (`enforce_owner`) |
| Case | `case_id` | `pack.csv`: `case_id`, `channel`, `technique`, `expected`, `hard`, `session_id`, `memory_owner`, `text`. The runner requires `case_id`, `channel`, `expected`, `text` |
| Result | `case_id` | In memory: `blocked`, the first `rule` that fired, `ok` against `expected` |
| Decision record | `pr_id` | Design: pull request, hashes of both rule files and the pack, tool version, regressions, notes, decision. Prototype: `step_04_decisions.csv` with `pr_id`, `kind`, `layer`, `note`, `lost`, `gained`, `truth`, `decision`, `pack_regressions`, `blind_spot_note` |
| Planted truth | `pr_id` | `rule_prs.csv` (`pr_id`, `kind`, `layer`, `note`, `new_rules_json`) and `population.csv`, a held-out set of 1000 attacks and 500 benign cases; exists only because the data is synthetic |

**Retention** is a design choice, not a measurement; confirm it against the bank's record-retention schedule. 🔴 Design default: decision records 7 years in PostgreSQL archived with a retention lock; the rule files and pack a decision used, the same period, in versioned storage.

**Lineage.** A decision traces back in three hops: the record names the pull request and the hashes of the two rule files and the pack; the versioned store returns those bytes; and the matcher is deterministic (no clock, locale or random draw), so re-running `compare` reproduces each regression line, which names the case, its channel and technique, and the rule that used to block it.

**Deliberately not stored.** Live traffic, model output and customer text. A pack holds attack strings and strings shaped like sensitive values; the design keeps real customer data out of it.

---

## 4. Security architecture

**Identity and roles.** The check runs under the CI platform's workload identity with no user account. `ip:runner` reads both rule files and the pack and writes a decision record. `ip:pack-owner` changes the pack, never to pass their own rule change. `ip:approver` approves rule and floor changes. `ip:auditor` reads decisions and config history. `ip:admin` manages roles, buckets and the ledger.

**Secrets.** None. The check calls no model and no gateway, so no key is in its path.

**Data classification and what leaves the boundary.** Rule files describe a bank's defenses; treat them as confidential. In the prototype everything is synthetic and nothing leaves the machine. In the design three things leave the job: the exit code, annotations on the pull request and the ledger write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a case id, rule id or text echoed into a log or annotation | An id holding a newline and text that looks like a workflow command | `escape_annotation` rewrites `%`, carriage return and newline; `clean` writes control characters as escapes and limits length. `tests/test_cli.py` covers an annotation, a log line and an error line |
| The pack is edited to hide a regression | The case that fails is deleted in the same pull request | Pack changes need a different approver; every decision stores the pack hash; the case count prints on the first line of the output |
| A catastrophic pattern in a rule file | A backtracking pattern that hangs the matcher | The design sets a job timeout and a per-pattern limit; the prototype has none |
| Real customer data pasted into the pack | A real account number in a benign case | Pack changes are reviewed with that in mind; the pack is classified as confidential |

---

## 5. Operational architecture

**SLIs.** Decisions per week; regressions per rule change; blind-spot notes per change; share of changed rules that match at least one pack case; techniques with no pack case (prototype: 🟢 1, doc_encoded_blob, `step_04_with_pack.py`); harmless changes stopped (prototype: 🟢 1 of 26, `step_04_with_pack.py`); time to decision.

**SLOs (all 🔴 design targets, none measured).**
- A decision within 60 seconds of a rule pull request opening.
- Every merged rule change passes through the check and leaves a decision record.
- Every BLOCK and every blind-spot note read by a named person within one business day (planning estimate).
- Every attack technique seen in an incident gets a pack case within the next release.

**Alerts.** P2: repeated input rejections, or the ledger down for more than a day. P3: a BLOCK on a protected branch, or a blind-spot note on a rule that guards a high-risk channel (chat). P4: a weekly digest of notes and floor misses.

**Runbooks** (in `docs/runbooks/`): `regression-found.md` (read the case, restore the rule or add a narrower one, re-run); `blind-spot-note.md` (add a case for the technique or record why not); `changing-the-pack.md` (propose, different approver, re-run the planted set); `changing-a-floor.md` (propose, compare with the golden numbers, approve).

**On-call and ownership.** The gateway-rules owner owns the check and runbooks; the pack owner owns the cases; a second-line reviewer approves rule, pack and floor changes. Nobody is paged for a note.

**Change control.** The check, the pack and the floors are versioned in the repo. A change needs a proposer, a different approver and a re-run of the planted set against the pinned numbers in `tests/test_golden.py`, so a change that moves a count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: [OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), read 2026-10-23. It separates direct injection from indirect injection, where external content such as a web page or a file carries instructions, and among its mitigations lists regular adversarial testing and attack simulations and input and output filtering.

- **What the design does.** It replays a fixed set of injection cases against the filter rules as a regression check, on every rule change. That is narrower than the testing the page describes.
- **What it does not claim.** It does not test a live gateway or a classifier. It makes no claim of conformity to the page or to any standard, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Changes the pack cannot see.** 🟢 Four of 25 harmful changes pass: RP-009, RP-021, RP-033 and RP-043, and only 1 of the 4 came with a blind-spot note (`step_04_with_pack.py`). RP-043 removes the rule for an encoded payload and the pack has no case for that technique.
- **A threshold I can defend.** The one-point harm line and the floors in step 3 are my assumptions. 🟢 RP-042 is stopped as a false alarm (`step_04_with_pack.py`).
- **A classifier.** The gateway here is regular expressions, and each case is read by one layer, so layers are not tested as a chain.
- **Other languages.** The rules are English; the three translated documents in the pack are all missed.
- **Layer 3 beyond `destination_keys`**, and any regex timeout.
- **A live endpoint, new attack generation, hosting, a published Action.**

---

## Appendix: sample contract

The call is the prototype's own; the `--demo` output is in the README.

```bash
python3 injection_pack.py compare old_rules.json new_rules.json --pack pack.csv \
    --min-catch 70 --max-fp 15 --fail-on regression --format github
```

Exit status: 0 when the check passes, 1 for a regression or a missed floor, 2 for bad input.
