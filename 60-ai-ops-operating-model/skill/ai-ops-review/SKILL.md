---
name: ai-ops-review
description: Walk one AI program in bank operations through the eight lifecycle stages of OPERATING_MODEL.md and ask for evidence at each stage, then run the ops_model_review command to compare the stage the owner claims with the stage the evidence reaches. Use when someone says a program is at a stage (admitted, in shadow, handed off, in review) and you need to check that claim, or when preparing the first 30, 60 and 90 days of an AI operating model. It collects an artifact reference, who produced it and its date for each owed item, never accepts a status without them, and ends with CONFIRMED, OVERCLAIM or UNDERCLAIM. It reads the register, not the artifacts, so it also lists what a person must open and confirm.
---

# AI ops review

A prototype review for one program at a time. It checks a claim against a register of evidence. It does not approve a program, rate it, or say anything about compliance. Run it from a clone of the repository that holds this folder; the command is `src/ops_model_review.py` and the checklist is `data/checklist.csv`.

## What to collect first

Ask for these and write them down. Do not guess any of them.

1. Program id and a short name.
2. Tier, 1 to 4. If the sponsor gives a tier, ask how it was computed. The tier decides which items are owed.
3. Builder: a person id. Independence checks compare against it.
4. The stage the owner claims, 0 to 8. Zero means no stage is complete.
5. The review date, as YYYY-MM-DD. The command never reads the clock.

## The loop

For each stage from 1 upward, in order:

