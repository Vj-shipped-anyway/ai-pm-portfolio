# 🏪 smb-faq-abstain (HalluGuard re-skin): an FAQ assistant that hands off instead of guessing

**I wanted to know whether a small-business FAQ assistant can hold back a drafted answer about deposits or lending when the bank's own text does not support it, and what that costs in questions sent to a banker. This is a rule-based gate: it reads a question, a drafted answer and a short knowledge base, and prints SERVE or ABSTAIN.** It re-skins the idea in [01 HalluGuard](../01-halluguard-bank-chatbot-safety/) on a new set of 30 small-business questions, with checks that read the text instead of fixed verifier scores.

**▶ Static demo, no install:** [open demo.html](./demo.html)

Tags used below: 🟢 measured (a script in this folder prints the number), 🟡 modeled (the assumption is named), 🔴 hypothetical.

## Run one now

```bash
cd 69-smb-faq-abstain/src && python3 smb_faq_abstain.py --demo
```

It prints:

```text
question: Does the Business Credit Card have an annual fee?
draft:    Yes. Expect an annual fee on the Business Credit Card.
decision: ABSTAIN (ungrounded) yes or no disagrees with the source (source F07)
```

The stored draft says yes. The passage (F07) says the card has no annual fee, so the draft is held back and the customer is handed to a banker. Standard library only, Python 3.9 or newer.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 30 questions, 12 passages and 30 stored drafts; the step is named in brackets):

- 🟢 A keyword router returns a canned passage for 3 of 30 questions, 2 of them the right one, points 23 to a page and hands 4 to a banker; the knowledge base can answer 17 of the 30 and the router answers 2 of those (step 1)
- 🟢 Serving every draft puts 28 of 30 in front of the customer: 10 are correct and 18 are wrong, which is 60.0% of the 30 questions (step 2)
- 🟢 No single check is enough: the source check alone serves 12 of 18 wrong drafts, the checks on the question alone serve 9 of 18, and the grounding check alone serves 5 of 18 (step 3)
- 🟢 A loose grounding threshold (half of the claims) serves 5 of 18 wrong drafts instead of 3 of 18; the two extra are Q13, a fake citation, and Q14, a wrong opening hour (step 3)
- 🟢 All checks together: 3 of 30 wrong answers served against 18 in step 2, 15 of 18 wrong drafts held back, 7 of 10 correct drafts served, and 20 of 30 (66.7%) handed to a banker, 2 of those because the draft already declined (step 4)

## What it still gets wrong

- 🟢 Three wrong drafts pass (step 4 prints each as a KNOWN LIMIT). Each quotes a number that is in the right passage and means something else. Q05 gives 1.20% APY for a $40,000 balance where the passage gives 2.10% for balances of $25,000 or more. Q10 calls the $150 annual fee monthly. Q16 answers a rate for a 700 credit score from a knowledge base that sets no rate by score. The gate reads numbers, not units or meaning.
- 🟢 Three correct drafts are held back by mistake (step 4 prints each). Q07 spells its number out ("ninety days"), so nothing is left to check. Q11 asks "what documents should I bring", and "should I" is a scope cue. Q26 says Hawaii and Alaska are "not available" where the passage says "except", and the yes or no check reads the negation word as a disagreement.
- 🟢 One advice question is held by the source check and not by the scope check: Q24 has a best coverage of 0.47 against a minimum of 0.50. I set the minimum before running anything and did not tune it. 🟡 Both thresholds (coverage 0.5, tie margin 0.05) are assumptions.
- **The set and the rules share an author.** I wrote the questions, the passages, the drafts and the rules, so the passages and questions share vocabulary. After the first run I rewrote the Q26 draft to add a negation word, because I had not planted a false alarm of that kind. Read the results as a ceiling for these rules, not a rate on real traffic, which I have not tested.
- **The drafts are stored text, not model output.** The gate has never seen drafts from a real model. It is a set of rules, not a trained verifier. HalluGuard's design calls for a trained verifier and its step 4 uses fixed scores, so the two sets of numbers do not compare.
- Retrieval is word overlap: no synonyms, and "Term Loan" shares words with "Equipment Loan". Only full state names are read, not "TX". English only. Numbers written as words are not parsed. Units are not read. The yes or no check looks for negation words anywhere in the passage.
- The handoff rate comes from a set built from failure cases. Live traffic is mostly routine, so the live rate should be lower, but I have not measured it. 🔴 Whether customers prefer a handoff to a wrong answer is not tested here.

## Use it on your own files

```bash
python3 smb_faq_abstain.py check --kb kb.csv --question "Is the Equipment Loan available in Texas?" --draft "Yes."
python3 smb_faq_abstain.py batch --kb kb.csv --pairs pairs.csv
```

`kb.csv` has the columns `fact_id`, `product`, `excluded_states` and `text`; `pairs.csv` has `query_id`, `question` and `draft`. `check` exits 0 to serve, 1 to hold back and 2 for malformed input, with a one-line message on stderr. `--min-grounded` sets the share of claims that must be supported (default 1.0). When no passage covers the question, the output says so.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does a keyword router answer? | `step_01_keyword_router.py` |
| 2 | What reaches the customer when every draft is served? | `step_02_draft_only.py` |
| 3 | Where does each check fail alone, and what stays missed? | `step_03_deficiencies_exposed.py` |
| 4 | What do all the checks catch together? | `step_04_with_gate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output. The scope I held to is in the [PRD](./PRD.md).

## Aligned to

None. I did not anchor this project to a regulation or a standard, and I claim no alignment with one. It extends the idea in [01 HalluGuard](../01-halluguard-bank-chatbot-safety/): hand the customer to a banker instead of stating something the source does not support. What is new here is the question set, drafts from a seeded generator, and rules that read the text. No code or number was copied. It is a prototype on synthetic data.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. The bank, its products and its numbers are invented. Nothing comes from any employer, customer or real bank. A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/kb.csv` with your own passages (keep the columns and name the excluded states explicitly), and `data/queries.csv` and `data/drafts.csv` with your questions and the drafts your assistant produced, then add a `data/truth.csv` row for each. The step scripts will score your drafts the same way.
