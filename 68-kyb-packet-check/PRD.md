# PRD: KYB Packet Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to an onboarding-controls review. It is not a record of a PRD landed at a named bank. The checks, the sum tolerance, the planted packets and the rollout plan are mine; the names, filings and personal details are invented, and the numbers are measured on synthetic data I generated or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | KYB Packet Check: a command-line check that takes the text of a business-onboarding packet and a model's extraction of it and prints PASS or REVIEW with the findings. It never calls a model |
| **Owner** | The person who owns the onboarding workflow behind a model extraction, with the owner of the filings as co-owner of the phrase lists |
| **Stage** | Portfolio prototype on synthetic data; not deployed |
| **Primary user** | The person who owns the onboarding workflow behind a model extraction, and the analyst who reviews what the workflow flags |
| **Secondary users** | The compliance lead who relies on the owner list; the owner of the extraction model; the privacy lead; internal audit |
| **Problem** | A model reads a business-onboarding filing and returns the owners, their percentages, the control person and their details. Nobody compares that reading with the filing. A percent read as 2.5 instead of 25, two percents swapped, or an owner left out all look like a normal, complete record, and the file then lists the wrong people as beneficial owners. In the planted set, 🟢 a process with no check stops 0 of 75 packets, and 20 of 75 files would list the wrong people (`step_01_no_check.py`). |
| **Solution** | Takes the text of one packet and the model's extraction as JSON. Checks completeness (the details for each 25 percent owner and the control person, and a signed, dated certification), arithmetic (percentages add up within a tolerance, and an entity holding 25 percent or more shows the owners behind it) and grounding (each name, percentage and personal detail appears on a filing line that names the same holder or person). Prints PASS or REVIEW with findings that do not repeat dates of birth, addresses or ID numbers, and exits 1 on REVIEW. |
| **North-star metric** | Share of onboarding packets that reach the file with an extraction compared with the filing, and either passed or cleared by a named person, with a decision record. Target 🔴 100%. Today in this model: 🟢 0 of 75 packets stopped (`step_01_no_check.py`). |
| **Measured metrics (synthetic)** | 🟢 40 of 43 misreads flagged and 0 of 32 clean packets flagged; 17 of 20 wrong-people packets flagged; 40 of 75 packets go to a person (`step_04_with_check.py`). |
| **Modeled metrics** | 🟡 Utility (17/20 − 2/20) × 40 = 30 wrong-people files flagged that a shape check would pass, assuming 40 such files reach the check. 🟡 The sum tolerance of 0.1 point and the rule that a schedule adds to 100 are my assumptions. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces and of the review they create has not been sized. |
| **Risk #1** | The packets and the checks share an author, so the numbers are a ceiling. Mitigation: run it on one real, shareable extraction log with the owner's permission, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The filing text here is clean synthetic text. A real scan needs a text layer, and its errors become this tool's errors: an OCR slip can flag a correct read or let a wrong one through. Mitigation: gate on text-layer quality before grounding (queued). |
| **Risk #3** | The sum tolerance and the rule that a schedule adds to 100 are mine, not the order's. 🟢 A sum check with zero tolerance flags 4 of 32 clean packets (`step_03_deficiencies_exposed.py`). Mitigation: set the tolerance against the owner's own filings in shadow mode. |
| **Out of scope** | Reading scans or PDFs; verifying that an identity is real; trusts; more than one level of look-through; a model call; any claim that the filing itself is true. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is packets. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Findings that never repeat a date of birth, address or ID number** | 75 packets | 3 | 0.9 | 1 | 202.5 | Built in prototype |
| 2 | **Completeness** (details for each 25 percent owner and the control person, signed and dated certification) | 75 packets | 2 | 0.9 | 1 | 135.0 | Built in prototype |
| 3 | **Input validation** (empty, truncated, wrong-type or oversized input exits 2, never a traceback) | 75 packets | 2 | 0.9 | 1 | 135.0 | Built in prototype |
| 4 | **Arithmetic** (percentages add up within a tolerance, an entity at 25 percent or more shows its owners) | 75 packets | 2 | 0.8 | 1 | 120.0 | Built in prototype |
| 5 | **Grounding** (each name, percentage and detail on a filing line for the same person) | 75 packets | 3 | 0.8 | 2 | 90.0 | Built in prototype |
| 6 | **CLI exit codes, `--fail-on` and `--tolerance`** | 75 packets | 1 | 0.9 | 1 | 67.5 | Built in prototype |
| 7 | **Nominee and side-letter phrase list** written by the owner of the filings | 75 packets | 3 | 0.5 | 3 | 37.5 | Sequenced for v0.2 |
| 8 | **Unallocated interests** (a schedule that legitimately adds to less than 100) | 75 packets | 2 | 0.6 | 3 | 30.0 | Sequenced for v0.2 |
| 9 | **Adapter that reads a live extractor's output into the JSON shape** | 75 packets | 2 | 0.5 | 3 | 25.0 | Sequenced for v0.2 |
| 10 | **Review queue and decision record** (findings, hashes, reviewer, outcome) | 75 packets | 2 | 0.6 | 4 | 22.5 | Sequenced for v0.2 |
| 11 | **Text-layer quality gate for scans** | 75 packets | 3 | 0.4 | 5 | 18.0 | Queued |
| 12 | **Trusts and more than one level of look-through** | 75 packets | 2 | 0.4 | 6 | 10.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from KYB Packet Check | What they fear |
| --- | --- | --- | --- |
| **Onboarding workflow owner** | Owner | A step that flags a misread early with a reason an analyst can act on, and passes clean packets. | A step that floods the queue and gets switched off. |
| **Onboarding analyst** | Reviews the flags | A short finding that names the holder, what was read and what the filing line shows. | A finding that sends them to re-read the whole filing anyway. |
| **Compliance lead** | Second line | An owner list that was compared with the filing, and a record that says so. | A clean-looking file that names the wrong owner. |
| **Extraction model owner** | Consulted | Findings grouped by kind so they can see which misreads recur. | The check read as a verdict on the model, not on one packet. |
| **Privacy lead** | Approver | Personal details never copied into logs, findings or telemetry. | A check that echoes a date of birth or an ID number into a log. |
| **Security / CISO** | Approver | Nothing leaving the boundary, strings from files kept out of logs, no model key in the tool. | Hostile text in a filing forging a log line. |
| **Internal audit** | Reader | A path from a decision to the packet, the extraction and the tolerance it used. | A tolerance changed silently between two runs. |

