# PRD: dispute-clock

## Problem
A dispute is not one deadline. The bank owes the customer an acknowledgement, a decision on provisional credit, an investigation result and a final notice, each with its own window and its own start. A case system with one flat target date cannot show which of these was missed, and a calendar-day countdown gets the due date wrong whenever a weekend or a holiday falls inside the window.

## Who it is for
The operations lead who owns a dispute queue, and the second-line reviewer who asks which deadlines were missed and which are about to be.

## What it does
1. Reads a policy file of clocks: anchor event, window, business or calendar days, and the events that satisfy it.
2. Counts business days against a holiday file and starts each clock at the date its policy row names.
3. Prints, for every dispute, each clock as on time, late, breached, running with days left, or not started.
4. Lists missed clocks and clocks due soon, exits 1 when a clock was missed, and prints GitHub annotations on request.

## Out of scope
Reading any regulation; pausing or restarting a clock by rule; cut-off times within a day; business-day rollover of a due date that lands on a day off; sending notices; a model call; hosting.

## Success, as the scripts print it
Statuses that match the planted truth (519 of 524); missed clocks found (150 of 151); false alarms counted (4); the hard cases shown (108 of 109 on the due day, 57 of 57 across a holiday); the known limits named (paused investigations, and a window class recorded wrong).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The windows are assumptions. The holiday file is a modeled calendar, and a missing closure would shift every business-day due date after it.

## Next
Run it on one real queue export that the owner may share; take the windows from counsel's reading of the rule that applies; add a pause rule; add cut-off times.
