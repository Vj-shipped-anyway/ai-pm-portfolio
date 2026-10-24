# PRD: TPRM Gap Map

## Problem
A proposed interagency guidance on third-party risk is out for comment. It is principles-based and does not mention AI. A bank buying an AI-enabled service has to decide what evidence to hold, and the agencies ask which characteristics should mark a relationship as high risk.

## Who it is for
A third-party risk or AI governance lead at a bank, and anyone drafting a comment on the proposal.

## What it does
1. Maps each stage of the proposed text to the evidence an AI-enabled vendor needs, marking whether the text names it, covers it by principle, gives an example, or does not mention it.
2. Tiers vendors by the text's own examples and by four added characteristics.
3. Tests each characteristic against an incident log: how many vendors with it had a material incident.

## Out of scope
Legal advice; predicting examiner behavior; scoring real vendors; any model call; submitting a comment.

## Success, as the scripts print it
The text's examples catch 17 of 24 material-incident vendors; with four characteristics, 22 of 24; false alarms rise from 13 to 19; two material-incident vendors are still marked LOWER; the method runs on a bank's own files.

## Risks
The incident log is simulated from my hazard rates, so the numbers show a method. The map is a reading of one proposal, and the proposal can change.

## Next
Run it on a real incident history the owner may share; re-read the map against the final text when it is issued.
