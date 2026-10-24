# 🏷️ Intake Tier Action: an issue form that recomputes its own risk tier

**I wanted to know what happens when AI intake lives in a GitHub issue form and a workflow, not the sponsor, decides the tier label. This is a command-line tool and a staged GitHub Action: it reads the issue body by the form's headings, recomputes the tier from six answers, checks two of them against a data catalog and a vendor registry, and says which labels to set and which stale ones to remove. If it cannot read the body, it says so and sets no tier.** It extends the rubric from [11 TierGate](../11-tiergate-ai-usecase-intake/) to a form that GitHub renders and a workflow that can be re-run on every edit.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 31-intake-tier-action/src && python3 intake_tier_action.py --demo
```

It prints:

```text
issue 301: 10 of 10 form fields read, 0 problems
declared tier 2 -> recomputed tier 3 (9 points)
  DATA_CLASS_BELOW_CATALOG   form says internal; the catalog records confidential for `d_card_disputes`; using confidential
  CUSTOMER_FACING_AMBIGUOUS  customer-facing answer is 'unsure'; treated as customer-facing until the sponsor confirms
  TIER_DECLARED_BELOW        sponsor declared tier 2; the rubric on the checked inputs gives tier 3 (9 points)
  note: the registry has no entry for issue 301
labels: add ai-tier:3, tier-mismatch; remove ai-tier:2
decision: TIERED
```

Standard library only, Python 3.9 or newer. To check your own issue: `python3 intake_tier_action.py check body.md --catalog catalog.csv --labels labels.json --out-dir out/`. Use `-` in place of `body.md` to read the body from standard input.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 160 planted intake issues; the script is named in brackets):

- 🟢 Declared tier as the label: 103 of 151 readable declared tiers equal the reference tier, and 21 of 55 tier 3-4 issues are declared at tier 1-2 (`step_01`)
- 🟢 Issue form plus a regex: 124 of 160 tiers equal the reference, 18 of 57 tier 3-4 issues get tier 1-2, and 14 of 160 bodies with a required input missing still get a tier label (`step_02`)
- 🟢 Seven named deficiencies of that workflow, each counted: a pasted heading is read as the answer on 4 of 4 bodies, 8 of 24 edited issues end with two tier labels, 184 comments are posted for 160 issues, and 5 of 160 bodies carry a line that starts with `::` (`step_03`)
- 🟢 This tool: 142 of 160 issues tiered and 18 sent to needs-info; 129 of 160 tiers equal the reference (124 for the regex), 129 of 142 among the tiered; 46 of 57 tier 3-4 issues found, 4 put at tier 1-2, 7 sent to needs-info (`step_04`)
- 🟢 Labels and comments: after 24 edits every one of 160 issues carries exactly one tier-or-needs-info label, the unrelated label is kept on 160 of 160, and edited issues that match the reference go from 14 of 24 to 24 of 24 (`step_04`)
- 🟢 Hostile text: 0 workflow commands forged in the log and 0 of 160 comments echo a mention, tag, link or command, across 9 bodies that carry such lines (`step_04`)
- 🟢 Hard negatives that could have raised false alarms: needs-info on 0 of 13 intact bodies with odd case or padding and 0 of 16 with Windows line endings; DATA_CLASS_ABOVE_CATALOG raised 12 times and the tier stayed at the form's class (`step_04`)

## What it still gets wrong

- 🟢 **The known limit.** 11 issues are tiered with a data class below the true class, because the form and the catalog both understate it (8) or the sponsor left the dataset blank (3). The tier is wrong on 2 of them, issues 141 and 155 (`step_03` and `step_04` print them). The bands are four points wide, so one point of data class often does not change the tier, which is why 2 and not 11.
- 🟢 **Six tiers too high, seven too low.** The 13 misses have these causes, and one issue can have more than one: 6 treat a blank or unsure customer-facing answer as customer-facing when it was not (the flag was raised 13 times and 2 were right), 4 have a vendor left off the form that the registry does not list, 2 have a customer-facing "no" that was wrong, 2 have a data class below the true class, and 1 has a catalog that overstates the class (`step_04`).
- 🟢 **The text cue is a weak signal.** A summary that mentions a customer while the form says "no" raised a flag 33 times and 3 were truly customer-facing. My first version let the cue raise the tier; I changed it to a flag only, so it does not move the tier (`step_04`).
- 🟢 **Strict reading costs a look.** 7 of 57 tier 3-4 issues get no tier until the sponsor fixes the form, and 4 complete forms are sent to needs-info only because a pasted block repeats a heading (`step_04`). I chose that over guessing which answer counts.
- **The test set and the rules share an author.** I wrote the generator and the rules, so the numbers above are a ceiling for these rules on this data, not a rate on real intake. The mention rates, error rates and the 4% of bodies that arrive with no form are parameters I picked.
- 🟡 **The rubric is mine.** The points per answer and the cut-offs (tier = min(4, 1 + points // 4)) are an assumption carried over from project 11. The same goes for the evidence list in the comment. Neither comes from a framework.
- 🟡 **The body format is from memory.** The parser expects `### label`, a blank line, then the answer, and `_No response_` for an empty optional field. I did not verify this against a real GitHub issue. If the format differs, the tool sends the issue to needs-info and names the heading it could not find; it does not guess.
- 🟡 **The registry is keyed by issue number**, which assumes procurement files its vendor decisions against the intake issue. That is an invented export.
- Not supported: checkboxes, several catalogs, headings in another language, a form that changes its labels between versions. The unit of work is one issue body.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action, the issue form it reads, an example workflow and the steps to publish it from its own repository. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`) and that the staged files agree with the tool (`tests/test_action.py`).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the declared tier as a label get right? | `step_01_declared_label.py` |
| 2 | What does an issue form and a regex add? | `step_02_form_and_regex.py` |
| 3 | Where does that workflow break? | `step_03_deficiencies_exposed.py` |
| 4 | What do strict reading, cross-checks and label reconciliation fix? | `step_04_with_action.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) (version 2, 20 October 2025; I read it on 23 October 2026) is a catalogue of risks and mitigations for generative AI in financial services. Its [heuristic risk identification page](https://air-governance-framework.finos.org/heuristic-assessment.html) asks, before deployment, about the use case and who is affected, the sensitivity of the data, where the model comes from (third party, self-hosted or in-house), whether the output is advisory or automated, and which regulations apply, and it suggests a Low, Medium or High rating. The page does not define fixed tiers or scores. This form turns five of those questions and an exposure band into dropdowns and adds a point rubric of my own, so the tier numbers are mine, not FINOS's. I read the heuristic page and the start of the front page through a fetch tool, not the full catalogue. This is a prototype, aligned to that framework's questions and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank, and no real company appears. A prototype on synthetic data, not a production case study. The data README lists every error parameter.

## Fork it

Swap `data/issues.csv`, `data/catalog.csv` and `data/registry.csv` for exports of your own issues and keep the columns, or skip the data and point `check` at one issue body. Change the headings in `FIELDS` to match your form. Read the [PRD](./PRD.md) for the scope I held to.
