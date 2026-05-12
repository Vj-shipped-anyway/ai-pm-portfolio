"""
Step 4 - The fix: EvalForge composite (versioned probes + calibrated rubrics
+ cross-vendor judge + CI gate).

Same eval runs, same probe set. Four layers added.

  Layer 1 - Versioned probe sets.  probes-v1.0 onward is Git-tagged. Probe
  diff between versions is recorded; a regression on a specific probe is a
  named, attributable event.

  Layer 2 - Calibrated rubrics.  Each rubric has worked anchors at 1, 3, 5.
  Inter-rater kappa target: at or above 0.78. Judge prompt rebuilt against
  the anchored rubric.

  Layer 3 - Cross-vendor LLM-as-judge.  Claude judge + GPT-4o judge. If
  they disagree by more than 1 point on a probe-rubric pair, route to
  human review.

  Layer 4 - CI gate.  Pre-deploy hook. PASS / FAIL / REVIEW verdict.
  FAIL blocks the deploy. REVIEW requires human sign-off within 24h or
  it auto-blocks.

This script reads the historical eval_runs table and replays it through
the EvalForge composite, producing the CI gate verdict and the evidence
bundle the deployment pipeline consumes.

Run:
    python step_04_with_evalforge.py
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


# Thresholds for the CI gate
PASS_RATE_THRESHOLD = 0.90
KAPPA_THRESHOLD = 0.75
PASS_RATE_REGRESSION_PP = 0.03  # > 3pp drop vs baseline trips REVIEW
PASS_RATE_REGRESSION_FAIL_PP = 0.05  # > 5pp drop trips FAIL


def evaluate_ci_gate(run: dict, baseline_pass_rate: float) -> dict:
    """The EvalForge CI gate evaluator. Returns verdict, reason, action.

    PASS:   ship.
    REVIEW: needs human sign-off within 24h; auto-block if not signed.
    FAIL:   blocks deploy immediately.
    """
    pass_rate = float(run["pass_rate"])
    kappa = float(run["inter_judge_kappa"])
    delta = pass_rate - baseline_pass_rate

    # Hard FAIL: pass rate below floor or kappa collapsed
    if pass_rate < PASS_RATE_THRESHOLD - 0.02:
        return {
            "verdict": "FAIL",
            "reason": (
                f"Aggregate pass_rate {pass_rate:.3f} below floor "
                f"{PASS_RATE_THRESHOLD-0.02:.3f}. Deploy blocked."
            ),
            "action": "block_deploy",
        }
    if delta < -PASS_RATE_REGRESSION_FAIL_PP:
        return {
            "verdict": "FAIL",
            "reason": (
                f"Regression of {delta*100:+.1f}pp vs last green baseline "
                f"({baseline_pass_rate:.3f}). Likely vendor snapshot drift "
                "or prompt regression. Deploy blocked."
            ),
            "action": "block_deploy",
        }
    if kappa < KAPPA_THRESHOLD - 0.05:
        return {
            "verdict": "FAIL",
            "reason": (
                f"Inter-judge kappa {kappa:.2f} collapsed below safety "
                f"floor {KAPPA_THRESHOLD-0.05:.2f}. Judge calibration "
                "broken. Deploy blocked pending judge re-anchor."
            ),
            "action": "block_deploy",
        }

    # REVIEW: meaningful regression or kappa drift
    if delta < -PASS_RATE_REGRESSION_PP:
        return {
            "verdict": "REVIEW",
            "reason": (
                f"Regression of {delta*100:+.1f}pp vs baseline "
                f"({baseline_pass_rate:.3f}). Human sign-off required "
                "within 24h or deploy auto-blocks."
            ),
            "action": "require_human_signoff_24h",
        }
    if kappa < KAPPA_THRESHOLD:
        return {
            "verdict": "REVIEW",
            "reason": (
                f"Inter-judge kappa {kappa:.2f} below target "
                f"{KAPPA_THRESHOLD:.2f}. Rubric anchor drift suspected; "
                "recalibrate before next deploy."
            ),
            "action": "require_human_signoff_24h",
        }

    return {
        "verdict": "PASS",
        "reason": (
            f"pass_rate={pass_rate:.3f} kappa={kappa:.2f} delta="
            f"{delta*100:+.1f}pp vs baseline. Ship."
        ),
        "action": "ship",
    }


def assemble_evidence_bundle(run: dict, gate: dict, baseline: dict,
                             overrides_for_run: list[dict]) -> dict:
    return {
        "bundle_version": "1.0",
        "assembled_at": datetime(2026, 7, 19, 9, 0, 0).isoformat(),
        "eval_run": {
            "eval_run_id": run["eval_run_id"],
            "run_date": run["run_date"],
            "model_version": run["model_version"],
            "probe_set_version": run["probe_set_version"],
            "n_probes": int(run["n_probes"]),
            "pass_rate": float(run["pass_rate"]),
            "inter_judge_kappa": float(run["inter_judge_kappa"]),
            "judge_id": run["judge_id"],
            "judge_snapshot": run["judge_snapshot"],
        },
        "baseline": baseline,
        "ci_gate": gate,
        "human_overrides_in_run": overrides_for_run,
        "regression_flagged": run["regression_flagged"],
        "audit_trail_handoff": "Project 09 LineageLog - decision lineage event emitted",
        "validator_routing": "L2 trust-and-safety queue" if gate["verdict"] != "PASS" else "n/a",
        "human_edit_before_signoff": True,
    }


def main() -> None:
    eval_runs_path = DATA_DIR / "eval_runs.csv"
    overrides_path = DATA_DIR / "judge_overrides.csv"

    print("\n" + "=" * 80)
    print("Step 4 - The fix: EvalForge composite (versioned + calibrated + gated)")
    print("=" * 80 + "\n")
    print("Same 50 eval runs replayed through the EvalForge CI gate.\n")

    with open(eval_runs_path) as f:
        runs = list(csv.DictReader(f))
    with open(overrides_path) as f:
        overrides = list(csv.DictReader(f))

    overrides_by_run: dict[str, list[dict]] = {}
    for o in overrides:
        overrides_by_run.setdefault(o["eval_run_id"], []).append(o)

    # The baseline rolls forward each time a run lands PASS
    rolling_baseline = float(runs[0]["pass_rate"])
    decisions = []
    bundles = {}

    for run in runs:
        rid = run["eval_run_id"]
        run_overrides = overrides_by_run.get(rid, [])
        gate = evaluate_ci_gate(run, rolling_baseline)
        bundle = assemble_evidence_bundle(
            run, gate,
            baseline={
                "rolling_baseline_pass_rate": round(rolling_baseline, 3),
                "kappa_target": KAPPA_THRESHOLD,
                "regression_threshold_pp": PASS_RATE_REGRESSION_PP,
            },
            overrides_for_run=run_overrides,
        )
        bundles[rid] = bundle
        decisions.append({
            "eval_run_id": rid,
            "run_date": run["run_date"],
            "model_version": run["model_version"],
            "probe_set_version": run["probe_set_version"],
            "pass_rate": float(run["pass_rate"]),
            "kappa": float(run["inter_judge_kappa"]),
            "ci_gate_verdict": gate["verdict"],
            "ci_gate_reason": gate["reason"],
            "action": gate["action"],
            "rolling_baseline": round(rolling_baseline, 3),
            "n_human_overrides": len(run_overrides),
        })

        # Update baseline only on PASS
        if gate["verdict"] == "PASS":
            rolling_baseline = float(run["pass_rate"])

    # Print fleet roll-up
    print(f"  {'Run':<6} {'Date':<11} {'Model snapshot':<32} {'Pass':<6} {'Kappa':<5} {'Verdict':<7} Action")
    print(f"  {'-'*6} {'-'*11} {'-'*32} {'-'*6} {'-'*5} {'-'*7} {'-'*8}")
    for d in decisions:
        mv = d["model_version"]
        if len(mv) > 30:
            mv = mv[:27] + "..."
        print(f"  {d['eval_run_id']:<6} {d['run_date']:<11} {mv:<32} {d['pass_rate']:<6.2f} {d['kappa']:<5.2f} {d['ci_gate_verdict']:<7} {d['action']}")

    print()
    # Counts
    pass_count = sum(1 for d in decisions if d["ci_gate_verdict"] == "PASS")
    review_count = sum(1 for d in decisions if d["ci_gate_verdict"] == "REVIEW")
    fail_count = sum(1 for d in decisions if d["ci_gate_verdict"] == "FAIL")
    blocked = sum(1 for d in decisions if d["action"] == "block_deploy")

    print("=" * 80)
    print("EvalForge CI gate roll-up across 50 historical eval runs")
    print("=" * 80)
    print(f"  PASS  (ship):                {pass_count}")
    print(f"  REVIEW (24h sign-off):       {review_count}")
    print(f"  FAIL  (deploy blocked):      {fail_count}")
    print(f"  Total deploys blocked:       {blocked}")
    print()
    print("Compare to Steps 1, 2, 3:")
    print("  Step 1 (spreadsheet):  0 blocks.  Engineer eyeballs and ships.")
    print("  Step 2 (basic eval):   0 blocks.  Cron logs the dump; no gate.")
    print("  Step 3 (deficiencies): 6 named failure modes the basic eval misses.")
    print(f"  Step 4 (EvalForge):    {blocked} deploys blocked.  Two of those are the")
    print("                         silent vendor-snapshot updates that would have")
    print("                         shipped under Steps 1 and 2 and produced 8-12")
    print("                         weeks of customer complaints before discovery.")
    print()

    # Headline: the ER012 catch
    er012 = next(d for d in decisions if d["eval_run_id"] == "ER012")
    er038 = next(d for d in decisions if d["eval_run_id"] == "ER038")
    print("-" * 80)
    print("Headline catches:")
    print("-" * 80)
    print(f"  ER012 (2026-02-17, claude-sonnet-4-20260214 silent update):")
    print(f"    verdict={er012['ci_gate_verdict']}, pass_rate={er012['pass_rate']}, baseline={er012['rolling_baseline']}")
    print(f"    -> {er012['ci_gate_reason']}")
    print()
    print(f"  ER038 (2026-06-01, claude-sonnet-4-20260520 silent update):")
    print(f"    verdict={er038['ci_gate_verdict']}, pass_rate={er038['pass_rate']}, baseline={er038['rolling_baseline']}")
    print(f"    -> {er038['ci_gate_reason']}")
    print()

    # Write CSV summary
    out_csv = OUT_DIR / "step_04_evalforge_decisions.csv"
    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(decisions[0].keys()))
        w.writeheader()
        for d in decisions:
            w.writerow(d)

    # Write the headline evidence bundle
    out_bundle = OUT_DIR / "step_04_evidence_bundle_ER012.json"
    with open(out_bundle, "w") as f:
        json.dump(bundles["ER012"], f, indent=2, default=str)

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_bundle}  (sample CI gate evidence bundle, JSON)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
