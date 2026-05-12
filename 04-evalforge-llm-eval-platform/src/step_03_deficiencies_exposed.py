"""
Step 3 - Where this still breaks: 6 named eval-system deficiencies.

The basic eval (Step 2) gives you binary pass/fail on an aggregate set. It
catches catastrophic breaks. It misses everything subtle.

There are six named deficiencies that matter for GenAI evals in regulated
contexts. This script walks each one with a concrete example pulled from the
eval_runs and judge_overrides tables.

Run:
    python step_03_deficiencies_exposed.py
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


DEFICIENCY_DEFS = {
    "no_probe_versioning": {
        "name": "No probe versioning",
        "summary": (
            "The eval set is 'the spreadsheet a senior engineer maintains.' "
            "No version history. If a probe gets edited, the diff lives in "
            "the engineer's head."
        ),
        "failure_mode": (
            "ER001-ER008 ran probes-v0.7 with 30 probes; ER009 jumped to "
            "probes-v0.8 with 45 probes. Nowhere is the diff captured - "
            "which 15 probes were added, who reviewed them, what slice "
            "coverage changed. Six months later nobody can explain why "
            "the pass rate moved."
        ),
    },
    "no_rubric_calibration": {
        "name": "No rubric calibration",
        "summary": (
            "The rubric ('is the answer correct?') has 3 different "
            "interpretations across 3 reviewers. Inter-rater agreement is "
            "below 0.6 in practice."
        ),
        "failure_mode": (
            "Cluster of overrides on rubric R002 (Refusal Appropriateness) "
            "in ER005-ER006 - three different reviewers gave different "
            "scores on the same probes. Without calibration anchors, the "
            "rubric is unstable - the judge score depends on which "
            "reviewer trained the prompt."
        ),
    },
    "no_judge_drift_detection": {
        "name": "No judge drift detection",
        "summary": (
            "The LLM-as-judge model itself can update silently; judge "
            "scores drift without anyone noticing."
        ),
        "failure_mode": (
            "Inter-judge kappa drifted from 0.78 (ER001) to 0.70 (ER011) "
            "while pass rate stayed flat at ~0.92. The judge was getting "
            "more lenient. Then ER012's vendor update produced a real "
            "regression and the basic eval framework had no baseline "
            "calibration to compare against."
        ),
    },
    "no_ci_gate": {
        "name": "No CI gate",
        "summary": (
            "Eval runs as a manual ad-hoc activity, not a deployment gate. "
            "Engineering ships first, checks the dashboard later."
        ),
        "failure_mode": (
            "ER012's vendor update on 2026-02-17 dropped pass rate from "
            "0.91 to 0.86 - a real regression - but the eval ran two days "
            "after deploy. With no pre-deploy CI gate, the regression went "
            "live, customer complaints accumulated, the issue got "
            "discovered via the complaint backlog 8 weeks later."
        ),
    },
    "no_behavioral_regression_suite": {
        "name": "No behavioral regression suite",
        "summary": (
            "When the prompt changes, only 'did the answer change' gets "
            "checked, not 'did the behavior shift on the edge cases.'"
        ),
        "failure_mode": (
            "Eight probes in the high-severity slices (fraud_workflow, "
            "account_specific, pii_refusal) regressed silently on ER012. "
            "Aggregate pass rate moved from 0.91 to 0.86 (-5pp). The "
            "fraud_workflow slice specifically moved from 0.95 to 0.78 "
            "(-17pp) - that is a customer-facing regression that hits the "
            "exact moment a customer needs the assistant most."
        ),
    },
    "no_human_override_audit": {
        "name": "No human override audit",
        "summary": (
            "When a reviewer overrides the judge, no record of why. "
            "Calibration drift accumulates silently."
        ),
        "failure_mode": (
            "Five overrides on rubric R010 (Identity Disclosure) clustered "
            "on ER012-ER013 - all from the same reviewer, all with "
            "different stated reasons. Without an override audit, the "
            "pattern is invisible. With one, you see 'reviewer.trust-"
            "safety consistently downgrades R010 under the new vendor "
            "snapshot' and you investigate why."
        ),
    },
}


def main() -> None:
    eval_runs_path = DATA_DIR / "eval_runs.csv"
    overrides_path = DATA_DIR / "judge_overrides.csv"
    probes_path = DATA_DIR / "probes.csv"
    out_csv = OUT_DIR / "step_03_deficiencies.csv"

    print("\n" + "=" * 80)
    print("Step 3 - Where this still breaks: 6 named eval-system deficiencies")
    print("=" * 80 + "\n")
    print("Six named failure modes the basic eval (Step 2) leaves on the table.")
    print("Each is grounded in a real pattern in the historical eval-runs table.\n")

    with open(probes_path) as f:
        probes = list(csv.DictReader(f))
    with open(eval_runs_path) as f:
        runs = list(csv.DictReader(f))
    with open(overrides_path) as f:
        overrides = list(csv.DictReader(f))

    # Counts per deficiency class across probes
    probe_def_counts: Counter[str] = Counter()
    for p in probes:
        probe_def_counts[p["deficiency_class_tested"]] += 1

    # Counts of overrides per deficiency class
    override_def_counts: Counter[str] = Counter()
    for o in overrides:
        override_def_counts[o["deficiency_class_addressed"]] += 1

    # Print each deficiency with evidence
    rows_out = []
    for i, (def_key, info) in enumerate(DEFICIENCY_DEFS.items(), start=1):
        print(f"### {i}. {info['name'].upper()}  (key: {def_key})")
        print(f"    {info['summary']}")
        print()
        print(f"    Failure mode in this dataset:")
        # word-wrap for readability
        words = info["failure_mode"].split()
        line = "      "
        for w in words:
            if len(line) + len(w) > 78:
                print(line)
                line = "      "
            line += w + " "
        if line.strip():
            print(line)
        print()
        n_probes_for_def = probe_def_counts.get(def_key, 0)
        n_overrides_for_def = override_def_counts.get(def_key, 0)
        print(f"    Probes designed to surface this:   {n_probes_for_def}")
        print(f"    Override events attributed to it:  {n_overrides_for_def}")
        print()
        rows_out.append({
            "deficiency_id": i,
            "deficiency_class": def_key,
            "name": info["name"],
            "summary": info["summary"],
            "n_probes_targeting": n_probes_for_def,
            "n_overrides_attributed": n_overrides_for_def,
        })

    # Identify the silent-vendor-update regression in ER012
    er012 = next((r for r in runs if r["eval_run_id"] == "ER012"), None)
    er011 = next((r for r in runs if r["eval_run_id"] == "ER011"), None)
    if er011 and er012:
        delta_pass = float(er012["pass_rate"]) - float(er011["pass_rate"])
        delta_kappa = float(er012["inter_judge_kappa"]) - float(er011["inter_judge_kappa"])
        print("-" * 80)
        print("Headline regression in this dataset (which Step 2's basic eval missed):")
        print("-" * 80)
        print(f"  ER011 (pre-update):  pass_rate={er011['pass_rate']}  kappa={er011['inter_judge_kappa']}  verdict={er011['ci_gate_verdict']}")
        print(f"  ER012 (post-update): pass_rate={er012['pass_rate']}  kappa={er012['inter_judge_kappa']}  verdict={er012['ci_gate_verdict']}")
        print(f"  Delta pass_rate:     {delta_pass:+.2f}")
        print(f"  Delta kappa:         {delta_kappa:+.2f}")
        print(f"  Vendor snapshot change: claude-sonnet-4-20251101 -> claude-sonnet-4-20260214")
        print(f"  Step 2's basic eval would have shipped this update. EvalForge catches it.")
        print()

    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    print(f"Wrote: {out_csv}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
