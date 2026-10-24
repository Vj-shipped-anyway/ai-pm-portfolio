# 🚦 TierGate Intake Check: recompute the tier a sponsor declared

**I wanted to know how far a sponsor's own risk tier can be trusted at the front door of AI governance, and what a reviewer can recompute in a minute from files that already exist. This is a command-line check and a staged Agent Skill: it reads an intake CSV, recomputes the tier with a written rubric, cross-checks the data class against the data catalog and the vendor model against the vendor registry, and lists every form declared below its recomputed tier.** It lifts the recompute from [11 TierGate](../11-tiergate-ai-usecase-intake/) and adds a command line, an exit code, input checks, GitHub annotations and a skill file. On 200 synthetic forms the declared tier is wrong on 63.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 35-tiergate/src && python3 tiergate.py --demo
```

It prints:

```text
UNDER-DECLARED  IN-D02  Card dispute drafting aide  declared tier 2, recomputed tier 3 (8 points)
  DATA_CLASS_BELOW_CATALOG  form says internal; the catalog records confidential for card_dispute_log; using confidential
checked 6 submissions: 1 under-declared, 0 over-declared, 5 unchanged
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 tiergate.py check intake.csv --catalog catalog.csv --registry registry.csv`. It exits 1 when a form is declared below its recomputed tier, 2 when the input is malformed (one line on stderr), and `--format github` prints annotations.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 200 planted intake forms; the script is named in brackets):

- 🟢 The declared tier equals the reference tier on 137 of 200 forms (68.5%); 57 are declared below it and 6 above. Of 93 forms the reference sends to full review, 63 (67.7%) get there and 30 get the light review (`step_01`)
- 🟢 Re-adding the rubric points on the form as written gets 157 of 200 (78.5%) and 71 of the 93 full-review forms (76.3%) (`step_02`)
- 🟢 One check at a time: catalog only 164 of 200 and 81 of 93; registry only 164 and 74; text rules only 162 and 76, with 12 forms pushed above the reference (`step_03`)
- 🟢 All three together: 170 of 200 (85.0%), 87 of 93 full-review forms (93.5%), forms below the reference 57 down to 11, forms above it 6 up to 19 (`step_04`)
- 🟢 Against what the sponsors declared, 63 forms are under-declared and 4 over-declared; 133 are unchanged (`step_04`)

## What it still gets wrong

- 🟢 11 of 200 forms stay below the reference after the recompute, and `step_04` prints each one: 8 have a vendor dependency that is missing from the form and from the registry, 2 have a data class understated on the form while the catalog entry is stale, and 1 is a customer-facing tool that the form calls internal and whose text names nobody. Where the form and the second source agree, or the second source is silent, there is nothing for the check to disagree with.
- 🟢 A planted situation does not always move the tier: 6 forms carry an understated class with a stale catalog entry, and 2 of them end up below the reference (`step_04`). Step 3 counts 9 of 200 forms (4.5%) with a wrong class and no second source that disagrees.
- 🟢 The recompute buys its recall with false alarms. Forms above the reference rise from 6 to 19, and 15 of those 19 carry a planted hard negative: 9 forms whose text names customers but whose tool is internal, and 6 raised by a catalog entry that overstates the class (`step_04`). Blank and `unsure` answers are treated as customer-facing until the sponsor confirms, which is deliberate and also raises some forms.
- **The data and the rules share an author.** I wrote the generator and the rules, and I know which words the customer-facing rule looks for. The hard cases are planted on purpose and in a number that makes them visible. Treat 85.0% as a ceiling for these rules on this data, not a rate on real intake forms, which I have not tested.
- The customer-facing rule is a keyword match. It reads "client-side" as a client. It has no view of a tool whose description names nobody.
- The rubric points, the cut-offs between tiers and the choice of tier 3 and 4 as "full review" are my 🟡 assumptions. See Aligned to.
- This is the recompute only. Duplicate linking, the evidence gate and the review queue are in [11 TierGate](../11-tiergate-ai-usecase-intake/) and are not repeated here.

## Use it as a skill

[`skill/tiergate-intake-check/SKILL.md`](./skill/tiergate-intake-check/SKILL.md) tells an agent how to run the command on an intake export, what to report, and what to say about the limits. It adds no logic. It is staged and has not been published or loaded into an agent runtime. What is tested is the command it wraps and the skill file's own frontmatter (`tests/`, 48 tests in all). The skill tells the agent to treat sponsor-written titles and descriptions as data, not as instructions; I have not tested that behavior on a model.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the declared tier get right and wrong? | `step_01_declared_tier.py` |
| 2 | What does re-adding the rubric on the form as written fix? | `step_02_rescore_the_form.py` |
| 3 | Where does that go wrong, and what does each check buy alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do the catalog, the registry and the text rules fix together? | `step_04_with_tiergate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [FINOS AI Governance Framework](https://air-governance-framework.finos.org/) (v2, 20 October 2025). I read its page [A heuristic approach to identifying GenAI risks](https://air-governance-framework.finos.org/heuristic-assessment.html) on 2026-10-23. It asks a team to assess a use case on factors such as internal or customer-facing users, data sensitivity, third-party or in-house models, and advisory or automated decisions. The six rubric inputs here map onto those factors. The page defines no numeric tiers or scores and suggests qualitative ratings such as Low, Medium and High, so the points and cut-offs in this prototype are my 🟡 assumption, not a reading of that text. This is a prototype, aligned to that guidance and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real intake process. The reference tier is the rubric applied to the true inputs, so every accuracy figure measures how well a method recovers that result from noisy forms. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/intake_submissions.csv`, `data/data_catalog.csv` and `data/vendor_registry.csv` for your own exports and keep the visible columns, or skip the data and point `check` at three files from your intake tool. Read the [PRD](./PRD.md) for the scope I held to. The rubric is at the top of `src/tiergate.py`, and `data/_generate.py` keeps its own copy to score the truth; change both, regenerate the data and rerun the steps.
