"""
Step 1 — Before any verification: the AI-drafted memo is trusted at face value.

This models the most common operating mode at CRE acquisitions teams today
that have an AI underwriting copilot in place: the copilot drafts the memo,
the analyst skims it, the memo goes into the IC packet.

The numbers in the memo are not verified. The comps are not dereferenced.
The T-12 is not recomputed. The submarket stat is read as current.

Run:
    python step_01_face_value_trust.py

Output: a per-memo "what the memo claims" summary + the headline number that
goes into the IC packet.
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def parse_memo_text(memo_text: str) -> dict:
    """Best-effort regex-style claim extraction. No verification."""
    claims = {
        "comps_cited": 0,
        "stated_cap_rate": None,
        "stated_noi": None,
        "stated_occupancy": None,
        "asking_price": None,
    }
    for line in memo_text.splitlines():
        low = line.lower().strip()
        if low.startswith("comp ") or low.startswith("  comp "):
            claims["comps_cited"] += 1
        if "stabilized noi" in low or "t-12 noi" in low:
            tokens = [t for t in line.replace(",", "").replace("$", "").split() if t.replace(".", "").isdigit()]
            if tokens:
                try:
                    claims["stated_noi"] = float(tokens[-1])
                except ValueError:
                    pass
        if "asking price" in low and "$" in line:
            tokens = [t for t in line.replace(",", "").replace("$", "").split() if t.replace(".", "").isdigit()]
            if tokens:
                try:
                    claims["asking_price"] = float(tokens[0])
                except ValueError:
                    pass
        if "cap rate" in low and "%" in line:
            for tok in line.split():
                if tok.endswith("%"):
                    try:
                        claims["stated_cap_rate"] = float(tok.rstrip("%."))
                        break
                    except ValueError:
                        continue
        if "stated occupancy" in low and "%" in line:
            for tok in line.split():
                if tok.endswith("%"):
                    try:
                        claims["stated_occupancy"] = float(tok.rstrip("%."))
                        break
                    except ValueError:
                        continue
    return claims


def main() -> None:
    memo_path = DATA_DIR / "sample_memos.csv"
    out_path = Path(__file__).parent / "out" / "step_01_results.csv"
    out_path.parent.mkdir(exist_ok=True)

    print(f"\n{'=' * 80}")
    print("Step 1 — Before verification: AI memo trusted at face value")
    print(f"{'=' * 80}\n")
    print("Operating mode: the AI copilot drafts the memo, the analyst skims it,")
    print("the memo lands in IC. No SOT dereference. No symbolic re-run.")
    print("This is the baseline. It's what is shipping today at most CRE shops.\n")

    rows = []
    with memo_path.open() as f:
        reader = csv.DictReader(f)
        for r in reader:
            claims = parse_memo_text(r["memo_text"])
            print(f"[{r['memo_id']}] {r['asset_name']} ({r['asset_class']}, {r['market']})")
            print(f"    Comps cited:      {claims['comps_cited']}")
            if claims['stated_cap_rate'] is not None:
                print(f"    Stated cap rate:  {claims['stated_cap_rate']:.2f}%")
            if claims['stated_noi'] is not None:
                print(f"    Stated NOI:       ${claims['stated_noi']:,.0f}")
            if claims['asking_price'] is not None:
                print(f"    Asking price:     ${claims['asking_price']:,.0f}")
            if claims['stated_occupancy'] is not None:
                print(f"    Stated occupancy: {claims['stated_occupancy']:.1f}%")
            print(f"    Verification:     NONE (trusted at face value)")
            print(f"    Action:           memo goes to IC packet as-is.\n")
            rows.append({
                "memo_id": r["memo_id"],
                "asset_name": r["asset_name"],
                "comps_cited": claims["comps_cited"],
                "stated_cap_rate_pct": claims["stated_cap_rate"],
                "stated_noi": claims["stated_noi"],
                "stated_occupancy_pct": claims["stated_occupancy"],
                "asking_price": claims["asking_price"],
                "verified": False,
            })

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{'=' * 80}")
    print("Result of Step 1 on the 6-memo eval set")
    print(f"{'=' * 80}")
    print(f"  Memos read: {len(rows)}")
    print(f"  Comps cited (total): {sum(r['comps_cited'] for r in rows)}")
    print(f"  Comps verified:      0")
    print(f"  T-12 sums recomputed: 0")
    print(f"  Submarket stats cross-checked: 0")
    print()
    print("  Every memo will land in the IC packet. The deficiencies designed")
    print("  into MEMO_03 / MEMO_04 / MEMO_05 / MEMO_06 are present and uncaught.")
    print(f"\nWrote: {out_path}")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
