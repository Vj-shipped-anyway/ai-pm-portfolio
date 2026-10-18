"""
Step 2 - The basic approach: trust the tier the sponsor declares.

The sponsor fills in the intake form and writes down a tier. The reviewer takes
that tier as given, applies the checklist for the declared tier, and approves
when that checklist is covered. Review depth follows the declared tier.

What this script measures against the committed reference tier (true by
construction: the written rubric applied to the true attributes):
  - mis-tier rate of the self-declared tier
  - under-tiering of the cases that are truly tier 3-4
  - approvals granted while evidence required by the reference tier is missing
  - evidence-gap detection rate of this approach
  - reviewer hours and tier 3-4 wait when review depth follows the declared tier

Run from this folder:  python3 step_02_self_declared_tier.py

Output:
  - prints the result
  - writes src/out/step_02_results.json and src/out/step_02_cases.csv
"""

from __future__ import annotations

import csv
import json

from step_01_spreadsheet_fifo import (
    HI_TIERS, OUT_DIR, REPLICATIONS, TIER_REVIEW_H,
    assumptions_text, load_cases, load_checklist, load_evidence_on_file, run_queue,
)


def evaluate_basic(cases: list[dict], checklist: dict, on_file: dict) -> list[dict]:
    """Per-case view of the basic approach."""
    rows = []
    for c in cases:
        have = on_file.get(c["use_case_id"], set())
        declared, ref = c["self_declared_tier"], c["reference_tier"]
        missing_declared = [e for e in checklist[declared] if e not in have]
        missing_ref = [e for e in checklist[ref] if e not in have]
        rows.append({
            "use_case_id": c["use_case_id"],
            "declared": declared,
            "reference": ref,
            "mis_tier": declared != ref,
            "under": declared < ref,
            "over": declared > ref,
            "approved": not missing_declared,
            "missing_declared": missing_declared,
            "missing_reference": missing_ref,
        })
    return rows


