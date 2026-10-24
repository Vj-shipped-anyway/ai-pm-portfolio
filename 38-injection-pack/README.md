# 🧪 Injection Pack: a regression suite for the rules of a prompt gateway

**I wanted to know whether a test pack can stop a pull request from quietly making a prompt gateway weaker, and which changes a 160-case pack can see. This is a command-line runner and a staged GitHub Action: it replays a pack of injection cases, the largest group of them hidden in retrieved documents, on the old and the new rules of a five-layer gateway, and fails the check when a case the old rules got right is now wrong.** The five layers and the retrieved-document attack path follow [06 PromptShield](../06-promptshield-prompt-injection-defense/); the cases, the rules and the runner here are new and nothing is imported from it.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 38-injection-pack/src && python3 injection_pack.py --demo
```

It prints:

```text
pack: 160 cases (100 attack, 60 benign)   rules: gateway-base -> gateway-demo-change
  changed: L2-04 pattern changed
  regression  PK-014 retrieved_doc/doc_note_to_ai: attack was blocked by L2-04, now allowed
  regression  PK-085 retrieved_doc/doc_polite_forward: attack was blocked by L2-04, now allowed
  regression  PK-114 retrieved_doc/doc_fake_system: attack was blocked by L2-04, now allowed
  regression  PK-123 retrieved_doc/doc_polite_forward: attack was blocked by L2-04, now allowed
  cases that got better: 0
before: 74 of 100 attacks blocked, 8 of 60 benign cases blocked
after:  70 of 100 attacks blocked, 8 of 60 benign cases blocked
decision: BLOCK (4 regressions)
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 injection_pack.py compare old_rules.json new_rules.json --pack pack.csv`. It exits 1 on a regression, so a CI step fails; `--format github` prints annotations; `run rules.json --pack pack.csv` reports one rule file by channel, with `--min-catch` and `--max-fp` as optional floors.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: a 160-case pack, a held-out population of 1000 attacks and 500 benign cases, and 51 planted rule changes; the script is named in brackets):

- 🟢 No pack in CI: 0 of 51 rule changes stopped, and 25 of 51 are harmful, meaning they block at least one point fewer attacks or one point more benign cases on the held-out population (`step_01`)
- 🟢 The base rules block 790 of 1000 held-out attacks and 37 of 500 benign cases; on the pack, 74 of 100 and 8 of 60. Of the 14 hard attacks the pack carries, 4 are blocked; of its 30 look-alike benign cases, 8 are blocked (`step_01`)
- 🟢 A smoke test of six well-known attack strings stops 3 of 25 harmful changes and 0 of 26 harmless ones, because the strings only reach layer 1 (`step_02`)
- 🟢 Three shortcut gates on the same pack: a fixed floor stops 5 of 25 harmful changes, attack cases only stops 16 of 25 and none of the 5 that only add false blocks, and a pack cut to every fourth case stops 12 of 25; 6 of 25 harmful changes pass all three (`step_03`)
- 🟢 The full pack compared case by case on the old and new rules: 21 of 25 harmful changes stopped (16 of 20 that lose attack coverage, 5 of 5 that add false blocks), 1 of 26 harmless changes stopped, and 46 of 51 decisions match the held-out truth (`step_04`)

## What it still gets wrong

- 🟢 Four of the 25 harmful changes pass (`step_04` prints each). RP-043 removes the rule for an encoded payload with a decode cue; the pack has no case for that technique (it is in the held-out population and not in the pack), so nothing regresses. That is the known limit, left in on purpose, and the tool prints a blind-spot note for it: 1 of the 4 passes came with that note. RP-009 and RP-021 touch a rule whose lost cases are phrasings of one technique that the pack's five cases for it do not include, and RP-033 does the same for fake system headers. A 100-attack pack samples phrasing thinly.
- 🟢 One harmless change is stopped: RP-042 drops one key from an egress pattern. It costs 7 of 1000 held-out attacks, under my one-point line, and the pack saw it. The pack is right about the change; my threshold calls it harmless. Move the line and both counts move.
- **The pack, the held-out population, the rules and the rule changes share an author.** I wrote the templates and the rules separately, but the population comes from the same templates as the pack, so it is a sibling and not independent traffic. I also changed the mix of look-alike benign cases after the first run, because my first mix blocked about a quarter of the held-out benign cases. Treat the results as a ceiling for these rules on this synthetic data, not a rate on a real gateway, which I have not tested.
- **The rules are regular expressions, and a real gateway has a classifier.** The runner reads a rule file. It does not call a live endpoint or a model, and each case is read by one layer, so a document that layer 2 misses and layer 4 would have caught is not tested as a chain.
- Layer 3 checks only the keys listed in `destination_keys`; one pack case puts the destination under another key and passes (tested in `test_engine.py`). The rules are English; the three translated documents in the pack are all missed. A regex has no timeout, so a pathological pattern in a rule file can hang the runner.
- 🔴 Hypothetical: that the Action works on a real pull request. It has not run on GitHub.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`, 54 tests in all across the folder).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What gets through when nobody runs injection tests on a rule change? | `step_01_no_pack.py` |
| 2 | What does a smoke test of six known strings catch? | `step_02_smoke_test.py` |
| 3 | Where does each shortcut gate fail? | `step_03_deficiencies_exposed.py` |
| 4 | What does the full pack catch, case by case? | `step_04_with_pack.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

[OWASP LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) (read 2026-10-23) separates direct injection, where a user's prompt changes the model's behavior, from indirect injection, where external content such as a web page or a file carries instructions. Among its mitigations it lists regular adversarial testing and attack simulations and input and output filtering. This pack is one way to keep those tests as a regression check on the filter rules. It is a prototype, aligned to that page and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, customer or real gateway. 🟡 Modeled: the harm line is one percentage point on the held-out population, and the floors in step 3 are the base rate with five points of slack; both are my assumptions, named in [data/README.md](./data/README.md). A prototype on synthetic data, not a production case study.

## Fork it

Replace `data/pack.csv` with your own cases, keeping the columns (`channel` decides which layer reads a case), and `data/gateway_rules.json` with your rules in the same shape, then run `python3 injection_pack.py run rules.json --pack pack.csv` to see where you stand. Read the [PRD](./PRD.md) for the scope I held to.
