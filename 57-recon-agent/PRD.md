# PRD: recon-agent

## Problem
Two ledgers describe the same cash for one month, the bank's and the company's, and the totals do not agree. Someone reads both to find out why. A script that pairs lines by amount and date makes the gap look smaller, but it cannot say why two lines were paired, and some of its pairs are wrong.

## Who it is for
The operations analyst who closes the month, and the reviewer who approves the matches that are not obvious.

## What it does
1. Matches bank lines to book lines with five rules in a fixed order, one bank line to one book line, except a batch where one bank line equals several book lines that share an explicit batch id.
2. Prints with every match the rule, the lines and the facts it rests on: reference, amount, date gap, counterparty.
3. Re-runs the rule on exactly those lines before a match posts, and again on a finished list (`verify`).
4. Lets a match post on its own only if its rule allows it; every other match waits for a recorded approval from someone other than the agent, bound to that exact proposal.
5. Lists every line that is not posted with a reason: no counterpart, reference conflict, ambiguous candidates, possible duplicate, currency differs, batch sum differs, awaiting approval, rejected.

## Out of scope
Any model call; currency conversion; amount tolerances; subset-sum search for splits with no batch id; a queue or user interface for approvers; posting to a ledger; hosting.

## Success, as the scripts print it
Matches posted on their own that are wrong (0 of 218 on the planted set); posted without a required approval (0); open lines each carry a reason (169); lines a person has to look at (385 of 821); the known misses named (18 true matches never proposed, 6 look-alike invoices approved by the scripted approver).

## Risks
The planted data and the rules share an author, so the numbers are a ceiling. The approver is a script. The window, fee schedule, limit and gate policy are assumptions. Identical-looking invoices one edit apart cannot be told apart from typos by the fields on screen.

## Next
Run it on one real pair of ledgers the owner is allowed to share, with a real reviewer, and count the approvals that were wrong.
