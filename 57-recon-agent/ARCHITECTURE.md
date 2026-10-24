# Architecture: recon-agent

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: `src/recon_agent.py` matches a bank statement to a cash book with five rules, re-runs each rule on the cited lines, applies an approval gate and lists every open line, over one synthetic month of 383 bank lines and 438 book lines. There is no model call, and the approver is a script. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![recon-agent flow](./assets/recon-agent-flow.svg)

---

## 1. Logical architecture

recon-agent is a batch step between two ledger exports and a posting decision: two files and an approvals file in, a match list and an open list out. It does not post, call a model or convert a currency.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `rc-ingest` | Loads both ledgers, the approvals and a finished match list. Rejects bad input with a one-line message. | Python 3.9+, standard library. Prototype: `load_ledger`, `load_approvals`, `load_matches`, `InputError` | Yes, by refusing: exit 2 | No |
| `rc-policy` | Window, fee schedule, approval limit, largest batch, and which rule may post alone. Changes only by review. | A reviewed config file (design). Prototype: `Params`, `GATE_POLICY` | Yes, config | Stateful, in git |
| `rc-propose` | Runs the five rules in order over free lines, nearest dates first; parks a bank line two book lines fit equally. | Python. Prototype: `propose`, `_find`, `_select` | Yes | No |
| `rc-check` | Re-runs the rule on the cited lines, builds the evidence text, and does the same on a finished list. | Python. Prototype: `rule_problems`, `evidence_lines`, `verify_matches` | Yes, by blocking or exit 1 | No |
| `rc-gate` | Decides post alone or wait; binds an approval to the exact proposal key; refuses self, stale and conflicting records. | Python. Prototype: `gate_for`, `make_key`, `apply_gate` | Yes | No |
| `rc-report` | Gives every unposted line a reason; prints the report; writes `matches.csv` and `unmatched.csv`; escapes untrusted strings. | Python. Prototype: `_open_items`, `render`, `write_outputs`, `clean`, `csv_safe` | No | No |
| `rc-queue` | Shows a reviewer the cited lines and records the decision under their identity (design). | Small web service (design). Prototype: `data/example_approvals.csv` | No, it carries the human decision | Stateful |
| `rc-ledger` | One record per match and approval (design). Prototype: `src/out/step_04_matches.csv`. | PostgreSQL, object storage with retention lock (design) | No | Stateful |

**What decides the outcome.** The input check, the policy, the ladder, the re-check and the gate. The report, the queue and the ledger carry or record it. An approval has weight only because the gate ties it to one proposal key, such as `ref_fee:BK-000002:GL-000002:499850`. The tool trusts the exports as written.

**Repo structure** (production shape):

```
recon-agent/
├── recon/      # ingest.py, propose.py, check.py, gate.py, report.py
├── policy/     # window, fees, limit, gate table; changed by pull request
├── queue/      # approver service
├── ledger/     # decision record writer
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, hostile strings
```

---

## 2. Physical and deployment architecture

One short-lived batch job runs after both exports land at month end. There is no server to keep warm.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Batch job (`rc-ingest` to `rc-report`) | Cloud Run job | ECS Fargate task | Container Apps job | Stateless, one pass over files |
| Exports and outputs | Cloud Storage, versioned | S3, versioned | Blob Storage, versioned | Keeps the exact bytes a decision used |
| `rc-queue` | Cloud Run service behind the identity proxy | Fargate service behind a load balancer | Container Apps with the identity provider | Reviewers sign in |
| `rc-ledger` | Cloud SQL for PostgreSQL | RDS for PostgreSQL | Azure Database for PostgreSQL | The platform team already runs it |

**Failure behavior (the decision that matters most).** The tool must never silently pass. A missing or malformed input does not become an empty result: it ends the run with exit 2 and a one-line reason naming the file and row. A line no rule can place is not dropped; it is in the open list with a reason. A posted match that no longer re-checks makes `verify` exit 1.

