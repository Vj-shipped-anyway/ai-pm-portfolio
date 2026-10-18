"""Step 2 - The basic approach: a questionnaire checklist.

Each vendor fills in 20 yes / partial / no answers about its own controls. The basic rule: a
vendor passes when at least 85 percent of its answers are yes (17 of 20). Partial counts as
not yes. This is how many questionnaire programs run, and it is reasonable as a first filter.

This script applies that rule to the 40 synthetic vendors and then compares the verdict with
data/truth.csv, where the generator wrote the true risk class of every vendor. The truth is
known because the data is synthetic. Nothing here is a real vendor, and no model is used.

Run (from src/):
    python3 step_02_questionnaire_checklist.py

Output: a readable summary, plus out/step_02_verdicts.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter

from step_01_status_quo import OUT_DIR, load_all

PASS_YES_PCT = 85           # the basic rule: at least this percent of answers must be yes


def yes_count(row: dict) -> int:
    return sum(1 for a in row.values() if a == "yes")


def passes(row: dict) -> bool:
    """Integer arithmetic on purpose: 17 of 20 is exactly 85 percent."""
    return yes_count(row) * 100 >= PASS_YES_PCT * len(row)


def pct(a: int, b: int) -> float:
    return round(100.0 * a / b, 1) if b else 0.0


def verdicts(data: dict) -> list:
    rows = []
    for v in data["vendors"]:
        a = data["answers"][v["vendor_id"]]
        t = data["truth"][v["vendor_id"]]
        rows.append({
            "vendor_id": v["vendor_id"], "criticality": v["criticality"], "data_access": v["data_access"],
            "yes": yes_count(a), "answers": len(a), "yes_pct": pct(yes_count(a), len(a)),
            "pass": passes(a), "true_risk": t["true_risk"], "overclaimed": t["overclaimed"],
        })
    return rows


def summarize(data: dict) -> dict:
    rows = verdicts(data)
    n = len(rows)
    p = [r for r in rows if r["pass"]]
    f = [r for r in rows if not r["pass"]]
    by_truth_pass = Counter(r["true_risk"] for r in p)
    by_truth_fail = Counter(r["true_risk"] for r in f)
    high = [r for r in rows if r["true_risk"] == "high"]
    high_found = [r for r in high if not r["pass"]]
    return {
        "vendors": n, "pass_rule_pct": PASS_YES_PCT,
        "passes": len(p), "fails": len(f), "pass_pct": pct(len(p), n),
        "pass_high": by_truth_pass["high"], "pass_medium": by_truth_pass["medium"], "pass_low": by_truth_pass["low"],
        "fail_high": by_truth_fail["high"], "fail_medium": by_truth_fail["medium"], "fail_low": by_truth_fail["low"],
        "true_high": len(high), "true_medium": sum(1 for r in rows if r["true_risk"] == "medium"),
        "true_low": sum(1 for r in rows if r["true_risk"] == "low"),
        "high_found": len(high_found),
        "high_missed": len(high) - len(high_found),
        "fail_precision_pct": pct(len(high_found), len(f)),
        "fail_recall_pct": pct(len(high_found), len(high)),
        "critical_pass": sum(1 for r in p if r["criticality"] == "critical"),
        "critical": sum(1 for r in rows if r["criticality"] == "critical"),
        "pii_pass": sum(1 for r in p if r["data_access"] == "customer_pii"),
        "overclaimed_total": sum(r["overclaimed"] for r in rows),
        "overclaimed_on_passes": sum(r["overclaimed"] for r in p),
        "passes_with_overclaim": sum(1 for r in p if r["overclaimed"] > 0),
        "answers_total": sum(r["answers"] for r in rows),
        "yes_total": sum(r["yes"] for r in rows),
        "missed_ids": [r["vendor_id"] for r in high if r["pass"]],
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    rows = verdicts(data)
    s = summarize(data)
    need = -(-PASS_YES_PCT * rows[0]["answers"] // 100)      # yes answers needed per vendor

    print("\n" + "=" * 78)
    print("Step 2 - The basic approach: a questionnaire checklist")
    print("=" * 78)
    print(f"\nRule: a vendor passes when at least {PASS_YES_PCT}% of its answers are yes "
          f"({need} of {rows[0]['answers']}). Partial counts as not yes.")
    print("The truth column comes from data/truth.csv (the generator's decision). It is used to score, never to decide.\n")

    print(f"{'vendor':<7} {'tier':<10} {'data':<13} {'yes':>3} {'pct':>6} {'verdict':>7} {'truth':>7} {'overclaimed':>11}")
    print(f"{'-' * 7} {'-' * 10} {'-' * 13} {'-' * 3} {'-' * 6} {'-' * 7} {'-' * 7} {'-' * 11}")
    for r in rows:
        mark = "  <-- passed, truly high" if r["pass"] and r["true_risk"] == "high" else ""
        print(f"{r['vendor_id']:<7} {r['criticality']:<10} {r['data_access']:<13} {r['yes']:>3} {r['yes_pct']:>5.1f}% "
              f"{'PASS' if r['pass'] else 'FAIL':>7} {r['true_risk']:>7} {r['overclaimed']:>11}{mark}")

    print("\nVERDICT BY TRUE RISK (rows: what the vendor really is; columns: what the checklist said)")
    print(f"  {'truth':<8} {'pass':>5} {'fail':>5}")
    for k in ("high", "medium", "low"):
        print(f"  {k:<8} {s['pass_' + k]:>5} {s['fail_' + k]:>5}")

    print("\nRESULT")
    print(f"  Passes: {s['passes']} of {s['vendors']} ({s['pass_pct']}%); fails: {s['fails']}.")
    print(f"  Truly high-risk vendors: {s['true_high']}. Found by the checklist (they fail): {s['high_found']}. "
          f"Passed: {s['high_missed']} of {s['true_high']}.")
    print(f"  Used as a high-risk detector, a fail has precision {s['fail_precision_pct']}% "
          f"({s['high_found']} of {s['fails']}) and recall {s['fail_recall_pct']}% ({s['high_found']} of {s['true_high']}).")
    print(f"  Critical vendors that pass: {s['critical_pass']} of {s['critical']}. "
          f"Passing vendors with customer PII access: {s['pii_pass']}.")
    print(f"  Answers over-claimed (said better than the truth): {s['overclaimed_total']} of "
          f"{s['answers_total']} answers; {s['overclaimed_on_passes']} of them sit on vendors that pass.")
    print("  The checklist cannot see an over-claim: it counts the word yes.")

    with open(OUT_DIR / "step_02_verdicts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["vendor_id", "yes", "answers", "yes_pct", "verdict", "true_risk", "overclaimed"])
        for r in rows:
            w.writerow([r["vendor_id"], r["yes"], r["answers"], r["yes_pct"], "pass" if r["pass"] else "fail",
                        r["true_risk"], r["overclaimed"]])
    with open(OUT_DIR / "step_02_summary.json", "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_02_verdicts.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
