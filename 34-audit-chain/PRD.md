# PRD: audit-chain (hash-chained log)

## Problem
An agent acts on cases, and the only record of what it did is a file its own operators can edit. A reviewer who opens that file after an incident has no way to tell whether it is what the agent wrote.

## Who it is for
The engineer who owns an agent's logging, and the reviewer or auditor who has to rely on it afterwards.

## What it does
1. Writes agent actions as an append-only JSON-lines log. Each event carries the hash of the one before it. There is no update or delete.
2. `verify` reads the log and exits 0, 1 or 2: nothing wrong, a sign of alteration, or could not run. It names the line.
3. `anchor` records the sequence number and hash of one event, to be kept somewhere the log's writer cannot edit. `verify --anchor` uses it to catch a log cut back or rewritten from the start.
4. `append` adds one event from the shell and refuses to extend a log that does not verify.

## Out of scope
Deciding who may write (no signatures, no key); storing the anchor; proving the time of an event; detecting an action that was never logged; locking for several writers; log shipping, retention or encryption; any model call.

## Success, as the scripts print it
Tampered logs flagged out of 91 planted edits, split by whether the edit touches an anchored event (64 of 64) or only the open tail (12 of 27); harmless changes flagged (0 of 10); the misses named (15 of 91).

## Risks
The planted edits and the checks share an author, so the numbers are a ceiling. The anchor only helps if it lives where the log's editor cannot reach. A forged append is the same bytes as a real one.

## Next
Sign events with a key held by the writer, so a forged append fails. Run it on one real agent log the owner is allowed to share. Add a completeness check against the orchestrator's own counts, as AgentKit has.