| Failure | Behavior | Alert |
| --- | --- | --- |
| A file missing, empty, header only, not UTF-8, a column missing; or a truncated row, bad date, non-numeric amount, bad currency, duplicate id, or a decision other than approve or reject | Exit 2, one line naming the file or row | P2 if repeated at one close, else P3 |
| An approval for a proposal that no longer exists, by the agent, or approve and reject on one proposal | Record refused with a reason, match stays pending, run goes on | P4 digest |
| A proposal fails its own re-check | Match blocked, lines go to the open list as `failed_check` | P3 |
| No match at all | The report says so; the open list holds every line | P4 |
| Queue or ledger down (design) | Held matches stay pending; no approval is assumed | P3 |

**Latency.** I have not timed the prototype, and I ran it on about 800 lines. 🔴 Design target: a run finished within 10 minutes of both exports landing, excluding reviewer time. Recovery is a re-run from the same versioned files.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Bank line | `a_id` | Date, signed amount, currency, counterparty, reference | `data/ledger_a.csv`: `a_id`, `value_date`, `amount`, `currency`, `counterparty`, `narrative`, `customer_ref` |
| Book line | `b_id` | The same, plus an explicit batch id | `data/ledger_b.csv`: `b_id`, `posting_date`, `amount`, `currency`, `counterparty`, `reference`, `batch_id`, `memo` |
| Approval | `key` | One decision on one proposal, and who | `key`, `decision`, `approver`, `note` |
| Match | `match_id`, `key` | Rule, status, gate, ids, amount, evidence, approver | `src/out/step_04_matches.csv` |
| Open line | ledger and id | Reason and detail for a line not posted | `src/out/step_04_unmatched.csv` |
| Planted truth | `link_id` | Kind and match status; synthetic data only | `data/truth.csv`: `link_id`, `kind`, `truth_status`, `a_ids`, `b_ids` |

**Retention** is a design choice, not a measurement; confirm it against the bank's own record-retention schedule. 🔴 Design default: match and approval records for 7 years, in PostgreSQL archived to object storage with a retention lock, and the exports a decision used kept as long, versioned, so it can be reproduced.

**Lineage.** A posted match traces back in three hops: the record names the rule, the cited ids, the approver and the hashes of both exports; the versioned store returns those bytes; and the rules are deterministic, so `verify` re-runs them on the cited lines and reproduces the evidence text or says what changed. In the prototype the trace is a row of `step_04_matches.csv`.

**Deliberately not stored.** Account numbers and customer detail beyond what the output needs. The rules do not match on the narrative or memo.

---

## 4. Security architecture

**Identity and roles.** The batch job runs under the platform's workload identity and has no account of its own. Reviewers sign in to the queue.

| Role | Can | Maps to |
| --- | --- | --- |
| `rc:runner` | Read the exports and policy; write matches and the open list | The batch job identity |
| `rc:approver` | Approve or reject a held match; cannot approve a policy change | Reviewer in finance operations |
| `rc:policy-owner` | Approve a change to the window, fees, limit or gate table | Finance controller |
| `rc:auditor` | Read matches, approvals and config history | Internal audit |

**Secrets.** The tool holds none, never calls a model and has no credential for the ledger system. The job uses workload identity, with no static keys.

**Data classification and what leaves the boundary.** Bank lines, book lines, counterparty names and references are confidential financial data. In the prototype nothing leaves the machine. In the design three things leave the job: the match list for posting under the ledger system's own controls, the open list, and the record write.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in a counterparty, reference or approver echoed into a report or CSV | A name holding a newline, or starting with `=` | `clean` writes control characters as visible escapes; `csv_safe` adds a leading apostrophe; `tests/test_cli.py` covers both |
| The agent approves its own match | An approval record by `recon-agent`, in any spelling | `apply_gate` refuses it. 🟢 Refused 101 of 101 times, 0 posted (`step_04_with_gate.py`) |
| A finished list is edited after approval | A line swapped, an approval relabelled, a match copied | `verify_matches` re-runs the rules. 🟢 Caught 299 of 299, 93 of 93 and 311 of 311 (`step_04_with_gate.py`) |
| The policy is changed to make a held match post | The limit raised | Pull request, the controller approves; records store the policy version |
| The approver reads the reference and not the invoice | A reviewer approves a look-alike | The tool cannot see this. The design shows the invoice with the proposal and counts approvals overturned |

