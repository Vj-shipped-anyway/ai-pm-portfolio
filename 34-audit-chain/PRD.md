# PRD: audit-chain (hash-chained log)

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an agent-governance review. It is not a record of a PRD landed at a named bank. The event layout is taken from project 27; the checks, the planted edits and the rollout plan are mine. Numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | audit-chain: an append-only JSON-lines log for agent actions in which each event carries the hash of the one before it, with a `verify` command, an `anchor` command and an `append` command |
| **Owner** | The engineer who owns the agent's logging, with a security reviewer as co-owner of where the anchor is kept |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | The engineer who owns an agent's logging |
| **Secondary users** | The reviewer or auditor who has to rely on the log afterwards; the security reviewer; the platform team that hosts the storage |
| **Problem** | An agent acts on cases, and the only record of what it did is a file its own operators can edit. A reviewer who opens that file after an incident has no way to tell whether it is what the agent wrote. In the synthetic set, 🟢 a log with no integrity check flags 0 of 91 tampered copies, and the edited file still holds well-formed events (`step_01_no_integrity_check.py`). |
| **Solution** | Writes agent actions as an append-only JSON-lines log with a hash link from each event to the one before it, and no update or delete. `verify` reads the log strictly and exits 0, 1 or 2: nothing wrong, a sign of alteration, or could not run; it names the line. `anchor` records the sequence number and hash of one event, to be kept where the log's writer cannot edit it, and `verify --anchor` uses it to catch a log cut back or rewritten from the start. `append` adds one event and refuses to extend a log that does not verify. |
| **North-star metric** | Share of agent audit logs that are verified on a schedule against an anchor held outside the writer's reach, with the result recorded. Target 🔴 100% of in-scope agents. Today in this model: nothing checks the log. |
| **Measured metrics (synthetic)** | 🟢 76 of 91 tampered logs flagged by the strict chain check plus an anchor at event 200, against 18 of 91 for a checksum with a sequence check and 0 of 91 with no check; 0 of 10 harmless changes flagged (`step_04_chain_and_anchor.py`, `step_02_record_checksums.py`, `step_01_no_integrity_check.py`). |
| **Modeled metrics** | 🟡 Utility (76/91 − 18/91) × 20 = 12.7 tampered logs a year caught that a checksum with a sequence check would pass, assuming 20 altered logs reach a review each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The planted edits and the checks share an author, so the numbers are a ceiling. Mitigation: run it on one real agent log the owner can share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The anchor helps only if it lives where the log's editor cannot reach. 🟢 15 of 91 planted edits pass, all in the open tail after the anchor (`step_04_chain_and_anchor.py`). Mitigation: a named custodian for the anchor, a fixed anchor interval, and a scheduled verify that alerts. |
| **Risk #3** | A forged append is the same bytes as a real one. 🟢 0 of 6 forged appends are flagged and 6 of 6 legitimate appends are accepted (`step_03_deficiencies_exposed.py`). Mitigation: sign events with a key held by the writer, so a forged event fails to verify; it is in the backlog. |
| **Out of scope** | Deciding who may write (no signatures, no key); storing the anchor; proving the time of an event; detecting an action that was never logged; locking for several writers; log shipping, retention or encryption; any model call. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is planted edits or cases, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation** (missing, empty, cut-off or wrong-type input exits 2, never a traceback; a bad anchor exits 2) | 91 edits | 2 | 0.9 | 1 | 163.8 | Built in prototype |
| 2 | **Hash chain write and verify** (sequence, hash and link checks; no update or delete) | 91 edits | 3 | 0.9 | 3 | 81.9 | Built in prototype |
| 3 | **Anchor and `verify --anchor`** (catches a cut or a rewrite up to the anchored event) | 64 edits | 3 | 0.8 | 2 | 76.8 | Built in prototype |
| 4 | **Append that refuses a log that does not verify** | 36 cases | 2 | 0.8 | 1 | 57.6 | Built in prototype |
| 5 | **Scheduled verify with an alert** | 91 edits | 2 | 0.6 | 3 | 36.4 | Sequenced for v0.2 |
| 6 | **Anchor published to a store the writer cannot edit, on a schedule** | 27 edits | 3 | 0.7 | 3 | 18.9 | Sequenced for v0.2 |
| 7 | **Strict reading of lines** (a duplicate key, a field outside the hash, an unknown kind or NaN is a problem) | 14 edits | 2 | 0.9 | 2 | 12.6 | Built in prototype |
| 8 | **Writer-held signing key** (a forged append fails to verify) | 27 edits | 3 | 0.6 | 5 | 9.7 | Sequenced for v0.2 |
| 9 | **Completeness check against the orchestrator's own counts** (an action never logged) | 36 cases | 2 | 0.5 | 4 | 9.0 | Sequenced for v0.3 |
| 10 | **Log shipping to locked object storage** | 36 cases | 2 | 0.6 | 5 | 8.6 | Sequenced for v0.3 |
| 11 | **Locking for several writers** (two writers fork the chain today, and `verify` reports it) | 36 cases | 1 | 0.5 | 3 | 6.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from audit-chain | What they fear |
| --- | --- | --- | --- |
| **Engineer who owns the agent's logging** | Owner | A writer that cannot break the log by mistake, and a verify whose output names the line. | A log that fails verify after a restart, with no way to say which side is wrong. |
| **Reviewer or auditor** | Reader of the trail | A way to tell that the file they read was not changed afterwards, and a plain statement of what the check cannot see. | A verdict of OK read as proof that the agent logged everything it did. |
| **Security reviewer** | Co-owner of the anchor | An anchor held where the log's editor cannot reach, and an alert when verify fails. | The person who can edit the log also being able to edit the anchor. |
| **Platform team** | Hosts storage and the schedule | Plain files, a standard hash and no service to keep warm. | A new stateful service to run for a log that already exists. |
| **Agent product owner** | Consulted | Logging that does not slow the agent or block a case. | An append that refuses to write and stops the queue. |
| **Compliance / model risk** | Approver | A trail they can cite in a review, with its limits stated. | A claim of immutability the code does not support. |
| **Internal audit** | Reader | A path from a reviewed incident to the exact log bytes and the anchor used. | An anchor taken after the event it was meant to protect. |