def run() -> dict:
    cases = load_cases()
    checklist = load_checklist()
    on_file = load_evidence_on_file()
    rows = evaluate_basic(cases, checklist, on_file)
    n = len(rows)

    mis = [r for r in rows if r["mis_tier"]]
    hi = [r for r in rows if r["reference"] in HI_TIERS]
    hi_under = [r for r in hi if r["under"]]
    hi_out_of_band = [r for r in hi if r["declared"] not in HI_TIERS]
    approved = [r for r in rows if r["approved"]]
    approved_gap = [r for r in approved if r["missing_reference"]]
    gap_cases = [r for r in rows if r["missing_reference"]]
    gap_held = [r for r in gap_cases if not r["approved"]]

    confusion = [[0] * 4 for _ in range(4)]   # rows: reference tier, cols: declared tier
    for r in rows:
        confusion[r["reference"] - 1][r["declared"] - 1] += 1

    # Review depth follows the declared tier; same FIFO queue as step 1.
    hours = [TIER_REVIEW_H[c["self_declared_tier"]] for c in cases]
    q = run_queue(cases, hours, priority=None)

    return {
        "n_cases": n,
        "mis_tier_n": len(mis),
        "mis_tier_rate": len(mis) / n,
        "under_n": sum(1 for r in rows if r["under"]),
        "over_n": sum(1 for r in rows if r["over"]),
        "hi_n": len(hi),
        "hi_under_n": len(hi_under),
        "hi_under_rate": len(hi_under) / len(hi),
        "hi_out_of_band_n": len(hi_out_of_band),
        "hi_recall": 1 - len(hi_out_of_band) / len(hi),
        "approved_n": len(approved),
        "approved_missing_ref_n": len(approved_gap),
        "approved_missing_ref_rate": len(approved_gap) / len(approved),
        "approved_missing_items": sum(len(r["missing_reference"]) for r in approved_gap),
        "gap_cases_n": len(gap_cases),
        "gap_held_n": len(gap_held),
        "gap_detection_rate": len(gap_held) / len(gap_cases),
        "confusion": confusion,
        "total_hours": q["total_hours"],
        "offered_load": q["offered_load"],
        "wait_hi_mean": q["wait_hi_mean"],
        "wait_lo_mean": q["wait_lo_mean"],
        "rows": rows,
        "per_case_mean_wait": q["per_case_mean_wait"],
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    res = run()
    n = res["n_cases"]
    print("\n" + "=" * 80)
    print("Step 2 - Basic approach: trust the self-declared tier")
    print("=" * 80)
    print("\nREFERENCE TIER: the written rubric applied to the TRUE attributes (true by construction).")
    print("Accuracy below measures agreement with that reference, not how real banks behave.")

    print("\nTIER ACCURACY (green, measured on the %d synthetic submissions)" % n)
    print("  Self-declared tier equals reference tier:     %d of %d  (%.1f%%)"
          % (n - res["mis_tier_n"], n, 100 * (1 - res["mis_tier_rate"])))
    print("  Mis-tier rate:                                %d of %d  (%.1f%%)"
          % (res["mis_tier_n"], n, 100 * res["mis_tier_rate"]))
    print("    declared too low: %d    declared too high: %d" % (res["under_n"], res["over_n"]))
    print("  True tier 3-4 cases:                          %d" % res["hi_n"])
    print("    declared below their reference tier:        %d of %d  (%.1f%%)"
          % (res["hi_under_n"], res["hi_n"], 100 * res["hi_under_rate"]))
    print("    declared outside the 3-4 band entirely:     %d of %d  (tier 3-4 recall %.1f%%)"
          % (res["hi_out_of_band_n"], res["hi_n"], 100 * res["hi_recall"]))

    print("\n  Confusion (rows = reference tier, columns = declared tier):")
    print("            declared 1  declared 2  declared 3  declared 4")
    for i, r in enumerate(res["confusion"], 1):
        print("  ref %d      %8d    %8d    %8d    %8d" % (i, r[0], r[1], r[2], r[3]))

    print("\nAPPROVALS (green, measured). The reviewer approves when the declared tier's checklist is covered.")
    print("  Approvals granted:                            %d of %d" % (res["approved_n"], n))
    print("  Approvals with evidence missing that the reference tier requires:  %d of %d  (%.1f%% of approvals)"
          % (res["approved_missing_ref_n"], res["approved_n"], 100 * res["approved_missing_ref_rate"]))
    print("    required items absent across those approvals: %d" % res["approved_missing_items"])
    print("  Evidence-gap detection rate of this approach: %d of %d cases with a real gap were held  (%.1f%%)"
          % (res["gap_held_n"], res["gap_cases_n"], 100 * res["gap_detection_rate"]))

    print("\nQUEUE AND HOURS (yellow, modeled; review depth follows the DECLARED tier, FIFO)")
    for line in assumptions_text(uniform=False):
        print("  - " + line)
    print("  Total reviewer hours:                         %.1f" % res["total_hours"])
    print("  Offered load on the reviewers:                %.0f%%" % (100 * res["offered_load"]))
    print("  Tier 3-4 mean queue wait (FIFO):              %.1f business days" % res["wait_hi_mean"])
    print("  Tier 1-2 mean queue wait (FIFO):              %.1f business days" % res["wait_lo_mean"])
    print("  Because under-declared cases get shallow reviews, hours look lower than the reference tiers need.")

    with open(OUT_DIR / "step_02_cases.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["use_case_id", "declared", "reference", "approved", "missing_declared", "missing_reference"])
        for r in res["rows"]:
            w.writerow([r["use_case_id"], r["declared"], r["reference"], r["approved"],
                        " ".join(r["missing_declared"]), " ".join(r["missing_reference"])])
    summary = {k: v for k, v in res.items() if k not in ("rows", "per_case_mean_wait")}
    summary["rows"] = res["rows"]
    summary["per_case_mean_wait"] = {r["use_case_id"]: round(w, 3)
                                     for r, w in zip(res["rows"], res["per_case_mean_wait"])}
    with open(OUT_DIR / "step_02_results.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print("\nWrote src/out/step_02_results.json and src/out/step_02_cases.csv")


if __name__ == "__main__":
    main()
