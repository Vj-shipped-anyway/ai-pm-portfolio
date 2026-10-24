# PRD: chargeback packet check

## Problem
A merchant who disputes a chargeback has one response window and one packet to send. Each reason code asks for different evidence, some of it either-or. People assemble the packet from whatever they can find, and nothing compares it with the list or watches the clock until the answer comes back.

## Who it is for
The person in merchant operations or a bank's merchant-services team who assembles and sends the packet, and the reviewer who signs it off.

## What it does
1. Looks up the evidence list for the case's reason code and reports each required item that is missing, naming the alternatives.
2. Runs the response clock: days left for a draft, on time or late for a sent packet, with the last day counting.
3. Checks consistency: every document names this order, post-purchase documents are not dated before the purchase, none is dated after the check date, the order record covers the disputed amount, the packet stays inside the page limit.
4. Prints READY, FIX or LATE per packet and exits 1 when any is not READY, 2 when the input cannot be read.

## Out of scope
Reading the documents themselves; predicting whether a dispute is won; any card network's real reason codes, lists or deadlines (the bundled ones are invented); weekends, holidays and time zones; filing the response; any model call; hosting.

## Success, as the scripts print it
Visible faults sent to FIX (34 of 34 on the planted set); late packets marked LATE (14 of 14); ready packets flagged by mistake (0 of 43); fewer packets opened than the 100 a full read takes (48 of 100); the known miss named (9 of 9 wrong-file packets pass).

## Risks
The recipe for a good packet and the rules share an author, so the numbers are a ceiling, although the set includes five kinds of hard negative and two kinds of fault the rules cannot see. The evidence list is invented and has to be replaced with the one a real acquirer publishes before the output means anything for a live dispute.

## Next
Load a real acquirer's published list into `rules.json`; add a business-day option for the window; add a document hash or a page-count check against the file itself so a wrong file is at least sometimes visible.
