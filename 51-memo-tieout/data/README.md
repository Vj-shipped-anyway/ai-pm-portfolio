# Data for project 51

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real memo, spread, bank, borrower or employer, and the borrower names are made up from word lists. No parameter comes from a regulation or standard. 🟡 The formulas in `src/memo_tieout.py` (EBITDA, margins, debt to EBITDA, current ratio, debt service coverage as EBITDA over interest plus scheduled principal, debt to equity, revenue growth) and the rounding rule (half away from zero at the decimals the memo shows, no tolerance) are my assumptions.

| File | What it holds |
|---|---|
| `memos.json` | 28 made-up credit memos in markdown: `memo_id`, `borrower`, `memo` |
| `spreads.csv` | One spread per memo, 14 lines over FY2022 to FY2024: `memo_id, period, period_end, line, value, unit`. The memo_id column groups the rows. 20 spreads are in `usd_thousands`, 4 in `usd` and 4 in `usd_millions` |
| `truth.csv` | One row per planted figure, 308 in all: `memo_id`, `line`, `col` (1-based position of the figure in the memo), `kind`, `expected` (`ok` or `flag`), `text`. The label comes from how the figure was built, not from the checker |
| `example_memo.md`, `example_spread.csv` | The worked example behind `python3 memo_tieout.py --demo` |

The spread lines are revenue, cogs, opex, depreciation, interest_expense, taxes, net_income, cash, current_assets, current_liabilities, total_debt, total_equity, capex and principal_payments. Capital expenditure always ends in 50 thousand dollars, so a one-decimal million figure for it sits exactly on a rounding boundary.

Planted figures that are fine (184): exact_thousand 30, million_rounded 30, dollars_plain 10, ratio_ok 30, pct_ok 30, growth_ok 16, half_up_edge 10 (a one-decimal figure on an exact boundary, such as 1,250 thousand written as $1.3 million), term_marked 16 (a proposed term with a `term:` mark), term_untagged 12 (a proposed term or ownership share with no mark, which the tool flags as untied).

Planted figures that are wrong (124): typo 14 (a digit changed or two swapped), wrong_period 14 (the value of another period), wrong_line 12 (the value of another line in the same group), unit_slip 12 (thousand written as million, or a decimal point moved), stale_denominator 10 (a ratio worked out on the prior year's EBITDA), covenant_round 10 (a ratio nudged by 0.01 in the borrower's favour), growth_wrong 8 (growth over two years, or growth of EBITDA), bad_tag 8 (an unknown line, an unknown period, or a figure of the wrong form), untied 16 (a spread figure with no mark), prose_tag_mismatch 10, unparsed_form 10.

Two kinds are hard on purpose. prose_tag_mismatch is a figure whose number and mark agree but whose sentence names another line, and unparsed_form is a figure written in words or with a USD prefix. Both pass every rule in `src/`. The prose around the figures also holds years, location counts, a section number, a quarter and a tenor in years, none of which is a figure.
