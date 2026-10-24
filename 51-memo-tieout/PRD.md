# PRD: Memo Tieout

## Problem
A credit memo quotes revenue, EBITDA and a handful of ratios from a spread. The spread is revised after the memo is drafted, a figure is copied from the wrong year, a ratio is worked out on last year's EBITDA, and a coverage ratio is rounded up to look better. Nothing compares the two files, so the reviewer opens both and looks each figure up.

## Who it is for
A credit analyst who writes the memo and the reviewer who signs it off. In this portfolio, the owner of a prototype who wants a number in a memo to be rerunnable against the spread.

## What it does
1. Reads the figures in a markdown memo: dollar amounts, percents and multiples. Skips code, links and URLs.
2. Ties each marked figure to one line and one period of a spread CSV, converting units, and recomputes margins and ratios from the spread.
3. Requires the figure to equal the spread value rounded to the decimals the memo shows, with no tolerance.
4. Reports figures with no mark as untied and proposed terms as set aside, prints each problem with its line and column, exits 1 on a problem, and writes GitHub annotations on request.

## Out of scope
Whether the spread matches the financial statements; whether the sentence around a figure names the right line; figures written in words; bracketed negatives; ranges; any model call; hosting; a Marketplace listing.

## Success, as the scripts print it
Wrong figures caught (104 of 124 on the planted set, against 98 of 124 for a value-anywhere script); fine figures flagged by mistake (12 of 184, against 107 of 184); a person opening 116 of 308 figures; the known passes named (a sentence that names another line, and figures in words).

## Risks
The planted set and the rules share an author. The formulas are mine. A mark can be edited with the number. The tool flags proposed terms that carry no term mark.

## Next
Run it on one memo and spread whose owner agrees; add a check that the words before a mark name the tied line; accept bracketed negatives; publish a staged GitHub Action from its own repository.
