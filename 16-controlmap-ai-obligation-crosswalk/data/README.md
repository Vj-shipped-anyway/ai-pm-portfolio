# Sample Data — ControlMap walkthrough

Four CSVs drive Steps 1 through 4 of the walkthrough. Everything is synthetic, seeded (`SEED = 20261018` in `_generate.py`) and reproducible by running `python3 _generate.py`; running it twice produces identical files. The generator uses only the Python standard library and runs on Python 3.9. **No customer data. No real bank, control library, vendor, regulator file or incident. Every owner, team and reviewer is an invented code. The obligation statements are paraphrases written for this exercise, not the text of any rule.**

**The truth is known because the data is synthetic.** The generator decides which control meets which obligation, so it can score any crosswalk method. A real control library does not hand you that; the first job in a real deployment is getting a control owner and a second-line reviewer to agree on a sample of true pairs.

The headline scenario the walkthrough resolves: **a modeled bank answers 48 AI-related obligations from four frameworks with 60 controls and 153 evidence items. A keyword spreadsheet gives the right status to 23 of 48 obligations. ControlMap, which reads the wording through a theme dictionary, checks the control's scope and dates the evidence, gives the right status to 46 of 48.**

**Seed and wording, stated plainly.** The seed is today's date as a number. I chose it once and did not try others; it only picks evidence dates, reviewer codes and evidence types. The obligations and controls are written by hand, not drawn at random. After the first run I reworded 5 controls and 2 obligations so the truth could not be argued (for example the inventory control no longer says it lists each system's "purpose", so nobody can read it as partly meeting the NIST map-function obligation). I later replaced the word "assistant" with "chatbot" in 7 control texts for consistency; because the control ids and the evidence dates both derive from the seed and the names, that renumbered the ids and redrew the dates. I did not change anything to reach a target score; the rewording did move which words overlap, so the keyword numbers moved a little.

**This is a test set, not an estimate.** It is dense on purpose: 11 orphan controls, 6 themes with no control and 7 stale obligations appear often enough to count. How often these failures occur in a real control library is a separate question this data cannot answer.

---

## `obligations.csv` — 48 obligations

| Column | Type | What it is |
| --- | --- | --- |
| `obligation_id` | string | `OB-01` onward, grouped by framework. |
| `framework` | string | One of `EU AI Act`, `Model risk guidance (SR 26-2)`, `NIST AI RMF`, `ECOA / Regulation B`. 12 rows each. |
| `theme` | string | The subject the obligation is about, assigned by me. 20 distinct themes; 12 of them appear in more than one framework (38 of the 48 obligations). |
| `statement` | string | A paraphrase written for this exercise, not the text of the rule. |
| `applies_to` | string | The use-case classes the modeled bank applies it to, semicolon-separated, or `all`. This is how the modeled bank scoped each row, not a reading of any law. Classes: `credit_decision`, `customer_chat`, `internal_copilot`, `fraud_scoring`. |

```
obligation_id,framework,theme,statement,applies_to
OB-01,EU AI Act,risk management,Keep a written risk process for each high-risk AI system and update it as the system changes.,credit_decision;fraud_scoring
OB-02,EU AI Act,data governance,"Check that data used to build and test the system is relevant, representative and free of known errors.",credit_decision;fraud_scoring
OB-03,EU AI Act,technical documentation,"Prepare documents that describe the system's design, purpose and limits before it goes live.",credit_decision
```

## `controls.csv` — 60 controls

| Column | Type | What it is |
| --- | --- | --- |
| `control_id` | string | `CT-01` onward. The order is shuffled by a hash of the seed and the name, so it does not reveal which controls are orphans. |
| `name`, `description` | strings | Written by hand. These are the only fields a keyword sheet or the dictionary reads. |
| `owner` | string | An invented function name, for example `Model Risk Management`. |
| `test_frequency_days` | int | The control's test cycle: 30, 90, 180 or 365. Evidence is stale when its latest item is older than 1.5 times this. |
| `scope` | string | The use-case classes the control runs for, or `all`. |
| `status` | string | `active` or `retired`. Retired controls meet nothing. |

