# Architecture: agent-breaker

> **Status.** This is the design for a production shape. The repo implements the product mechanic as a prototype: a module and command, `src/agent_breaker.py`, that replays a recorded stream of an agent's tool calls through one breaker per agent, trips on a critical failure, a run of failures or a failure rate, holds calls for a person, probes before closing, and writes a hash-chained log that `verify` checks by replay, run here over 7523 synthetic calls from 5 agents. It is a back-test: no live loop, queue or agent is connected. Nothing below is claimed as deployed or load-tested. Where a figure is a design target, it says so.

GCP is primary; AWS and Azure sit beside it.

![agent-breaker flow](./assets/agent-breaker-flow.svg)

---

## 1. Logical architecture

agent-breaker is a state machine between an agent and its tools: a call and its outcome in, a route (agent or person) and a log event out. It reads outcomes and failure kinds, not whether an outcome was right.

Eight components: five decide the outcome, three support or report.

| Component | Responsibility | Language or framework | Decides the outcome? | Stateful? |
| --- | --- | --- | --- | --- |
| `ab-ingest` | Loads events, controls and policy. Rejects empty, truncated, wrong-type or out-of-order input and unknown policy with a one-line message. | Python 3.9+, standard library. Prototype: `load_events`, `load_controls`, `load_policy`, `check_policy` in `src/agent_breaker.py` | Yes, by refusing: exit 2 | No |
| `ab-policy` | The thresholds: window, trip rate, warn and clear fractions, failures in a row, critical kinds, hold, backoff, cap, probes. Changes by review only. | A reviewed config file (design). Prototype: `data/policy.csv`, `PARAMS` | Yes, config | Stateful, in git |
| `ab-breaker` | One breaker per agent, from a data field. Routes each call; trips on critical, failures in a row, then rate; holds; probes; backs off. | Python. Prototype: `Fleet`, `Breaker.admit`, `Breaker.report` | Yes | Yes, per agent (design: shared store) |
| `ab-switch` | Engage forces open; release goes to probes, never to closed. | Python. Prototype: `Breaker.engage`, `Breaker.release`, `Fleet.control` | Yes | Yes |
| `ab-audit` | Hash-chains every policy, call, transition, warn and control; `verify` replays the calls through a fresh breaker. | Python. Prototype: `AuditLog`, `verify_log` | Yes for `verify`: exit 1 | Stateful, append-only |
| `ab-report` | Prints the run and escapes untrusted strings. | Python. Prototype: `report`, `describe`, `safe` | No | No |
| `ab-wrap` | Wraps a live loop: `admit`, `record`, timeouts (design). | A thin library in the agent service (design) | No | No |
| `ab-queue` | Delivers held calls to a review queue with the reason (design). | A managed queue plus a review task (design) | No | Stateful |

Two more pieces are design only and appear in the README diagram: `ab-store`, shared breaker state and log storage across processes, and `ab-telemetry`, off the decision path.

**What decides the outcome.** The input check, policy, breaker, switch and replay. The rest carry or record it. The breaker acts on the outcome the agent reports.

**Repo structure** (production shape):

```
agent-breaker/
├── breaker/    # ingest.py, policy.py, breaker.py, switch.py, audit.py, report.py
├── wrap/       # live-loop wrapper
├── queue/      # human-queue connector
├── policy/     # thresholds per agent, changed by pull request
├── infra/      # terraform for gcp, aws, azure
├── docs/runbooks/
└── tests/      # unit, golden, audit, hostile strings
```

---

## 2. Physical and deployment architecture

The breaker runs inside the service that runs the agent, so a route costs no network hop. The back-test job runs on demand.

| Component | GCP (primary) | AWS | Azure | Why |
| --- | --- | --- | --- | --- |
| Agent service with `ab-wrap` and `ab-breaker` | Cloud Run service | ECS Fargate service | Container Apps | The decision sits on the call path |
| Back-test job | Cloud Run job | Fargate task | Container Apps job | Stateless, replays a history |
| `ab-store` shared state | Memorystore | ElastiCache | Azure Cache for Redis | Replicas must agree on one state per agent |
| `ab-queue` | Pub/Sub plus a review tool | SQS plus a review tool | Service Bus plus a review tool | Held calls must not be dropped |
| Audit log and head hash | Cloud Storage with a retention lock; head stored apart | S3 Object Lock; head apart | Immutable Blob storage; head apart | The writer must not be able to edit the head |

