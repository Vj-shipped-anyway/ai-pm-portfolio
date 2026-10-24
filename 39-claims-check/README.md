# 🧾 Claims Check: fail the build when a README number is not printed by a script

**I wanted to know how many of the numbers I tag as measured in my own READMEs are printed by a script, and how many were typed once and never checked again. This is a command-line check and a staged GitHub Action: it reads the numbers after each green circle in a README and fails when one is not printed, as a whole number, in the output of your scripts.** It is the number check from [`tools/check_repo.py`](../tools/check_repo.py) pulled out into a tool of its own, with three changes: whole-number matching, "a of b" matched as a pair, and wrapped bullets read as one item.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 39-claims-check/src && python3 claims_check.py --demo
```

It prints:

```text
claims-check: example_claims.md against 1 evidence file (9 numbers, 3 ratios printed)
  line 6    not supported  "3.4"          3.4 is not printed by any script (a longer figure that contains it is printed: 3.42)
  line 8    not supported  "14 of 480"    both numbers are printed, never as "14 of 480" on one line
  line 9    not supported  "58"           58 is not printed by any script (a longer figure that contains it is printed: 158)
claims: 6 checked, 3 supported, 3 not supported, 1 skipped (fewer than 2 digits)
result: FAIL
```

Standard library only, Python 3.9 or newer. To check your own README: `python3 claims_check.py check README.md --evidence out/*.txt`. It exits 1 when a number is not printed and 2 when an input cannot be read; `--format github` prints annotations.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 40 projects and 284 planted bullets, 98 of them wrong; the script is named in brackets):

- 🟢 With no check, 0 of 98 wrong bullets are stopped, and a reviewer would compare 301 numbers by hand (`step_01`)
- 🟢 The grep check from `check_repo.py` catches 38 of 98 wrong bullets and flags 19 of 186 fine ones (`step_02`)
- 🟢 That grep misses all 14 bullets whose number is a piece of a longer one, all 8 rounded figures, all 12 broken pairs and all 8 bullets that wrap onto a second line (`step_02`)
- 🟢 Reading claims first, with wrapped bullets joined and code spans and links skipped, moves it to 46 of 98 caught and 0 of 186 false alarms (`step_03`)
- 🟢 Matching whole numbers moves it to 68 of 98 caught, still 0 of 186 false alarms (`step_03`)
- 🟢 Matching "a of b" as a pair moves it to 80 of 98 caught: broken pairs go from 0 of 12 to 12 of 12 (`step_03`)
- 🟢 With all three changes a person opens 88 of 284 bullets, and 80 of 88 are real problems (`step_04`)

## What it still gets wrong

- 🟢 Numbers of one digit are skipped, 16 of them in this set, so a wrong small count passes (`step_04`). Checking them as well catches every wrong one and flags every bullet that carries a stray small numeral (`step_03`), which is why the default is two digits.
- 🟢 The pair rule has a price: it flags 8 of 186 fine bullets, the ones whose two numbers are printed on separate lines (`step_04`). Print "a of b" in the script, or pass `--no-pairs`.
- 🟢 A wrong number that equals another number the scripts print passes. All 10 such bullets pass (`step_04`); the row count and the seed are the usual accomplices. The tool checks that a number was printed, not what it was printed next to.
- **The data and the rules share an author.** I planted the wrong bullets and wrote the rules, so 80 of 98 shows that the rules cover what I planted. Treat it as a ceiling, not a rate on READMEs I have not seen. I have run it on this README (a test does that) and on nothing else.
- Evidence can be stale. If CI does not rerun the scripts, a number passes against last month's output. The tool reads files; it does not run anything.
- A rounded figure is flagged on purpose: write the number as the script prints it. The day in a printed date supports a claim of the same number, and so does any other printed number of the same value.
- Markdown paragraphs, lists and tables are read. HTML is not parsed. A number inside a Markdown link's text is a claim; a number inside a code span or a link target is not.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`, 48 tests in all).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What gets through when nothing ties README numbers to output? | `step_01_no_check.py` |
| 2 | What does grepping for each number cost and catch? | `step_02_grep_for_the_number.py` |
| 3 | What does each change to the check add, and what does it cost? | `step_03_deficiencies_exposed.py` |
| 4 | What do the default settings catch, and what still passes? | `step_04_with_claims_check.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

Nothing. I claim no alignment with a standard, framework or regulation. The credibility tags (green measured, yellow modeled, red hypothetical) are a convention of this portfolio, and this tool is what enforces the green ones. It is a prototype.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real repository. 🟡 The two-digit minimum is my assumption, chosen to keep list numerals and step numbers out of the check. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/projects.json` and `data/truth.csv` for your own READMEs and output, keeping the columns, or skip the data and point `check` at your README and a folder of captured output. Read the [PRD](./PRD.md) for the scope I held to.
