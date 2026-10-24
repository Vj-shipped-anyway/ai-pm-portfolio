# PRD: ATLAS case-study drafter

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a security and incident-review forum. It is not a record of a PRD landed at a named bank. The rules, the planted runs and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and nothing has been submitted to any catalog.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ATLAS case-study drafter: a command-line tool that reads the trace of one agent run and drafts a case study in the shape the MITRE ATLAS contribution schema describes, with call numbers behind each step |
| **Owner** | The program owner for agent incidents, with a privacy or legal reviewer as co-owner of what may leave the firm |
| **Stage** | Portfolio prototype on synthetic data; nothing submitted |
| **Primary user** | An engineer or program owner who has a trace of an agent failure, permission to share it, and wants a first draft to edit before offering it to the MITRE ATLAS maintainers |
| **Secondary users** | The on-call engineer who writes the ticket; the security analyst who reviews the draft; the privacy reviewer who reads it before it goes anywhere |
| **Problem** | An agent run goes wrong and an on-call engineer writes a ticket. The trace holds what happened, the ticket holds what someone thought, and neither is in a form a public threat catalog can use. Writing the case study by hand is slow, and a draft written from the ticket copies identifiers and names into a public place. In the planted set, 🟢 0 of 60 flagged runs have a case study and 45 of 60 tickets carry an identifier or a first name (`step_01_trace_as_report.py`). |
| **Solution** | Splits the calls of one run into phases of the same tool and argument shape and finds loops. Writes procedure steps with a tactic, a technique and the call numbers behind each: a denial-of-service step for each loop, plus an injection step and a cost step where the trace shows them. Redacts declared identifiers and never copies the ticket note. Lints the draft against the rules of the ATLAS contribution schema and says which fields a person still owes. |
| **North-star metric** | Share of flagged failure runs worth a case study that end up with a reviewed draft and no leaked identifier. Target 🔴 100%. Today in this model: no flagged run has a case study. |
| **Measured metrics (synthetic)** | 🟢 22 of 32 failures drafted; 0 of 28 harmless runs drafted; 22 of 22 technique sets equal to the planted set; 0 of 22 drafts with an identifier or planted string; the known miss named (10 of 32 failures get no draft) (`step_04_with_case_study_tool.py`). |
| **Modeled metrics** | 🟡 Utility (22/32 − 15/32) × 20 = 4.4 more failures a year with a draft than the ticket-words draft gives, assuming 20 failures a year are worth a case study and arrive with a trace. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted set and the rules share an author, so the numbers are a ceiling, not a rate on real traces. Mitigation: run it on one real trace its owner is allowed to share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The 20-call threshold is an assumption and a trade. 🟢 At 10 calls the rule drafts 27 of 32 failures and also 5 of 28 harmless runs; at 20 calls it drafts 22 of 32 and 0 of 28 (`step_03_deficiencies_exposed.py`). Mitigation: calibrate the line on real traces, and keep the draft a first draft that a person reads. |
| **Risk #3** | A synthetic run is not an incident, and the maintainers decide whether a failure with no adversary is in scope. A draft that leaves the firm could also carry an identifier the bundle did not declare. Mitigation: the staged issue asks the scope question first, nothing is submitted by the tool, and a privacy reviewer reads the draft before it leaves. |
| **Out of scope** | Reading ticket text; deciding whether an adversary was involved; submitting anything; techniques other than the three; full JSON Schema validation; any model call. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is flagged runs unless labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Identifier redaction** (declared identifiers replaced, long digit runs scrubbed, the ticket note never copied) | 60 runs | 3 | 0.9 | 1 | 162.0 | Built in prototype |
| 2 | **Bundle validation** (empty, truncated, wrong-type or unreadable input exits 2, never a traceback) | 60 runs | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 3 | **Draft output** (YAML and JSON, call numbers in an evidence block, actor, reporter and references left TODO) | 60 runs | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 4 | **Loop rule** (phases of the same tool and argument shape, 20 or more calls, 0.9 or more not ok) | 60 runs | 3 | 0.8 | 2 | 72.0 | Built in prototype |
| 5 | **Technique mapping** (denial of service per loop, injection on a flagged response, cost at the cap) | 60 runs | 3 | 0.8 | 2 | 72.0 | Built in prototype |
| 6 | **Lint** (the contribution schema rules I read, plus a leak check against the bundle) | 60 runs | 2 | 0.8 | 2 | 48.0 | Built in prototype |
| 7 | **Review and sign-off step** (a person completes the TODO fields, privacy and security approve) | 60 runs | 3 | 0.6 | 3 | 36.0 | Sequenced for v0.2 |
| 8 | **Threshold calibration on real traces** | 60 runs | 2 | 0.5 | 2 | 30.0 | Sequenced for v0.2 |
| 9 | **Draft record** (bundle hash, rules version, who approved what) | 60 runs | 2 | 0.6 | 3 | 24.0 | Sequenced for v0.3 |
| 10 | **Trace export from the tracing store** into the bundle shape | 60 runs | 3 | 0.5 | 4 | 22.5 | Sequenced for v0.2 |
| 11 | **Cycle rule** for tools called in turn (the alternating loop) | 10 runs | 2 | 0.6 | 2 | 6.0 | Queued |
| 12 | **More techniques** (a poisoned record needs more than a trace shows) | 10 runs | 2 | 0.3 | 4 | 1.5 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from the drafter | What they fear |
| --- | --- | --- | --- |
| **Agent program owner** | Owner | A first draft that cuts the time to explain an incident, with the evidence behind each step. | A draft that overstates what the trace shows, such as naming an adversary. |
| **On-call engineer** | Consulted | Not having to turn a ticket into a public format by hand. | Being asked to read a trace row by row for a write-up. |
| **Security analyst** | Reviewer | Steps that cite call numbers so the claim can be checked against the trace. | A mapping to a technique that the trace does not support. |
| **Privacy or legal reviewer** | Approver | A guarantee, or a clear failure, on identifiers and names reaching a public place. | A name or an identifier in a draft that leaves the firm. |
| **Customer-facing owner** | Informed | No customer detail in anything shared. | A customer learning of an incident from a public catalog. |
| **Catalog maintainers (MITRE ATLAS)** | External, not engaged | A scope question asked before a case study arrives. | Receiving a failure write-up with no adversary that does not fit the catalog. |
| **Internal audit** | Reader | A path from a draft to the bundle and rules version that produced it. | A draft edited after approval with no record. |

