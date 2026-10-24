# PRD: ISO 20022 Map Check

## Problem
A team moving payments from a legacy message format to ISO 20022 writes a field mapping, builds a converter, and validates the output against the ISO element rules. That validation passes a name cut short, a field that was never written and an amount that was rounded, because each is still a valid ISO value. The loss shows up later, in a repair queue or a return.

## Who it is for
A payments analyst or engineer who owns the mapping between a legacy format and an ISO 20022 message, and the reviewer who signs it off.

## What it does
1. Reads the mapping with the two field catalogues and reports a legacy field with no row, a mandatory ISO element nothing fills, a legacy code with no table entry, and a field that cannot fit its target.
2. Compares each legacy message with the ISO message the converter produced and reports a value dropped, cut short, changed, or present with no source.
3. Prints legacy messages with every field at its limit (`probe`) so a converter that cuts early shows itself.
4. Reports what no message exercised, so a missing test is not read as a pass.
5. Exits 0, 1 or 2, and never prints a payment value.

## Out of scope
XML parsing and schema validation; structured-address parsing; judging whether a mapping is semantically right; the ISO-to-legacy direction beyond a length warning; any model call; hosting.

## Success, as the scripts print it
Planted mapping defects found (5 of 5); harmless rows flagged (0 of 3); planted converter defects found in pairs (212 of 212); harmless variations flagged (0 of 162); builds with a defect found with and without probes (7 of 8 against 5 of 8); the known miss named (build B10).

## Risks
The data and the rules share an author, so event-level results are a ceiling. The legacy format is invented and the ISO lengths are my simplification. A defect that fires only on a combination of codes stays hidden until a message carries it.

## Next
Run it on one real mapping the owner may share; cross the coded fields in the probes; add a check on the ISO-to-legacy direction with converted messages.