---

## User stories (top 4)

1. **As the onboarding workflow owner**, I want an extraction compared with the filing before a person signs it off, so a misread owner does not reach the file as a complete record.
2. **As an onboarding analyst**, I want each finding to name the holder, the percent read and the percent on the filing line, so I can clear it without re-reading the packet.
3. **As the privacy lead**, I want findings to carry names and percentages but never a date of birth, address or ID number, so the check does not copy personal details into logs.
4. **As internal audit**, I want each decision tied to the packet, the extraction and the tolerance it used, so I can reproduce it later.

---

## KPIs

**North star:** share of onboarding packets that reach the file with an extraction compared with the filing, and either passed or cleared by a named person, with a decision record. Target 🔴 100%.

**Inputs (leading):**
- Packets with a usable text layer (the prototype set has 🟢 75 packets, from `data/README.md`; real scans are not covered).
- Extractions in the JSON shape the check reads (target: every extractor in front of the check).
- Sum tolerance set against the owner's own filings (the prototype's 0.1 is an assumption).
- A nominee and side-letter phrase list written by the owner of the filings (target: one list; not in the prototype).

**Outputs (lagging):** prototype baselines from the planted set.
- Misreads flagged. 🟢 40 of 43 (`step_04_with_check.py`), against 12 of 43 for a shape check (`step_02_field_validation.py`).
- Clean packets flagged. 🟢 0 of 32 (`step_04_with_check.py`).
- Wrong-people packets flagged. 🟢 17 of 20 (`step_04_with_check.py`).
- Packets sent to a person. 🟢 40 of 75 (`step_04_with_check.py`).
- Known miss. 🟢 3 nominee notes pass (`step_04_with_check.py`).
- Findings overturned by a reviewer: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one real, shareable extraction log with `--fail-on never`. Print the findings, hold nothing, and compare with what analysts catch. |
| 1: Calibration | 4w | Set the tolerance against the owner's filings. Check how often the text layer is good enough for grounding. Have the filings owner write the nominee phrase list. |
| 2: Advisory in the workflow | 4w | Show the findings to the analyst next to the extraction, without blocking sign-off. |
| 3: Review required | 6w | Route a REVIEW packet to a person before it reaches the file. Record who cleared it and why. |
| 4: Record and edge cases | 8w | Write a decision record per packet. Handle unallocated interests, then test trusts and deeper look-through and the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **What tolerance should the sum allow?** The 0.1 point tolerance and the rule that a schedule adds to 100 are mine. Recommendation: keep 0.1 in shadow mode, then set it against the owner's own filings; the planted set shows thirds written to two decimals need it.
2. **Should every finding go to a person?** In the prototype, 🟢 40 of 75 packets did on a deliberately dense mix (`step_04_with_check.py`). Recommendation: send every finding to a person first, and tier them only after the real mix is known.
3. **Who writes the nominee and side-letter phrase list?** A check for the word "nominee" would catch the three misses, and I left it out because it would be fit to my own wording. Recommendation: the owner of the filings writes it, from real filings.
4. **What if the filing is a scan?** Grounding is only as good as the text layer. Recommendation: add a text-layer quality gate before grounding, and treat a poor layer as REVIEW, never PASS.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the onboarding workflow.** The check is stateless: it reads a packet text and an extraction and returns findings and a decision. Production adds a review queue, a decision record and telemetry, all designed and none built.
- **Never silent.** An empty, truncated, oversized or mistyped input exits 2. A missing or empty value in the extraction is a finding, not a crash.
- **Personal details stay out of output.** Findings print names and percentages, never a date of birth, address or ID number, and control characters in any string are shown as escapes.
- **Changes to a tolerance are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves a flagged count shows in the diff.

**What is next.** Run it on one real, shareable extraction log; add a phrase list written by the filings owner; handle unallocated interests.

**What would have to be true before a pilot.**
- A real extraction log and its filings can be shared with the owner's permission.
- The text layer the extractor read is the text the check is given.
- A named person owns the tolerance, the phrase list and the review of findings.
- The privacy lead has approved where findings and decision records live.
- The team agrees whether REVIEW blocks sign-off or only informs it.

---

*This PRD names [77 Spread Extraction Eval](../77-spread-extraction-eval/), [51 Memo Tieout](../51-memo-tieout/), [08 OversightOps](../08-oversightops-hitl-workflow/) and [76 Name Match Eval](../76-name-match-eval/) as designed interlocks (🔴 designed, none built). The prototype reads no file from any of them.*
