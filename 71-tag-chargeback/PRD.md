# PRD: tag-chargeback (cost allocation check)

**Author:** Vijay Saharan, Sr PM
**Stage:** Portfolio prototype
**Date:** 2026-Q4

> **Framing:** This PRD is the product I would bring to a cloud finance review. It is not a record of a PRD landed at a named bank. The rules, the defects planted in the bill and the rollout plan are mine; the numbers are measured on synthetic data I generated, or modeled with the assumption named. RICE scores and rollout durations below are planning estimates (🔴), not measurements. Nothing here is deployed, load-tested or used by anyone.

---

## 1-page PRD (the version that goes on the wall)

| Field | Value |
| --- | --- |
| **Product** | tag-chargeback: a command-line tool that reads a billing export, a cost-center registry, an account map and a tag policy, allocates each line by rule, reports tag compliance and lists the spend nobody owns |
| **Owner** | The cloud finance lead who produces the monthly chargeback, with the platform lead as co-owner of the tag policy |
| **Stage** | Portfolio prototype on synthetic data; no model, no hosted service |
| **Primary user** | The person in cloud finance who produces the monthly chargeback |
| **Secondary users** | The platform engineer who is asked to fix the tags; cost-center owners who are charged; internal audit |
| **Problem** | A cloud bill arrives by account and by service. A bank wants it by cost center, and the only evidence of who owns a line is a tag someone typed. Some tags are missing, some are misspelled, some name a cost center that no longer exists, and some are valid and wrong. A report that groups by the tag as written looks complete and leaves money with no one to bill. In the planted bill, 🟢 grouping by the tag as written puts 64.0% of net spend on the owner and leaves 23.1% as "Unallocated" (`step_02_exact_tag_report.py`). |
| **Solution** | Reads a billing export, a cost-center registry, an account map and a tag policy. Allocates each line by rule: tag, shared-service split, inherit from the same resource, account default. A tag that is present and bad is refused, not overridden. Reports tag compliance twice, strict and after alias and format repair. Prints the unallocated spend by reason and the largest unallocated resources, and exits 1 above a limit. |
| **North-star metric** | Share of net cloud spend allocated to an active cost center by a named rule, with the unallocated share at or under the policy limit and every line reconciled to the bill. Target 🔴 at or under the limit every month. Today in this model: nothing tests whether the tags can be trusted. |
| **Measured metrics (synthetic)** | 🟢 89.9% of net spend on the planted owner against 64.0% for a plain tag report; 4.8% on the wrong team; 5.2% left for a person; allocated plus unallocated equals the bill to the cent (`step_04_with_tool.py`, `step_02_exact_tag_report.py`). |
| **Modeled metrics** | 🟡 Utility (89.9% − 64.0%) × $10,000,000 = $2,590,000 a year of cloud spend placed on the owner that a plain tag report would not, assuming $10,000,000 of annual cloud spend goes through the chargeback. |
| **Cost** | 🔴 Not estimated. The prototype is standard-library Python with no model call; the cost of the production pieces and of the people who clear the unallocated list has not been sized. |
| **Risk #1** | The planted data and the rules share an author, so the numbers are a ceiling. The mix of defects is my guess. Mitigation: run it on one real export the owner may share, next to the current chargeback, and report the planted numbers and the real numbers apart. |
| **Risk #2** | Wrong dollars rise when coverage rises, and the account default is the least reliable rule. 🟢 Wrong spend goes from 3.7% to 4.8%, and the account default places $59,311.25, of which 28.1% belongs to another team (`step_02_exact_tag_report.py`, `step_03_deficiencies_exposed.py`). Mitigation: the account default runs last, and the policy can switch it off. |
| **Risk #3** | A valid tag for the wrong cost center is charged as tagged, and no tag check can see it. 🟢 24 lines ($20,618.63) in the planted bill (`step_04_with_tool.py`). Mitigation: the report names the number, and a check against an application-owner list is queued. |
| **Out of scope** | Fetching a real bill; amortizing commitments; forecasting; choosing a shared-cost basis for the user; any model call; hosting. |

---

## RICE-prioritized backlog

> Scoring: Reach (R) × Impact (I) × Confidence (C) / Effort (E). Reach is cost centers, accounts or lines, as labeled. Effort in PM-weeks. All scores are 🔴 planning estimates. The top of the list is what gets built first. Status says "Built in prototype" only for what the code does.

