"""Step 2 - With the basic approach: one adoption percentage from licenses and logins.

The baseline turns the license portal and the sign-in log into one number: the share of
licensed users who have logged in. It reports that number week by week and by org unit. It is
cheap, it is easy to explain, and it is what a login count gives you. This step computes it
exactly as a dashboard would, and shows what it tells the program lead (a high number, rising,
with nothing to act on).

ASSUMPTIONS (modeled):
  B1. Adoption in week W = licensed users who have logged in at least once by the end of week W,
      divided by users licensed by the end of week W. It is cumulative: a person who logged
      in once stays counted, so the number does not fall when usage does.
  B2. The unit view is the same ratio at the end of week 12, for each org unit.
  B3. A unit is read as healthy at or above ADOPTION_OK_PCT. The cut is an assumption.

Run (from src/):
    python3 step_02_login_adoption_baseline.py

Output: a readable summary, plus out/step_02_weekly.csv, out/step_02_by_unit.csv and
out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_license_counts_status_quo import OUT_DIR, WEEKS, ever_logged_in, load_all

ADOPTION_OK_PCT = 80.0       # assumption B3


def logged_in_by_week(use_u: dict) -> int:
    """First week (1-based) in which the user logged in, or 0 when never."""
    for w in range(1, WEEKS + 1):
        if use_u["logins"][w - 1] > 0:
            return w
    return 0


def weekly_adoption(data: dict) -> list:
    rows = []
    first = {u["user_id"]: logged_in_by_week(data["use"][u["user_id"]]) for u in data["users"]}
    for w in range(1, WEEKS + 1):
        lic = [u for u in data["users"] if u["licensed_week"] <= w]
        logged = [u for u in lic if 0 < first[u["user_id"]] <= w]
        rows.append({"week": w, "licensed": len(lic), "logged_in": len(logged),
                     "adoption_pct": round(100 * len(logged) / len(lic), 1)})
    return rows


def unit_adoption(data: dict) -> list:
    rows = []
    for unit in data["units"]:
        us = data["by_unit"][unit]
        logged = sum(1 for u in us if ever_logged_in(data["use"][u["user_id"]]))
        rows.append({"unit": unit, "licensed": len(us), "logged_in": logged,
                     "adoption_pct": round(100 * logged / len(us), 1)})
    return rows


def summarize(data: dict) -> dict:
    weekly, units = weekly_adoption(data), unit_adoption(data)
    by_pct = sorted(units, key=lambda r: (-r["adoption_pct"], r["unit"]))
    falls = sum(1 for a, b in zip(weekly, weekly[1:]) if b["adoption_pct"] < a["adoption_pct"])
    return {
        "weekly": weekly, "units": units,
        "overall_pct": weekly[-1]["adoption_pct"], "overall_logged": weekly[-1]["logged_in"],
        "overall_licensed": weekly[-1]["licensed"],
        "best_unit": by_pct[0], "worst_unit": by_pct[-1],
        "spread_points": round(by_pct[0]["adoption_pct"] - by_pct[-1]["adoption_pct"], 1),
        "units_ok": sum(1 for r in units if r["adoption_pct"] >= ADOPTION_OK_PCT),
        "units_total": len(units), "weeks_fell": falls, "week_pairs": len(weekly) - 1,
        "adoption_ok_pct": ADOPTION_OK_PCT,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 2 - Basic approach: one adoption percentage from licenses and logins")
    print("=" * 78)
    print("\nASSUMPTIONS (modeled):")
    print("  B1  adoption in a week = users who have logged in by then / users licensed by then (cumulative: a login stays counted)")
    print("  B2  the unit view is the same ratio at the end of week 12")
    print(f"  B3  a unit reads as healthy at {ADOPTION_OK_PCT:.0f}% or above (an assumed cut)\n")

    print("WEEK BY WEEK")
    print(f"  {'week':>4} {'licensed':>9} {'logged in':>10} {'adoption':>9}")
    for r in s["weekly"]:
        print(f"  {r['week']:>4} {r['licensed']:>9} {r['logged_in']:>10} {r['adoption_pct']:>8.1f}%")

    print("\nBY ORG UNIT (end of week 12, highest first)")
    print(f"  {'unit':<22} {'licensed':>8} {'logged in':>9} {'adoption':>9}")
    for r in sorted(s["units"], key=lambda x: (-x["adoption_pct"], x["unit"])):
        print(f"  {r['unit']:<22} {r['licensed']:>8} {r['logged_in']:>9} {r['adoption_pct']:>8.1f}%")

    b, w = s["best_unit"], s["worst_unit"]
    print("\nRESULT")
    print(f"  Reported adoption: {s['overall_logged']} of {s['overall_licensed']} ({s['overall_pct']}%)")
    print(f"  Across units: {w['adoption_pct']}% ({w['unit']}) to {b['adoption_pct']}% ({b['unit']}), "
          f"a spread of {s['spread_points']} points")
    print(f"  Units reading as healthy (at or above {ADOPTION_OK_PCT:.0f}%): {s['units_ok']} of {s['units_total']}")
    print(f"  Weeks in which the percentage fell: {s['weeks_fell']} of {s['week_pairs']}")
    print("  What it tells the program lead: adoption is high and rising. It names no team to help.")

    with open(OUT_DIR / "step_02_weekly.csv", "w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["week", "licensed", "logged_in", "adoption_pct"])
        for r in s["weekly"]:
            wr.writerow([r["week"], r["licensed"], r["logged_in"], r["adoption_pct"]])
    with open(OUT_DIR / "step_02_by_unit.csv", "w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["unit", "licensed", "logged_in", "adoption_pct"])
        for r in s["units"]:
            wr.writerow([r["unit"], r["licensed"], r["logged_in"], r["adoption_pct"]])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump({k: v for k, v in s.items() if k not in ("weekly", "units")}, f, indent=2)
    print("\nWrote step_02_weekly.csv, step_02_by_unit.csv and step_02_summary.json in src/out/")


if __name__ == "__main__":
    main()
