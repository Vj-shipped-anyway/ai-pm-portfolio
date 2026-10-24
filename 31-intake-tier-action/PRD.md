# PRD: Intake Tier Action

## Problem
AI use cases arrive as issues. The sponsor fills in a form and declares a tier, and that declaration becomes the label. It is the answer most likely to be low for the use cases that matter. A workflow that reads the form with a regex fixes the arithmetic but not the inputs, and it labels bodies it cannot read, adds a second tier label when an issue is edited, and echoes issue text into logs.

## Who it is for
The person who runs AI intake for a regulated team, and the reviewer who picks the next issue from a label.

## What it does
1. Reads an issue body by the form's own headings and refuses to guess a missing or ambiguous input.
2. Recomputes the tier from six answers, using the higher of the form and a data catalog for the data class and the higher of the form and a vendor registry for the vendor model, and counting a blank or unsure customer-facing answer as customer-facing until confirmed.
3. Says which labels to add and which of its own labels to remove, so a re-run on edit leaves one tier label and any other label alone.
4. Writes one comment with a marker, listing the checks that ran and the evidence the tier asks for.
5. Echoes only text it has made safe, and escapes annotations.

## Out of scope
Approving anything; reading free text with a model; checkboxes and several forms; a hosted service; a Marketplace listing, which is a later, separate step.

## Success, as the scripts print it
More tiers equal the reference than with a regex (129 of 160 against 124 of 160); unreadable bodies are named, not tiered (18 of 160); one tier label per issue after edits (160 of 160); no forged command and no echoed mention (0 and 0 of 160); the known misses printed (11 issues with a data class below the true class, the tier wrong on 2).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The rubric and the body format are assumptions. The cross-checks are only as good as the catalog and the registry. A strict parser costs a person one look on a complete form that was pasted over.

## Next
Open one real issue from the form and compare its body with what the parser expects; run it on a throwaway repository; publish the Action from its own repository.
