"""
Step 2 — With basic analyst spot-checking.

This is the operating mode at most analyst-staffed CRE teams: the senior analyst
manually verifies 10% of the comp citations against CoStar. T-12 line items are
spot-checked on the largest deals. Submarket stats are checked when "something
feels off."

In a 6-memo set with 31 cited comps across all memos, a 10% spot-check rate
verifies roughly 3 comps. With the fabricated comps spread across MEMO_04 and
MEMO_06, the probability that the spot-check actually hits a fabricated one
is on the order of 25-35%.

This step models that. Some memos catch fabrications, most don't. T-12 math
drift is not spotted because the analyst is not re-running 12 monthly rows.
Stale submarket stats are not spotted because the analyst doesn't have time
to load CoStar twice.

Run:
    python step_02_analyst_spotcheck.py

Output: a per-memo "spot-check result" + the deficiencies that slip through.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

SPOT_CHECK_RATE = 0.10  # 10% of comps verified manually


def load_sot_comp_index() -> set[str]:
    """Index SOT comps by lowercased property name for a coarse existence check."""
    idx: set[str] = set()
    with (DATA_DIR / "sot_comps.csv").open() as f:
        for row in csv.DictReader(f):
            idx.add(row["property_name"].lower().strip())
    return idx


def extract_comp_names(memo_text: str) -> list[str]:
    names: list[str] = []
    for line in memo_text.splitlines():
        s = line.strip()
        if not (s.lower().startswith("comp ") and " - " in s):
            continue
        try:
            after_dash = s.split(" - ", 1)[1]
            name = after_dash.split(",")[0].strip()
            names.append(name)
        except IndexError:
            continue
    return names


def main() -> None:
    sot_index = load_sot_comp_index()
    out_path = Path(__file__).parent / "out" / "step_02_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    rng = random.Random(2026)  # deterministic for the walkthrough

    print(f"\n{'=' * 80}")
    print("Step 2 — With basic analyst spot-checking (10% of comps verified)")
    print(f"{'=' * 80}\n")
    print("Operating mode: senior analyst spot-checks roughly 10% of cited comps")
    print("against CoStar. T-12 math is trusted. Submarket stats are trusted.")
    print("This is the analyst-staffed baseline.\n")

    rows = []
    total_comps_cited = 0
    total_spot_checked = 0
    total_fabricated_caught = 0
    total_fabricated_present = 0

    with (DATA_DIR / "sample_memos.csv").open() as f:
        for r in csv.DictReader(f):
            names = extract_comp_names(r["memo_text"])
            comps_cited = len(names)
            total_comps_cited += comps_cited

            # Identify the truly fabricated comps for accounting
            fabricated_names = [n for n in names if n.lower() not in sot_index]
            total_fabricated_present += len(fabricated_names)

            n_to_check = max(1, int(round(comps_cited * SPOT_CHECK_RATE)))
            n_to_check = min(n_to_check, comps_cited)
            checked = rng.sample(names, k=n_to_check)
            caught = [n for n in checked if n.lower() not in sot_index]
            total_spot_checked += n_to_check
            total_fabricated_caught += len(caught)

            slipped = max(0, len(fabricated_names) - len(caught))

            print(f"[{r['memo_id']}] {r['asset_name']}")
            print(f"    Comps cited:        {comps_cited}")
            print(f"    Comps spot-checked: {n_to_check}")
            print(f"    Fabrications caught by spot-check: {len(caught)}")
            print(f"    Fabrications that slipped through: {slipped}")
            print(f"    T-12 math:          NOT recomputed")
            print(f"    Submarket stats:    NOT cross-checked")
            print()

            rows.append({
                "memo_id": r["memo_id"],
                "asset_name": r["asset_name"],
                "comps_cited": comps_cited,
                "comps_spot_checked": n_to_check,
                "fabrications_caught": len(caught),
                "fabrications_slipped": slipped,
            })

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'=' * 80}")
    print("Aggregate result of Step 2 on the 6-memo eval set")
    print(f"{'=' * 80}")
    print(f"  Comps cited (total):                {total_comps_cited}")
    print(f"  Comps spot-checked (10%):           {total_spot_checked}")
    print(f"  Fabricated comps present:           {total_fabricated_present}")
    print(f"  Fabricated comps caught (modeled):  {total_fabricated_caught}")
    print(f"  Fabricated comps slipped through:   {total_fabricated_present - total_fabricated_caught}")
    print()
    print("  T-12 arithmetic drift:    UNDETECTED (analyst didn't recompute)")
    print("  Submarket stat staleness: UNDETECTED (analyst trusted memo)")
    print("  Cap-rate computational:   UNDETECTED")
    print("  Exit-cap mismatch:        UNDETECTED")
    print("  Occupancy discrepancy:    UNDETECTED")
    print()
    print("  This is the analyst-staffed baseline that DealSentry replaces.")
    print(f"\nWrote: {out_path}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
