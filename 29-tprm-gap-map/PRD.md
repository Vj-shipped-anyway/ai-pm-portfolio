# PRD: TPRM Gap Map

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a third-party risk review while a guidance proposal is out for comment. It is not a record of a PRD landed at a named bank. The map, the rules, the simulated incident log and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | TPRM Gap Map: a command-line tool that maps each stage of a proposed third-party risk guidance to the evidence an AI-enabled vendor needs, tiers vendors by the text's own examples and by four added characteristics, and tests each characteristic against an incident log |
| **Owner** | The third-party risk or AI governance lead at the bank, with the vendor manager as co-owner of the vendor file |
| **Stage** | Portfolio prototype on synthetic data |
| **Primary user** | A third-party risk or AI governance lead at a bank |
| **Secondary users** | Anyone drafting a comment on the proposal; the vendor manager; the business owner of an AI-enabled service; internal audit |
| **Problem** | A proposed interagency guidance on third-party risk is out for comment. It is principles-based and does not mention AI. A bank buying an AI-enabled service has to decide what evidence to hold, and the agencies ask which characteristics should mark a relationship as high risk. In the synthetic set, 🟢 the questionnaire passes 36 of 60 vendors and 16 of those passes had a material incident (`step_01_due_diligence_only.py`). |
| **Solution** | Maps each stage of the proposed text to the evidence an AI-enabled vendor needs, marking whether the text names it, covers it by principle, gives an example, or does not mention it. Tiers vendors by the text's own examples and by four added characteristics. Tests each characteristic against an incident log: how many vendors with it had a material incident. |
| **North-star metric** | Share of AI-enabled vendors whose tier was set with a recorded test of the markers against the bank's own incident history. Target 🔴 100%. Today in this model: no tier is tested. |
| **Measured metrics (synthetic)** | 🟢 The text's examples catch 17 of 24 material-incident vendors; with four characteristics, 22 of 24; false alarms rise from 13 to 19; 41 of 60 vendors are marked HIGH against 30 of 60; 2 of 24 stay LOWER (`step_02_text_examples.py`, `step_04_with_ai_fields.py`). |
| **Modeled metrics** | 🟡 Utility (22/24 − 17/24) × 20 = 4.2 material-incident vendors flagged HIGH that the text's examples would leave LOWER, assuming 20 vendors with a material incident in a 36-month window. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The incident log is simulated from hazard rates I chose before the first run, so the numbers show a method and not how often real vendors fail. Mitigation: run it on one real incident history the owner may share and report the simulated and the real numbers apart. |
| **Risk #2** | The map is a reading of one proposal, and the proposal can change. Mitigation: each row cites the section of the proposal; re-read the map against the final text when it is issued. |
| **Risk #3** | More flags mean more false alarms. 🟢 19 against 13, so a reviewer reads 41 vendors in place of 30 (`step_04_with_ai_fields.py`). Mitigation: show each characteristic alone so the owner can adopt the ones that earn their review load. |
| **Out of scope** | Legal advice; predicting examiner behavior; scoring real vendors; any model call; submitting a comment. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is vendors, stages or incidents, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Tiering by the text's own examples** (named service types, share of activity) | 60 vendors | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 2 | **Vendor-file validation** (a non-numeric or missing column exits 2) | 60 vendors | 2 | 0.9 | 1 | 108.0 | Built in prototype |
| 3 | **Close the silent paths** (header-only file, unknown service type, incident log without a material column) | 60 vendors | 2 | 0.9 | 1 | 108.0 | Sequenced for v0.2 |
| 4 | **Test against the incident log** (caught, missed, false alarms, per characteristic) | 60 vendors | 3 | 0.7 | 2 | 63.0 | Built in prototype |
| 5 | **Four AI-specific characteristics** (concentration, notice, training, retention) | 60 vendors | 3 | 0.6 | 2 | 54.0 | Built in prototype |
| 6 | **Calibrate the 30% and 365-day lines on a real log** | 60 vendors | 3 | 0.5 | 3 | 30.0 | Sequenced for v0.2 |
| 7 | **Guidance map** (16 rows, section of the proposal, named, principle, example or not mentioned) | 16 stages | 2 | 0.8 | 1 | 25.6 | Built in prototype |
| 8 | **Incident-log feed** from the incident process | 100 incidents | 2 | 0.5 | 4 | 25.0 | Sequenced for v0.2 |
| 9 | **Upstream concentration from real dependencies** | 60 vendors | 3 | 0.5 | 4 | 22.5 | Sequenced for v0.2 |
| 10 | **Map refresh against the final text** | 16 stages | 2 | 0.7 | 1 | 22.4 | Queued |
| 11 | **Tiering ledger** (characteristic set, thresholds, file hashes, result) | 60 vendors | 2 | 0.6 | 4 | 18.0 | Sequenced for v0.2 |
| 12 | **Review-hours per HIGH vendor**, so false alarms carry a cost | 60 vendors | 2 | 0.3 | 3 | 12.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from TPRM Gap Map | What they fear |
| --- | --- | --- | --- |
| **Third-party risk lead** | Owner | A way to test a proposed marker against the bank's own history before adopting it. | Adding markers that double the review queue and prove nothing. |
| **AI governance lead** | Co-owner of the characteristics | Evidence for the points the text does not mention: model changes, use of bank data, upstream providers. | A tiering that treats an AI-enabled service like any other cloud service. |
| **Business owner of the vendor** | Consulted | To know early which vendor will be reviewed harder and why. | A HIGH tier set by a rule they cannot read. |
| **Vendor manager** | Owner of the vendor file | Columns that match what the contract and the questionnaire already hold. | A new data request to every vendor. |
| **Regulatory affairs** | Drafts the comment | A short list of characteristics with counts behind it, clearly labeled as simulated. | Quoting a simulation as if it were evidence about real vendors. |
| **Security / CISO** | Approver | Nothing leaving the boundary and no vendor names in the output. | Incident detail copied into another tool. |
| **Internal audit** | Reader | A path from a tier to the file, the characteristic set and the thresholds it used. | Thresholds changed silently between two runs. |

