"""Step 2 - The common basic approach: a service is green when its latest drill passed.

This is the spreadsheet most teams keep. For each service take the latest drill of any kind; green
if it passed, red if it failed or if there is none. The truth is known, so this step counts what
the green and the red get wrong.

Run (from src/):  python3 step_02_last_drill_passed.py
"""
from __future__ import annotations

from collections import Counter

from common import load_all, truth_class


def latest_passed(drills: list) -> bool:
    if not drills:
        return False
    return max(drills, key=lambda d: (d["date"], d["drill_id"]))["outcome"] == "pass"


def main() -> None:
    data = load_all()
    mine = {i: [] for i in data["by_id"]}
    for d in data["drills"]:
        mine[d["service_id"]].append(d)
    green = sorted(i for i in mine if latest_passed(mine[i]))
    red = sorted(i for i in mine if i not in green)
    false_green = [i for i in green if truth_class(data, i) == "not_ready"]
    needless_red = [i for i in red if truth_class(data, i) != "not_ready"]
    kinds = Counter(data["truth"][i]["story"] for i in false_green)
    print("STEP 2 - green when the latest drill passed")
    print(f"  green: {len(green)} of {len(mine)}   red: {len(red)} of {len(mine)}")
    print(f"  green services that would not recover: {len(false_green)} of {len(green)}")
    print("  by planted story: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    print(f"  red services that are not a gap (accepted risk): {len(needless_red)} of {len(red)}")
    t1 = [i for i in green if data["by_id"][i]["tier"] == 1]
    t1_bad = [i for i in t1 if truth_class(data, i) == "not_ready"]
    print(f"  tier-1 services shown green that would not recover: {len(t1_bad)} of {len(t1)}")
    print("  A pass of any kind counts, however old, however narrow, however slow.")


if __name__ == "__main__":
    main()