---

## User stories (top 4)

1. **As the engineer who owns an agent's logging**, I want each event to carry the hash of the one before it, so an edited, removed or reordered event breaks the chain at a named line.
2. **As a reviewer**, I want `verify` to say what it checked and what it cannot see, so an OK is not read as proof of completeness.
3. **As a security reviewer**, I want an anchor I can keep outside the log, so a cut or a full rewrite by someone with write access is caught up to the anchored event.
4. **As an auditor**, I want the log, the anchor and the verify result for a given incident kept together, so I can reproduce the check later.

---

## KPIs

**North star:** share of agent audit logs that are verified on a schedule against an anchor held outside the writer's reach, with the result recorded. Target 🔴 100% of in-scope agents.

**Inputs (leading):**
- Agents that write through the chain (the prototype log holds 🟢 280 events from 36 cases, `step_01_no_integrity_check.py`).
- Agents with an anchor held by a named custodian (target: every agent).
- Anchor interval: 🟡 one anchor at event 200 of 280 in the prototype, an assumption with no rule behind it.
- Scheduled verifies that ran on time (target: every one).

**Outputs (lagging):** prototype baselines from the planted set.
- Tampered logs flagged. 🟢 76 of 91, against 18 of 91 for a checksum with a sequence check and 0 of 91 with no check (`step_04_chain_and_anchor.py`).
- Edits that touch an anchored event, flagged. 🟢 64 of 64; open-tail edits flagged 12 of 27 (`step_04_chain_and_anchor.py`).
- Harmless changes flagged. 🟢 0 of 10 (`step_04_chain_and_anchor.py`).
- Known misses. 🟢 15 of 91 pass, all in the open tail (`step_04_chain_and_anchor.py`).
- Forged appends flagged. 🟢 0 of 6 (`step_03_deficiencies_exposed.py`).
- Alterations found by a real reviewer: not measured; the planted set has none.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `verify` read-only on one existing agent log, with no anchor. Print the output and compare with what the owner expected. |
| 1: Write through the chain | 4w | One agent writes with `append`. Read the failure behavior on restart and on a second writer. |
| 2: Anchor outside the log | 4w | Name the custodian. Take an anchor on a fixed interval and keep it where the writer cannot edit it. |
| 3: Scheduled verify | 6w | A job runs `verify --anchor` and alerts on exit 1 or 2. Review each alert with the custodian. |
| 4: Signing and shipping | 8w | Sign events with a writer-held key, ship the log to locked storage and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **How often should the anchor be taken?** Whatever is written after the last anchor is protected by the chain alone. The prototype uses one anchor at event 200 of 280, an assumption. Recommendation: take the interval from how much of the tail a reviewer is willing to leave unprotected, and write it down.
2. **Where is the anchor kept?** Recommendation: a store with a different owner and a retention lock; the log's editor has no write access to it.
3. **Whose key signs events?** A forged append fails only if the writer holds a key the editor does not. Recommendation: the agent's service identity, with the key in the platform's key service, in v0.2.
4. **What happens when verify fails?** Recommendation: it raises an alert and freezes the log for review; it does not stop the agent, since a stopped queue is its own incident.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **Plain files and a standard hash.** The log is JSON lines and the verifier is stateless. Production adds a signer, a locked store and a scheduler, all designed and none built.
- **Never silent.** An unreadable, empty or malformed input exits 2. A line that is cut off or is not an event counts as a sign of alteration. Without `--anchor`, the output says that events removed from the end would not be noticed.
- **Strings from the log are data.** Values are escaped before they are printed, so a hostile string in a log line cannot forge output.
- **Changes to a check are changes to a number.** A golden test pins the step 4 numbers, so a change that moves a count shows in the diff.

**What is next.** Sign events with a key held by the writer; run it on one real agent log the owner is allowed to share; add a completeness check against the orchestrator's own counts.

**What would have to be true before a pilot.**
- A named custodian holds the anchor in a place the log's editor cannot write to.
- The agent writes through one writer, or a lock is added.
- The team accepts that OK means no sign of alteration, not that the log is complete or true.
- One real log can be shared, so the false-alarm rate is measured on real bytes and not mine.

---

*This PRD names [27 AgentKit](../27-agentkit-reference-agent-and-playbook/), [09 LineageLog](../09-lineagelog-ai-decision-audit/) and [05 AgentWatch](../05-agentwatch-agent-observability/) as designed interlocks (🔴 designed, none built). The event layout, event kinds and hash are copied from 27, not imported.*
