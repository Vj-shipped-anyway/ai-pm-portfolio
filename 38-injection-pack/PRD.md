# PRD: Injection Pack

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a gateway-rules change review. It is not a record of a PRD landed at a named bank. The pack, the rules and the planted rule changes are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone, and the gateway in the runs is a rule file of regular expressions.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | Injection Pack: a command-line regression runner for the rules of a prompt gateway, with a staged GitHub Action. It replays a pack of injection cases on the old and the new rules and fails the check when a case the old rules got right is now wrong |
| **Owner** | The engineer or security reviewer who owns the rules of a gateway, with the person who approves rule changes as co-owner of the pack and the floors |
| **Stage** | Portfolio prototype on synthetic data (a 160-case pack, a held-out population, 51 planted rule changes); the Action is staged and unpublished |
| **Primary user** | The engineer or security reviewer who owns the rules of a gateway |
| **Secondary users** | The person who approves changes to them; the owner of the pack; internal audit |
| **Problem** | A prompt gateway is a set of rules in front of an internal assistant. Teams edit those rules in pull requests: a pattern narrowed to stop a false alarm, a rule removed because nobody remembers why it is there, a domain added to an allow-list. The unit tests on the code pass. Nobody replays injection cases, so a change can make the gateway weaker without any check failing, and the first signal is an incident. In the planted set, 🟢 CI with no pack stops 0 of 51 rule changes and 25 of 51 are harmful (`step_01_no_pack.py`). |
| **Solution** | (1) Holds a test pack as a CSV: attack and benign cases, each tagged with the channel it arrives on (user input, retrieved document, tool call, model response, session memory). (2) Runs the pack on one rule file (`run`) and reports blocked attacks, blocked benign cases and the misses, by channel. (3) Compares two rule files on the pack (`compare`): a case the old rules got right and the new rules get wrong is a regression, and any regression fails the check. (4) Says so when a changed rule matches no case in the pack, so a silent pass is not mistaken for a safe change. (5) Optional floors for the catch rate and the false-block rate; GitHub annotations on request; a staged Action wraps the command. |
| **North-star metric** | Share of harmful rule changes blocked before merge, with a recorded decision. Target 🔴 100%. Prototype today: 21 of 25 stopped. |
| **Measured metrics (synthetic)** | 🟢 21 of 25 harmful rule changes stopped (16 of 20 that lose attack coverage, 5 of 5 that add false blocks); 1 of 26 harmless changes stopped; 46 of 51 decisions match the held-out truth (`step_04_with_pack.py`). |
| **Modeled metrics** | 🟡 Utility (21/25 − 3/25) × 10 = 7.2 harmful rule changes a year stopped that a six-string smoke test would pass, assuming 10 harmful rule changes reach the gate each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The pack, the held-out population, the rules and the rule changes share an author, so the numbers are a ceiling. Mitigation: run it on the rule file of one real gateway and report the planted numbers and the real numbers apart. |
| **Risk #2** | The harm line (one percentage point) is an assumption. 🟢 RP-042 costs 7 of 1000 held-out attacks and is stopped as a false alarm (`step_04_with_pack.py`). Mitigation: set the line against the real gateway's own noise and review it with the rule owner. |
| **Risk #3** | Regex rules stand in for a gateway that, in a real deployment, includes a classifier model this prototype does not have, and a 100-attack pack samples phrasing thinly. 🟢 4 of 25 harmful changes still pass (`step_04_with_pack.py`). Mitigation: a technique coverage report and a pack that grows from incidents. |
| **Out of scope** | Calling a live gateway or a model; testing the layers in combination; non-English rules; regex timeouts; generating new attacks; hosting. A Marketplace listing is a later, separate step. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is rule pull requests, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Case-by-case regression compare** (old right and new wrong fails the check) | 51 PRs | 3 | 0.9 | 1 | 137.7 | Built in prototype |
| 2 | **CI output** (text and GitHub annotations, `--fail-on`, escaped strings) | 51 PRs | 2 | 0.9 | 1 | 91.8 | Built in prototype |
| 3 | **Blind-spot and empty-layer notes** (a changed rule that no pack case matches) | 51 PRs | 2 | 0.8 | 1 | 81.6 | Built in prototype |
| 4 | **Five-layer replay by channel** (each case read by one layer) | 51 PRs | 3 | 0.8 | 2 | 61.2 | Built in prototype |
| 5 | **Input validation** (bad rules or pack exit 2, never a traceback) | 51 PRs | 2 | 0.9 | 2 | 45.9 | Built in prototype |
| 6 | **Optional floors** (minimum catch rate, maximum false-block rate) | 51 PRs | 1 | 0.8 | 1 | 40.8 | Built in prototype |
| 7 | **Technique coverage report** (attack techniques with no pack case) | 51 PRs | 3 | 0.6 | 3 | 30.6 | Sequenced for v0.2 |
| 8 | **Publish the Action from its own repository** | 51 PRs | 2 | 0.5 | 2 | 25.5 | Sequenced for v0.2 (staged in `action/`, not published) |
| 9 | **Regex time limit** (a pattern that hangs cannot hang the job) | 51 PRs | 2 | 0.5 | 3 | 17.0 | Sequenced for v0.2 |
| 10 | **Decision ledger** (hashes of both rule files and the pack, regressions, notes) | 51 PRs | 2 | 0.6 | 4 | 15.3 | Sequenced for v0.3 |
| 11 | **Combined-layer cases** (a document that layer 2 misses and layer 4 catches) | 51 PRs | 3 | 0.4 | 6 | 10.2 | Queued |
| 12 | **Live-endpoint mode** (post cases to a running gateway) | 51 PRs | 3 | 0.5 | 8 | 9.6 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Injection Pack | What they fear |
| --- | --- | --- | --- |
| **Gateway-rules owner** | Owner | A check that names the case that got worse and the rule that used to block it. | A check that blocks harmless edits and gets switched off. |
| **Rule-change approver** | Approver | To know what the pack tested and what it could not see, so the review is about the gaps. | Signing off on a green check for a change the pack never touched. |
| **Pack owner** | Owns the cases | A way to add a case from an incident and see it fail the rule that missed it. | A pack that drifts to match the rules, or shrinks to let a change pass. |
| **Application owner** | Informed | A gateway that does not get weaker without anyone noticing. | Learning of a gap from an incident. |
| **Security / CISO** | Approver | No model call and no key in the path; rule files and the pack treated as confidential. | Attack strings and defenses leaking through logs or annotations. |
| **Internal audit** | Reader | A path from a rule change to the pack, rules and thresholds it was checked with. | A floor or the pack changed silently between two runs. |

