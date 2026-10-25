# PRD · IncidentLedger — AI Incident Response with the Notification Clock Running

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype — designed for an incident-response read in a real engagement
**Date:** 2026-Q4

> **Framing:** This PRD is the product I'd bring to an AI risk and operations review in the seat. It is not a record of a PRD landed at a named bank. The rubric, the clock vocabulary, the architecture and the rollout plan are mine; the numbers are measured on synthetic data I generated or modeled with the assumption named; the production validation is what the next role does. Notification hours and rubric thresholds are assumptions of a modeled bank, not legal advice. RICE scores and rollout durations below are planning estimates (🔴), not measurements.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | IncidentLedger — AI incident response with the notification clock running |
| **Owner** | AI incident manager (line-1), with compliance and counsel as co-owners of the policy file |
| **Stage** | Portfolio prototype; incident-response read |
| **Primary user** | AI incident manager, who owns the response from ticket to closed follow-up |
| **Secondary users** | Executive on call; regulatory liaison; model or product owner; model risk reviewer |
| **Problem** | AI incidents sit in a ticket queue. The reporter picks the priority, the category is free text, nobody tracks the notification deadlines, follow-up actions close without evidence and related tickets are not linked. In the synthetic data, 🟢 39 of 87 notification deadlines are missed and the queue shows 0; 🟢 30 of 65 truly S1 or S2 tickets were filed P3 or P4. |
| **Solution** | An incident layer on the queue: a classifier (fields first, keywords second, 'needs a person' when unsure), a severity rubric (S1 to S4 from five fields), a clock engine (policy hours from determination, hours left or breached), a follow-up tracker (overdue, or closed with no evidence) and a linker (same system and change id, else same category inside a week). |
| **North-star metric** | Share of in-scope notification deadlines met on time or still running. Target 🔴 100%. Today in this model: 🟢 34 of 87 on time (39.1%) plus 6 running. |
| **Measured metrics (synthetic)** | 🟢 39 of 39 missed deadlines flagged (by construction); 🟢 110 of 120 categories right; 🟢 120 of 120 severities match the truth file (by construction); 🟢 35 of 42 repeat tickets linked. |
| **Modeled metrics** | 🟡 Utility about 19.5 missed deadlines avoided a quarter, assuming 60 AI incidents a quarter and that every countdown is acted on. |
| **Cost** | 🔴 Not estimated. The prototype runs in seconds on a laptop; production cost depends on incident volume and the notification channels and has not been sized. |
| **Risk #1** | Determination is delayed or never recorded, so the clock never starts. 🟢 5 incidents have none at the read date and 8 deadlines have not started. Mitigation: a named person must decide within a set time, and the tool shows hours since detection while it waits. |
| **Risk #2** | The policy hours are wrong or out of date, which gives false comfort. Mitigation: hours live in a versioned policy file that counsel signs off, and every clock shows its hours and its basis. |
| **Risk #3** | The classifier is wrong with no flag. 🟢 5 of 120 categories are wrong with no flag (for example, an injection that exposes personal data is filed as data exposure). Mitigation: clocks run on rubric fields, not on category; a person reviews every S1 and S2 category. |
| **Out of scope** | Runtime detection (AgentWatch, 05); the human review workflow (OversightOps, 08); AI decision records (LineageLog, 09); change control (SchemaWatch, 15; SwapBrief, 13); mapping obligations to controls (ControlMap, 16); the fallback itself (KillSwitch, 25); sending the notices, which stay with people. |

---

