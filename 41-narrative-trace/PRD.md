# PRD: narrative-trace

## Problem
A case narrative states amounts, dates, counterparties and counts. A reviewer confirms each one by opening the transaction behind it. When a sentence cites no record, cites a record that does not exist, or states a figure the record does not show, the reviewer finds out only by reading all of it.

## Who it is for
A financial-crime operations lead who owns the narrative review step, and the engineer who builds the tooling around it.

## What it does
1. Splits a narrative into sentences, keeping abbreviations such as "Inc." and a citation placed after the period intact.
2. Resolves each `[txn: ID]` against a transactions file, and against one case when asked.
3. Compares the amount, date, counterparty, direction, channel and count in the sentence with the cited records.
4. Prints each sentence as traced, unchecked (cites a record, states nothing comparable) or not traced, and exits non-zero at a chosen level, with GitHub annotations on request.

## Out of scope
Judging whether a narrative is complete, persuasive or ready to file; reading implied meaning; any model call; filing; hosting; a staged Action.

## Success, as the scripts print it
Planted defects flagged (120 of 140); fine sentences flagged (10 of 268); sentences a person reads (158 of 408 instead of 408); the known passes named (12 laundered, 8 mixed-record).

## Risks
The data and the rules share an author, so the numbers are a ceiling. Sentences are template-built. The tool cannot tell an unsupported claim from a fine connecting sentence when neither states a comparable fact.

## Next
Run it on a narrative set an institution is allowed to share; add a relative-date reader; measure the reviewer time saved against a hand check.
