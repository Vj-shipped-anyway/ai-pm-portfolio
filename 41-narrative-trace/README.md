# 🔗 narrative-trace (citation check): every sentence of a case narrative, traced to a transaction

**I wanted to know how much of a suspicious-activity narrative a program can check against the ledger before a person reads it. This is a command-line check: it splits a narrative into sentences, looks up the transaction each one cites as `[txn: ID]`, and compares the amount, date, counterparty, direction, channel and count the sentence states with the record.** It prints the sentences it cannot trace, and it prints the sentences that cite a real record but state nothing it can compare. It takes the claims-to-evidence idea from [39 Claims Check](../39-claims-check/) and uses a transactions file as the evidence instead of script output.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 41-narrative-trace/src && python3 narrative_trace.py --demo
```

It prints:

```text
narrative-trace: example_narrative.txt against 7 records (case EX-1)
  s3   channel mismatch   says ACH; cited T-E004 wire
       "The customer paid $14,500.00 to Tessel Trading Ltd. by ACH on 2026-02-06 [txn: T-E004]."
  s4   amount mismatch    says $2,800.00; cited T-E005 2300.00
       "On 2026-02-10 the account received an ACH credit of $2,800.00 from Brindle Foods Inc. [..."
  s5   uncited            no [txn: ID] citation
       "The customer moved the balance offshore the same week."
  s6   other case         cites T-E101 (case EX-2)
       "On 2026-02-12 the customer sent a wire of $3,100.00 to Ostrel Marine LLC [txn: T-E101]."
  s7   dangling citation  cites T-E099, not in the transactions file
       "A further payment followed on 2026-02-20 [txn: T-E099]."
  s8   unchecked          cites T-E005; states no amount, date, party, direction, channel or count to compare
       "The activity is inconsistent with the stated business of the customer [txn: T-E005]."
sentences: 8 checked, 2 traced, 1 cite a record but state nothing checkable, 5 not traced
result: FAIL
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 narrative_trace.py check narrative.txt txns.csv --case C-007`. A citation is `[txn: ID]` or `[txn: ID, ID]`, before the period or after it. The transactions file needs the columns txn_id, date, amount, direction, channel and counterparty, plus case_id when you pass `--case`. It exits 0 when every sentence is traced or unchecked, 1 when one is not traced, and 2 when an input cannot be read. `--fail-on unchecked` also fails on sentences that state nothing checkable; `--format github` prints annotations. `--demo` prints FAIL and exits 0, so it works as a smoke test.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 40 narratives, 408 sentences, 478 transaction records, 140 sentences with a planted defect; the script is named in brackets):

- 🟢 With no trace, 0 of 140 planted defects are stopped before a reviewer reads them, the reviewer looks up 471 citations by hand, and 38 of 40 narratives hold at least one defect (`step_01`)
- 🟢 The usual first check, a pattern for a missing bracket on text split at punctuation plus a space, flags 44 of 140 defects and 99 of 268 fine sentences. It finds 19 of 20 uncited sentences; the other 25 flags are defects that a period after "Inc." or "Ltd." cut in two (`step_02`)
- 🟢 Adding one check at a time: a bracket check with the tool's own splitter finds 20 of 140; looking up each ID in the case finds 46 of 140; comparing facts to the cent finds 120 of 140 but flags 64 of 268 fine sentences; allowing rounding and sums brings that to 10 of 268 (`step_03`)
- 🟢 The full trace flags 120 of 140 planted defects and 10 of 268 fine sentences, and leaves 158 of 408 sentences for a person to read (`step_04`)
- 🟢 Every sentence planted as uncited (20 of 20), dangling (14 of 14), other-case (12 of 12), wrong amount (14 of 14), wrong date (12 of 12), wrong counterparty (12 of 12), wrong direction (10 of 10), wrong channel (10 of 10), wrong count (8 of 8) or wrong total (8 of 8) is flagged (`step_04`)
- 🟢 The splitter cuts all 408 sentences where I planted the boundaries, including 24 with "Inc." or "Ltd." mid-sentence and 16 with the citation after the period (`step_04`)

## What it still gets wrong

- 🟢 20 of 140 planted defects pass by default: 12 sentences that cite a real record and say something no field of it can confirm, and 8 whose figures are each right for some cited record but bound to the wrong one. `step_04` prints every one.
- 🟢 The tool cannot tell those 12 from 16 fine connecting sentences, because both come back "unchecked". `--fail-on unchecked` flags 132 of 140 defects and 26 of 268 fine sentences (`step_04`). Pick the setting by what a missed sentence costs you.
- 🟢 A date that is not a transaction date is read as a claim about the cited records, so a sentence about when the account was opened is flagged: 10 of 10 such sentences (`step_04`).
- **The data and the rules share an author.** I planted the defects and wrote the rules, so 120 of 140 shows that the rules cover what I planted. The sentences are built from templates and are more regular than an analyst's prose; the first run of this set had no false alarms, so I added the opening-date sentences to give the rules something to get wrong. Treat the result as a ceiling, not a rate on real narratives, which I have not tested.
- The direction check knows a short list of words (deposited, received, credited, sent, paid, withdrew, debited and a few more). "Wrote a check" carries none, so a sentence with the wrong direction and only that verb is not caught (`tests/test_trace.py` pins it). It did not occur in this data.
- A counterparty is checked only if the ledger holds its name. A name that is not in the file, a person's name, a relative date such as "the next day" and an amount in words are not read. The abbreviation list is short and English only, and a sentence that ends on "Inc." runs into the next one.
- It checks that a sentence agrees with the record it cites. It does not check that the narrative is complete, well argued or ready to file, and it does not read a sentence for what it implies.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a reviewer face when nothing checks the citations? | `step_01_no_trace.py` |
| 2 | What does a missing-bracket pattern catch and break? | `step_02_bracket_check.py` |
| 3 | What does each added check buy, and what passes all of them? | `step_03_deficiencies_exposed.py` |
| 4 | What does the full trace flag, and what does it leave? | `step_04_with_trace.py` |

Run any of them from `src/`. Data is built by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. 61 tests run under `unittest` (`tests/`).

## Aligned to

The FinCEN proposed AML/CFT program rule, announced in a [news release of 2026-04-07](https://www.fincen.gov/news/news-releases/fincen-proposes-rule-fundamentally-reform-financial-institution-programs). I read the release on 2026-10-23 and did not read the rule text. It describes a program judged on effectiveness and risk focus, and separates deficiencies of design from deficiencies of implementation. It does not mention suspicious activity report narratives or artificial intelligence, so I take no requirement for narratives from it. What I take is the direction: a control that tests, on every narrative, that each statement traces to a record is one an institution can show working. No limit, threshold or deadline from any rule is used here. This is a prototype, aligned to that direction, not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real bank; the counterparty names are invented. 🟡 Six of the 18 invented counterparties end in "Inc." or "Ltd.", and every case has at least two records with such a counterparty. That is my assumption, chosen to test the splitter, and the 99 of 268 in step 2 depends on it. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/transactions.csv`, `data/narratives.json` and `data/truth.csv` for your own, keeping the columns, or skip the data and point `check` at a narrative and a transactions export. Read the [PRD](./PRD.md) for the scope I held to.