---

## User stories (top 4)

1. **As the gateway-rules owner**, I want the pipeline to fail when a case the old rules blocked is now allowed, so a narrowed pattern does not quietly open a hole.
2. **As the person who approves rule changes**, I want a note when a changed rule matches no pack case, so a silent pass is not read as a safe change.
3. **As the pack owner**, I want to add a case for a technique and see which rule changes it would have stopped, so the pack grows where the gaps are.
4. **As internal audit**, I want each decision tied to the hashes of the two rule files and the pack it used, so I can reproduce it.

---

## KPIs

**North star:** share of harmful rule changes blocked before merge, with a recorded decision. Target 🔴 100%. Prototype baseline: 21 of 25 stopped.

**Inputs (leading):**
- Pack size and mix (prototype: 🟢 160 cases, 100 attacks and 60 benign cases, `step_01_no_pack.py`).
- Hard cases in the pack (prototype: 🟢 14 hard attacks and 30 look-alike benign cases, `step_01_no_pack.py`).
- Attack techniques with a pack case (prototype: all but one; 🟢 held-out techniques with no pack case: doc_encoded_blob, `step_04_with_pack.py`).
- Changed rules that match at least one pack case (target: every changed rule).

**Outputs (lagging):** prototype baselines from the planted set.
- Harmful rule changes stopped. 🟢 21 of 25, against 3 of 25 for the six-string smoke test and 0 of 51 for no pack (`step_04_with_pack.py`, `step_02_smoke_test.py`, `step_01_no_pack.py`).
- Harmless changes stopped. 🟢 1 of 26 (`step_04_with_pack.py`).
- Decision matches the held-out truth. 🟢 46 of 51 (`step_04_with_pack.py`).
- Known misses. 🟢 4 of 25 harmful changes still pass, and 1 of the 4 came with a blind-spot note (`step_04_with_pack.py`).
- BLOCKs overturned after review: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run `compare` on the rule pull requests of one gateway with `--fail-on never`. Print the decision, fail nothing, and compare with what the review found. |
| 1: Calibration | 4w | Read every regression and every note. Add pack cases for the techniques the gateway owner sees in incidents. Set the harm line and the floors against the real gateway. |
| 2: Regressions enforced | 4w | Fail the step on a regression on one repository. Notes stay advisory. |
| 3: Floors enforced and Action published | 6w | Turn on the catch and false-block floors. Publish the Action from its own repository. |
| 4: Coverage report and ledger | 8w | Report techniques with no pack case. Write a decision record per run. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should a blind-spot note block?** In the prototype it does not; the decision stays ALLOW. 🟢 Only 1 of the 4 harmful changes that pass came with a note (`step_04_with_pack.py`). Recommendation: keep notes advisory in shadow, count how often a note precedes a real gap, then decide.
2. **Where does the harm line come from?** One percentage point on a held-out population is my assumption. Recommendation: set it against the real gateway's own variation, and review it with the rule owner.
3. **Who owns the pack, and how does it grow?** Recommendation: the pack owner adds a case for every incident, a different person approves, and the pack hash is stored with every decision.
4. **Is the pack a sample of real traffic?** In the prototype the held-out population comes from the same templates as the pack. Recommendation: with the owner's permission, score the final rules on sampled real traffic and report that apart from the planted numbers.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the pipeline.** The check is stateless: it reads two rule files and a pack and returns a decision. Production adds a reviewed pack repository, a decision ledger and a published Action, all designed and none built.
- **Never silent on input.** A rule file or pack that cannot be read exits 2. A changed rule the pack cannot see prints a note.
- **Strings from input are data.** Annotations and text output escape control characters, so a hostile case id cannot forge a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a count shows in the diff.

**What is next.** Run it on the rule file of one real gateway whose owner is allowed to share it; add a mode that posts cases to a live endpoint; add combined-layer cases; publish the Action from its own repository.

**What would have to be true before a pilot.**
- The gateway rules live in a file the pipeline can read, with a base revision to compare.
- A named pack owner exists, and pack changes need a different approver.
- One real rule file can be shared, so the pack and the harm line are set against a real gateway and not mine.
- The team agrees whether a note or a floor miss fails the step.
- Real customer data stays out of the pack.

---

*This PRD names [06 PromptShield](../06-promptshield-prompt-injection-defense/), [28 Tool Schema Drift](../28-tool-schema-drift/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The code here imports nothing from them.*
