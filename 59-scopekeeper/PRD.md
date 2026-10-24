# PRD: scopekeeper, a usage-versus-grant diff

## Problem
An AI agent calls tools through scopes. Scopes are granted at launch from a template and added for one-off tasks, and some grants are groups such as `accounts:*`. The control is an annual review that approves what is on the list. The list shows names, dates and tickets. It does not show a single call, so a grant nobody has used looks the same as one used every day.

## Who it is for
The person who runs the access review for an agent platform, and the owner of an agent who has to say what it may do.

## What it does
1. Reads a grant list and a call log (CSV), plus an optional catalog of what each group scope reaches and an optional list of which agents share a service account.
2. For each grant, asks whether a scope it reaches was called. No call: propose removal. A group called on some members only: propose narrowing to those members.
3. Credits a call with no agent tag to every agent on its service account that holds the scope, so a grant in use is never proposed for removal.
4. Replays the proposal against the same calls and counts the calls it would newly deny.
5. Prints a report, or GitHub annotations on request. Exits 1 when it proposes a change, 2 on input it cannot read.

## Out of scope
Applying any change; reading a real grant store; risk scoring; any model call; a longer log than the one given; hosting. Project 23 holds the risk ranking and the architecture notes.

## Success, as the scripts print it
Unneeded grants removed against what the annual review removes (46 of 62 against 4 of 62 on the planted set); no logged call newly denied in the replay (0 of 5210); the misses named (8 of 10 quarterly grants removed, 14 unneeded grants kept on a sibling's untagged calls, 2 kept after a smoke test).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The replay is in-sample: the proposal is built from the calls it is replayed on. A scope used less often than the log is long looks unused. Sibling credit trades a safer proposal for a larger one that stays.

## Next
Run it on one real grant export and call log that the owner may share; add the owner question "is this scope periodic?" to each removal proposal, which is designed in project 23 and not built here.
