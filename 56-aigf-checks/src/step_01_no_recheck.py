"""Step 1 - Status quo: a crosswalk sheet that nobody re-runs.

A contributor writes a row per risk: this check covers it, and this line of its output shows it.
The row is typed once. Nothing re-reads it when the check changes. This step counts what a reader
who trusts every row would believe, and what the planted truth says about the same rows. The data
is synthetic (data/_generate.py); the truth is the defect planted in each row, not a rule's verdict.

Run (from src/):  python3 step_01_no_recheck.py
"""
from __future__ import annotations

from collections import Counter

from common import KIND_ORDER, load_all, status_counts


def main() -> None:
    d = load_all()
    truth = d["row_truth"]
    kinds = Counter(t["kind"] for t in truth.values())
    defective = [r for r, t in truth.items() if t["defective"] == "yes"]
    believed = {r["risk_id"] for r in d["rows"] if r["covers"] == "full" and r["risk_id"] in d["risks"]}
    with_row = {r["risk_id"] for r in d["rows"] if r["risk_id"] in d["risks"]}
    print("STEP 1 - a crosswalk sheet nobody re-runs")
    print(f"  risks: {len(d['risks'])}   checks: {len(d['checks'])}   crosswalk rows: {len(d['rows'])}   captured outputs: {len(d['outputs'])}")
    print(f"  rows that hold up today: {len(truth) - len(defective)} of {len(truth)}")
    print(f"  rows with a planted defect: {len(defective)} of {len(truth)}")
    print("    " + ", ".join(f"{k} {kinds[k]}" for k in KIND_ORDER))
    print(f"  rows the sheet itself flags: 0 of {len(truth)}")
    print(f"  risks with at least one row: {len(with_row)} of {len(d['risks'])}")
    print(f"  risks a reader who trusts every full row would call covered: {len(believed)} of {len(d['risks'])}")
    print(f"  risks that are covered once the rows are checked (planted truth): {sum(1 for s in d['risk_truth'].values() if s == 'CHECKED')} of {len(d['risks'])}")
    print(f"  planted truth by status: {status_counts(d['risk_truth'])}")
    print("  The sheet looks the same whether a row holds or not. A reader finds out when someone runs the check.")


if __name__ == "__main__":
    main()
