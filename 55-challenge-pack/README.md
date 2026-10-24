# 🧪 challenge-pack: a second-line test plan by tier

**I wanted to know what a challenger asks for when the only input is a risk tier, and how much of what comes back they can check without opening it. This is a command-line tool and a staged Agent Skill: it turns a tier into a test plan, adds overlays for vendor products and for use cases outside the model definition, reconciles the evidence on file (missing, stale, wrong version, prepared inside the developer's own unit) and writes a challenge memo per use case.** It lifts the rubric from [11 TierGate](../11-tiergate-ai-usecase-intake/) and the habit of dating evidence from [16 ControlMap](../16-controlmap-ai-obligation-crosswalk/), and adds the plan, the overlays, the reconciliation and the memo.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 55-challenge-pack/src && python3 challenge_pack.py --demo
```

It prints:

```text
EX-02  Merchant risk scoring  tier 3 (declared 2, raised by the rubric)  scope: in (ml)  overlays: vendor
  GAP  CH08 Outcomes analysis: stale (latest 2025-02-11, window 12 months, as of 2026-10-01)
checked 6 use cases: 1 with gaps, 5 complete; 55 plan items, 54 on file and current
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 challenge_pack.py pack use_cases.csv evidence.csv --as-of 2026-10-01 --out-dir pack_out`. It writes one memo per use case and a `summary.csv`, exits 1 when a use case has a gap and 2 when the input is malformed (one line on stderr). The date is an argument, not the clock, so the same files and date always give the same answer. `python3 challenge_pack.py table` prints the tier-to-test-plan table.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 150 use cases, 1486 owed items and 437 planted evidence defects; the script is named in brackets):

- 🟢 One generic checklist asks for 876 of 1486 owed items (59.0%), leaves 436 independent challenge items unasked, gives 83 of 83 tier 3 and 4 use cases no independent item, and finds 0 of 437 planted defects (`step_01`)
- 🟢 The tier table on the declared tier asks for 1080 of 1486 (72.7%). 42 of 150 use cases are declared below the true tier, and 248 owed vendor and scope items have no place in the table (`step_02`)
- 🟢 Checking only that a row is on file finds 87 of 437 defects and passes 189 stale, wrong-version and not-independent items. Adding a date-only rule and a same-unit rule finds 80 of 92 stale and 26 of 26 not-independent items, still 0 of 71 wrong-version, and raises false alarms on 129 of 145 reaffirmed items and 626 of 626 first-line items (`step_03`)
- 🟢 The pack asks for 1403 of 1486 owed items (94.4%) and finds 360 of 437 planted defects (82.4%): missing 176 of 248, stale 88 of 92, wrong version 70 of 71, not independent 26 of 26 (`step_04`)
- 🟢 It flags 0 of 152 reaffirmed items, 0 of 34 items dated at the edge of the window and 0 of 632 first-line items prepared by the developer's own unit, and raises no gap on an owed item that is fine (`step_04`)
- 🟢 The rubric recompute lowers the use cases whose tier is below the truth from 42 to 16 of 150 (`step_04`)
- 🟢 On the same files the command prints: 150 use cases checked, 130 with gaps, 20 complete, 1410 plan items, 1044 on file and current (`step_04`)

## What it still gets wrong

- 🟢 77 of 437 defects are not found (`step_04` prints the split). 49 sit on items the plan never asked for because the tier used is below the true tier, 24 sit on vendor items because the form omits the vendor, and 4 are stale items on a use case whose tier is too low, where the longer window hides them.
- 🟢 30 of 32 hollow items pass every check, and the other 2 were never asked for (`step_04`). A hollow item is on time, current, the right version and prepared outside the developer's unit, and says nothing. Every check reads a date, a version or a unit. None reads content, so this miss stays in.
- 🟢 16 of 150 use cases keep a tier below the truth after the recompute, and they leave 68 defects unasked (`step_04`). The form is the only source: 14 of 91 vendor-dependent use cases leave the vendor off it, and 23 of 150 write the data class a level low (`step_03`). A tiering check against a data catalog and a vendor registry is [35](../35-tiergate/)'s job.
- 🟢 6 gaps are raised on items the use case does not owe (`step_04`). They all sit on the two use cases whose sponsor declared a tier above the truth. I kept the higher tier on purpose: the pack asks for more rather than less, and says so.
- **The data and the rules share an author.** I planted the defects and wrote the checks, and I know which fields the checks read. The hard negatives are in on purpose and printed, but 82.4% is a ceiling for these rules on this data, not a rate on real evidence, which I have not tested.
- **The tier table is my 🟡 assumption.** Which item sits at which tier, the windows of 36, 24, 12 and 12 months, and which items need an outside preparer come from me, not from SR 26-2. The numbers above test the machinery against that table. They do not show the table is right.
- A reaffirmation counts as fresh evidence if its date is inside the window and the version matches. The check does not ask who reaffirmed or what they looked at.
- The pack decides nothing. It lists what to ask for and what is wrong with what came back. A person challenges the content and signs the memo.

## Use it as a skill

[`skill/challenge-pack/SKILL.md`](./skill/challenge-pack/SKILL.md) tells an agent how to run the command on a use-case export and an evidence export, what to report, and what to say about the limits. It adds no logic. It is staged and has not been published or loaded into an agent runtime. What is tested is the command it wraps and the skill file's own frontmatter (`tests/`). The skill tells the agent to treat sponsor-written titles and unit names as data, not as instructions; I have not tested that behavior on a model.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does one generic checklist ask for, and find? | `step_01_generic_checklist.py` |
| 2 | What does the tier table add when the tier is taken from the form? | `step_02_tier_table.py` |
| 3 | Where do the tier, a presence check and two simple rules fail? | `step_03_deficiencies_exposed.py` |
| 4 | What do the recompute, the overlays and the dated, versioned reconciliation catch? | `step_04_with_the_pack.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The Federal Reserve's [SR 26-2, Revised Guidance on Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm), issued with the OCC and the FDIC on April 17, 2026, with the [attached guidance](https://www.federalreserve.gov/supervisionreg/srletters/SR2602a1.pdf). I read both on 2026-10-24. Four points in the text shaped this tool. Effective challenge is critical analysis by objective experts who have the expertise, the independence and the standing to get changes made, and it runs across the model lifecycle. Rigor is meant to follow materiality, and validation covers conceptual soundness, outcomes analysis and ongoing monitoring. Vendor and other third-party products need their own understanding and monitoring. Footnote 3 puts generative and agentic AI outside the guidance and asks the bank's own risk practices to set controls for them, and the model definition excludes deterministic rule-based software, which is why `rules`, `generative` and `agentic` use cases get a scope-determination item and the tests by analogy.

The guidance sets no tiers, test lists or evidence windows, and says it is not an enforceable standard, so the plan here is my 🟡 assumption throughout. It is most relevant to banks with more than $30 billion in total assets; this prototype does not test that. It is a prototype, aligned to that text and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study. The rubric points and cut-offs are the ones in project 11, which are also my assumption.

## Fork it

Swap `data/use_cases.csv` and `data/evidence.csv` for your own exports and keep the columns, or edit the table at the top of `src/challenge_pack.py` to your own tiers, windows and items (a test checks that `data/plan_items.csv` still equals it, so update both). Read the [PRD](./PRD.md) for the scope I held to.