1. Ask the stage question.
2. For each owed item in the table below (skip items above the program's tier), ask for three things: the artifact reference (a document id or link a second person can open), the person who produced it, and its date.
3. Write one row per item into the evidence file. If the person cannot give a reference, write no row. A status said aloud ("it is done") is not evidence. Never invent a reference, a producer or a date, and never fill a placeholder such as TBD to keep the walk moving.
4. Move on only after the stage is written down. Do not skip a stage because the owner says a later one is finished.

Evidence file columns: `program_id,item_id,artifact_ref,produced_by,date`. One row per program and item. Programs file columns: `program_id,program_name,tier,builder,claimed_stage`.

## Stages, questions and items

The "Tier" column is the lowest tier that owes the item. "Cycle" is how often the evidence should be renewed, in days; evidence older than 1.5 times the cycle is stale. "Other than builder" means the producer must not be the program's builder. "Window" is the first-N-days mark in which the item belongs for a first candidate (my mapping from section 10 of OPERATING_MODEL.md; 0 means after day 90).

| Stage | Question | Item | Tier | Cycle | Other than builder | Window | Confirm when you open it |
|---|---|---|---|---|---|---|---|
| 1 Find the work | Which steps can an agent take over? | I01 Build brief | 1 | 180 | no | 30 | every step has a class and the control screen names the worker-data limits |
| 2 Admit and tier | Which tier, evidence and vendor? | I02 Tier record | 1 | 180 | no | 30 | the tier is recomputed from the form questions and not copied from the sponsor |
| | | I03 Evidence status | 1 | 90 | no | 60 | each missing item is listed by id |
| | | I04 Vendor rating | 3 | 365 | no | 60 | the rating states criticality, data access and the upstream provider |
| 3 Commit capacity | Are reviewers and a benefit owner available? | I05 Board status | 1 | 30 | no | 60 | the reasons cite evidence and not the owner's color |
| | | I06 Reviewer capacity row | 2 | 90 | no | 60 | planned demand is set against supply for the quarter |
| | | I07 Benefit baseline | 2 | 90 | no | 60 | the baseline period and the holdout are stated |
| 4 Build and prove | Do the controls hold offline, and how does shadow differ from people? | I08 Permissions record | 1 | 90 | no | 90 | each tool maps to one credential and one owner |
| | | I09 Offline test report | 2 | 90 | no | 90 | the probe-set version and the failing cases are listed |
| | | I10 Independent validation | 3 | 365 | yes | 90 | the challenge points and how each was resolved |
| | | I11 Shadow scorecard | 2 | 90 | no | 90 | each known miss has an owner |
| 5 Limited rollout | Does it hold live, with people at both gates? | I12 Human review design | 3 | 180 | no | 0 | the floors and the escalation path are written down |
| | | I13 Rollout report | 1 | 7 | no | 0 | scope violations and unapproved resubmits are counted, including a count of zero |
| | | I14 Decision lineage plan | 3 | 180 | no | 0 | the log fields cover the decision from input to outcome |
| 6 Hand off | Can the owning team run, stop and restore it? | I15 Signed hand-off record | 1 | 365 | yes | 0 | the signer is on the owning team and the brief version is named |
| | | I16 Rehearsed runbook | 2 | 45 | yes | 0 | both steps were run and left an audit trace |
| | | I17 Fallback and exit plan | 4 | 365 | no | 0 | the trip conditions and a named approver for restoring |
| | | I18 Monitors wired | 1 | 90 | no | 0 | each listed signal alerts into platform monitoring |
| 7 Run and watch | Is it drifting, leaking, over-permissioned or unused? | I19 Run-health report | 1 | 30 | no | 0 | the latest report ends in a named decision and not only charts |
| | | I20 Permission usage diff | 2 | 90 | no | 0 | grants with no call are listed with an owner decision |
| | | I21 Incident clock policy | 3 | 365 | no | 0 | the hours are dated and the determination role is a person |
| 8 Review | Widen, fix, hold or retire? | I22 Review record | 1 | 90 | no | 0 | the decision is one of the four and cites evidence |
| | | I23 Benefit statement | 2 | 90 | no | 0 | hard cash and soft capacity are shown apart |

The cycles, the tier assigned to each item (except where OPERATING_MODEL.md section 4 sets it) and the window mapping are my assumptions. Change them in `data/checklist.csv`, and change this table to match; a test checks that every item id in the file appears here.

## Run the command

```bash
cd src
python3 ops_model_review.py review --checklist ../data/checklist.csv --programs programs.csv \
    --evidence evidence.csv --as-of 2026-09-30 --window 90
```

Add `--program ID` for one program, `--format github` for annotations, and `--fail-on never` to keep the exit status at 0. Exit status 1 means a claim is above its evidence; 2 means the input is malformed and the message names the line.

## Read the result

- `evidence reaches stage N`: every owed item in stages 1 to N is OK, and stage N+1 has a gap.
- `OVERCLAIM`: the claim is above N. List each gap printed under the claim and ask for the missing artifact; do not argue the status.
- `CONFIRMED`: the claim equals N. Go to the next section before you say it is true.
- `UNDERCLAIM`: the evidence reaches further than the owner says. Ask why; a later stage may have been started out of order.
- `first N days: x of y`: how many of the items due by day N are evidenced. After day 90 the model has reached a shadow run for one candidate and not the full ladder.
- Statuses: MISSING (no row), BLANK_REF (empty or placeholder reference), FUTURE (dated after the review date), STALE (older than 1.5 times the cycle), NOT_INDEPENDENT (the builder, or nobody, produced an item that needs someone else).

## What the command cannot see: open the artifacts

The command reads the register. A row with a real-looking reference for an artifact that is empty, a template or about something else passes. After a CONFIRMED result, open one artifact per stage the review marks OK and check the sentence in the last column of the table. Write down what you saw. If the sentence is not true, record the item as hollow, remove its row, and run the command again.

Evidence that lapsed recently also passes: anything younger than 1.5 times its cycle counts as fresh, even if the last cycle was skipped. Ask for the date of the last run, not only the file.

## Do not

- Do not accept an owner's color, percent complete or "signed off" as evidence.
- Do not write a reference you did not see.
- Do not use the output as an approval or as a statement that the program meets any rule or standard.
- Do not review a program on a date other than the review date you wrote down.

## Status of this skill

Staged in this folder. It has not been installed in any agent or run as a skill by anyone. What is tested is the command it wraps (`tests/`).
