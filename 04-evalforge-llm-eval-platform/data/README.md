# Sample Data — EvalForge walkthrough

Four CSVs that drive Steps 1 through 4 of the walkthrough. Everything here is synthetic, seeded, and reproducible. No customer data. No PII. The shapes are calibrated against published BFSI GenAI deployment patterns and Hamel Husain's eval-first writing.

---

## `probes.csv` — 60 versioned eval probes

The eval set itself. Each row is one probe — a question we send the deployed assistant and a documented expected behavior. Probes are versioned (the eval-run table records which probe-set version a run used) so a regression on a specific probe is a real, attributable event, not a vibes diff.

| Field | Description |
| --- | --- |
| `probe_id` | Stable identifier. Once published, never reused. |
| `question` | The natural-language input we send the assistant. |
| `expected_behavior` | What a correct response looks like — written by the L1 product owner and reviewed by L2 trust-and-safety. Not a regex; a behavior contract. |
| `deficiency_class_tested` | Which of the six EvalForge deficiencies this probe is designed to surface. |
| `slice` | The behavioral slice this probe belongs to — `refusal_edge`, `policy_specific`, `account_specific`, `fraud_workflow`, etc. Lets us compute slice-level pass-rate, not just aggregate. |
| `severity` | `high` / `med` / `low` — used by the CI gate to weight blocking decisions. A `high` regression blocks; a `low` one warns. |

Composition: 60 probes across 6 deficiency classes and ~15 behavioral slices. Weighted heavier toward the high-severity cases (PII refusal, fraud workflow, advice-boundary, identity disclosure) because those are the ones that actually hit customers when they regress.

---

## `rubrics.csv` — 12 calibration rubric criteria

The scoring rubric the LLM-as-judge applies, and the calibration anchors a human reviewer uses to override. The whole reason this file exists is that "is the answer correct?" without anchors gives you ~0.55 inter-rater kappa. Anchor every score on the 1-5 scale and you get kappa above 0.78.

| Field | Description |
| --- | --- |
| `rubric_id` | Stable identifier (R001-R012). |
| `criterion` | The thing being measured (Answer Accuracy, Refusal Appropriateness, Source Citation, …). |
| `scale_low` / `scale_high` | Always 1 and 5. |
| `calibration_anchors` | Worked examples for scores 1, 3, and 5 — the part that makes the rubric usable across reviewers. |
| `deficiency_class_addressed` | Which of the six EvalForge deficiencies this rubric helps catch. |
| `owning_role` | L1 product / L2 trust-and-safety / L3 compliance — who signs off on changes to this rubric. |

The 12 criteria cover answer accuracy, refusal appropriateness, citation truthfulness, compliance-boundary adherence, identity disclosure, recording-and-privacy disclosure, and complaint-right acknowledgement. Each is anchored, each is owned, each is versioned.

---

## `eval_runs.csv` — 50 historical eval runs across 6 model versions

The flight log. Each row is one nightly or pre-deploy eval run, with the model snapshot, the probe set version, the judge configuration, and the CI gate verdict.

| Field | Description |
| --- | --- |
| `eval_run_id` | Stable identifier (ER001-ER050). |
| `run_date` | When the run executed. |
| `model_version` | The vendor snapshot of the assistant being evaluated. |
| `probe_set_version` | Pinned probe set version. |
| `n_probes` | Probe count at that version (the set grew from 30 to 60 over the walkthrough window). |
| `pass_rate` | Aggregate pass rate. |
| `judge_id` | Which judge configuration scored this run. Cross-vendor judging (Claude + GPT-4o) lights up at ER021. |
| `judge_snapshot` | The judge model's own snapshot pin — critical for catching the "judge silently drifted" failure mode. |
| `inter_judge_kappa` | Cohen's kappa between primary and secondary judge. Drift below 0.7 fires a calibration alert. |
| `ci_gate_verdict` | `PASS` / `FAIL` / `REVIEW` — what EvalForge tells the deployment pipeline. |
| `regression_flagged` | `yes` / `no` / `partial` — whether the run flagged a behavioral regression vs the last green baseline. |
| `human_override_count` | How many judge scores got overridden by a human reviewer this run. |
| `notes` | Free-text — vendor updates, rubric recalibration, probe-set bumps. |

**The narrative arc inside this file.** ER001-ER011 is the pre-EvalForge world (clean PASS streak but inter-judge kappa quietly drifting from 0.78 to 0.70). ER012 is the Anthropic Feb-14, 2026 silent snapshot update — the probe set catches it, pass rate drops to 0.86, regression flags. ER017-ER019 is the rubric recalibration + prompt patch. ER021 introduces cross-vendor judging. ER038 is the second silent vendor update (claude-sonnet-4-20260520) — the CI gate blocks deploy on first run. ER050 is the current production baseline.

---

## `judge_overrides.csv` — 30 human-override-of-judge events

The audit-trail-of-overrides table. Every time a human reviewer disagreed with the LLM-as-judge's score, the override is logged with the reason. This is the file that catches deficiency #6 (no human override audit). Without it, calibration drift accumulates silently — reviewers learn to override certain rubrics in certain slices and nobody notices the pattern.

| Field | Description |
| --- | --- |
| `override_id` | Stable identifier. |
| `eval_run_id` | Which run this override belonged to. |
| `probe_id` | Which probe was scored. |
| `rubric_id` | Which rubric criterion the override applied to. |
| `judge_score` | What the LLM-as-judge gave (1-5). |
| `human_score` | What the reviewer gave (1-5). |
| `reviewer_id` | Who overrode. Lets us spot reviewer-specific drift. |
| `override_reason` | Free-text rationale. The data behind the calibration-drift detector. |
| `deficiency_class_addressed` | Which of the six deficiencies the override pattern is evidence for. |

**What the override table reveals.** Eight overrides cluster on rubric R002 (Refusal Appropriateness) on the refusal-edge slice after the Feb-14 vendor update — that pattern is the rubric-drift signal EvalForge raises to L2 trust-and-safety. Five overrides cluster on R010 (Identity Disclosure) on the post-vendor-update window — that's the judge-drift signal.

---

## How the four files connect

```
probes.csv  ──┬──>  eval_runs.csv  (50 runs × 60 probes × scored on rubrics)
              │              │
              │              v
              │      CI gate evaluator
              │              │
              │              v
              ├────>  judge_overrides.csv  (when humans disagreed and why)
              │
              v
        rubrics.csv  (12 criteria with calibration anchors)
```

Reproducibility: every value above is hand-curated to match the README narrative. The step scripts in `src/` read these CSVs and print a story that matches the walkthrough text. Re-run any step script and the output will match the README to the digit.
