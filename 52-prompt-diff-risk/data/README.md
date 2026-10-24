# Data for project 52

Synthetic. Produced by `_generate.py` with a fixed seed, so a rerun reproduces every file byte for byte. Nothing here comes from a real prompt, bank, vendor or employer. No model was called: the probes that "fail" after each edit are planted by the generator.

| File | What it holds |
|---|---|
| `base_prompts.json` | The 6 assistant prompts as they stand before any pull request (plain text, `#` lines are headings or comments) |
| `pr_cases.csv` | 70 pull requests: `pr_id`, `assistant`, `old_prompt`, `new_prompt` |
| `pr_truth.csv` | The planted edit per pull request: `change_kind`, `truth_class` (high, medium, low), `truth_slices`, `failing_probes`, `changed_item`. The label comes from the edit that was planted, not from the classifier |
| `probes.csv` | 54 probes, 6 in each of 9 slices: `probe_id`, `slice`, `severity`, `question`, `expected_behavior` |
| `slices.csv` | The 9 slices with their dimension, severity and probe count |
| `tools.json` | The 8 tools (4 read, 4 write) with an explicit `access` field |
| `example_old.txt`, `example_new.txt` | The worked example behind `python3 prompt_diff_risk.py --demo` (one rule weakened, one scope line added, one comment line edited) |

Planted edits (70): high risk 22 = rule removed 5, rule weakened to a soft word 4, rule given an exception 3, rule narrowed by a short clause 3, write tool granted 4, confirmation condition dropped from a write tool 3. Medium risk 30 = new rule 3, number changed in a rule or fact 5, scope line added 3, scope line removed 2, scope line narrowed or widened 2, tone changed 4, read tool granted 3, tool dropped 2, routing target swapped 3, tone image swapped 3. Low risk 18 = heading or comment edit 5, typo fixed 3, rule reworded with the same meaning 7, background sentence removed 3.

Failing probes are planted for every medium and high pull request: 2 per truth slice for high risk, 1 for medium risk, 74 in all. Low-risk pull requests have none.

Four kinds are hard on purpose. The routing swap and the tone-image swap change one word inside a long sentence with no rule word, tone word, tool name or number: a risky edit the rules cannot see. The short-clause narrowing keeps the rule word: a risky edit the rules may only send to review. The reworded rule and the removed background sentence are harmless edits the rules may flag.