**Failure behavior (the decision that matters most).** The breaker must never silently pass. In the prototype, an input it cannot read ends the run with exit 2 and is never read as "no failures", and a log that does not verify ends with exit 1. In the design, when the breaker cannot read its own state or policy, the call goes to the human queue, not to the agent, and the owner is alerted.

| Failure | Behavior | Alert |
| --- | --- | --- |
| Events, controls or policy missing, empty, truncated, out of time order, with an unknown parameter; `--agent` matches no rows (prototype) | Exit 2, one line naming the file and row; nothing is run | P3 |
| Log fails `verify`: edit, removal, reorder, re-hashed forgery, a call that reached the agent while open, a different policy (prototype) | Exit 1 with up to five problems listed | P2 |
| Log cut at an event boundary, no stored head (prototype) | Not detected without the stored head | P2 in the design |
| State store or policy unavailable (design) | Calls go to the human queue until state is read | P2 |
| A call never returns (design) | `ab-wrap` times it out and records a failure | P3 |
| Queue connector or log store down (design) | Held calls and log events spool locally in order; none is dropped, the gap is alerted | P2 |

**Latency.** The prototype replays 7523 calls in one pass; I have not timed it. 🔴 Design target: a route decision for each call within 50 milliseconds.

---

## 3. Data architecture

| Entity | Key | What it holds | Real columns in the prototype |
| --- | --- | --- | --- |
| Call event | `agent`, `case_id`, `t_min` | Outcome and failure kind | `data/events.csv`: `t_min`, `agent`, `case_id`, `outcome` (ok or fail), `failure_kind` |
| Control | `agent`, `t_min` | Engage or release, who, why | `data/controls.csv`: `t_min`, `agent`, `action`, `by`, `reason` |
| Policy | `parameter` | One value per threshold, and where it came from | `data/policy.csv`: `parameter`, `value`, `unit`, `set_by`, `note`. The module reads `parameter` and `value` |
| Breaker state | `agent` | State, window of recent calls, failures in a row, time opened, hold, good probes | In memory in the prototype (design: `ab-store`) |
| Audit event | `seq` | `t`, `agent`, `kind` (policy, call, transition, warn, control), `data`, `prev`, `hash` | The JSON-lines file from `--log` |
| Planted truth | `fault_id` | The fault planted and the harm per call | `data/faults.csv`, `data/truth_calls.csv`. Exists only because the data is synthetic; the breaker never reads it |

**Retention** is a design choice; confirm it against the bank's own schedule. Audit logs: 🔴 7 years design default, in object storage with a retention lock. Breaker state is rebuilt from the log and is not kept.

**Lineage.** A held call names its state and rule; the transition event carries the evidence (calls in the window, failures, failures in a row, rate); the chain links every event to the one before it; and the replay rebuilds the same states from the calls and the policy.

**Deliberately not stored.** Call payloads, prompts and case content. The breaker needs the case id, the outcome and the failure kind.

---

## 4. Security architecture

**Identity and roles.** The breaker runs under the agent service's workload identity. `ab:runner` calls `admit` and `record`; `ab:operator` engages and releases the switch, with a name and reason on every action; `ab:approver` approves a policy change, never their own; `ab:auditor` reads logs and runs `verify`.

**Secrets.** The breaker holds none and never calls a model, so no vendor key is in its path. State, queue and storage are reached through workload identity, with no static keys.

**Data classification and what leaves the boundary.** Case ids, agent names and operator reasons are internal; treat the log as confidential and confirm against the bank's own policy. In the prototype nothing leaves the machine. In the design held calls, log events and the head hash leave the service.

| Threat | Example | Mitigation in the design |
| --- | --- | --- |
| Hostile string in an agent name, case id, failure kind or reason | A value holding a newline and text that looks like an output line | Each log event is one JSON line; `safe` escapes control characters on the terminal. `tests/test_cli.py` and `tests/test_audit.py` cover hostile values |
| The log is rewritten | A trip deleted and every later line re-hashed | The chain and the replay. 🟢 Of 4 tamper tests, 3 are caught from the log alone and 4 with the stored head (`step_04_with_breaker.py`) |
| The log is cut short | The last events removed | The head hash stored outside the log; the design anchors it by default |
| The switch is misused | Engaged to park work, or released early | Roles; every control logged with name and reason; a release goes to probes |
| A threshold is weakened to avoid a trip | The trip rate raised | Pull request with a different approver; the policy is the log's first event, and `verify --policy` requires a named policy |
| The agent labels its own failure | A scope violation reported as a plain failure | The wrapper takes the failure kind from the tool's response, not from the agent's text (design) |

