# PRD: Payment Mandate Check

## Problem
A customer lets an agent pay on their behalf, inside limits: these payees, up to this amount, until this date. The credential the agent signs in with says it may submit payments. It does not say how much, to whom, or until when. Without a check at the point of release, the limits live in a document and the agent's own prompt.

## Who it is for
An engineer who owns the payment gateway an agent submits to, and the person who approves what the gateway holds for review.

## What it does
1. Reads a mandate file (limits, payees pinned to an account, rails, categories, validity, revocation) and a batch of instructions.
2. Decides each instruction in the order the gateway received it: RELEASE, HOLD for a person, or REJECT, with a reason code and a plain sentence for each reason.
3. Keeps a ledger of what was released, for the daily limit and for repeated instructions.
4. Writes one hash-chained audit record per decision, and verifies a file of them.
5. Exits 1 when an instruction reaches the level you chose, and 2 for malformed input.

## Out of scope
Capturing or signing the customer's consent; moving money; verifying that an account belongs to a payee; reading the memo or any free text; foreign exchange; rolling windows; any model call; hosting.

## Success, as the scripts print it
Every legitimate instruction released (0 of 249 stopped); every hard negative released (49 of 49); held and rejected instructions found against the planted truth (46 of 62 held, 156 of 164 rejected); the known misses named (24 released that should not be); an edited audit record found.

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The check trusts what the instruction says about itself (category, rail, account). Split payments under the threshold pass. The audit chain proves consistency, not authorship.

## Next
Add a same-payee aggregate over a rolling window, which would hold the second and third piece of a split. Run the check on a log a payments team is allowed to share. Decide where the head hash of the audit chain is stored outside the gateway.