## RICE-prioritized backlog (sequenced for v0.x)

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is incidents per quarter (the modeled 60) or roles, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Severity rubric and category classifier (S1 to S4 from five fields)** | 60 incidents | 3 | 0.9 | 3 | 54.0 | Built in prototype; v0.1 |
| 2 | **Clock engine (policy file, determination time, hours left or breached)** | 60 incidents | 3 | 0.9 | 3 | 54.0 | Built in prototype; v0.1 |
| 3 | **Incident intake (replace the free-text category and the reporter's priority)** | 60 incidents | 3 | 0.8 | 4 | 36.0 | Sequenced for v0.1 |
| 4 | **Follow-up tracker (evidence required at closure)** | 60 incidents | 2 | 0.8 | 3 | 32.0 | Built in prototype; v0.2 |
| 5 | **Linking by change id and category window** | 60 incidents | 2 | 0.7 | 3 | 28.0 | Built in prototype; v0.2 |
| 6 | **Countdown warnings to the incident manager** | 3 roles | 3 | 0.9 | 3 | 2.7 | Sequenced for v0.2 |
| 7 | **Determination prompt: ask a named person to decide within a set time** | 60 incidents | 3 | 0.5 | 2 | 45.0 | Sequenced for v0.2 |
| 8 | **Policy editor with counsel sign-off and change history** | 2 reviewers | 2 | 0.9 | 4 | 0.9 | Sequenced for v0.3 |
| 9 | **Evidence record to the model-risk file (LineageLog interlock)** | 2 reviewers | 2 | 0.8 | 3 | 1.1 | Sequenced for v0.3 |
| 10 | **Detection feed (AgentWatch interlock sets detected_at)** | 60 incidents | 2 | 0.6 | 4 | 18.0 | Queued |
| 11 | **Change-id feed (SchemaWatch and SwapBrief interlocks)** | 60 incidents | 2 | 0.6 | 3 | 24.0 | Queued |
| 12 | **Fallback trigger for S1 (KillSwitch interlock)** | 60 incidents | 2 | 0.4 | 5 | 9.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from IncidentLedger | What they fear |
| --- | --- | --- | --- |
| **AI incident manager** (line-1) | Owner | To know how severe an incident is on facts, which notices are owed and how many hours are left, without keeping a spreadsheet. | A tool that adds a form and does not change the outcome; being blamed for a clock that started late because no one decided. |
| **Executive on call** | Consumer of the notice | A clear message inside the window with the severity and the facts. | Hearing about an S1 from a regulator or a customer first. |
| **Regulatory liaison** | Co-owner of the policy file | Deadlines that match the bank's reading of its obligations, with the basis shown. | A tool that states a deadline as law when it is an assumption. |
| **Model or product owner** | Consulted | The incident, its linked tickets and its change id in one place; follow-ups with a due date. | Follow-ups assigned with no context; every ticket treated as a crisis. |
| **Model risk reviewer** (line-2) | Auditor | A record of what was rated, when it was determined, what was sent and when, and which actions have evidence. | A parallel record that competes with the model inventory; a classifier presented as a guarantee. |
| **Counsel and compliance** | Approver of the policy file | Every deadline versioned, with a named approver and an effective date. | Hours changed by an engineer without sign-off. |
| **Security / CISO** | Approver | Incident text and personal data handled under least privilege; no customer values copied into a second store. | Another store of sensitive descriptions. |
| **Customer communications** | Consulted | Early sight of any incident that will need a customer notice, with the number of customers. | A customer notice drafted in a hurry from a ticket title. |

---

## User stories (top 4)

1. **As an AI incident manager**, I want every incident rated by rubric and every notification clock running with hours left, so I know which notices are owed and which are about to be missed without building a spreadsheet.
2. **As an executive on call**, I want a countdown before a deadline passes, with the severity and the reason, so I am not the last to know.
3. **As a regulatory liaison**, I want each clock to show its hours, its anchor and its basis in a policy file counsel has signed, so I can defend the number and change it in one place.
4. **As a model risk reviewer**, I want the rating, the determination time, the notices sent and the follow-up evidence in one record, so ongoing monitoring (SR 26-2) and incident response (the NIST AI RMF 'Manage' function), the themes this work is written against, are documented per incident and not rebuilt from tickets afterwards.

---

## KPIs

**North star:** share of in-scope notification deadlines met on time or still running. Target 🔴 100%.

**Inputs (leading):**
- Incidents with a determination recorded (target: every incident rated S1 or S2 within a set time of detection). Prototype: 🟢 5 of 120 have none.
- Incidents classified without a flag (target: every S1 and S2 category read by a person). Prototype: 🟢 110 of 120 right.
- Countdown acknowledgements (target: every clock with a named person who saw it).
- Policy file changes with a named approver (target: 100%).

**Outputs (lagging):**
- Notification deadlines missed. Prototype: 🟢 39 of 87 (44.8%) in the queue; the engine flags 39 of 39.
- S1 and S2 incidents filed as P3 or P4 (the gap between the reporter and the rubric). Prototype: 🟢 30 of 65.
- Follow-up actions overdue or closed with no evidence. Prototype: 🟢 84 of 200.
- Repeat tickets for a known root cause. Prototype: 🟢 42 of 120 tickets are repeats; 35 of 42 are linked.
- Deadlines that would be missed under the other anchor. Prototype: 🟢 65 from detection against 39 from determination.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0 — Shadow | 4w | Read the existing queue. Compute rubric severity and clocks for each ticket; show nothing to the manager. Compare against what was actually sent. |
| 1 — Rubric and classifier | 4w | Rubric and category shown beside the reporter's priority on new tickets. A person confirms each S1 and S2. |
| 2 — Clocks, advisory | 6w | Countdowns to the incident manager for S1 and S2. Policy file signed by counsel. Determination prompt live. |
| 3 — Required for S1 and S2 | 6w | Follow-ups need an evidence link to close. Missed deadlines go into the weekly risk report. |
| 4 — Estate and interlocks | 8w | All severities; detection feed from AgentWatch; change ids from SchemaWatch and SwapBrief; evidence record to the model-risk file. |

---

## Open questions

1. **Who records the determination, and by when?** The clock starts there. Recommendation: a named role, with a maximum time from detection that shows as its own countdown. 🟢 Anchoring at detection instead gives 65 missed deadlines against 39, so the choice is policy, not arithmetic.
2. **Whose hours are in the policy file?** The values here are assumed. Recommendation: counsel and the regulatory liaison own the file, with an effective date on each row.
3. **What counts as evidence for closing a follow-up?** Recommendation: a link to a change, a test result or a signed review, checked for existence at closure and sampled by line-2.
4. **Does IncidentLedger send notices?** Recommendation: no. It shows the countdown and records what was sent; people send.
5. **How many labeled tickets are enough to trust the classifier?** The prototype scores 120 synthetic tickets. Recommendation: label a quarter of real tickets in the first phase and measure before trusting any flag.

---

## Build & scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Intake and classifier:** an API behind the existing incident system; a typed form replaces the free-text category and the reporter's priority.
- **Rubric and clock engine:** stateless workers reading the policy file as versioned configuration, with a scheduler that evaluates open clocks on an interval.
- **Tracker and linker:** follow-ups with a required evidence link at closure; tickets grouped by system and change id.
- **Storage:** Postgres for incidents, clocks, notices and actions; object storage with retention for the evidence record.

**Throughput envelope and latency budget.**
- The prototype evaluates 120 incidents and 87 clocks with a plain Python loop. Production volumes have not been sized.
- Countdown latency: 🔴 design target is a warning inside one evaluation interval of the threshold. Not built, not timed.

**Failure modes and degradation strategy.**
- Policy file unavailable: the engine uses the last signed version and flags it as stale.
- Determination missing: the clock shows 'not started' with hours since detection, and a prompt goes to the named role.
- Classifier unsure (tie or no keyword): 'needs a person', never a guess.
- Notification channel down: the breach flag is also written to the record, and the incident manager sees it on the console.

**Migration path from current state.**
- If the bank keeps a deadline spreadsheet: keep it during phase 0 and compare. The first test is whether the engine's list matches it.
- If tickets have no determination field: add it first. Without it nothing else can start.

**Org dependencies.**
- Counsel and compliance must own and sign the policy file. Without that the clocks are assumptions.
- A named role must record the determination. Without that the clock does not start.
- The model-risk team must accept the evidence record as part of its file.

---

*This PRD names interlocks with [Project 05 (AgentWatch)](../05-agentwatch-agent-observability/), [Project 08 (OversightOps)](../08-oversightops-hitl-workflow/), [Project 09 (LineageLog)](../09-lineagelog-ai-decision-audit/), [Project 13 (SwapBrief)](../13-swapbrief-model-migration/) and [Project 15 (SchemaWatch)](../15-schemawatch-tool-schema-drift/), [Project 16 (ControlMap)](../16-controlmap-ai-obligation-crosswalk/) and [Project 25 (KillSwitch)](../25-killswitch-ai-fallback-drills/). All seven are 🔴 designed, none built.*
