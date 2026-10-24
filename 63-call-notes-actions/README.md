# 🗒️ call-notes-actions (grounding check): every CRM action has to point at a sentence

**I wanted to know what reaches the CRM when a model turns a relationship manager's call note into follow-up tasks and nobody checks that each task is something the manager actually said. This is a command-line check: for every proposed action it looks up the sentence the action cites and accepts it, holds it for a person, or rejects it.** On 120 synthetic notes it cut ungrounded actions written to the CRM from 256 to 38, and it left 175 of 440 candidates for a person to read.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 63-call-notes-actions/src && python3 call_notes_actions.py --demo
```

It prints:

```text
call_notes_actions: 7 candidates against 1 note
  ACCEPT E01    send_document     rm      2026-10-16  S2    "I will send Ms. Okafor the rate sheet by Friday."
  ACCEPT E02    await_document    client  2026-10-21  S3    "She will return the KYC form by 21 October."
  REVIEW E03    callback          rm                  S4    "If the term deposit rate moves by more than 25 basis ..."  -> conditional:if
  ACCEPT E04    log_complaint     rm                  S5    "She complained about the card replacement delay."
  REVIEW E05    send_document     rm                  S6    "I already sent the fee schedule last week."  -> owner_unclear; past:already
  REVIEW E06    send_document     rm      2026-10-17  S2    "I will send Ms. Okafor the rate sheet by Friday."  -> due_not_in_sentence
  REJECT E07    schedule_review   rm      2026-10-20  S7    "I will book the annual review for 20 October."  -> cite_not_found
checked 7: 3 accepted, 3 held for review, 1 rejected
notes with no proposed action: 0 of 1
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 call_notes_actions.py check notes.csv candidates.csv`. It exits 1 when any action is rejected (`--fail-on hold` also fails on a held one) and 2 for a missing or malformed file. Column layouts are in the [data README](./data/README.md).

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 120 planted notes, 258 planted actions and 440 candidate actions from a stub extractor; the script is named in brackets):

- 🟢 No check: 256 of 440 candidates are ungrounded and all 256 are written (58.2%); only 184 of 258 planted actions reach the CRM correctly (`step_01`)
- 🟢 Requiring a quote: a non-empty citation stops 0 of 256; an exact match anywhere in the note stops 6 of 256 and rejects 29 of 184 grounded actions whose quote the model had tidied (`step_02`)
- 🟢 Citation alone stops 14 of 256. Adding support, slots and owner stops 187 of 256, and 69 are still written because a conditional, negated, past or hedged sentence reads as a commitment (`step_03`)
- 🟢 All five parts together: 38 of 256 ungrounded actions are written (14.8%), 166 are held for a person and 52 are rejected (`step_04`)
- 🟢 The cost: 9 of 184 grounded actions are held and none is rejected; 175 of 440 candidates need a person, and 94.9% of those held are ungrounded (`step_04`)

**What I assumed** (🟡 modeled): the stub extractor's error rates, listed in the [data README](./data/README.md), are mine, so 58.2% describes the stub, not any real extractor. A held candidate costs one read and a rejected one costs none; I did not time anyone. A weekday name means its first occurrence after the call.

**What I could not show** (🔴 hypothetical): that a real extractor's mix of errors resembles this one, or that a relationship manager would work a held queue of this size.

## What it still gets wrong

- 🟢 38 of 256 ungrounded actions pass, in three groups that `step_04` prints id by id. Clause swaps (13): a date or a document taken from the other clause of "Ms. X will return the form by 16 October, and I will send the sheet by 21 October"; the rules read a sentence, not a clause. Soft hedges (17): "I will try to call". Phrasal negations (8): "asked me to hold off calling". The last two are word lists, and the lists are mine.
- 🟢 9 of 184 grounded actions are held for nothing: an amount written in words (5) and a negation about something else in the same sentence (4).
- 🟢 74 of 258 planted actions never come out of the extractor correctly (`step_04`). The check removes bad actions; it cannot add a missing one.
- **ACCEPT means the sentence says it, not that it is true.** A wrong note produces a grounded wrong action.
- **The test set and the rules share an author.** I wrote the sentence templates, the stub's errors and the word lists, so catching every conditional, negated, past and declined case shows the lists cover my phrasings. I planted three kinds the rules cannot see and three kinds of valid action that look suspicious, and printed both. Treat the result as a ceiling for these rules, not a rate on real notes, which I have not tested.
- Dates: "next Friday" reads as "Friday"; "end of the month" and "in two weeks" are not read. Amounts need a dollar sign or a k, thousand or million suffix. Word lists are English only. The input is one sentence per row; there is no sentence splitter, so a bad split produces bad citations.
- The stub gives each candidate one defect. A real extractor combines them.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What reaches the CRM when nothing checks the citation? | `step_01_no_check.py` |
| 2 | What does "every action must cite a quote" stop? | `step_02_citation_present.py` |
| 3 | Where does each half of the check fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do citation, support, slots, owner and modality catch together? | `step_04_with_grounding_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The layout follows [28 Tool Schema Drift](../28-tool-schema-drift/); no code is shared.

## Aligned to

Nothing. I did not read a standard or a regulation for this project, so I claim no alignment. It is a prototype on synthetic data, not compliant with or certified against anything. Call notes in a regulated bank carry recordkeeping and privacy duties that I have not touched.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, client or real CRM. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/notes.csv` and `data/candidates.csv` for your own export and keep the columns, or point `check` at two files of your own. The trigger words, subject rules and hedge words are lists at the top of `src/call_notes_actions.py`. Read the [PRD](./PRD.md) for the scope I held to.