---

## User stories (top 4)

1. **As the third-party risk lead**, I want each candidate characteristic tested against my incident history, so I add a marker because vendors with it had incidents and not because a list suggested it.
2. **As the AI governance lead**, I want to see which AI-enabled vendors the text's examples leave LOWER, so I can decide what evidence to hold on them.
3. **As someone drafting a comment**, I want each stage of the proposal mapped to AI evidence with the section cited, so the comment points at the stage where the text is silent.
4. **As internal audit**, I want each tier tied to the file, the characteristics and the thresholds it used, so I can reproduce it later.

---

## KPIs

**North star:** share of AI-enabled vendors whose tier was set with a recorded test of the markers against the bank's own incident history. Target 🔴 100%.

**Inputs (leading):**
- Vendors with a service type, a share of activity and an upstream provider on file (the prototype set has 🟢 60 vendors, 22 of them AI-enabled, from `step_01_due_diligence_only.py`).
- Incidents with a vendor, a month, a cause and customer-impact hours (the prototype log has 🟢 100 simulated incidents over 36 months, from `data/README.md`).
- AI-enabled vendors with a model-change notice, a training flag and a retention period recorded (target: every one).
- Rows in the guidance map checked against the current text (the prototype map has 🟢 16 rows, from `data/README.md`).

**Outputs (lagging):** prototype baselines from the synthetic set.
- Material-incident vendors caught by the text's examples. 🟢 17 of 24 (`step_02_text_examples.py`).
- Material-incident vendors caught with four characteristics. 🟢 22 of 24 (`step_04_with_ai_fields.py`).
- False alarms. 🟢 13 under the text's examples and 19 with the characteristics (`step_04_with_ai_fields.py`).
- Vendors marked HIGH. 🟢 30 of 60 and 41 of 60 (`step_04_with_ai_fields.py`).
- Known miss. 🟢 2 of 24 material-incident vendors stay LOWER (`step_04_with_ai_fields.py`).
- HIGH vendors that were not later found to need the extra review: not measured; the synthetic set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tiering on one vendor file beside the bank's own tiers. Print both, change nothing. |
| 1: Calibration | 4w | Run the test on the bank's incident history. Set the share, concentration and retention lines against it, and fix the vendor-file columns that are blank. |
| 2: Advisory flags | 4w | Add the characteristics that earned their review load as an advisory flag on the vendor record. The tier of record does not change. |
| 3: Tier of record | 6w | Let an agreed characteristic set the tier of record, with a named approver. Refresh the map against the final text. |
| 4: Feeds and ledger | 8w | Connect the vendor inventory and the incident feed, write a tiering record per run, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should the characteristics set the tier, or only raise a flag?** In the prototype they set a HIGH tier because that is the way to count what they catch. Recommendation: advisory first, and a tier of record only after a pilot shows the extra review load is worth it.
2. **Where should the 30% concentration line and the 365-day retention line come from?** They are my choices. 🟢 At 20% the catch is 23 of 24; at 30% and 50% it is 22 of 24 (`step_04_with_ai_fields.py`). Recommendation: set them against the bank's own log and record the reason.
3. **What counts as a material incident?** Here it is 4 hours or more of customer impact. Recommendation: use the bank's own incident severity, so the test and the incident process agree.
4. **What should happen to an AI-enabled vendor with no upstream provider on file?** It cannot show as concentrated; the tool prints the count. Recommendation: treat a blank upstream as a finding to chase and not as LOWER.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process, run on demand.** The tool is stateless: it reads a vendor file and an incident log and prints tiers and a table. Production adds feeds, a reviewed characteristic config and a tiering ledger, all designed and none built.
- **Never silent, as a design.** The prototype exits 2 for an unreadable file or a non-numeric field, but a header-only file, an unknown service type and an empty incident log pass without a word. The design closes those paths; the PRD lists it as backlog item 3.
- **The guidance map is data.** It is a hand-written file with the section of the proposal on each row, so a change in the final text is a change to a file.
- **Changes to a rule are changes to a number.** A golden test pins the synthetic-set numbers, so a change that moves the catch or false-alarm count shows in the diff.

**What is next.** Run it on a real incident history the owner may share; re-read the map against the final text when it is issued.

**What would have to be true before a pilot.**
- The vendor file carries service type, share of activity, upstream provider, notice period, training flag and retention for every AI-enabled vendor.
- The incident history has a customer-impact figure, so "material" can be defined by the bank.
- A named person owns the characteristic set and the thresholds.
- One real history can be shared, so the markers are tested on real incidents and not on my hazard rates.
- The team agrees whether a characteristic flags or sets the tier.

---

*This PRD names [18 VendorLens](../18-vendorlens-ai-vendor-due-diligence/), [19 IncidentLedger](../19-incidentledger-ai-incident-response/), [45 Concentration Register](../45-concentration-register/) and [44 Inventory Check](../44-inventory-check/) as designed interlocks (🔴 designed, none built). This folder extends 18 in idea and does not import or read any sibling's files.*
