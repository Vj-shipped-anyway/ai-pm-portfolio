# PRD: aigf-checks

## Problem
A governance framework lists risks. A team that wants to show it has dealt with one writes a crosswalk row: this check covers this risk, and this line of its output shows it. The row is typed once. When the check changes, nothing re-reads the row, so the crosswalk keeps saying what was true on the day it was written.

## Who it is for
A contributor who wants to offer a risk-to-check mapping to a public framework, and the maintainer or reviewer who has to decide whether to trust it.

## What it does
1. Resolves the risk and the check in every row, and reports duplicates.
2. Binds each claim to the labelled line of the check's printed output and compares the value, setting aside case, spacing and thousands separators.
3. Reports a row whose check has no captured output instead of skipping it.
4. Compares the aspects a risk needs with the aspects the check declares, and reports a row marked full that is not.
5. Reads the note for the words compliant, certified and guarantee.
6. Gives each risk a status: CHECKED, PARTIAL, UNVERIFIED or GAP.
7. Lints a commit message for a `Signed-off-by` line and a subject of 72 characters or fewer.

## Out of scope
Running the checks; reading a check's code; deciding what a real framework entry requires; any model call; opening the issue or the pull request. The contribution is drafted in `contribution/` and waits for the author.

## Success, as the scripts print it
Defective rows found (38 of 45 on the planted set); harmless rows flagged (0 of 28); risk statuses right (23 of 24); rows a person reads (38 of 73); the known misses named (7 of 45 defective rows pass).

## Risks
The planted set and the rules share an author, so the numbers are a ceiling. The declared aspects are taken as written. A captured output that is out of date gives an out-of-date pass.

## Next
Send the issue draft to the framework's maintainers and wait for an answer on where a table of checks belongs; then open the pull request with a sign-off on every commit. Run the tool on one real crosswalk the owner may share.
