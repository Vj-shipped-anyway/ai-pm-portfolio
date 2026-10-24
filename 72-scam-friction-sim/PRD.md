# PRD: scam-friction-sim

## Problem
A bank that sees a suspicious real-time payment can hold it for a short time and hope the customer thinks again. The hold has two sides. It stops some scam payments, depending on what a held victim does. It also makes people who are paying a solicitor or a seller wait, and some of them give up. Teams usually look at the first side with a made-up stop rate and leave the second to a complaints report.

## Who it is for
A fraud or payments product owner deciding whether to build a hold, and the reviewer who has to say how many legitimate customers it will touch.

## What it does
1. Replays a file of payments against a policy: no hold, a blanket hold on first payments to a new payee, or a scored hold with a warning band.
2. Prints the scam value stopped next to the legitimate payments held, lost and delayed, and the legitimate holds per scam payment stopped.
3. Takes every customer response as a named assumption in a JSON file, so the same data can be rerun under different beliefs.
4. Exits 1 when a friction budget or a stop target is broken, 2 for bad input.

## Out of scope
Any real stop rate, any claim that a hold of this length is permitted or advisable on a real rail, repeat attempts, payments moved to another rail, support calls, recovery after money has left, model calls, hosting.

## Success, as the scripts print it
Scam value stopped and legitimate payments held, side by side for each policy (21.6% and 336 for the blanket rule, 20.1% and 52 for the scored one); the ceiling a hold on every payment would reach under the assumptions (29.7% with no coaching); the known miss named (60 of 60 payments to an established payee pass untouched).

## Risks
The stop side rests on invented probabilities and the model has no hold-length curve. The data and the rules share an author, so the numbers are a ceiling for these rules, not a rate on real payments. The share of scams is far above any real share, which flatters the ratio of holds to stops.

## Next
Replace the assumptions with results from a controlled trial the owner is allowed to run; add repeat attempts and a second rail; test a score fitted on real labelled data.
