# 🗺️ TPRM Gap Map: what the proposed third-party guidance prompts for an AI-enabled vendor

**I read the proposed interagency third-party risk management (TPRM) guidance (released 2026-09-11) to see what it asks a bank to hold on an AI-enabled vendor. This prototype maps each stage of the text to that evidence, then tests four AI-specific characteristics against a simulated incident log, because the agencies ask which characteristics should mark a relationship as high risk.** It extends [18 VendorLens](../18-vendorlens-ai-vendor-due-diligence/).

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 29-tprm-gap-map/src && python3 tprm_gap_map.py --demo
```

It prints:

```text
vendors: 60   AI-enabled: 22
HIGH under the text's examples: 30   with AI characteristics added: 41
upstream concentration (share of the service type's activity): P1 (ai_enabled_service) 62%, P2 (ai_enabled_service) 27%, P3 (ai_enabled_service) 8%, P4 (ai_enabled_service) 4%, C1 (cloud_hosting) 50%, C2 (cloud_hosting) 30%, C3 (cloud_hosting) 20%
candidate characteristic: vendors with it, of which had a material incident
  concentrated_upstream: 14, 8
  no_model_change_notice: 10, 7
  trains_on_bank_data: 4, 3
  long_data_retention: 11, 8
material incident in the log: 24 vendors
text examples catch 17 of 24; with AI characteristics 22 of 24
```

Standard library only, Python 3.9 or newer. `python3 tprm_gap_map.py map` prints the guidance map. `python3 tprm_gap_map.py tier vendors.csv --incidents log.csv` runs the same test on your own files (columns in [data/README.md](./data/README.md)).

## What I found in the text

The text is principles-based and says it is non-enforceable. It names the stages a bank would expect (identification, risk assessment, due diligence, contract, monitoring, termination, subcontractors, resilience, residual risk, governance), and most of them can hold an AI-enabled vendor without change. Two things stand out:

- I extracted the text from the agencies' PDF on 2026-10-22 and counted AI wording with `python3 tprm_gap_map.py terms TEXT_FILE`. It read 8,926 words and found 0 occurrences of artificial intelligence, machine learning, generative, algorithm, large language model, neural, LLM or AI. Reproduce it from the [OCC copy](https://www.occ.gov/news-issuances/news-releases/2026/nr-ia-2026-77a.pdf) and any PDF-to-text tool.
- The agencies ask commenters whether a list of characteristics that generally indicate high risk would help, and which to include. The text's own examples are service types (core processing, cloud processing, cloud storage, compliance tools, fintech partners) and share of business.

[`data/guidance_map.csv`](./data/guidance_map.csv) has 16 rows. Two are marked "not mentioned": AI-specific high-risk characteristics, and AI evidence in due diligence. Concentration is covered inside one third party; several vendors sharing one upstream provider is not named. The map classifies each stage as named, principle, example or not mentioned, with the section of the proposal.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 60 vendors and a simulated 36-month incident log; the script is named in brackets):

- 🟢 A due-diligence questionnaire passes 36 of 60 vendors, and 16 of those passes had a material incident (`step_01`)
- 🟢 The text's own examples mark 30 of 60 vendors HIGH and catch 17 of the 24 vendors with a material incident; all 7 misses are AI-enabled services, and there are 13 false alarms (`step_02`)
- 🟢 One upstream model provider carries 61.6% of AI-enabled activity across 14 of 22 AI-enabled vendors, and a single outage there reached all 14 at once (`step_03`)
- 🟢 Adding four AI-specific characteristics marks 41 of 60 HIGH and catches 22 of 24, with 19 false alarms against 13 (`step_04`)
- 🟢 Added alone to the text's examples, long data retention catches 22 of 24 with 16 false alarms; no notice before a model change catches 20 with 16; training on bank data catches 20 with 14 (`step_04`)

## What it still gets wrong

- **The incident log is simulated from hazard rates I chose before the first run** (`data/_generate.py`). Change them and every number moves. The result shows how to test a characteristic against a log, not how often real vendors fail.
- 🟢 Two material-incident vendors stay LOWER with the AI characteristics added (`step_04` prints V011 and V039).
- More flags mean more false alarms: 19 against 13. A reviewer reads 41 vendors instead of 30.
- The concentration threshold of 30% is a choice. At 20% the catch is 23 of 24; at 30% and 50% it is 22 of 24, because only one provider sits above 30% (`step_04`).
- The map is my reading of one proposed text. It is a proposal, it may change, and the classification of each row is a judgment. It is not legal advice and it says nothing about what an examiner will expect.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the questionnaire alone say? | `step_01_due_diligence_only.py` |
| 2 | What do the text's own examples catch? | `step_02_text_examples.py` |
| 3 | What do they miss, and what do the misses share? | `step_03_deficiencies_exposed.py` |
| 4 | What changes with four AI-specific characteristics? | `step_04_with_ai_fields.py` |

Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms a rerun reproduces every file and that the green numbers above appear in a script's output. [PRD](./PRD.md).

## Aligned to

The proposed interagency third-party risk management guidance, docket OCC-2026-0793, as released 2026-09-11 for comment. A prototype aligned to a proposal, not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, bank or real vendor. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/vendors.csv` and `data/incident_log.csv` with your own exports and keep the columns. The useful output is the table of how many vendors with each characteristic had a material incident.
