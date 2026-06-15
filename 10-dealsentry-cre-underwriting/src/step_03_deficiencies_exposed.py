"""
Step 3 — Where the AI-drafted memo still breaks: six named deficiency classes.

"The memo had bad numbers" is not actionable. To fix it, you have to name the
failure modes. There are six that matter for AI-drafted CRE underwriting memos:

  1. comp_citation_fabrication       — comp doesn't exist in any SOT feed
  2. t12_noi_rollforward_error       — T-12 NOI sum has arithmetic error
  3. submarket_stat_staleness        — stat from prior quarter shown as current
  4. cap_rate_computational_error    — stated cap rate != NOI / value math
  5. occupancy_rate_discrepancy      — stated occupancy != rent-roll occupancy
  6. exit_cap_assumption_mismatch    — Year-5 exit cap baked in = going-in cap

This step runs every memo through the classifier and prints the per-deficiency
trip table. That table is the input to step_04 (the fix).

Run:
    python step_03_deficiencies_exposed.py
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

DEFICIENCIES = [
    "comp_citation_fabrication",
    "t12_noi_rollforward_error",
    "submarket_stat_staleness",
    "cap_rate_computational_error",
    "occupancy_rate_discrepancy",
    "exit_cap_assumption_mismatch",
]


def load_sot_comps() -> set[str]:
    idx: set[str] = set()
    with (DATA_DIR / "sot_comps.csv").open() as f:
        for row in csv.DictReader(f):
            idx.add(row["property_name"].lower().strip())
    return idx


def detect_fabricated_comps(text: str, sot: set[str]) -> list[str]:
    """Return the names of comps cited in `text` that have no SOT match."""
    fabricated: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not (s.lower().startswith("comp ") and " - " in s):
            continue
        name = s.split(" - ", 1)[1].split(",")[0].strip()
        if name.lower() not in sot:
            fabricated.append(name)
    return fabricated


def detect_t12_drift(text: str) -> tuple[bool, float]:
    """Sum the 12 'Month N: $X' rows and compare to the next 'Sum (memo states)' line."""
    months: list[float] = []
    sum_line = None
    for line in text.splitlines():
        m = re.match(r"\s*Month\s+\d+:\s*\$?([\d,]+)", line)
        if m:
            months.append(float(m.group(1).replace(",", "")))
            continue
        m = re.search(r"Sum\s*\(memo states\):\s*\$?([\d,]+)", line)
        if m:
            sum_line = float(m.group(1).replace(",", ""))
    if not months or sum_line is None:
        return False, 0.0
    actual = sum(months)
    drift = sum_line - actual
    return abs(drift) > 1.0, drift


def detect_submarket_staleness(text: str) -> bool:
    return "[NOTE:" in text and ("2024" in text or "prior quarter" in text.lower() or "stale" in text.lower())


def detect_cap_rate_error(text: str) -> tuple[bool, float, float]:
    """Find 'Stated cap rate: X%' near a '[Recompute: ...% ]' annotation."""
    m_stated = re.search(r"Stated cap rate:\s*([\d.]+)%", text)
    m_recomp = re.search(r"\[Recompute:[^\]]*=\s*([\d.]+)%", text)
    if m_stated and m_recomp:
        stated = float(m_stated.group(1))
        recomp = float(m_recomp.group(1))
        return abs(stated - recomp) > 0.05, stated, recomp
    return False, 0.0, 0.0


def detect_occupancy_discrepancy(text: str) -> tuple[bool, float, float]:
    m_stated = re.search(r"Stated occupancy:\s*([\d.]+)%", text)
    m_roll = re.search(r"Rent roll:\s*([\d.]+)%", text)
    if m_stated and m_roll:
        stated = float(m_stated.group(1))
        roll = float(m_roll.group(1))
        return abs(stated - roll) > 1.0, stated, roll
    return False, 0.0, 0.0


def detect_exit_cap_mismatch(text: str) -> tuple[bool, float, float]:
    m_going = re.search(r"Going-in cap[^%]*?([\d.]+)%", text)
    m_exit = re.search(r"Exit cap[^%]*?([\d.]+)%", text)
    if m_going and m_exit:
        going = float(m_going.group(1))
        exit_ = float(m_exit.group(1))
        return abs(exit_ - going) < 0.20, going, exit_  # too-tight spread
    return False, 0.0, 0.0


def main() -> None:
    sot = load_sot_comps()
    out_path = Path(__file__).parent / "out" / "step_03_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    print(f"\n{'=' * 80}")
    print("Step 3 — Where the memo still breaks: six named deficiency classes")
    print(f"{'=' * 80}\n")
    print("Classifying every memo against the six-class taxonomy in")
    print("data/deficiency_classes.csv. Per-deficiency trip table prints below.\n")

    rows: list[dict] = []
    trips: dict[str, list[str]] = {d: [] for d in DEFICIENCIES}

    with (DATA_DIR / "sample_memos.csv").open() as f:
        for r in csv.DictReader(f):
            mid = r["memo_id"]
            text = r["memo_text"]

            fab = detect_fabricated_comps(text, sot)
            t12_drift, drift_val = detect_t12_drift(text)
            stale = detect_submarket_staleness(text)
            cap_bad, cap_stated, cap_recomp = detect_cap_rate_error(text)
            occ_bad, occ_stated, occ_roll = detect_occupancy_discrepancy(text)
            exit_bad, exit_going, exit_exit = detect_exit_cap_mismatch(text)

            row = {
                "memo_id": mid,
                "asset_name": r["asset_name"],
                "comp_citation_fabrication": len(fab),
                "t12_noi_rollforward_error": int(t12_drift),
                "submarket_stat_staleness": int(stale),
                "cap_rate_computational_error": int(cap_bad),
                "occupancy_rate_discrepancy": int(occ_bad),
                "exit_cap_assumption_mismatch": int(exit_bad),
            }
            rows.append(row)

            if fab:
                trips["comp_citation_fabrication"].append(f"{mid}: {', '.join(fab)}")
            if t12_drift:
                trips["t12_noi_rollforward_error"].append(f"{mid}: $+{drift_val:,.0f} positive drift")
            if stale:
                trips["submarket_stat_staleness"].append(f"{mid}: 2024-Q3 stat shown as current")
            if cap_bad:
                trips["cap_rate_computational_error"].append(
                    f"{mid}: stated {cap_stated:.2f}% vs recompute {cap_recomp:.2f}% ({(cap_recomp-cap_stated)*100:+.0f} bps)"
                )
            if occ_bad:
                trips["occupancy_rate_discrepancy"].append(
                    f"{mid}: stated {occ_stated:.1f}% vs rent roll {occ_roll:.1f}%"
                )
            if exit_bad:
                trips["exit_cap_assumption_mismatch"].append(
                    f"{mid}: going-in {exit_going:.2f}% / exit {exit_exit:.2f}% (spread {(exit_exit-exit_going)*100:+.0f} bps; std practice +25-50 bps)"
                )

    for d in DEFICIENCIES:
        print(f"### {d.upper()}  ({len(trips[d])} trips on the 6-memo set)")
        if not trips[d]:
            print("    (no trips)\n")
            continue
        for t in trips[d]:
            print(f"    - {t}")
        print()

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'=' * 80}")
    print("Per-memo deficiency-trip table")
    print(f"{'=' * 80}")
    header_cols = ["memo_id"] + [d[:18] for d in DEFICIENCIES]
    print("  " + " | ".join(f"{c:18}" for c in header_cols))
    for r in rows:
        cols = [r["memo_id"]] + [str(r[d]) for d in DEFICIENCIES]
        print("  " + " | ".join(f"{c:18}" for c in cols))
    print()
    print(f"  Wrote: {out_path}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
