"""
Step 2 - With basic evals: 30 probes run nightly via cron, results dumped to S3.

This is what most engineering-mature BFSI shops have today. A nightly cron
runs a 30-probe regression test against the deployed assistant. Output is a
binary pass/fail per probe, written to S3 as a JSON or CSV.

This catches the easy regressions (broken prompts, syntax errors, complete
breaks). It does NOT catch behavioral regression - the model still answers,
the answer is still plausible, but the answer is subtly worse than yesterday.
It also has no slice breakdown, no rubric scoring, no judge audit.

This script simulates that nightly cron over the 30-probe v0.7 probe set,
producing the artifact the cron job would have dumped to S3.

Run:
    python step_02_basic_eval_set.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from random import Random

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    today = date(2026, 1, 8)  # matches ER002 in eval_runs.csv

    probes_path = DATA_DIR / "probes.csv"
    out_csv = OUT_DIR / "step_02_basic_eval.csv"
    out_json = OUT_DIR / "step_02_nightly_dump.json"

    print("\n" + "=" * 80)
    print("Step 2 - With basic evals: 30 probes via cron, results dumped to S3")
    print("=" * 80 + "\n")
    print("A nightly cron runs the v0.7 probe set (30 probes). Output is binary")
    print("pass/fail. Dumped to S3. Reviewed when someone has time.\n")

    with open(probes_path) as f:
        all_probes = list(csv.DictReader(f))
    probes = all_probes[:30]  # probes-v0.7

    rng = Random(123)
    rows = []
    for p in probes:
        # The cron job calls the deployed assistant and a binary "matches expected behavior" check.
        # Pass rate roughly 0.93 on this run - matches ER002 baseline.
        passed = rng.random() < 0.93
        rows.append({
            "probe_id": p["probe_id"],
            "slice": p["slice"],
            "severity": p["severity"],
            "deficiency_class_tested": p["deficiency_class_tested"],
            "result": "PASS" if passed else "FAIL",
            "run_date": today.isoformat(),
            "probe_set_version": "probes-v0.7",
            "judge_used": "none - exact-match string compare",
            "rubric_scored": "no",
            "slice_breakdown": "not computed",
        })

    pass_count = sum(1 for r in rows if r["result"] == "PASS")
    fail_count = len(rows) - pass_count
    pass_rate = pass_count / len(rows)

    # Slice breakdown the cron does NOT produce, but we will print for contrast.
    slice_counts: Counter[str] = Counter()
    slice_passes: Counter[str] = Counter()
    for r in rows:
        slice_counts[r["slice"]] += 1
        if r["result"] == "PASS":
            slice_passes[r["slice"]] += 1

    print(f"  {'Probe':<6} {'Slice':<22} {'Severity':<8} Result")
    print(f"  {'-'*6} {'-'*22} {'-'*8} {'-'*6}")
    for r in rows[:15]:  # print first 15 to keep output tidy
        print(f"  {r['probe_id']:<6} {r['slice']:<22} {r['severity']:<8} {r['result']}")
    print(f"  ... ({len(rows) - 15} more rows, see step_02_basic_eval.csv)")
    print()

    with open(out_csv, "w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)

    with open(out_json, "w") as out:
        json.dump({
            "run_date": today.isoformat(),
            "probe_set_version": "probes-v0.7",
            "n_probes": len(rows),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": round(pass_rate, 3),
            "judge_used": "none - exact-match string compare",
            "rubric_scored": False,
            "slice_breakdown": "not_computed",
            "s3_path": "s3://eval-dumps-prod/assistant/2026-01-08.json",
        }, out, indent=2)

    print("=" * 80)
    print("Summary - what basic-evals gives you, and what it still misses")
    print("=" * 80)
    print(f"  Probes run:                 {len(rows)}")
    print(f"  PASS:                       {pass_count}")
    print(f"  FAIL:                       {fail_count}")
    print(f"  Aggregate pass rate:        {pass_rate*100:.1f}%")
    print(f"  Probe set version:          probes-v0.7 (locked - good!)")
    print(f"  Slice breakdown:            not computed (aggregate only - this is the gap)")
    print(f"  Rubric-scored:              no (binary pass/fail - no calibration)")
    print(f"  Judge audit trail:          none")
    print(f"  CI gate:                    none (cron only - results dumped, not blocking)")
    print(f"  Pre-deploy hook:            none - this is post-deploy reporting only")
    print()
    print("Reading: 93% pass rate on aggregate looks healthy. Behind it:")
    print("  - Slice level not computed - refusal-edge slice could be 60% and nobody")
    print("    would notice until customer complaints catch up.")
    print("  - Probe set v0.7 is 30 probes; 6 named behavioral classes need ~10 probes")
    print("    each minimum - this set is too small to be statistically reliable.")
    print("  - Judge is exact-match - any paraphrase variant fails. Paraphrase-blind")
    print("    in both directions: misses real regressions AND produces false alarms.")
    print()
    print("Step 3 enumerates the six named deficiencies this regime leaves on the table.")
    print()
    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_json}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
