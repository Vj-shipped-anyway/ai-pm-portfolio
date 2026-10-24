# 🔗 aigf-checks: from a framework risk to a check you can run

**I wanted to know what it takes for one line in a crosswalk, "this check covers this framework risk", to stay true after the check changes. This is a command-line tool: it reads a crosswalk of risks to runnable checks, the registry of those checks and the text each one printed, and reports the rows that no longer hold. It is built to back a contribution to the [FINOS AI Governance Framework](https://air-governance-framework.finos.org/): five risks mapped to checks in this portfolio, drafted as an issue and a pull request that I have not opened.** It moves the crosswalk idea from [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), obligations to controls, to framework risks to checks that print a number.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 56-aigf-checks/src && python3 aigf_checks.py --demo
```

It prints:

```text
crosswalk: 5 rows, 4 risks, 3 checks; claims compared: 5
  ROW-2  R-02 -> C-01  stale_value       'retrieved cases caught' claimed 17 of 20, the check prints 15 of 20
  ROW-3  R-09 -> C-08  overclaim_wording the note says 'Compliant'; say 'aligned to' instead
  ROW-4  R-15 -> C-13  aspect_gap        marked full but C-13 does not exercise approval_step
  ROW-5  R-01 -> C-01  duplicate_row     same risk, check and claim label as ROW-1
risk status: R-01 CHECKED, R-02 UNVERIFIED, R-09 CHECKED, R-15 PARTIAL
result: 4 findings in 4 of 5 rows
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 aigf_checks.py check risks.csv checks.csv crosswalk.csv outputs.json`. It exits 1 when a row has a finding, 2 when an input cannot be read; `--format github` prints annotations. `python3 aigf_checks.py signoff message.txt` checks a commit message for a `Signed-off-by` line and a subject of 72 characters or fewer.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 24 risks, 20 checks and 73 crosswalk rows with planted defects; the script is named in brackets):

- 🟢 No re-check: the sheet flags 0 of 73 rows, 45 of 73 carry a planted defect, and a reader who trusts every full row calls 20 of 24 risks covered where 16 are (`step_01`)
- 🟢 Resolve the ids and grep for the number: 11 of 45 defective rows found, 6 of 28 harmless rows flagged (all 6 reformatted outputs), 18 of 24 risks given the right status (`step_02`)
- 🟢 Where grep fails: 5 of 10 stale rows pass because a short number sits inside a longer one, 4 of 4 rows pass whose label is gone, 4 of 4 pass whose check has no output, 7 of 7 pass that are marked full against a check covering part of the risk (`step_03`)
- 🟢 With `aigf_checks.py`: 38 of 45 defective rows found, 0 of 28 harmless rows flagged, 23 of 24 risk statuses right, and a person reads 38 of 73 rows (`step_04`)
- 🟢 Hard negatives that could have raised a false alarm: 0 of 6 reformatted outputs, 0 of 3 notes that say "non-compliant", 0 of 5 honest partial rows (`step_04`)

## What it still gets wrong

- 🟢 7 of 45 defective rows still pass (`step_04` prints each one). Three are notes that overclaim in words the rule does not list ("fully satisfies the requirement"). Four are rows whose registry entry declares an aspect the check does not exercise: the tool takes the declared aspects as written and never reads the check. One of them leaves R-18 shown as CHECKED where the planted truth is PARTIAL.
- **The data and the rules share an author.** I planted the defects and wrote the rules, so 38 of 45 shows the rules cover what I planted. A real crosswalk will not hold 45 defective rows in 73, and its defects will not be the ones I thought of. Treat the result as a ceiling for these rules, not a rate.
- **It compares text, not meaning.** A check that keeps its label and starts measuring something else passes. If a check prints one label twice, the tool reads the first line; I planted no such case.
- **It does not run the check.** It compares a claim with a capture the contributor supplies. A stale capture gives a stale pass, so the capture should be regenerated in the same CI job that runs the tool.
- **Aspects are a judgment.** For the synthetic risks I wrote the aspects. For a real framework entry, a person would read the risk text and decide what a check has to exercise; the tool cannot do that.
- The sign-off lint checks the form of the line and the subject length. It does not check that the address is the author's, or that the subject is in the imperative mood.

## The contribution this was built for

I read the [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) on 2026-10-24: the home page (it shows v2, October 20, 2025), the [repository](https://github.com/finos/ai-governance-framework) (licence CC BY 4.0), its [contribution guide](https://github.com/finos/ai-governance-framework/blob/main/CONTRIBUTING.md) and the entries for the five risks below in [`docs/_risks`](https://github.com/finos/ai-governance-framework/tree/main/docs/_risks). The guide asks for small commits, a subject line of 72 characters or fewer in the imperative mood, issues on the project's issue page, and a `Signed-off-by` line on every commit (`git commit -s`).

The idea is one runnable check per risk, with the command, what it covers and what it does not. The five mappings I would offer first, all 🔴 hypothetical: no maintainer has read them, and the covered and not-covered columns are my reading of each risk entry and each project's README. I listed the paths by hand and did not rerun the commands for this folder.

| AIGF risk | Check in this portfolio | What it covers | What it does not |
|---|---|---|---|
| `ri-4` Hallucination and Inaccurate Outputs (OP) | [41 narrative-trace](../41-narrative-trace/): `cd 41-narrative-trace/src && python3 narrative_trace.py --demo` | Traces each sentence of a generated narrative that cites a transaction and compares the figures it states with the record | Sentences with no citation; claims that are not about a transaction |
| `ri-5` Foundation Model Versioning (OP) | [47 swapbrief](../47-swapbrief/): `cd 47-swapbrief/src && python3 swapbrief.py --demo` | Compares a retiring and a successor model on the team's own results and prices before a move | It reads two files you supply; it does not detect that a provider changed a model |
| `ri-10` Prompt Injection (SEC) | [38 injection-pack](../38-injection-pack/): `cd 38-injection-pack/src && python3 injection_pack.py --demo` | Replays a pack of injection cases, many hidden in retrieved documents, on the old and new rules of a gateway | A real model; attack kinds the pack does not contain |
| `ri-24` Agent Action Authorization Bypass (SEC) | [23 scopekeeper](../23-scopekeeper-agent-permission-review/): `cd 23-scopekeeper-agent-permission-review/src && python3 step_04_with_scopekeeper.py` | Diffs the permissions an agent holds against the ones it used and proposes a least-privilege set | Its README names scope; I have not tested it on call chaining or skipped approval steps |
| `ri-26` MCP Server Supply Chain Compromise (SEC) | [28 tool-schema-drift](../28-tool-schema-drift/): `cd 28-tool-schema-drift/src && python3 tool_schema_drift.py --demo` | Compares two revisions of a tool schema and replays recorded calls against the new one | Reading a description for malicious instructions, intercepted connections, a server taking data |

The issue and the pull request are drafted in [`contribution/ISSUE_DRAFT.md`](./contribution/ISSUE_DRAFT.md) and [`contribution/PR_DRAFT.md`](./contribution/PR_DRAFT.md). Neither has been opened. The pull request waits for a maintainer's answer on where such a table belongs.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a reader believe when nothing re-checks the rows? | `step_01_no_recheck.py` |
| 2 | What does resolving the ids and grepping for the number catch? | `step_02_link_and_grep.py` |
| 3 | Where does that fail, and what does the fix still miss? | `step_03_deficiencies_exposed.py` |
| 4 | What do labelled claims, aspects and notes catch together? | `step_04_with_checks.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. `tests/` holds 42 tests, including one that pins these numbers.

## Aligned to

The [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) risk entries named above, as read on 2026-10-24, and its contribution guide. The status words come from [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), changed to fit a risk and a check; nothing is imported from that folder. [39 Claims Check](../39-claims-check/) ties the numbers in a README to a script's output; this tool does the same for a crosswalk row and adds the risk-level view. It is a prototype, aligned to that framework. It makes no claim of conformity to it and is not endorsed by FINOS.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. The 24 risks are paraphrases written for this exercise, not the text of any framework entry, and the 20 checks and their printed output are invented. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study.

## Fork it

Keep the columns and swap in your own files: `risks.csv` (`risk_id`, `title`, `aspects`), `checks.csv` (`check_id`, `project`, `command`, `exercises`), `crosswalk.csv` (`row_id`, `risk_id`, `check_id`, `covers`, `claim_label`, `claim_value`, `note`) and `outputs.json` (the text each check printed, by `check_id`). In CI, run the checks, save their output into `outputs.json`, then run `python3 aigf_checks.py check ... --format github`. Read the [PRD](./PRD.md) for the scope I held to.
