# PRD: SMB FAQ abstention gate

## Problem
A small-business FAQ assistant that drafts answers about deposit and lending products will, some of the time, state a fee, rate, term or availability the bank does not offer, or answer a question nobody should answer from an FAQ. The customer cannot tell which drafts are wrong.

## Who it is for
The product owner of a bank's small-business chat channel, and the banker who receives the handoffs.

## What it does
1. Reads a question, a drafted answer and a short knowledge base.
2. Holds back the draft when it already declines, when the question asks for advice, when no passage covers the question, or when the question fits more than one product.
3. Otherwise checks every number, citation, yes or no and named state in the draft against the best passage, and serves the draft only when all of them are supported.
4. Prints SERVE or ABSTAIN with a one-line reason, and exits 0, 1 or 2 so a script can use it.

## Out of scope
A trained verifier, a language model call, a live chat integration, units and meaning of numbers, synonyms, state abbreviations, any regulation or standard.

## Success, as the scripts print it
Wrong answers served fall from 18 of 30 to 3 of 30; 15 of 18 wrong drafts are held back; 7 of 10 correct drafts are still served; the known misses and the false alarms are listed by question id.

## Risks
The set and the rules share an author, so the numbers are a ceiling. The drafts are stored stand-ins. Three wrong drafts pass because their number is real. Three correct drafts are held back by blunt cues. The handoff rate (20 of 30) comes from a set built from failure cases.

## Next
Run the gate on real drafts and a real knowledge base the owner may share; add a units check; replace word overlap with a retriever; measure the handoff rate on live traffic.