| Rank | Item | R | I | C | E | RICE | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Input validation and exact money** (a bad column, date, amount or tag JSON exits 2; integer millionths so the totals reconcile) | 14 cost centers | 3 | 0.9 | 1 | 37.8 | Built in prototype |
| 2 | **Tag rule with alias and format repair** (a present but bad tag is refused, not overridden) | 14 cost centers | 3 | 0.9 | 1 | 37.8 | Built in prototype |
| 3 | **Unallocated report by reason, largest resources and an exit code above the limit** | 14 cost centers | 2 | 0.8 | 1 | 22.4 | Built in prototype |
| 4 | **Tag compliance, strict and after repair** | 14 cost centers | 2 | 0.8 | 1 | 22.4 | Built in prototype |
| 5 | **Shared-service split in proportion to the other allocations** | 14 cost centers | 2 | 0.7 | 1 | 19.6 | Built in prototype |
| 6 | **CI output** (text and GitHub annotations, escaped strings, chargeback and line CSVs) | 14 cost centers | 1 | 0.9 | 1 | 12.6 | Built in prototype |
| 7 | **Account default for a dedicated account, last in order** | 12 accounts | 2 | 0.5 | 1 | 12.0 | Built in prototype |
| 8 | **Inherit from the same resource when its tagged lines agree** | 14 cost centers | 1 | 0.7 | 1 | 9.8 | Built in prototype |
| 9 | **Successor field so a closed cost center suggests its replacement** | 32 lines | 1 | 0.5 | 2 | 8.0 | Sequenced for v0.2 |
| 10 | **Shared-cost basis chosen in the policy** | 16 lines | 2 | 0.5 | 2 | 8.0 | Sequenced for v0.2 |
| 11 | **Check a valid tag against an application-owner list** (closes the wrong-valid miss) | 24 lines | 3 | 0.4 | 5 | 5.8 | Queued |
| 12 | **Monthly run record** (file hashes, policy version, totals, unallocated share) | 14 cost centers | 2 | 0.6 | 4 | 4.2 | Queued |

---

## Stakeholder map

| Stakeholder | Role | What they want from tag-chargeback | What they fear |
| --- | --- | --- | --- |
| **Cloud finance lead** | Owner and primary user | A chargeback that adds up to the bill to the cent and a short list of what is left. | A number a cost-center owner can take apart in one meeting. |
| **Platform engineer** | Fixes the tags | A ranked list of resources and the reason each is unallocated, so one fix clears the most dollars. | A flat list of bad tags with no dollars on it. |
| **Cost-center owner** | Charged | Charges that match what their teams run, and a clear route to dispute one. | Paying for another team's untagged resource. |
| **Controller** | Approver of the method | A written rule order and a shared-cost basis that finance has signed. | A split basis changed quietly between two months. |
| **Application owner** | Consulted | The tag on their resources read the way they wrote it. | A tag they typed refused for a case or a space. |
| **Security / CISO** | Approver | Bill data kept inside the boundary and hostile strings kept out of logs. | Resource names and account ids copied into a tool outside the platform. |
| **Internal audit** | Reader | A path from a charge to the line, the rule and the policy version that placed it. | A policy changed after the month closed. |

---

## User stories (top 4)

1. **As the cloud finance lead**, I want every line allocated by a named rule or listed as unallocated with a reason, so the chargeback adds up to the bill and I can explain each charge.
2. **As a platform engineer**, I want the largest unallocated resources and the reason for each, so I fix the tags that clear the most money first.
3. **As a cost-center owner**, I want a tag that is present but wrong to be refused and not overridden by a default, so I am not charged by a guess when the tag says otherwise.
4. **As internal audit**, I want each charge tied to the rule and the policy that produced it, so I can reproduce a month later.

---

## KPIs

**North star:** share of net cloud spend allocated to an active cost center by a named rule, with the unallocated share at or under the policy limit and every line reconciled to the bill. Target 🔴 at or under the limit every month.