---

## 5. Operational architecture

**SLIs.** Trips per agent per week; minutes from first failure to trip; held calls per trip; probe failures; calls that reached the agent while open (prototype: 🟢 0, `step_04_with_breaker.py`); log verification result; age of the oldest held call.

**SLOs (all 🔴 design targets, none measured).**
- A route decision within 50 milliseconds.
- 0 calls reach the agent while the breaker is open.
- Every trip read by a named person within 30 minutes (planning estimate).
- 99.9 percent of log events written and every log verified daily.

**Alerts.** P2: a trip on a production agent (page the owner), a switch engaged, a log that fails `verify`, the state store or queue down. P3: a warn, a repeated probe failure, input rejections. P4: a weekly digest of trips and held calls.

**Runbooks** (one page each, in `docs/runbooks/`):
- `breaker-tripped.md`: read the transition evidence, work the queue, hold or probe.
- `engaging-the-switch.md`: who may engage, what to record, how a release goes to probes.
- `log-failed-verify.md`: which problem, which line, whether the head matches.
- `changing-a-threshold.md`: propose, re-run the planted set, compare with the golden numbers, approve.

**On-call and ownership.** The agent owner owns the breaker, wrapper and runbooks; the queue lead owns the queue; the second-line reviewer approves policy changes and reads trips.

**Change control.** The policy is versioned in the repo and is the first event of every log. A change needs a different approver, and the planted set is re-run against `tests/test_golden.py`, so a change that moves the tripped count shows in the diff.

---

## 6. Alignment and posture

Alignment, not certification. The README's "Aligned to" section cites one source, restated with the same wording about what was read: the [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative) (page read 2026-10-24). It sets out three pillars: industry-led standards, community-led open protocols, and research into agent authentication, identity and security evaluation. It names no stop, hold or logging requirement and no threshold.

- **What the design does.** It is a runtime control for an agent and an evidence trail that can be checked. That is alignment in direction only.
- **What it does not claim.** It takes no requirement or threshold from that page. Every value in `data/policy.csv` is my assumption except the warn and clear fractions, copied from project 25. It makes no claim of conformity to that guidance, holds no certification, and I have not read or mapped any other source.

---

## 7. What is deliberately not here

- **Silent errors.** 🟢 33 of the 312 harmful calls were reported ok, and 0 of 2 silent-error faults tripped (`step_04_with_breaker.py`). The breaker reads outcomes, not whether they were right.
- **A slow burn.** A 0.28 failure rate sits under the trip rate: 🟢 0 of 2 tripped and 30 of 30 harmful calls were served (`step_04_with_breaker.py`).
- **A quiet agent.** 🟢 `limit-review` never had more than 8 calls in a 30 minute window and the rate is scored from 10, so 0 of its 2 must-trip faults tripped (`step_04_with_breaker.py`).
- **Long blips.** 🟢 2 of 7 must-not-trip faults tripped, the two that fail 5 or 6 times in a row; a count cannot tell them from an outage (`step_04_with_breaker.py`).
- **A fitted trip rate.** I set 0.5 before looking at the stream; moving it now would be tuning to my own data.
- **A signature on the log.** The chain proves consistency, not authorship; a cut tail passes unless the head hash is kept elsewhere.
- **A live run.** As shipped it is a back-test; one call in flight per agent. Timeouts, a live loop and cross-process state are not built.
- **Real traffic.** The planted set and the rules share an author, so the numbers are a ceiling.

---

## Appendix: sample contract

The call is the prototype's own; the `--demo` output is under "Run one now" in the README.

```bash
python3 agent_breaker.py run events.csv --controls controls.csv --policy policy.csv --log audit.jsonl
python3 agent_breaker.py verify audit.jsonl --head <hash stored elsewhere>
```

Events need `t_min`, `agent`, `case_id`, `outcome` and `failure_kind`; controls need `t_min`, `agent`, `action`, `by` and `reason`. Exit status: 0 when nothing tripped (run) or the log checks out (verify), 1 when the breaker tripped (run) or the log does not check out, 2 for input that cannot be read.
