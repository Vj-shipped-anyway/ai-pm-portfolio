# PRD: controlmap

## Problem
A bank has to show, for each AI-related obligation, which control meets it and whether the evidence is current. The answer lives in a register column someone typed, or in a sheet that links rows by shared words. Neither knows a control's scope or evidence date, and neither says when it cannot decide.

## Who it is for
The model risk or AI governance analyst who prepares the answer, and the second-line reviewer who has to defend the dictionary behind it.

## What it does
1. Reads an obligations CSV, a controls CSV and a theme dictionary CSV.
2. Matches controls to obligations on dictionary phrases; ignores retired controls and phrases that are denied ("this is not model monitoring").
3. Labels each match full, partial or out of scope, and checks evidence age against a multiple of the control's test cycle.
4. Prints one status per obligation (COVERED, STALE, PARTIAL, UNCOVERED, UNMAPPED) with the reason, lists controls that serve nothing and dictionary phrases that matched nothing, and groups stale evidence into one request per control.
5. Exits 1 at a chosen level, 2 on bad input.

## Out of scope
Reading obligation text to choose a theme; testing whether a control works; any model call; a regulation text or framework mapping; hosting.

## Success, as the scripts print it
Right status per obligation against the planted truth (42 of 56, against 19 of 56 for a keyword sheet); the controls that serve nothing listed (13 of 15); the wrong answers named with a cause (14, of which 4 are UNMAPPED and said out loud).

## Risks
The data and the rules share an author, so the numbers are a ceiling. The dictionary is the weak point: controls worded outside it are missed, and a phrase used in another sense is linked.

## Next
Run it on one real register and library its owner is allowed to share; have a reviewer label a sample of pairs; write the theme rows for whatever comes back UNMAPPED.
