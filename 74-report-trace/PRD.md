# PRD: report-trace

## Problem
A filed report gives one number per cell. When a reviewer, an auditor or a colleague asks which loans make up a cell, the answer is a hunt: a mapping sheet that may be out of date, a query re-run on a table that has moved since filing, and no way to tell a logged adjustment from an unlogged one.

## Who it is for
The person who owns a recurring report and has to answer "where does this number come from?", and the reviewer who has to believe the answer.

## What it does
1. Captures, for every leaf cell, the rule and the source rows behind it with the fields the rule reads, plus the adjustments logged against it.
2. Explains each filed value as rows plus logged adjustments, and names any unexplained amount.
3. Compares the lineage with a current copy of the source: changed rows, missing rows, rows that now fit the rule and were never in the cell. Fields the rule does not read are ignored.
4. Checks that totals and ratios foot the filed numbers, and lists open loans that sit in no cell.
5. Prints the path from one cell to its rows, and exits non-zero when a cell needs a person.

## Out of scope
Any model call; counts, joins and multi-table lineage; rounding tolerance; deciding whether a source row is right; hosting; wiring the capture into a real reporting job.

## Success, as the scripts print it
Planted problems found (21 of 21); false alarms (0 of 46); rows named equal the rows planted (14 of 14); rows a reviewer reads (18 against 611 with a mapping sheet); the known miss named (4 of 4 wrong source rows trace cleanly).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The source has to be frozen or versioned for the comparison to mean anything. The lineage file grows with the rows behind the report.

## Next
Run it on one real recurring report the owner is allowed to share; add counts and a join case; test the capture inside a real job and measure its cost.
