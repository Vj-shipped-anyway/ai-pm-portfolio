# PRD: ISO 20022 Map Check

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a payments change review. It is not a record of a PRD landed at a named bank. The legacy format, the mapping, the ten converter builds and the planted defects are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | ISO 20022 Map Check: a command-line check that reads a legacy-to-ISO field mapping and, optionally, pairs of legacy and ISO messages from a converter, and reports fields with no home, values that cannot fit, and values that arrived cut short, dropped or changed |
| **Owner** | The payments analyst or engineer who owns the mapping between a legacy format and an ISO 20022 message, with the reviewer who signs the mapping off as co-owner of the capacity and code decisions |
| **Stage** | Portfolio prototype on synthetic data; no CI wrapper is staged |
| **Primary user** | The payments analyst or engineer who owns the mapping |
| **Secondary users** | The reviewer who signs it off; the converter engineer who fixes findings; the payment operations lead who works the repair queue; internal audit |
| **Problem** | A team moving payments from a legacy message format to ISO 20022 writes a field mapping, builds a converter, and validates the output against the ISO element rules. That validation passes a name cut short, a field that was never written and an amount that was rounded, because each is still a valid ISO value. The loss shows up later, in a repair queue or a return. In the planted set, 🟢 schema validation alone passes 214 of 230 pairs, and 113 of the 129 pairs that carry a planted defect still pass it (`step_01_schema_check_only.py`). |
| **Solution** | Reads the mapping with the two field catalogues and reports a legacy field with no row, a mandatory ISO element nothing fills, a legacy code with no table entry, and a field that cannot fit its target. Compares each legacy message with the ISO message the converter produced and reports a value dropped, cut short, changed, or present with no source. Prints legacy messages with every field at its limit (`probe`) so a converter that cuts early shows itself. Reports what no message exercised, so a missing test is not read as a pass. Exits 0, 1 or 2 and never prints a payment value. |
| **North-star metric** | Share of converter builds and mapping changes released with a check run that includes boundary messages and a recorded decision. Target 🔴 100%. Today in this model: schema validation only. |
| **Measured metrics (synthetic)** | 🟢 5 of 5 planted mapping defects found with 0 of 3 harmless rows flagged; 212 of 212 planted converter defects found in pairs with 0 of 162 harmless variations flagged; 7 of 8 defective builds found with probes against 5 of 8 on typical messages alone; the known miss is build B10 (`step_04_with_check.py`). |
| **Modeled metrics** | 🟡 Utility 99/212 × 40 = 18.7 converter defects a year that the check sees and an exact comparison cannot, assuming 40 converter defects reach review each year. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces has not been sized. |
| **Risk #1** | The data and the rules share an author, so event-level results are a ceiling, not a rate. Mitigation: run it on one real mapping and one build the owner may share, and report the planted numbers and the real numbers apart. |
| **Risk #2** | The legacy format is invented and the ISO lengths are my simplification. A real mapping will have lengths, mandatory flags and structures I did not model. Mitigation: take the element lengths and mandatory flags from the message specification the bank actually uses, and treat the capacity findings as only as good as those columns. |
| **Risk #3** | A defect that fires only on a combination of codes stays hidden until a message carries it. 🟢 Build B10 drops the beneficiary account only when TYP is 16 and CHGS is S; the defect fired 0 times, and 2 of 9 code combinations are in no message (`step_04_with_check.py`). Mitigation: the coverage line prints the gap; cross the coded fields in the probes while the product of code counts stays small. |
| **Out of scope** | XML parsing and schema validation; structured-address parsing; judging whether a mapping is semantically right; the ISO-to-legacy direction beyond a length warning; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is message pairs or mapping rows, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Mapping checks** (legacy field with no row, mandatory element unsourced, code with no table entry, capacity overflow) | 230 pairs | 3 | 0.9 | 1 | 621.0 | Built in prototype |
| 2 | **Input validation** (empty, wrong-type or truncated input exits 2, never a traceback; strings from input escaped; no payment value printed) | 230 pairs | 2 | 0.9 | 1 | 414.0 | Built in prototype |
| 3 | **Pair value checks** (dropped, truncated, altered, unmapped, untraced, plus the schema basics) | 230 pairs | 3 | 0.9 | 2 | 310.5 | Built in prototype |
| 4 | **Probe messages at every field limit** (`probe`) | 230 pairs | 2 | 0.6 | 1 | 276.0 | Built in prototype |
| 5 | **Coverage report** (code values, code combinations and mapping rows no message exercised) | 230 pairs | 1 | 0.7 | 1 | 161.0 | Built in prototype |
| 6 | **Cross the coded fields in the probes** | 230 pairs | 2 | 0.6 | 2 | 138.0 | Sequenced for v0.2 |
| 7 | **CI step on a mapping change** (fails the pull request at the chosen level) | 230 pairs | 2 | 0.5 | 2 | 115.0 | Sequenced for v0.2 |
| 8 | **Decision record per run** (mapping hash, pairs hash, findings) | 230 pairs | 1 | 0.6 | 4 | 34.5 | Sequenced for v0.2 |
| 9 | **Structured addresses and real XML files** | 230 pairs | 2 | 0.4 | 8 | 23.0 | Queued |
| 10 | **Reverse-exposure warning** (the ISO element takes more than the legacy field holds) | 12 rows | 1 | 0.7 | 1 | 8.4 | Built in prototype (arithmetic only) |
| 11 | **ISO-to-legacy check with converted-back messages** | 12 rows | 2 | 0.5 | 4 | 3.0 | Queued |
| 12 | **Semantic mapping review** (is the right field sent to the right element) | 20 rows | 3 | 0.3 | 6 | 3.0 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from Map Check | What they fear |
| --- | --- | --- | --- |
| **Mapping owner** | Owner | A finding that names the element, the field and the count, so the fix is a row or a length. | A tool that flags harmless padding and gets ignored. |
| **Mapping reviewer** | Approver of capacity and code decisions | A list of what was checked and what no message exercised, so sign-off does not rest on a green run that never reached the risky case. | Signing off a mapping whose gaps nobody read. |
| **Converter engineer** | Consulted | A pair-level finding that points at the output element and the first message, without needing to read a payment. | A check that is slow or that blocks a build on noise. |
| **Payment operations lead** | Informed | Fewer cut or missing fields arriving in the repair queue after cutover. | Learning about a systematic cut from the queue, weeks after go-live. |
| **Security / CISO** | Approver | No payment value in any log, and no production message in the tool's path. | A check that copies customer data into CI logs. |
| **Internal audit** | Reader | A path from a release decision to the mapping version and the pairs it used. | A mapping changed silently between two releases. |

