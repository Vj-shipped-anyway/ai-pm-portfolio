# PRD: Credit Policy Needle

## Problem
A credit policy states a limit in one clause and changes it for some applicants in another. The change can sit in the same clause, in the next one, in another section that cites the clause number, in a register at the back, or in a clause that cancels it for one case. An assistant that answers from a long policy can state the limit confidently and leave out the exception. A short test set does not show it.

## Who it is for
The owner of a policy-grounded assistant for credit staff, and the model risk or policy reviewer who signs off its test set.

## What it does
1. Lists the clauses in a manual that read as exceptions, and says which of them do not name the rule they change.
2. Scores an assistant's answers against exact expected answers, flags the form-by-length-by-depth cells that fail, and prints PASS or FAIL with an exit code.
3. Ships four stub readers (a control and three with a planted fault) and a synthetic set of three manuals, so the checks can be tried against faults that are known to be there.

## Out of scope
Any model call; scoring free-text answers; exceptions that tighten a limit or stack on one rule; tables and amendments; real policy text; hosting.

## Success, as the scripts print it
The gate fails the three faulty readers and passes the control with no cells flagged; the cells flagged for each fault match the cells predicted from the planted offsets; the audit's misses and false alarms are named (15 restated limits missed, 12 pointers listed by mistake).

## Risks
Data, readers and rules share an author, so the numbers are a ceiling. The retrieval stub is blunter than a real retriever. Exact match scores a wrapped answer as wrong. A score on answers alone passes a reader that never opens an exception whenever the exception does not apply.

## Next
Run the sweep on one real policy manual the owner is allowed to share, with questions the policy owner wrote. Add a second exception per rule and an exception that tightens a limit. Add a check that the expected answers still match after an amendment.
