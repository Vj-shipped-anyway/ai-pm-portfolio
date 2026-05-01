"""
Step 1 — Before automated abstraction: a paralegal reads the lease.

This is what most CRE owner-operators were doing as recently as 2022, and what
many small-to-mid landlords are still doing today. A paralegal — typically
junior, sometimes a contracted vendor (Donnelley, Yardi Aspire, an offshore
abstraction shop) — reads each lease cover-to-cover, fills in a 12-field
template, and a senior asset manager spot-checks 5-10% of the abstracts.

It works. The fields are right. The bottleneck is time and cost.

Run:
    python step_01_manual_abstraction.py

Output: a per-lease summary + estimated time/cost roll-up.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# Calibrated from the BOMA Lease Abstracting Workshop materials and three
# US-based abstraction vendors I priced in 2024.
HOURS_PER_PAGE = 0.10              # 6 minutes per page reading
HOURS_PER_FIELD = 0.18             # ~11 minutes per field (read, locate, transcribe, double-check)
COMPLEXITY_MULTIPLIER = {
    "lease_01": 1.0,   # standard
    "lease_02": 1.0,   # standard
    "lease_03": 1.4,   # non-standard, embedded amendments
    "lease_04": 1.6,   # redlined; paralegal has to track every STRIKE/INSERT
    "lease_05": 1.3,   # main lease + side letter
    "lease_06": 1.5,   # complex anchor tenant
}
PARALEGAL_BLENDED_RATE = 65.00    # USD/hour, US-based contracted abstraction
QC_REVIEW_HOURS_PER_LEASE = 0.5    # senior asset-manager spot check
QC_REVIEW_RATE = 145.00            # USD/hour
ASSUMED_FIELD_ACCURACY = 0.96      # paralegals are good at this on a per-field basis


def page_count(lease_text: str) -> int:
    # Rough heuristic: 30 lines per page.
    return max(1, len(lease_text.splitlines()) // 30 + 1)


def main():
    leases_dir = DATA_DIR / "leases"
    out_path = Path(__file__).parent / "out" / "step_01_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    print(f"\n{'='*80}")
    print("Step 1 — Before automated abstraction: manual paralegal workflow")
    print(f"{'='*80}\n")

    rows = []
    total_hours = 0.0
    total_cost = 0.0

    for lease_path in sorted(leases_dir.glob("lease_*.txt")):
        lease_id = lease_path.stem.split("_")[0] + "_" + lease_path.stem.split("_")[1]
        text = lease_path.read_text()
        pages = page_count(text)
        complexity = COMPLEXITY_MULTIPLIER.get(lease_id, 1.0)

        read_hours = pages * HOURS_PER_PAGE * complexity
        field_hours = 12 * HOURS_PER_FIELD * complexity
        paralegal_hours = read_hours + field_hours
        paralegal_cost = paralegal_hours * PARALEGAL_BLENDED_RATE
        qc_cost = QC_REVIEW_HOURS_PER_LEASE * QC_REVIEW_RATE
        total_lease_cost = paralegal_cost + qc_cost
        total_lease_hours = paralegal_hours + QC_REVIEW_HOURS_PER_LEASE

        total_hours += total_lease_hours
        total_cost += total_lease_cost

        rows.append({
            "lease_id": lease_id,
            "pages": pages,
            "complexity_x": complexity,
            "paralegal_hours": round(paralegal_hours, 2),
            "qc_hours": QC_REVIEW_HOURS_PER_LEASE,
            "total_hours": round(total_lease_hours, 2),
            "cost_usd": round(total_lease_cost, 2),
            "assumed_accuracy": ASSUMED_FIELD_ACCURACY,
        })

        print(f"[{lease_id}]")
        print(f"    Pages:                   {pages}")
        print(f"    Complexity multiplier:   {complexity:.1f}x")
        print(f"    Paralegal time:          {paralegal_hours:.2f} hours")
        print(f"    QC review:               {QC_REVIEW_HOURS_PER_LEASE} hours @ ${QC_REVIEW_RATE}/hr")
        print(f"    Total time:              {total_lease_hours:.2f} hours")
        print(f"    Cost:                    ${total_lease_cost:,.2f}")
        print(f"    Assumed field accuracy:  {ASSUMED_FIELD_ACCURACY*100:.0f}%")
        print()

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'='*80}")
    print("Roll-up across the 6 sample leases")
    print(f"{'='*80}")
    print(f"  Total time:         {total_hours:.2f} hours")
    print(f"  Total cost:         ${total_cost:,.2f}")
    print(f"  Avg time / lease:   {total_hours/6:.2f} hours")
    print(f"  Avg cost / lease:   ${total_cost/6:,.2f}")
    print()
    print("  At 220-asset portfolio scale, abstracting once at lease signing")
    print(f"  and re-abstracting every ~3 years on amendments:")
    avg_cost = total_cost / 6
    print(f"     220 leases × ${avg_cost:,.0f}/lease = ${220*avg_cost:,.0f} per cycle")
    print(f"     ~$ {220*avg_cost/3:,.0f}/year amortized")
    print()
    print("  Bottleneck: scale. Paralegals are accurate, but you can't")
    print("  re-abstract a 5,000-lease portfolio every quarter at this cost.")
    print(f"\nWrote: {out_path}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
