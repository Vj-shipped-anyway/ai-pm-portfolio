# 🚦 Eval Gate: a CI gate on probe-set regression

**I wanted to know what stops a deploy when a model vendor changes the snapshot behind an API name and the pass rate on my probes barely moves. In a pipeline that gates only on the pass rate, the answer is nothing. This is a command-line gate and a staged GitHub Action: it reads a probe file and a results file, compares the snapshot id each response reported with the one I pinned, and prints ALLOW, REVIEW or BLOCK.** It takes the CI gate in [04 EvalForge](../04-evalforge-llm-eval-platform/) and turns it into a command that reads two files, so any pipeline can run it. The 3 and 5 point lines are 04's; the rules around them are new.

**▶ Static demo, no install:** [open demo.html](./demo.html)

## Run one now

```bash
cd 40-eval-gate/src && python3 eval_gate.py --demo
```

It prints:

```text
run: single run   pin vendor-balanced-4-20260214   30 of 30 probes scored
pass rate 0.89 against a baseline of 0.93 (-3.7 points)
  [BLOCK ] snapshot_changed 30 of 30 probes were served by vendor-balanced-4-20260811, not the pinned vendor-balanced-4-20260214. Read the vendor's notice and re-run before moving the pin.
  [REVIEW] overall_drop     mean pass rate 0.89 is 3.7 points below the baseline 0.93 (review above 3.0, block above 5.0).
  [BLOCK ] probe_collapse   high-severity probe P005 fell from 1.00 to 0.50.
  [BLOCK ] probe_collapse   high-severity probe P009 fell from 1.00 to 0.10.
decision: BLOCK
```

Standard library only, Python 3.9 or newer. To check your own files: `python3 eval_gate.py check probes.csv results.csv --pin vendor-balanced-4-20260214`. It exits 1 on BLOCK, so a CI step fails; `--format github` prints annotations. The probe file needs `probe_id`, `severity` and `baseline_rate`; the results file needs `probe_id`, `passes`, `trials` and `served_model`.

## What the numbers say

**What it shows** (🟢 measured on synthetic data: 64 planted deploys of a 30-probe set; the script is named in brackets):

- 🟢 No check on the served id: 0 of 64 deploys stopped, 17 of 64 had a probe answered by an id other than the pin (7 of those were partial rollouts), and 11 of 64 lost more than 5 points of mean pass rate (`step_01_no_gate.py`)
- 🟢 A pass-rate floor of 0.90 stops 13 of 25 should-block deploys and passes all 6 silent swaps whose scores did not move (`step_02_pass_rate_floor.py`)
- 🟢 An alarm on any id change stops 23 of 25 should-block deploys and also stops 6 of 31 fine ones, the swaps the team had announced (`step_03_deficiencies_exposed.py`)
- 🟢 The pin alone stops 17 of 25 and 0 of 31 fine; the probe rules alone stop 17 of 25 and flag 5 of 8 should-review. They miss different deploys (`step_03_deficiencies_exposed.py`)
- 🟢 Pin, coverage, drop and collapse together: 25 of 25 should-block deploys stopped, 5 of 8 should-review flagged, 0 of 31 fine blocked and 1 of 31 sent to review; the decision matches the planted truth on 59 of 64 (`step_04_with_gate.py`)

## What it still gets wrong

- 🟢 Three subtle drifts pass: RUN-042, RUN-052 and RUN-061 (`step_04_with_gate.py` prints each). The id is unchanged and the mean pass rate moved about two points, which ten trials per probe cannot tell from noise; the worst clean run sat 3.3 points under its baseline.
- 🟢 1 of 31 fine runs goes to review on noise alone (`step_04_with_gate.py`), and one of the three moderate drifts reached BLOCK where I labeled it REVIEW.
- **The test set and the rules share an author.** I planted the events and wrote the rules, so 25 of 25 shows the rules cover what I planted. Treat it as a ceiling for these rules, not a rate on a real pipeline, which I have not tested.
- **The blocking of a silent swap that scores the same is my policy.** The truth label says an id change nobody announced is read before it ships. If you would rather ship on a flat score, drop the first rule; the other three still run.
- **The pin is only as good as the person who moves it.** Updating it without reading the vendor's notice turns rule one into a formality.
- The gate trusts `served_model`. If the harness copies the id it asked for instead of the one the response reported, or a gateway rewrites the id, the comparison means nothing. The match is an exact string; a vendor that reports the same model under two spellings would raise a false BLOCK.
- 🟡 The 3 and 5 point lines and the 0.90 pass-rate threshold are the constants 04 uses, taken here as assumptions. The 50-point collapse line is mine. None is tuned on real traffic.
- The gate reads `passes` as given. It does not judge answers, so judge noise is outside it, and it does not refresh the baseline.

## Use it in CI

[`action/`](./action/README.md) holds a staged GitHub Action and the steps to publish it from its own repository, which a Marketplace listing requires. It has not been published and has not run on GitHub. What is tested is the command it wraps (`tests/test_cli.py`; 46 tests in `tests/` in all).

## How the four steps fit

| Step | Question | Script |
|---|---|---|
| 1 | What ships when nothing checks the served snapshot? | `step_01_no_gate.py` |
| 2 | What does a pass-rate floor catch and miss? | `step_02_pass_rate_floor.py` |
| 3 | Where does each half fail alone? | `step_03_deficiencies_exposed.py` |
| 4 | What do pin, coverage, drop and collapse catch together? | `step_04_with_gate.py` |

Run any of them from `src/`. Data is generated by [`data/_generate.py`](./data/README.md); the check in `tools/check_repo.py` confirms that a rerun reproduces every file and that the green numbers above appear in a script's output.

## Aligned to

The [NIST AI RMF Playbook](https://airc.nist.gov/AI_RMF_Knowledge_Base/Playbook/Measure), MEASURE 2.4, which I read on 2026-10-23 (the page shows no publication date). It covers monitoring AI systems once they are in production and suggests comparing production metrics with pre-deployment test results. This gate runs a related comparison earlier, on the candidate deploy, and does no production monitoring. It is a prototype, aligned to that guidance and not compliant with or certified against anything.

## Data and limits

Synthetic, seeded, byte-for-byte reproducible. Nothing comes from any employer, vendor or real model. A prototype on synthetic data, not a production case study.

## Fork it

Swap `data/probes.csv` and `data/runs.csv` for your own exports and keep the columns, or skip the data and point `check` at your harness output. Read the [PRD](./PRD.md) for the scope I held to.
