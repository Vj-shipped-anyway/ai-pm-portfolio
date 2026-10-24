# 🔎 Credit Policy Needle: where an assistant loses the exception clause

**I wanted to know whether an assistant that answers from a 300-page credit policy finds the exception that changes the answer, and where in the document it stops finding it. This is a small command-line tool that lists the clauses that read as exceptions and scores an assistant's answers by form of exception and depth, plus four stub readers with planted faults to try it against.** It extends [14 PolicyNeedle](../14-policyneedle-long-context-fidelity/) from planted facts to planted exceptions in a synthetic credit policy.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 67-credit-policy-needle/src && python3 credit_policy_needle.py --demo
```

It prints:

```text
audit  example_manual.txt: 5 exception clauses flagged among 67 clauses; 3 cite a clause without naming its rule
score  example_answers.csv: 6 of 8 probes pass
  crossref 8 pages depth 75%: 1 of 2
  register 8 pages depth 50%: 1 of 2
gate: FAIL (overall pass 75.0% is below 98.0%; 4 more)
```

The example is an 8-page manual with four rules and an assistant that searches on the rule's own words. It finds the exception that sits in the rule clause and the one in the next clause, and misses the one in another section and the one in the register. One of the five flagged clauses is a look-alike pointer, not an exception (see below). Standard library only, Python 3.9 or newer.

To check your own files: `python3 credit_policy_needle.py audit manual.txt`, and `python3 credit_policy_needle.py score probes.csv answers.csv`. The second exits 1 on FAIL so a CI step fails; `--format github` prints annotations with every value from the files escaped; a file that cannot be read exits 2 with one line on stderr.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 3 manuals, 210 questions, 4 stub readers; the script is named in brackets):

- 🟢 A plain-rule question set of 30 questions catches 1 of 3 faulty readers. The two it misses pass 30 of 30 and then answer 90 of 180 and 120 of 180 of the exception questions correctly (step 1)
- 🟢 Twelve exception questions with the exception beside the rule, asked at depth 50%, flag 2 of 3 faulty readers; the retrieval reader passes 12 of 12 (step 2)
- 🟢 The full sweep of 210 questions: the control passes 210, the truncating reader 56, the base-only reader 120 and the retrieval reader 150 (step 3)
- 🟢 The retrieval reader passes 30 of 30 with the exception beside the rule, 0 of 45 with it elsewhere, and 0 of 15 when a far clause cancels it (step 3)
- 🟢 The gate fails 3 of 3 faulty readers and passes the control with 0 cells flagged. The cells it flags for each faulty reader are the cells the fault should hit: 84 of 84, 90 of 90 and 60 of 60, with 0 other flags (step 4)
- 🟢 The audit lists 90 of 105 planted exception clauses, and lists 45 of the 60 that do not name their rule (step 4)

🟡 Modeled: one page is 1,800 characters, borrowed from project 14. The truncating reader sees 60,000 characters, about 33 pages; that is an assumption, not a measured model limit. Every limit and threshold in the manuals is invented.

🔴 Hypothetical: that a production assistant loses exceptions in the way the retrieval stub does. I have not run this against one.

## What it still gets wrong

- 🟢 The audit misses 15 of 15 restated limits, which carry no exception wording ("For an applicant with ..., the limit in clause X is ..."), and lists 12 of 36 look-alikes by mistake: pointers such as "Reviewers cite clause X, except for files closed with no decision" (step 4 prints both)
- 🟢 A reader that never opens an exception passes 90 of 90 questions where the exception does not apply. A score on answers alone cannot tell it from a reader that read the exception and judged it did not apply; only the paired question where the exception does apply fails it (step 3 prints this as the known limit, and step 4 does not remove it)
- **The data, the readers and the checks share an author.** I planted the exceptions, wrote the stub readers and wrote the audit rules. The control passes 210 of 210 because I wrote it to, and each faulty reader fails where I wrote it to. Treat the results as a ceiling for these rules on this wording, not a rate on a real policy manual, which I have not tested. The agreement between the cells the gate flags and the cells I predicted from the planted offsets shows the gate sees what was planted. It does not show the faults are realistic.
- The retrieval reader is blunt on purpose: it reads only blocks that hold every word of the product name and the attribute phrase. A real retriever is softer and will sometimes find a far exception.
- Exceptions here only loosen a limit, carry one numeric condition, and nest one level. Not covered: exceptions that tighten, several exceptions stacked on one rule, amendments, tables, or conditions that are not numbers. Matching is exact on a normalized answer, so a correct answer wrapped in a sentence scores as wrong; I have not measured how many answers that would affect.
- The audit reads English cue words and clause numbers in the form "7.12" with register entries "R-3". A manual numbered another way needs the patterns changed.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a plain-rule question set tell you? | `step_01_plain_rule_questions.py` |
| 2 | What does a first set of exception questions tell you, with the exception beside the rule? | `step_02_exception_beside_rule.py` |
| 3 | Where does each reader fail when the exception is somewhere else? | `step_03_deficiencies_exposed.py` |
| 4 | What do the audit and the gate catch, and what do they miss? | `step_04_with_gate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The 50 tests in `tests/` pin those numbers and cover empty, wrong-type and truncated input and hostile strings.

## Aligned to

Nothing. I claim no alignment to a regulation or a standard and cite none. The idea of planting a fact at a known depth comes from the needle-in-a-haystack tests, and this project reuses the approach of [14 PolicyNeedle](../14-policyneedle-long-context-fidelity/) (stub readers with known faults, a page convention, a gate on form-by-depth cells) without importing its code or data. It is a prototype, not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible: three manuals of 50, 150 and 300 pages with 105 planted exception clauses and 36 look-alikes, and 210 questions with exact answers. Nothing comes from any employer, lender or real policy. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/manuals/*.txt` and `data/probes.csv` with your own policy and with questions your policy owner has signed off, keep the five probe columns the score command reads (`probe_id`, `form`, `length_pages`, `depth_pct`, `expected_answer`), and put your assistant's answers in a two-column file. Write each exception question as a pair: one applicant who meets the condition and one who does not. Read the [PRD](./PRD.md) for the scope I held to.
