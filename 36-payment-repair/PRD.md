# PRD: payment-repair

## Problem
A payment message with a missing or unusable required field is rejected at the next hop and lands in a repair queue, where a person fixes it by hand. A script that fills every empty field clears the queue fast and writes wrong values into messages that then move money: a currency from the wrong account, the first of two BICs, a beneficiary name from a stale payee list.

## Who it is for
The payments-operations lead who owns the repair queue, and the reviewer who approves a repair before it goes out.

## What it does
1. Finds the required fields that are missing, blank, placeholders or malformed in a pacs.008-style message. Optional fields are never touched.
2. Proposes a value only from a table the policy allows, and records the source.
3. Applies it without a person only for fields that do not change where the money goes (tier AUTO).
4. Holds a plan that changes routing or the payment's identity until an approval carries the digest of that exact plan, from an active person with the reviewer role who did not enter the order (tier APPROVAL).
5. Returns the message whole, with the reasons, when any field has no allowed source (tier NEVER): amount, currency, names, account numbers.
6. Writes one audit row per applied change and exits non-zero when something is held or returned.

## Out of scope
Validation against the ISO 20022 schema; structured postal addresses; more than one transaction per message; sanctions screening; a real approval workflow or identity check; any model call; hosting.

## Success, as the scripts print it
Routes match the planted intent (488 of 500); repairs without a person equal the true value (90 of 90); bad approvals blocked (766 of 766); returned messages untouched (129 of 129); messages released with a wrong or unusable value, against the basic script (21 of 371 against 126 of 500); the known misses named (12 wrong-but-well-formed BICs pass, 9 wrong proposals approved).

## Risks
The planted data and the rules share an author, so the numbers are a ceiling. The approver in the run is a test double. An approval is a CSV row, not an identity. The directory snapshot can be stale in ways the tool cannot see.

## Next
Run it on one real queue export the owner is allowed to share, with a real reviewer, and count what the reviewer catches among the proposals that are wrong; add a BIC-to-IBAN consistency check; read the ISO 20022 usage rules before the required-field list is treated as more than an assumption.