---

## 5. Operational architecture

**SLIs.** Matches per rule; share posted alone; held matches and their age; approvals refused; posted matches that fail `verify`; open lines by reason; time to report. Prototype baseline: 🟢 169 open lines, each with a reason (`step_04_with_gate.py`).

**SLOs (all 🔴 design targets, none measured).**
- A month-end run finished within 10 minutes of both exports landing, excluding reviewer time.
- Every held match read by a named person within one business day (planning estimate).
- No posted match that fails `verify` at close.
- 99.9 percent of match and approval records written to the ledger.

**Alerts.** P2: repeated input rejections at one close, or the ledger down for more than a day (low-urgency page). P3: a posted match that fails `verify`, or a proposal that fails its own re-check (chat). P4: a daily digest of refused approvals and open lines (email).

**Runbooks** (one page each, in `docs/runbooks/`):
- `input-rejected.md`: read the reason, fix the export, re-run.
- `held-matches.md`: how to read a proposal and when to reject.
- `verify-failed.md`: find which cited line changed, record the cause.
- `changing-the-policy.md`: propose, re-run the planted month, compare, approve.

**On-call and ownership.** The finance operations lead owns the job, queue and runbooks; the controller owns the policy and limit; platform engineering owns infrastructure. Nobody is paged for a held match.

**Change control.** Rules and policy are versioned. A change needs a proposer and a different approver. Before merge the planted month is re-run against the pinned numbers in `tests/test_golden.py`, so a change that moves the posted or wrong count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites no standard, regulation or published control: I have not mapped this tool to any, so I claim no alignment. It names one borrowed pattern from [27 AgentKit](../27-agentkit-reference-agent-and-playbook/): a person-held gate, a scripted stand-in for the person, and no approval from the agent itself. I copied no code from that folder.

- **What the design does.** A person approves every match except the narrowest rule, the record says who, and a reader can re-check a finished list against the ledgers.
- **What it does not claim.** It is not compliant with any standard, holds no certification, and I have read and mapped no source. Reviewer behavior is hypothetical; I have not tested a real reviewer.

---

## 7. What is deliberately not here

- **True matches the rules cannot reach.** 🟢 18 true matches never get a proposal: no_ref_abbrev 4, out_of_window 6, ref_garbled 4 and split_no_batch 4 (`step_03_deficiencies_exposed.py`). They sit in the open list with a reason.
- **A careful approver.** The gate records who approved; it does not make anyone careful. 🟢 The scripted approver approved all 21 `ref_near` proposals; 6 were distinct invoices (`step_04_with_gate.py`).
- **Amount tolerance and currency conversion.** Amounts must match to the cent. A currency clash stays open.
- **A fee beyond the schedule I gave it, or a name abbreviation the table lacks.** The table knows three; the generator uses four.
- **A subset-sum search for splits with no batch id.** Those deposits stay open.
- **A model.** The proposer is a rule ladder. If a model proposed matches, I would keep the check and the gate; I have not tested that.
- **Thresholds tuned on real ledgers.** The window, fees, limit and gate table are assumptions; the planted month and the rules share an author.
- **Posting, hosting, an approver interface.** The queue is a design; posting stays with the ledger system's controls.

---

## Appendix: sample contract

```bash
python3 recon_agent.py reconcile bank.csv book.csv --approvals approvals.csv --out out/
python3 recon_agent.py verify bank.csv book.csv out/matches.csv
```

```csv
key,decision,approver,note
ref_fee:BK-000002:GL-000002:499850,approve,reviewer-1,remittance advice shows a 1.50 fee
```

Exit status: 0 when the command ran (`verify`: every posted match re-checks), 1 when `verify` finds a problem or `--fail-on-open` finds an open line, 2 for bad input. The `--demo` output is under "Run one now" in the README.
