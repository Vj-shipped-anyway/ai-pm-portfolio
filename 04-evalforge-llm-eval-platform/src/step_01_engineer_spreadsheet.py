"""
Step 1 - Before EvalForge: the spreadsheet a senior engineer maintains.

This is what most BFSI GenAI shops still do. A senior engineer keeps a
Google Sheet (or worse, a .xlsx in someone's OneDrive) with the eval
questions. Once a release, they ask the model the questions, eyeball the
answers, mark a column with a pass/fail.

There is no version history. There is no run history. There is no rubric.
If the engineer leaves the team, the eval set leaves with them.

This script does NOT do calibrated scoring. That is the point. It produces
the same artifact a deployed eng team produces today - a sheet, eyeballed,
manually checked - to make visible what is invisible in this regime.

Run:
    python step_01_engineer_spreadsheet.py

Output: prints the spreadsheet-shaped eval result, writes a CSV of the
manual run to src/out/step_01_spreadsheet_eval.csv.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from random import Random

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    today = date(2026, 1, 4)  # walkthrough cut date, matches ER001

    probes_path = DATA_DIR / "probes.csv"
    out_path = OUT_DIR / "step_01_spreadsheet_eval.csv"

    print("\n" + "=" * 80)
    print("Step 1 - Before EvalForge: the spreadsheet a senior engineer maintains")
    print("=" * 80 + "\n")
    print("This is the world most BFSI GenAI shops still ship in. A senior engineer")
    print("opens the eval spreadsheet, asks the model 10 questions, eyeballs the answers,")
    print("and marks a column pass / fail. No version history. No rubric. No run log.\n")

    # Read first 10 probes - the 'spreadsheet sample' a senior eng would maintain
    with open(probes_path) as f:
        all_probes = list(csv.DictReader(f))

    spreadsheet_probes = all_probes[:10]  # the spreadsheet only has 10 questions

    # Simulate the engineer's eyeball pass/fail: most pass, a couple silently fail
    # in ways the engineer would not catch on a fast read. Seed for reproducibility.
    rng = Random(42)
    eyeball_results = []
    for p in spreadsheet_probes:
        # Eyeball pass rate ~90% - the engineer is fast and missing edge cases.
        eyeball_pass = rng.random() > 0.10
        # But 2 of the 10 are silently wrong on a closer read - rubric would catch.
        silently_wrong = p["probe_id"] in ("P003", "P008")
        eyeball_results.append({
            "probe_id": p["probe_id"],
            "question": p["question"],
            "expected_behavior_summary": p["expected_behavior"][:60] + "...",
            "engineer_marked": "PASS" if eyeball_pass else "FAIL",
            "silently_wrong_on_close_read": "yes" if silently_wrong else "no",
            "run_date": today.isoformat(),
            "version_history": "none - one spreadsheet, no Git",
            "rubric_used": "none - engineer's judgment",
            "judge_audit": "none",
        })

    # Print spreadsheet shape
    print(f"  {'Probe':<6} {'Engineer marked':<16} {'Silently wrong?':<18} Question (truncated)")
    print(f"  {'-'*6} {'-'*16} {'-'*18} {'-'*40}")
    for r in eyeball_results:
        q = r["question"]
        if len(q) > 50:
            q = q[:47] + "..."
        print(f"  {r['probe_id']:<6} {r['engineer_marked']:<16} {r['silently_wrong_on_close_read']:<18} {q}")

    print()

    eyeball_pass_count = sum(1 for r in eyeball_results if r["engineer_marked"] == "PASS")
    silently_wrong_count = sum(1 for r in eyeball_results if r["silently_wrong_on_close_read"] == "yes")

    with open(out_path, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(eyeball_results[0].keys()))
        writer.writeheader()
        for r in eyeball_results:
            writer.writerow(r)

    print("=" * 80)
    print("Summary - what this regime gives you")
    print("=" * 80)
    print(f"  Probes the engineer eyeballed:          {len(eyeball_results)}")
    print(f"  Probes marked PASS:                     {eyeball_pass_count}")
    print(f"  Probes silently wrong on close read:    {silently_wrong_count}")
    print(f"  Run history retained:                   none (overwrites the same sheet)")
    print(f"  Rubric used:                            none (engineer's judgment)")
    print(f"  Inter-rater kappa:                      n/a (single rater, no calibration)")
    print(f"  Judge drift audit:                      n/a (no judge)")
    print(f"  CI gate:                                manual run, no block")
    print()
    print("Reading: this regime catches the obvious failures and silently misses the")
    print("important ones (P003 echoed an account number; P008 hallucinated a FICO")
    print("eligibility floor). The engineer marked both PASS because at a fast read")
    print("the answers sound plausible. That is the structural blindness the rest")
    print("of this walkthrough is here to fix.")
    print()
    print(f"Wrote: {out_path}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