```
control_id,name,description,owner,test_frequency_days,scope,status
CT-01,Fair lending compliance program,Written program with named owners for fair lending testing and issue follow-up.,Fair Lending Office,180,credit_decision,active
CT-02,Benchmark replication exercise,Second-line analysts rebuild the model's headline results from raw data and reconcile any difference.,Model Risk Management,365,credit_decision;fraud_scoring,active
CT-03,Legacy scorecard validation,Annual validation of the previous credit scorecard; closed when the scorecard was replaced.,Model Risk Management,365,credit_decision,retired
```

What the generator builds on purpose (design labels from `_generate.py`, which prints them):

- **11 orphan controls** that meet no obligation (2 retired). Of these, 6 are lookalikes that share words with an obligation (for example a network-traffic control that shares "monitoring" with the model-monitoring obligations) and 1 is a developer self-check whose description names "independent validation" only to say it is not one.
- **Different words, same meaning.** Most true controls are worded differently from the obligation they meet, so a keyword sheet misses many of the pairs. 2 of the controls are worded outside the synonym dictionary in `src/step_04`; they are the known limit.
- **Scope mismatches.** 62 of the 156 true pairs are partial: the control serves the theme but its scope misses a class the obligation applies to.
- **Themes with no control at all.** 6 themes (8 obligations) have no control.

## `evidence.csv` — 153 evidence items

| Column | Type | What it is |
| --- | --- | --- |
| `evidence_id` | string | `EV-001` onward. |
| `control_id` | string | Join key to `controls.csv`. |
| `evidence_type` | string | One of `test result`, `review minutes`, `system report`, `sample check`, `attestation`, `exception log`. |
| `collected_on` | date | ISO date. The reference date is the constant `AS_OF = 2026-09-30` in the generator; nothing reads the clock. |
| `reviewer` | string | An invented reviewer code, `R-01` to `R-09`. |

```
evidence_id,control_id,evidence_type,collected_on,reviewer
EV-001,CT-01,sample check,2025-08-13,R-01
EV-002,CT-01,exception log,2026-02-05,R-09
EV-003,CT-01,system report,2026-08-06,R-02
```

The 1.5 factor is an assumption of the modeled bank, not a requirement of any framework. Each control is given a fate: fresh (latest item inside one test cycle), late (inside 1.5 cycles, so still fresh by the rule), stale (outside 1.5 cycles) or none. The seed only picks the exact dates. As of 2026-09-30: 48 controls have fresh evidence, 9 have stale evidence and 3 have none.

## `truth_map.csv` — 156 true pairs (the ground truth)

| Column | Type | What it is |
| --- | --- | --- |
| `obligation_id`, `control_id` | strings | A control that meets the obligation. |
| `coverage` | string | `full` when the control's scope includes every class the obligation applies to, `partial` otherwise. |

```
obligation_id,control_id,coverage
OB-01,CT-04,full
OB-01,CT-25,full
OB-01,CT-38,full
OB-01,CT-53,full
```

Rules the generator applies:

- Each control is written with a hidden list of themes it serves. A control that serves a theme meets every obligation filed under that theme. That is the crosswalk's unit: a theme, not a sentence.
- Coverage is judged one control at a time. A design guard in the generator checks that no obligation is covered only by partial controls that together span its classes (0 found), so "partial" is never arguable.
- The true status of an obligation is derived from the pairs and the evidence: COVERED (a full-scope control with fresh evidence), STALE (a full-scope control, none fresh), PARTIAL (only partial controls), UNCOVERED (no control). Truth totals: COVERED 25, STALE 7, PARTIAL 8, UNCOVERED 8.
- Freshness is a definition, not a finding. The generator and ControlMap apply the same 1.5-times-the-cycle rule to the same dates, so their agreement on freshness and on the full or partial label holds by construction. The part that is not by construction is the wording match.

---

## Headline scenario — vendor model oversight (OB-12)

| Source | What it gives you |
| --- | --- |
| `obligations.csv` | OB-12, EU AI Act, theme `vendor model oversight`, applies to all classes. |
| `controls.csv` | 7 controls share words with it; 4 serve the theme, 2 with full scope and 2 with partial. |
| `evidence.csv` | The newest evidence among the full-scope controls is 812 days old; the limit is 547 days. |
| `truth_map.csv` | 4 true pairs. The true status is STALE. |

Replay the walkthrough and you see the same thing three ways: one list per framework (a separate evidence request), a keyword sheet (COVERED, with no evidence date), and ControlMap (STALE, with the control, its scope and the evidence age).
