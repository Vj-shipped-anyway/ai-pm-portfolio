# PRD: Claims Check

## Problem
A README says "caught 80 of 98" and the number was right when I typed it. The script moves on, the README does not, and CI stays green because nothing compares the two. A grep for the number does not fix it: it passes a 12 that is really a 112, and it reads a wrapped bullet one line at a time.

## Who it is for
Anyone who publishes numbers next to code and wants a reader to be able to rerun a script and see the same number. In this portfolio, the owner of a README with green-tagged figures.

## What it does
1. Reads the numbers after each green circle in a README, per paragraph or list item.
2. Skips fenced code, code spans, link targets and URLs.
3. Checks each number against the text the scripts printed: as a whole number, with "a of b" matched as a pair.
4. Prints each unsupported number with its line, exits 1 when there is one, and writes GitHub annotations on request.

## Out of scope
Running the scripts; judging whether a printed number means what the sentence says; HTML; nested documents; any model call; hosting. A Marketplace listing is a later, separate step.

## Success, as the scripts print it
Wrong bullets caught (80 of 98 on the planted set, against 38 of 98 for a grep); fine bullets flagged by mistake (8 of 186, against 19 of 186); a person opening 88 of 284 bullets; the known passes named (coincidence, and numbers of one digit).

## Risks
The planted set and the rules share an author. The check proves a number was printed, not that it is the right one. Stale evidence passes. The pair rule flags a pair printed on two lines.

## Next
Run it against one other README whose author agrees; add a check that the evidence files are newer than the scripts; publish the Action from its own repository.