---

## User stories (top 4)

1. **As an agent program owner**, I want a draft built from the trace, so I do not copy words from a ticket that carries names.
2. **As a privacy reviewer**, I want the tool to fail, and name the field, when a declared identifier appears in a draft, so a leak is a stop and not a surprise.
3. **As a security analyst**, I want each procedure step to cite the call numbers behind it, so I can check the claim against the trace in a minute.
4. **As a program owner**, I want the scope question asked of the maintainers before any real case is offered, so I do not send something that cannot fit.

---

## KPIs

**North star:** share of flagged failure runs worth a case study that end up with a reviewed draft and no leaked identifier. Target 🔴 100%.

**Inputs (leading):**
- Flagged runs with the call order, `response_kind` and `response_flag` recorded (the prototype set has 🟢 3591 calls over 60 runs, from `data/README.md`; target: every run).
- Bundles that declare their identifier fields in `identifier_keys` (target: every bundle).
- Tickets that carry an identifier or a first name, a measure of how risky a ticket-based draft is (prototype: 🟢 45 of 60, `step_01_trace_as_report.py`).
- Drafts with a named reviewer for the actor, reporter and references fields (target: every draft).

**Outputs (lagging):** prototype baselines from the planted set.
- Failures drafted. 🟢 22 of 32 with the trace, against 15 of 32 from the ticket's words (`step_04_with_case_study_tool.py`, `step_02_ticket_keywords.py`).
- Harmless runs drafted. 🟢 0 of 28 with the trace, against 19 of 28 from the ticket's words (`step_04_with_case_study_tool.py`, `step_02_ticket_keywords.py`).
- Technique sets equal to the planted set. 🟢 22 of 22 (`step_04_with_case_study_tool.py`).
- Schema problems and leaks. 🟢 0 schema problems, and 0 of 22 drafts with a declared identifier (`step_04_with_case_study_tool.py`).
- Steps pointing at a call. 🟢 51 steps in all, each with its call position, against 0 of 43 from the ticket's words (`step_04_with_case_study_tool.py`, `step_02_ticket_keywords.py`).
- Known miss. 🟢 10 of 32 failures get no draft (`step_04_with_case_study_tool.py`).
- Drafts the maintainers would accept: not measured; nothing has been submitted.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Export traces of past flagged runs into the bundle shape. Run `build` and compare with what the on-call engineer wrote. Submit nothing. |
| 1: Calibration | 4w | Read the loops it finds and misses. Set the 20-call line and the 0.9 share against real traffic. Declare the identifier fields for each tracing store. |
| 2: Internal use | 6w | Drafts feed internal incident reviews. A person fills the actor, reporter and references. `lint` runs with `--bundle` on every draft. |
| 3: Review path | 6w | Privacy and security sign-off before anything leaves the firm. Record the bundle hash and who approved. |
| 4: Outside contact | 8w | Ask the maintainers the scope question. Offer one real case only if they say a failure with no adversary fits. |

---

## Open questions

1. **Is a failure with no confirmed adversary in scope for the catalog?** The trace shows effects, not an actor. Recommendation: ask the maintainers before writing more, and until they answer, use the drafts internally only.
2. **Where should the loop threshold come from?** The 20-call line and the 0.9 share are my assumptions. Recommendation: start there, then set them against real traces, knowing the line is a trade between missed failures and harmless runs drafted.
3. **Who signs off on sharing?** Recommendation: a privacy or legal reviewer and a security reviewer, neither the author of the draft, with the contribution terms in `CONTRIBUTING.md` read first.
4. **Which fields should stay TODO?** The trace never shows an actor, a reporter or references. Recommendation: leave all three TODO and let `lint --strict` fail while any is left.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process after the incident.** The drafter is stateless: it reads a bundle and returns a draft, a lint result and an exit code. Production adds a trace export, a review step and a draft record, all designed and none built.
- **Never silent.** A missing, empty, malformed or wrongly shaped bundle exits 2. A trace with no loop prints that it made no draft and exits 1; it never writes an empty case study.
- **Names stay out.** The ticket note is never an input, declared identifiers are redacted, and `lint --bundle` fails when one is still present.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the drafted count shows in the diff.

**What is next.** Run it on one real trace its owner can share; ask the maintainers about scope; add a cycle rule for tools called in turn.

**What would have to be true before a pilot.**
- The tracing store records the call order, `response_kind` and, if a scanner exists, `response_flag`.
- The identifier fields are declared for that store.
- A privacy reviewer and a security reviewer are named and read every draft before it leaves.
- One real trace can be shared, so the threshold is set against real traffic and not mine.
- The team accepts that a draft maps effects and does not name an adversary.

---

*This PRD names [05 AgentWatch](../05-agentwatch-agent-observability/), [06 PromptShield](../06-promptshield-prompt-injection-defense/) and [19 IncidentLedger](../19-incidentledger-ai-incident-response/) as designed interlocks (🔴 designed, none built). The trace shape follows 05; no row is copied from it and this folder does not read its files.*
