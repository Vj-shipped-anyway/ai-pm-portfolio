# PRD: call-notes-actions grounding check

## Problem
A relationship manager finishes a call and a model proposes CRM tasks from the notes. The tasks look right. Some are not in the note at all, some cite a sentence that says the opposite (a conditional, a refusal, something already done), and some carry a date or an owner the sentence does not give. Written straight to the CRM, they send a client a chaser for a document already delivered.

## Who it is for
The person who owns the note-to-CRM step, and the relationship manager who has to trust the tasks that land in their queue.

## What it does
1. Takes the notes (one sentence per row) and the proposed actions, each with a cited sentence id and quote.
2. Checks that the citation is in the note, that the sentence carries this kind of action and names its subject, that the due date and amount are in the sentence, and that the owner matches who is speaking.
3. Holds a sentence that is conditional, negated, past or hedged for a person.
4. Prints ACCEPT, REVIEW or REJECT per action, and exits non-zero at a chosen level.

## Out of scope
Finding actions the extractor never proposed; splitting notes into sentences; reading a note for meaning; any model call; writing to a CRM; recordkeeping and privacy rules for call notes.

## Success, as the scripts print it
Ungrounded actions written to the CRM (38 of 256 against 256 with no check); grounded actions written without a person (175 of 184); the known misses named (clause swaps 13, soft hedges 17, phrasal negations 8).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The stub extractor's error mix is mine. The word lists are English only. A sentence-level check cannot see which clause a date belongs to.

## Next
Run it on a few hundred real notes the owner is allowed to share, with the extractor that will be used; add clause splitting and see what it costs in held actions; measure how long a person takes per held action.
