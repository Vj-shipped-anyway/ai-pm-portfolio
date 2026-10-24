# PRD: name-match-eval

## Problem
A screening team picks a name-match threshold without seeing what it costs. A strict one misses reordered, shortened and respelled names; a loose one floods reviewers with clear names that resemble a listed one. The two costs are rarely printed side by side.

## Who it is for
An analyst or program lead who owns a name-screening step and has to defend its threshold, and the engineer who tunes it.

## What it does
1. Scores a customer name against every listed name with three matchers: exact, whole-name edit similarity, and folded words aligned in any order with rarity weights.
2. Sweeps the threshold and prints, per matcher, planted matches caught and clear names alerted.
3. Finds the threshold for a false-alert limit and for a recall target, and exits 1 when no threshold meets both.
4. Breaks results down by the kind of spelling change that was planted.

## Out of scope
Phonetic codes, non-Latin scripts, secondary identifiers, list updates, any model call, and any claim about a regulator's expectations.

## Success, as the scripts print it
The cost of the common approach (36.0% recall at the 10.0% false-alert limit), what folded words and rarity add (57.3%), the built-in misses named (alias_unlisted 0 of 10, namesake 8 of 8), and the finding that no threshold meets both targets.

## Risks
The same author wrote the data and the rules, so the numbers are a ceiling. The variant mix and both targets are assumptions. The word matcher is worse than edit on joined particles.

## Next
Run it on a real list and customer extract that the owner is allowed to share; add a second identifier to separate namesakes; compare a phonetic code.
