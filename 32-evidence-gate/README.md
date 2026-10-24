# 🧾 Evidence Gate: no merge without the evidence the tier requires

**I wanted to know what it takes to make "we have the evidence" something a pull request has to show, not just say. This is a command-line gate and a staged GitHub Action: it reads the AI change record in a pull request description, looks up what the use case's tier requires, checks that each piece of evidence is listed, ticked, points at a file in the repository and is in date, and prints ALLOW, REVIEW or BLOCK.** It takes the tier-to-evidence table from [11 TierGate](../11-tiergate-ai-usecase-intake/) and the idea of a freshness limit from [24 PortfolioBoard](../24-portfolioboard-ai-program-portfolio/), and moves the check to the one place work cannot skip: the merge button.

**▶ Static demo, no install:** [open demo.html](./demo.html)

Tags used below: 🟢 measured (a script in this folder prints the number), 🟡 modeled (the assumption is named), 🔴 hypothetical (reasoned about, never tested).

## Run one now

```bash
cd 32-evidence-gate/src && python3 evidence_gate.py --demo
```

It prints:

```text
use case UC-003   declared tier 2   registry tier 3   bar: tier 3, 8 evidence items
  [review] tier_mismatch          the record declares tier 2 but the registry holds 'UC-003' at tier 3; the registry sets the bar
  [block ] evidence_missing       E05, E06, E07, E08 are required at tier 3 and not in the record
  [block ] stale                  E03 is 130 days old; the limit is 90
decision: BLOCK
```

Standard library only, Python 3.9 or newer. To check your own description: `python3 evidence_gate.py check --body pr_body.md --tiers tier_evidence.csv --registry registry.csv --files repo_files.txt`. It exits 1 on BLOCK, so a CI step fails; `--format github` prints annotations. The gate reads one block of the description, a use case, a declared tier and one line per evidence item:

```text
Use case: UC-014
Declared tier: 2
- [x] E01 Use-case card | ref: evidence/UC-014/E01-use-case-card.md | date: 2026-09-02
```

Text inside HTML comments and fenced code blocks is not read, so the example line in a template's comment does not count.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 107 planted pull request descriptions, 36 use cases; the script is named in brackets):

- 🟢 No gate: 0 of 107 pull requests stopped, 59 of 107 lack evidence their true tier requires, and 129 of 642 owed evidence items are missing, stale or unusable (`step_01`)
- 🟢 A check that every box is ticked passes 98 of 107, stops 8 of the 59 and lets 51 through (`step_02`)
- 🟢 The gate blocks 49 of the 59, and in all 46 blocked descriptions that have a record, the items it names are exactly the items I planted as bad (`step_04`)
- 🟢 It sends 6 of 6 wrong-tier-label pull requests to review, and allows 8 of 8 reformatted descriptions (CRLF line endings, `[X]`, bold labels) and 2 of 2 with evidence dated on its last valid day (`step_04`)
- 🟢 Take one input away from the gate and the blocked count falls: without the registry 41 of 59, without the file listing 44, without the dates 37, parser alone 24 (`step_03`)
- 🟢 A reviewer is asked to look at 16 of 107 pull requests; the author fixes the 52 that are blocked (`step_04`)
- 🟡 The freshness limits (90 days for evaluation results and CRO sign-off, 180 or 365 for the rest) are my assumptions, in [`data/tier_evidence.csv`](./data/tier_evidence.csv). The limit is inclusive: evidence dated exactly that many days before the as-of date is valid.

## What it still gets wrong

- 🟢 7 of the 59 should-block pull requests pass (`step_04` prints each). Four are a reference to a real file that holds another use case's evidence: the listing proves the file is there, not what it says. A rule that the path must contain the use case id would catch them, and I left it out on purpose, because it infers structure from a naming convention. Three are use cases the registry holds one tier too low, where the author copies the registry (PR-031, PR-034 and PR-067).
- 🟢 3 of the 59 only reach review: a use case not yet in the registry that declares a tier one below its true one. The gate cannot know the true tier, so it asks a person.
- 🟢 3 of 42 fine pull requests are blocked because the evidence is a markdown table, not the template's lines. 7 of 42 fine ones go to review: 4 with a link outside the repository and 3 new use cases that declared the right tier. I accept both costs.
- **The test set and the rules share an author.** I planted the cases and wrote the rules, and every finding kind exists because I planted a case for it, so 49 of 59 shows the rules cover what I planted. Treat it as a ceiling, not a rate on real descriptions, which I have not tested. The set is dense in problems on purpose (59 of 107 should be blocked).
- **The date is the author's claim.** The gate checks the date typed on the line, not the file's history. A stale document with a fresh date typed next to it passes.
- **Presence, not quality.** It does not open the evidence. A one-line file named `E05-independent-validation.md` passes.
- The parser is not a full markdown parser. It handles HTML comments and fenced code blocks, labelled fields and the template's line format. Tables, indented code blocks and free prose are not read.
- Evidence must be a path in the repository to be checked. A link to a wiki is only sent to review.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`, 55 tests in all across four files).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What happens when the template is only a template? | `step_01_no_gate.py` |
| 2 | What does requiring every box to be ticked catch? | `step_02_checklist_rule.py` |
| 3 | What does the gate lose when one input is taken away, and what does it still miss? | `step_03_deficiencies_exposed.py` |
| 4 | What do the parser, the tier table, the file listing and the dates catch together? | `step_04_with_gate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) is a catalogue of risks and mitigations for generative AI; its home page is marked version 2, 20 October 2025. I read the home page and the start of its mitigation list through a page fetch on 2026-10-23, and the catalogue lists preventative mitigations with identifiers such as AIR-PREV-005 (System Acceptance Testing). This gate implements none of them and does not map E01 to E11 to the framework's identifiers: that needs a read of each mitigation page and is not done. What it does is narrower. It checks that the evidence a team says it holds is attached to the change that needs it. It is a prototype, aligned to that kind of governance practice and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, bank or real repository. 🔴 A team would keep a registry current and fill the template in honestly; I have not tested either. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/tier_evidence.csv` for your own tier table and `data/registry.csv` for an export of your use-case inventory, keep the columns, and point `check` at a description file. Read the [PRD](./PRD.md) for the scope I held to.
