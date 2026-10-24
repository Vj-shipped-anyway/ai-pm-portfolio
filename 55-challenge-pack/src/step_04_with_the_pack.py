"""Step 4 - The fix: the challenge pack.

  1. the tier used is the higher of the declared tier and the rubric recomputed from the form
  2. the plan is the tier's core items plus a vendor overlay and a scope overlay
  3. each plan item is reconciled against the evidence row: missing, wrong version, prepared inside the
     developer's unit (only for items that require an outside preparer), and stale on the latest of the
     evidence date and the reaffirmation date
The command line (`challenge_pack.py pack`) and the staged skill run exactly this code.

KNOWN LIMIT, left in on purpose: hollow evidence passes, because every check reads a date, a version or a
unit and none reads content; and a use case whose form understates its risk keeps a light plan. The
script prints both counts.

Run (from src/):  python3 step_04_with_the_pack.py
Output: a report, plus out/step_04_cases.csv, out/step_04_gaps.csv and out/step_04_summary.json
"""
from __future__ import annotations

from common import (AS_OF, DEFECTS, ITEM_BY_ID, assess, defects, load_world, pct, same_unit, score_requests, write_csv,
                    write_json)


def main() -> None:
    world = load_world()
    forms, by_uc, truth = world["forms"], world["by_uc"], world["truth"]
    requested, case_rows, gap_rows = {}, [], []
    planted = {d: 0 for d in DEFECTS}
    found = {d: 0 for d in DEFECTS}
    unasked_tier = unasked_overlay = asked_not_found = 0
    fine_flagged = not_owed_flagged = 0
    hard = {"reaffirmed": [0, 0], "boundary": [0, 0], "first_line": [0, 0]}
    hollow = hollow_pass = hollow_unasked = plan_total = gap_total = with_gaps = 0
    below = above = below_unasked = 0
    for f in forms:
        uid = f["use_case_id"]
        r = assess(f, by_uc.get(uid, {}), AS_OF)
        asked = {g["item"]["id"] for g in r["items"]}
        requested[uid] = asked
        flagged = {g["item"]["id"]: g for g in r["gaps"]}
        plan_total += len(r["items"])
        gap_total += len(r["gaps"])
        with_gaps += 1 if r["gaps"] else 0
        d = defects(world, uid)
        unasked_here = 0
        for item_id, status in d.items():
            planted[status] += 1
            if item_id not in asked:
                unasked_here += 1
                if ITEM_BY_ID[item_id]["overlay"]:
                    unasked_overlay += 1
                else:
                    unasked_tier += 1
            elif item_id in flagged and status in flagged[item_id]["problems"]:
                found[status] += 1
            else:
                asked_not_found += 1
        for item_id, g in flagged.items():
            owed, status = truth[uid].get(item_id, (0, ""))
            if not owed:
                not_owed_flagged += 1
            elif status not in DEFECTS:
                fine_flagged += 1
            gap_rows.append([uid, item_id, ";".join(g["problems"]), "; ".join(g["details"][p] for p in g["problems"])])
        for item_id, (owed, status) in truth[uid].items():
            row = by_uc.get(uid, {}).get(item_id)
            if status == "hollow":
                hollow += 1
                hollow_pass += 1 if item_id in asked and item_id not in flagged else 0
                hollow_unasked += 1 if item_id not in asked else 0
            if row is None or not owed or item_id not in asked:
                continue
            kinds = [status] if status in ("reaffirmed", "boundary") else []
            if not ITEM_BY_ID[item_id]["independent"] and status not in DEFECTS and same_unit(row["prepared_by_unit"], f["developer_unit"]):
                kinds.append("first_line")
            for key in kinds:
                hard[key][0] += 1 if item_id in flagged else 0
                hard[key][1] += 1
        true_tier = world["true_tier"][uid]
        if r["tier"] < true_tier:
            below += 1
            below_unasked += unasked_here
        elif r["tier"] > true_tier:
            above += 1
        case_rows.append([uid, f["title"], f["model_type"], r["declared"], r["tier"], true_tier, len(r["items"]),
                          len(r["gaps"]), len(d), sum(1 for i in d if i in flagged)])
    s = score_requests(world, requested)
    d_total = sum(planted.values())
    f_total = sum(found.values())
    declared_below = sum(1 for f in forms if f["declared_tier"] < world["true_tier"][f["use_case_id"]])
    declared_above = sum(1 for f in forms if f["declared_tier"] > world["true_tier"][f["use_case_id"]])
    n = len(forms)

    print("STEP 4 - the challenge pack: recomputed tier, overlays, dated and versioned reconciliation")
    print("  tier used below the true tier: %d of %d use cases (declared alone: %d); above it: %d (declared alone: %d)"
          % (below, n, declared_below, above, declared_above))
    print("  owed items the plan asks for: %d of %d (%s); asked for but not owed: %d"
          % (s["covered"], s["required"], pct(s["covered"], s["required"]), s["over"]))
    print("  planted defects found: %d of %d (%s): missing %d of %d, stale %d of %d, wrong version %d of %d, "
          "not independent %d of %d"
          % (f_total, d_total, pct(f_total, d_total), found["missing"], planted["missing"], found["stale"],
             planted["stale"], found["wrong_version"], planted["wrong_version"], found["not_independent"],
             planted["not_independent"]))
    print("  defects not found: %d, of which never asked for because the tier used is low: %d, because the form omits the "
          "vendor: %d, asked for and passed: %d"
          % (d_total - f_total, unasked_tier, unasked_overlay, asked_not_found))
    print("  gaps raised on owed items that are fine: %d; on items the use case does not owe: %d"
          % (fine_flagged, not_owed_flagged))
    print("  hard negatives flagged: reaffirmed %d of %d, edge of the window %d of %d, first-line items prepared by the "
          "developer's unit %d of %d"
          % (hard["reaffirmed"][0], hard["reaffirmed"][1], hard["boundary"][0], hard["boundary"][1],
             hard["first_line"][0], hard["first_line"][1]))
    print("  checked %d use cases: %d with gaps, %d complete; %d plan items, %d on file and current"
          % (n, with_gaps, n - with_gaps, plan_total, plan_total - gap_total))
    print("  KNOWN LIMIT 1: %d of %d hollow items pass every check and %d were never asked for (the checks read dates, "
          "versions and units, not content)" % (hollow_pass, hollow, hollow_unasked))
    print("  KNOWN LIMIT 2: %d use cases keep a tier below the true tier because the form understates it; "
          "they leave %d defects unasked" % (below, below_unasked))
    write_csv("step_04_cases.csv", ["use_case_id", "title", "model_type", "declared_tier", "tier_used", "true_tier",
                                    "plan_items", "gaps", "defects_planted", "defects_flagged"], case_rows)
    write_csv("step_04_gaps.csv", ["use_case_id", "item_id", "kinds", "detail"], gap_rows)
    write_json("step_04_summary.json", {
        "use_cases": n, "tier_below": below, "tier_above": above, "declared_below": declared_below,
        "declared_above": declared_above, "required": s["required"], "covered": s["covered"], "over": s["over"],
        "defects": d_total, "found": found, "found_total": f_total, "planted": planted, "unasked_tier": unasked_tier,
        "unasked_overlay": unasked_overlay, "asked_not_found": asked_not_found, "fine_flagged": fine_flagged,
        "not_owed_flagged": not_owed_flagged, "hard": hard, "with_gaps": with_gaps, "plan_items": plan_total,
        "current": plan_total - gap_total, "hollow": hollow, "hollow_pass": hollow_pass, "hollow_unasked": hollow_unasked, "below_unasked": below_unasked})
    print("Wrote step_04_cases.csv, step_04_gaps.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
