# 🧭 AI Ops Operating Model Review: a skill that asks for evidence at each stage

**I wanted to know how far a bank-operations AI program has really got when its owner says "we are in rollout", and to find out in an afternoon rather than after an incident. This is a staged Agent Skill and the command it wraps. The skill walks the eight stages of [OPERATING_MODEL.md](../OPERATING_MODEL.md), asks for an artifact reference, a producer and a date for every item the program's tier owes, and the command prints the stage the evidence reaches and CONFIRMED, OVERCLAIM or UNDERCLAIM against the stage the owner claims.** It turns the first 30, 60 and 90 days of that model into a checklist you can run.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 60-ai-ops-operating-model/src && python3 ops_model_review.py --demo
```

It prints:

```text
program: EX-01 (Dispute triage - card operations)   tier 3   claimed stage 6
  stage 2 Admit and tier   I04 Vendor rating: MISSING  no evidence row
  stage 4 Build and prove  I10 Independent validation: NOT_INDEPENDENT  produced by the builder, u007
  stage 5 Limited rollout  I13 Rollout report: STALE  46 days old, limit 10.5 days
first 90 days: 9 of 11 owed items evidenced; open: I04, I10
evidence reaches stage 1 of 8
decision: OVERCLAIM (claimed 6)
```

Standard library only, Python 3.9 or newer. To review your own register: `python3 ops_model_review.py review --checklist C.csv --programs P.csv --evidence E.csv --as-of 2026-09-30`. It exits 1 when a claim is above its evidence, 2 for malformed input; `--format github` prints annotations and `--window 90` adds the first-90-days count.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 60 planted programs, 23 checklist items and 677 evidence rows; the script is named in brackets):

- 🟢 Owners' reported stage equals the true stage for 16 of 60 programs; 36 of 60 report a stage above it (118 stages over in total), and 14 of the 18 that report hand-off or later have not reached it (`step_01`)
- 🟢 A flat checklist ticked when a row exists reaches the true stage for 19 of 60, flags 11 of 24 claims that were not overclaims, flags 220 missing items the program's tier does not owe (in 44 programs), and accepts 24 lapsed, 19 hollow, 9 blank-reference, 5 builder-produced and 2 future-dated items (`step_02`)
- 🟢 Each check earns its place: without the tier-aware list the stage matches fall to 32 of 60, without the placeholder test to 41, without freshness to 37, without independence to 44; without the future-date test the match stays at 45 of 60 and 2 more defective items get through (26 against 24) (`step_03`)
- 🟢 All five checks together reach the true stage for 45 of 60 programs, flag 30 of the 36 claims above the truth and none of the other 24 (`step_04`)
- 🟢 Of the owed items planted as lapsed, it rejects 19 of 24; blank reference 9 of 9; builder-produced 5 of 5; future-dated 2 of 2 (`step_04`)
- 🟢 First 90 days, every owed item evidenced: the review counts 18 of 60 programs, the planted truth 14 of 60 (`step_04`)

## What it still gets wrong

- 🟢 It reads the register, not the artifacts. It rejects 0 of 19 hollow artifacts. The review's stage is above the truth for 14 of 60 programs, and 6 of the 36 overclaims still pass (`step_03` and `step_04` print each one with the planted state that let it through).
- 🟢 Lapsed evidence younger than 1.5 times its cycle passes: 5 of the 24 lapsed items did. The reverse also happens: 8 items planted as fine, from a cycle that ran late, are rejected as stale, and one program lands below its true stage because of it (`step_03`, `step_04`).
- **The data and the rules share an author.** I planted the states and wrote the checks, so 45 of 60 shows the checks cover what I planted. I drew the hollow and lapsed cases on purpose so that the rules miss them, and the late-cycle cases so that they raise a false alarm. Treat the numbers as a ceiling for these rules, not a rate on a real register, which I have not seen.
- 🟡 The tier assigned to each item, its cycle in days and the first-90-days window are my assumptions, except where OPERATING_MODEL.md section 4 sets the evidence owed at a tier. The 1.5 times factor is the one that file gives for obligation evidence, itself an assumption. Items E01, E02, E04, E09 and E11 of that table are not in the checklist.
- 🔴 The audit sample, where a person opens one artifact per stage the review marks OK and confirms one sentence, is designed in the skill and not measured. Whether it finds hollow artifacts is unknown.
- The register holds one row per program and item, so it shows the latest artifact and not the history. The tool does not compute the tier; [11 TierGate](../11-tiergate-ai-usecase-intake/) does that.

## Use it as a skill

[`skill/ai-ops-review/SKILL.md`](./skill/ai-ops-review/SKILL.md) is a staged Agent Skill with the eight-stage table, the questions to ask, the rule that no reference means no row, the command to run and the audit step. Copy the folder into your agent's skills directory to try it. It has not been installed in any agent and has not been run as a skill by anyone. What is tested is the command it wraps (`tests/`, 52 tests in all), and a test checks that the skill's table matches `data/checklist.csv`.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does the status deck show when the owner writes the stage? | `step_01_self_reported_status.py` |
| 2 | What does a flat checklist ticked on a row's existence add? | `step_02_presence_checklist.py` |
| 3 | What does each check add, and what does none of them see? | `step_03_deficiencies_exposed.py` |
| 4 | What do the five checks reach together? | `step_04_evidence_review.py` |

Run any of them from `src/`. Data is produced by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The Financial Stability Board's [Sound Practices for Responsible Adoption of Artificial Intelligence](https://www.fsb.org/uploads/P151026-1.pdf) (final report, 15 October 2026; I read the full text on 24 October 2026). Sound Practice 3 asks institutions to document AI use and to assess materiality and risk; Sound Practice 5 asks for that assessment at inception and after; Sound Practice 9 asks for performance evaluation in proportion to materiality and risk, including ongoing monitoring. The tier that sets what is owed, the evidence register and the renewal cycle are one way to make those three concrete. The report has its own section on stages of AI development and deployment (3.1); I did not map the ladder here to it, and the eight stages are OPERATING_MODEL.md's.

On [SR 26-2, Revised Guidance on Model Risk Management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (Federal Reserve, OCC and FDIC, 17 April 2026; I read the attached guidance on 24 October 2026): it says it sets no enforceable standards or prescriptive requirements, expects to be most useful for models behind significant business lines, and says in a footnote that generative AI and agentic AI models are outside its scope while a bank's own risk management and governance practices should guide their controls. So this review is a design for that governance. It does not map to SR 26-2 clause by clause. This is a prototype, aligned to that guidance and not compliant with or certified against anything. The paraphrases are mine, not the text of either document.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/checklist.csv` with your own items, tiers and cycles, and export your register to the three-file format in [data/README.md](./data/README.md). Read the [PRD](./PRD.md) for the scope I held to.