**Inputs (leading):**
- Tag compliance. 🟢 630 of 1244 lines carry every required tag written exactly (63.1% of dollars) and 694 of 1244 after alias and format repair (74.3%) (`step_04_with_tool.py`).
- Cost centers in the registry with an owner and an active flag (the prototype has 🟢 14 cost centers, two of them closed, from `data/README.md`).
- Accounts mapped (the prototype has 🟢 12 accounts: 8 dedicated to one cost center each, 4 shared with no default, from `data/README.md`).
- Aliases and shared services named in the policy.

**Outputs (lagging):** prototype baselines from the planted bill.
- Spend on the planted owner. 🟢 $702,526.86 (89.9%) with the tool, against $499,835.82 (64.0%) for a plain tag report (`step_04_with_tool.py`, `step_02_exact_tag_report.py`).
- Spend on the wrong team. 🟢 $37,705.69 (4.8%) (`step_04_with_tool.py`).
- Left for a person. 🟢 $40,880.75 (5.2%), against a limit of 10.0% (`step_04_with_tool.py`).
- Known misses. 🟢 24 lines ($20,618.63) with a valid tag for the wrong cost center, and 36 lines ($16,460.42) in the wrong team's account (`step_04_with_tool.py`).
- Disputed charges after a month closes: not measured; the planted bill has no cost-center owner.

---

## Rollout

| Phase | Duration (🔴 planning estimate) | Scope |
| --- | --- | --- |
| 0: Shadow | 4w | Run the tool on one real billing month next to the current chargeback. Publish nothing, and compare the two by cost center. |
| 1: Calibration | 4w | Set the aliases, the shared services, the unallocated limit and the shared-cost basis with finance and platform. Decide whether the account default stays on. |
| 2: Publish the unallocated list | 6w | Send platform teams the ranked list each month. The chargeback is still produced the old way. |
| 3: Chargeback from the tool | 6w | The tool produces the monthly chargeback. A month over the limit fails the pipeline step. |
| 4: Run record and owner check | 8w | Write a record per month. Add the successor field and the application-owner check. Test the designed interlocks named in the ARCHITECTURE doc. |

---

## Open questions

1. **Should the account default stay on?** It lifts correct spend to 83.6% in the step-3 table and places $59,311.25, of which 28.1% belongs to another team. Recommendation: keep it on for the pilot and last in order, report its dollars on their own line, and let finance switch it off if wrong-team charges cost more than unallocated spend.
2. **What basis should shared services use?** The prototype splits in proportion to what the other rules allocated, which is my choice. Recommendation: keep it for the pilot, put the basis in the policy, and have the controller sign it before any month is published.
3. **Who confirms a valid tag for the wrong cost center?** No tag check can see it, and the tool charges all 24 of those lines as tagged. Recommendation: queue an application-owner list as the cross-check and name the number in every report until it exists.
4. **Is 10.0% the right unallocated limit?** It is mine and not tuned on a real bill. Recommendation: set it against what a person can clear in a month, after the shadow phase.

---

## Build and scale notes

**Reference architecture.** See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full systems doc. Headlines:

- **One monthly batch job.** The tool is stateless: it reads four files and returns a chargeback and an unallocated list. Production adds a billing feed, a reviewed policy, a run record and telemetry, all designed and none built.
- **Never silent.** A missing, empty or malformed file, a bill that spans months or an amount with too many decimals exits 2. Accounts missing from the map are named in the report, and a tag that cannot be placed becomes an unallocated line with a reason, not a quiet default.
- **Strings from input are data.** Resource names and tag values are escaped before they reach a log or a workflow command.
- **Changes to a rule are changes to a number.** A golden test pins the planted-bill numbers, so a rule change that moves a dollar shows in the diff.

**What is next.** Run it on one real export the owner may share; add a successor field so a closed cost center can suggest its replacement; let the shared-cost basis be chosen in the policy.

**What would have to be true before a pilot.**
- One real billing month the owner can share, with the registry and the account map.
- A controller who has agreed the rule order and the shared-cost basis.
- A platform lead who will work the unallocated list each month.
- A decision on whether the account default stays on.
- The team agrees which unallocated share fails the step.

---

*This PRD names [07 InferenceLens](../07-inferencelens-inference-finops/), [12 ValueLedger](../12-valueledger-ai-benefit-tracking/), [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/) and [09 LineageLog](../09-lineagelog-ai-decision-audit/) as designed interlocks (🔴 designed, none built). The idea of per-owner spend attribution comes from 07; no code or data was imported.*