---

## User stories (top 4)

1. **As the mapping owner**, I want the mapping checked on its own before any converter exists, so a legacy field with no row, an unsourced mandatory element and a field that cannot fit are fixed in the spreadsheet and not discovered in production.
2. **As a reviewer who signs the mapping off**, I want a coverage line that says which code values and code combinations no message exercised, so a pass is not read as proof for cases the messages never reached.
3. **As a converter engineer**, I want legacy messages with every field at its limit, so a converter that cuts a value early shows itself before real traffic does.
4. **As internal audit**, I want each decision tied to the mapping files and the pairs it used, so I can reproduce a release decision later.

---

## KPIs

**North star:** share of converter builds and mapping changes released with a check run that includes boundary messages and a recorded decision. Target 🔴 100%.

**Inputs (leading):**
- Mapping rows with a transform and a capacity recorded (the prototype mapping has 🟢 19 rows over 20 legacy fields and 20 ISO elements, `data/README.md`).
- Messages in the pairs file that reach the boundary: 🟢 23 legacy messages per build, 3 of them boundary probes (`data/README.md`).
- Code combinations exercised (prototype: 🟢 2 of 9 never in any message, `step_04_with_check.py`).
- Mapping owners who record a decision for every capacity finding (target: every one).

**Outputs (lagging):** prototype baselines from the planted set.
- Planted mapping defects found. 🟢 5 of 5 with 0 of 3 harmless rows flagged (`step_04_with_check.py`).
- Planted converter defects found in pairs. 🟢 212 of 212 with 0 of 162 harmless variations flagged (`step_04_with_check.py`).
- Defective builds found. 🟢 7 of 8 with probes, 5 of 8 on typical messages alone (`step_04_with_check.py`).
- Defective pairs that pass schema validation. 🟢 113 of 129 (`step_01_schema_check_only.py`).
- Known miss. 🟢 build B10 is not found (`step_04_with_check.py`).
- Findings overturned by the mapping owner as harmless: not measured; the planted set has no reviewer.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the check on one real mapping and one build using test messages only. Print the findings, fail nothing, and compare with what the team already knew. |
| 1: Calibration | 4w | Replace the invented lengths and mandatory flags with the bank's own message specification columns. Decide which capacity findings are accepted cuts and record each. |
| 2: Mapping errors enforced | 4w | Fail the pull request on a mapping error. Pair findings stay advisory. |
| 3: Pair findings enforced | 6w | Fail the build on any pair finding. Cross the coded fields in the probes. |
| 4: Record and reverse direction | 8w | Write a decision record per run. Add the ISO-to-legacy check with converted-back messages, and test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should pairs ever come from real traffic?** Recommendation: no. Build the pairs from the probe messages and from test fixtures in a test environment, because the check prints no value but the pairs file holds every value.
2. **Is a capacity overflow an error or a decision?** In the prototype it is an error. Recommendation: keep it an error until the mapping owner records the accepted cut, so a silent truncation is always a named choice.
3. **How far should the probes cross the code fields?** The coverage report computes combinations only when the product of code counts is 64 or fewer, a constant in the code. Recommendation: cross every coded field while that product stays small, and print the gap beyond it.
4. **When does the reverse direction matter?** The check reports it as arithmetic only. Recommendation: keep it a warning until a sample of converted-back messages exists to test it.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One process in the converter's pipeline.** The check is stateless: it reads the mapping files and a pairs file and returns a decision. Production adds a reviewed mapping registry, a decision ledger and counts, all designed and none built.
- **Never silent.** A missing, empty or malformed mapping or pairs file exits 2 and fails the step. A run with no pairs says it checked only the mapping. A gap in what the messages exercised is printed, not skipped.
- **Values stay out of the output.** Findings carry field names, counts and lengths. Strings from input are escaped, so a hostile field name cannot forge an output line.
- **Changes to a rule are changes to a number.** A golden test pins the planted-set numbers, so a rule change that moves the found count shows in the diff.

**What is next.** Run it against one real mapping whose owner can share it; cross the coded fields in the probes; add the converted-back check for the ISO-to-legacy direction.

**What would have to be true before a pilot.**
- The element lengths and mandatory flags come from the bank's own message specification, not from my simplification.
- The converter runs in a test environment that can take the probe messages and write the pairs file.
- A named person owns the mapping and will record a decision for each capacity finding.
- No production message enters the check's path.
- The team agrees which level fails the step.

---

*This PRD names [36 Payment Repair](../36-payment-repair/), [53 Feature Contract](../53-feature-contract/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The folder layout follows [28 Tool Schema Drift](../28-tool-schema-drift/); the check shares no code with it.*
