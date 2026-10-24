# PRD: KYB Packet Check

## Problem
A model reads a business-onboarding filing and returns the owners, their percentages, the control person and their details. Nobody compares that reading with the filing. A percent read as 2.5 instead of 25, two percents swapped, or an owner left out all look like a normal, complete record, and the file then lists the wrong people as beneficial owners.

## Who it is for
The person who owns the onboarding workflow behind a model extraction, and the analyst who reviews what the workflow flags.

## What it does
1. Takes the text of one packet and the model's extraction as JSON. It never calls a model.
2. Checks completeness: the details the order recites for each 25 percent owner and the control person, and a signed, dated certification.
3. Checks arithmetic: percentages add up within a tolerance, and an entity holding 25 percent or more shows the owners behind it.
4. Checks grounding: each name, percentage and personal detail appears on a filing line that names the same holder or person.
5. Prints PASS or REVIEW with findings that do not repeat dates of birth, addresses or ID numbers, and exits 1 on REVIEW.

## Out of scope
Reading scans or PDFs; verifying that an identity is real; trusts; more than one level of look-through; a model call; any claim that the filing itself is true.

## Success, as the scripts print it
Misreads flagged (40 of 43 on the planted set); clean packets flagged (0 of 32); packets that would list the wrong people and are flagged (17 of 20); the known miss named (3 nominee notes pass).

## Risks
The packets and the checks share an author, so the numbers are a ceiling. The filing text here is clean synthetic text; a real scan needs a text layer, and its errors become this tool's errors. The sum tolerance and the rule that a schedule adds to 100 are my assumptions, not the order's.

## Next
Run it on one real, shareable extraction log with the owner's permission; add a nominee and side-letter phrase list that the owner of the filings writes, not me; handle unallocated interests.
