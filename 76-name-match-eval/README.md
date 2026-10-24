# 🔎 name-match-eval: what a screening threshold costs in missed names and false alerts

**I wanted to know what a name-screening threshold actually trades, so I planted the answer and measured it. This is a command-line evaluator and a synthetic set of 400 customer names planted against a 90-name watchlist: it runs three matchers (exact, character edit similarity, and a word-based matcher), sweeps the alert threshold, and prints how many planted matches each one catches and how many clear names it alerts on.** It is a prototype for thinking about the threshold, not a screening product.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 76-name-match-eval/src && python3 name_match_eval.py --demo
```

It prints:

```text
sample: 12 names screened against 6 listed names; 5 are the same party as a listed entity, 7 are not
edit   at 0.80: caught 1 of 5, false alerts 1 of 7
tokens at 0.80: caught 4 of 5, false alerts 1 of 7
```

Standard library only, Python 3.9 or newer. To score two names: `python3 name_match_eval.py score "Hasan Karimov" "Karimov, Hassan"`. To sweep your own files: `python3 name_match_eval.py sweep watchlist.csv customers.csv truth.csv --matcher tokens`. It exits 1 when no threshold meets both targets, and 2 for malformed input.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 90 listed names for 60 entities, 400 customer names of which 150 are planted matches and 250 are different people; the script is named in brackets):

- 🟢 Exact match on the normalized name catches 24 of 150 (16.0%) and raises 8 false alerts on 250 clear names (3.2%); all 8 are namesakes. It has no threshold to tune (`step_01`)
- 🟢 Character edit similarity on the whole name: to keep false alerts on at most 10.0% of clear names the threshold has to be 0.93, and recall is then 36.0%. Recall of 85.0% is not reachable at any threshold from 0.30 to 1.00; at 0.30 recall is 81.3% and 99.2% of clear names alert (`step_02`)
- 🟢 The edit matcher catches no more than 4 of 24 order swaps or 5 of 14 initials at the three thresholds I printed (0.60, 0.75, 0.93), and going from 0.60 to 0.93 takes shared_given alerts from 47 of 56 to 0 of 56 while translit hits fall from 22 of 22 to 14 of 22 (`step_03`)
- 🟢 The word-based matcher at the same 10.0% limit: threshold 0.93, recall 57.3% (86 of 150) with 24 false alerts; edit similarity gets 54 of 150 with 25 false alerts. Order swaps go from 3 of 24 to 24 of 24 (`step_04`, `step_03`)
- 🟢 Weighting words by rarity on the list matters at the strict end: at the 10.0% limit the unweighted word matcher reaches 50.0% recall (threshold 0.94) against 57.3% weighted. At the 85.0% recall target both land on 18.4% false alerts (`step_04`)
- 🟢 No threshold meets both targets. The word matcher reaches 85.0% recall at 0.73 (128 of 150) with 46 false alerts on 250 clear names (18.4%) (`step_04`)
- 🟡 Modeled, with the base rate as my assumption of 1 real match in every 10,000 customers: the edit matcher at its 10.0% limit gives about 2,778 false alerts for each true hit, the word matcher about 1,674 (`step_02`, `step_04`). The 150 of 400 in the synthetic set is not a base rate; use the false-alert rate, not the alert count, when you read across

## What it still gets wrong

- 🟢 A party known by a name that is not on the list is not found: `alias_unlisted` is caught 0 of 10 at 0.50 by the word matcher (1 of 10 by edit). The fix is a list that carries the alias, not a better score (`step_03`, `step_04`).
- 🟢 A different person with a listed party's exact name always alerts: `namesake` 8 of 8 at 1.00 under all three matchers. Separating them takes a second identifier such as a date of birth, which I did not model (`step_03`, `step_04`).
- 🟢 A surname one letter from a listed one looks like a typo: `near_name` 30 of 30 alert at 0.85, while the word matcher keeps 14 of 14 typo hits at 0.73. No name-only score separates the two (`step_04`).
- 🟢 The word matcher is worse than edit on two planted kinds. A particle joined to its surname ("Altavari" for "Al Tavari") is caught 2 of 8 at 0.75 against 8 of 8 for edit, and `translit_heavy` (three spelling changes my fold table does not know) is caught 5 of 10 against 10 of 10 (`step_04`).
- **The data and the rules share an author.** I wrote the generator that plants the variants and the matcher that folds them. Its fold table covers the 14 common spelling swaps the generator uses and none of the 12 rare ones, so some misses are built in, but the overlap flatters the translit numbers. Treat every figure as a ceiling for this data, not a rate on a real customer file, which I have not tested.
- 🟡 The mix of variants (24 order swaps, 22 transliterations, 8 namesakes and so on) and the two targets (10.0% false alerts, 85.0% recall) are my assumptions. A different mix moves every number.
- Not covered: names in non-Latin scripts (compared letter by letter, never transliterated), phonetic codes such as Soundex, secondary identifiers, and any commercial screening product. A swap of two letters costs two edits.

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What does matching only exact names catch? | `step_01_exact_match.py` |
| 2 | What does a threshold on whole-name edit similarity cost? | `step_02_edit_similarity.py` |
| 3 | Where does that approach break, and what no matcher fixes? | `step_03_deficiencies_exposed.py` |
| 4 | What do folded words, any order and rarity weights buy? | `step_04_token_matcher.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

Name screening against sanctions lists, where the practical question is how loosely to match a name and what the review queue costs. I did not read any regulator's or list publisher's published text for this project, so it cites none and takes no threshold, score scale or rule from one. Every threshold here is a value I swept, not a rule parameter. It is a prototype, aligned to that practice in outline and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Given names are common first names; surnames are invented from syllables. Nothing comes from any employer, customer, list publisher or real person, and any resemblance to a real name is chance. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/watchlist.csv`, `data/customers.csv` and `data/truth.csv` for your own and keep the columns (`entity_id, listed_name`; `customer_id, name`; `customer_id, truth, entity_id`). To try another matcher, add a class with a `score(a, b)` method to `src/name_match_eval.py` and register it in `make_matcher`. Read the [PRD](./PRD.md) for the scope I held to.
