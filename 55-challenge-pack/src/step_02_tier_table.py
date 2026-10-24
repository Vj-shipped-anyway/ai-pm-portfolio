"""Step 2 - The common basic approach: look the declared tier up in the tier-to-test-plan table.

The plan is the core items of the declared tier (3, 6, 10 or 13 items). There are no overlays for vendor
products or for use cases outside the model definition, the tier is whatever the sponsor wrote, and what
comes back is not reconciled. The planted truth says what each use case really owes.

Run (from src/):  python3 step_02_tier_table.py
Output: a report, plus out/step_02_summary.json
"""
from __future__ import annotations

from common import ITEM_BY_ID, ITEMS, load_world, pct, required, score_requests, write_json


def core_ids(tier: int) -> set:
    return {it["id"] for it in ITEMS if it["overlay"] == "" and it["min_tier"] <= tier}


def main() -> None:
    world = load_world()
    forms = world["forms"]
    requested = {f["use_case_id"]: core_ids(f["declared_tier"]) for f in forms}
    s = score_requests(world, requested)
    below = sum(1 for f in forms if f["declared_tier"] < world["true_tier"][f["use_case_id"]])
    above = sum(1 for f in forms if f["declared_tier"] > world["true_tier"][f["use_case_id"]])
    missed_tier = missed_overlay = 0
    for f in forms:
        uid = f["use_case_id"]
        for i in required(world, uid) - requested[uid]:
            if ITEM_BY_ID[i]["overlay"]:
                missed_overlay += 1
            else:
                missed_tier += 1
    print("STEP 2 - the tier table on the declared tier, core items only")
    print("  owed items the plan asks for: %d of %d (%s)" % (s["covered"], s["required"], pct(s["covered"], s["required"])))
    print("  items asked for that the use case does not owe: %d" % s["over"])
    print("  declared tier below the true tier: %d of %d use cases; above it: %d" % (below, len(forms), above))
    print("  owed items missed because the declared tier is low: %d" % missed_tier)
    print("  owed items missed because the table has no vendor or scope overlay: %d" % missed_overlay)
    print("  evidence defects found by reading what comes back: 0 (the plan is a list; nothing is reconciled)")
    write_json("step_02_summary.json", {"required": s["required"], "covered": s["covered"], "missed": s["missed"],
                                        "over": s["over"], "declared_below": below, "declared_above": above,
                                        "missed_tier": missed_tier, "missed_overlay": missed_overlay})
    print("Wrote step_02_summary.json in src/out/")


if __name__ == "__main__":
    main()
