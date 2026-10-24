# 🗂 ATLAS Case Study: from the trace of one agent run to a draft a threat catalogue can read

**I wanted to know how much of an agent incident can be turned into a case study by rules, and what only a person can supply. This is a command-line tool that reads the trace of one run and drafts a case study in the shape the MITRE ATLAS contribution schema describes: a short procedure of steps, each with a tactic, a technique and the call numbers that back it. The actor, the reporter and the references stay marked TODO.** The trace shape follows [05 AgentWatch](../05-agentwatch-agent-observability/); the rows here are new and none are copied from it.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 62-atlas-case-study/src && python3 atlas_case_study.py --demo
```

It prints:

```text
draft: "Retry loop after an instruction-like tool response" (2026-03-24), synthetic
procedure: 3 steps: AML.T0051.001 at call 4, AML.T0029 over calls 4-61, AML.T0034 at call 61
lint: schema ok; todo fields: actor, references, reporter; identifier leaks: 0
```

Standard library only, Python 3.9 or newer. To draft from your own trace: `python3 atlas_case_study.py build bundle.json --reporter "Team A" --yaml draft.yaml --json draft.json`, then `python3 atlas_case_study.py lint draft.json --bundle bundle.json`. A bundle is one JSON file with the run, its calls and the names of the fields that hold identifiers; the shape is at the top of [`src/atlas_case_study.py`](./src/atlas_case_study.py). It exits 1 when it finds no loop, a schema problem or a leaked identifier, and 2 for input it cannot read. The draft for the demo run is staged in [`issue/case_study_draft.yaml`](./issue/case_study_draft.yaml).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 60 flagged runs and 3591 tool calls; the script is named in brackets):

- 🟢 Status quo: 0 of 60 flagged runs have a case study. 32 of the 60 were failures and the alert does not say which. A reader scans a median of 59 trace rows per run, and 45 of 60 tickets carry an identifier or a first name (`step_01_trace_as_report.py`)
- 🟢 Writing from the ticket's words drafts 34 of 60 runs: 15 of 32 failures but also 19 of 28 harmless runs. Only 6 of 34 drafts get the planted technique set, 23 of 34 carry a planted identifier or name, and 0 of 43 steps point at a call in the trace (`step_02_ticket_keywords.py`)
- 🟢 Each approach alone: the injection step is found in 1 of 10 poisoned runs from the ticket's words and in 10 of 10 from the trace shape; the trace shape misses 10 of 32 failures and the ticket's words reach 7 of those (`step_03_deficiencies_exposed.py`)
- 🟢 The loop threshold is a trade, not a setting: at 10 calls the rule drafts 27 of 32 failures and also 5 of 28 harmless runs; at 20 or 30 calls it drafts 22 of 32 and 0 of 28 (`step_03_deficiencies_exposed.py`)
- 🟢 Draft from the trace: 22 of 32 failures drafted and 0 of 28 harmless runs; 22 of 22 technique sets equal the planted set; 0 schema problems; 0 declared identifiers and 0 planted strings in the 22 drafts; a median of 2 steps (longest 3) stand for 2060 calls, and 3 fields are left for a person in each draft (`step_04_with_case_study_tool.py`)

## What it still gets wrong

- 🟢 10 of 32 failures get no draft, and `step_04_with_case_study_tool.py` prints each one. Five are retry storms cut off after a dozen or so calls (the longest same-shape run is 15 to 18 calls against a threshold of 20) and five are two tools called in turn (the longest same-shape run is 1 to 4). I left both in on purpose.
- 🟡 The threshold of 20 calls and the share of 0.9 not-ok responses are my assumptions, not values from ATLAS. In my data a short storm (12 to 18 calls) and a not-found walk (6 to 18 calls) overlap in length, so no length separates them.
- **The test set and the rules share an author.** I planted the runs and wrote the rules, so 22 of 22 shows the rules cover what I planted. Treat it as a ceiling for these rules, not a rate on real traces, which I have not tested.
- **A trace cannot show intent.** ATLAS records adversary behavior. A retry loop after a bad response and one after a poisoned record look the same in the trace except for one flag set by an upstream scanner, which I assume exists. The draft marks the actor TODO and states in `meta` that it maps effects, not an adversary action. Whether a failure with no adversary belongs in the catalogue is the maintainers' call, and the staged [issue draft](./issue/ISSUE_DRAFT.md) asks them.
- The ticket note is never copied, because notes carry names and identifiers. The cost is that the draft gives no root cause beyond what the trace shows.
- Three techniques are mapped. AI Agent Tool Data Poisoning (AML.T0099) is not, because a trace cannot show who changed a record.
- The lint applies the rules I read in the contribution schema. It is not a full JSON Schema validator and does not check the object forms of tactic and technique.
- 🔴 A synthetic run is not an incident. ATLAS case studies are real incidents or exercises, so the staged draft is a format example. I have not submitted anything, and I could not open the contribution page (see below).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What is there to work from when an alert flags a run? | `step_01_trace_as_report.py` |
| 2 | What does a draft written from the ticket's words cost? | `step_02_ticket_keywords.py` |
| 3 | Where does each approach fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What does a draft from the trace get right, and miss? | `step_04_with_case_study_tool.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

[MITRE ATLAS](https://github.com/mitre-atlas/atlas-data) case-study format. I read, on 2026-10-24: the repository README (format version 6.0.0); `dist/schemas/atlas_contribution_schema.json` and `dist/schemas/atlas_website_case_study_schema.json` (version 1.1) for the study fields, their enums and the id patterns; and `dist/v6/ATLAS-2026.09.yaml` (collection 2026.09, modified 2026-09-15) for the three techniques and two tactics used here: AML.T0029 Denial of AI Service, AML.T0034 Cost Harvesting, AML.T0051.001 Indirect (under LLM Prompt Injection), AML.TA0005 Execution and AML.TA0011 Impact. I read the long files through a fetch tool that returns summaries, so check the id mapping against the release file before you rely on it. `CONTRIBUTING.md` points to `https://atlas.mitre.org/contribute` for new content; that page returned HTTP 404 when I fetched it, so I have not read the submission steps. This is a prototype, aligned to the case-study format and not reviewed, endorsed or accepted by MITRE.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real agent. People's names in the tickets are invented first names. A prototype on synthetic data, not a production case study.

## Fork it

Export a trace from your own tracing store into the bundle shape, list your identifier fields in `identifier_keys`, and run `build`. Or swap `data/runs.csv`, `data/tool_calls.csv` and `data/truth.csv` for your own and keep the columns. Read the [PRD](./PRD.md) for the scope I held to.
