"""Step 3 - Deficiencies exposed: where each piece of the basic approach fails.

  A. The tier comes from the form, and the form is wrong in places.
  B. A presence-only reconciliation (is there a row on file for the item?) cannot see a stale item, a
     version mismatch or evidence prepared inside the developer's own unit.
  C. Two simple rules added to B (date-only freshness, preparer equals developer unit on every item) find
     the defects they were written for and raise false alarms on reaffirmed items and on first-line items.

KNOWN LIMIT, left in on purpose: hollow evidence (on time, current, right version, prepared outside the
developer's unit, and empty of content) cannot be seen from any field in the files. The script counts it.

Run (from src/):  python3 step_03_deficiencies_exposed.py
Output: a report, plus out/step_03_summary.json
"""
from __future__ import annotations

from common import (AS_OF, CLASS_ORDER, DEFECTS, TIERS, add_months, defects, effective_tier, load_world, plan_items,
                    same_unit, write_json)


def main() -> None:
    world = load_world()
    forms, by_uc, truth = world["forms"], world["by_uc"], world["truth"]
    n = len(forms)

    # A. the form
    below = sum(1 for f in forms if f["declared_tier"] < world["true_tier"][f["use_case_id"]])
    vendor_dep = [f for f in forms if world["true_vendor"][f["use_case_id"]] != "none"]
    vendor_off = sum(1 for f in vendor_dep if f["vendor_model"] == "none")
    class_low = sum(1 for f in forms if CLASS_ORDER.index(f["data_class"]) < CLASS_ORDER.index(world["true_class"][f["use_case_id"]]))
    still_below = sum(1 for f in forms if effective_tier(f)[0] < world["true_tier"][f["use_case_id"]])

    # B and C. the declared tier plus the overlays the form allows
    planted = {d: 0 for d in DEFECTS}
    b_found = {d: 0 for d in DEFECTS}
    c_found = {d: 0 for d in DEFECTS}
    reaff_total = reaff_flag = line1_total = line1_flag = 0
    for f in forms:
        uid = f["use_case_id"]
        rows = by_uc.get(uid, {})
        plan = {it["id"]: it for it in plan_items(f["model_type"], f["vendor_model"], f["declared_tier"])}
        cutoff = add_months(AS_OF, -TIERS[f["declared_tier"]]["window_months"])
        for item_id, status in defects(world, uid).items():
            planted[status] += 1
            row = rows.get(item_id)
            if item_id in plan and row is None:
                b_found[status] += 1
                c_found[status] += 1
            elif row is not None and item_id in plan:
                if status == "stale" and row["evidence_date"] < cutoff:
                    c_found[status] += 1
                if status == "not_independent" and same_unit(row["prepared_by_unit"], f["developer_unit"]):
                    c_found[status] += 1
        for item_id, it in plan.items():
            row = rows.get(item_id)
            owed, status = truth[uid].get(item_id, (0, ""))
            if row is None or not owed:
                continue
            if status == "reaffirmed":
                reaff_total += 1
                reaff_flag += 1 if row["evidence_date"] < cutoff else 0
            if not it["independent"] and status not in DEFECTS and same_unit(row["prepared_by_unit"], f["developer_unit"]):
                line1_total += 1
                line1_flag += 1
    d_total = sum(planted.values())
    b_total = sum(b_found.values())
    hidden_b = d_total - b_total
    hollow = sum(1 for uid in truth for (o, s) in truth[uid].values() if o and s == "hollow")

    print("STEP 3 - where each piece fails")
    print("  A. the tier comes from the form")
    print("     declared tier below the true tier: %d of %d use cases" % (below, n))
    print("     vendor dependency left off the form: %d of %d vendor-dependent use cases" % (vendor_off, len(vendor_dep)))
    print("     data class written below the truth: %d of %d use cases" % (class_low, n))
    print("     after the rubric recompute (higher of declared and recomputed) still below the true tier: %d of %d"
          % (still_below, n))
    print("  B. presence only: is there a row on file for the item?")
    print("     missing items found: %d of %d" % (b_found["missing"], planted["missing"]))
    print("     stale, wrong-version and not-independent items that pass: %d (stale %d, wrong version %d, not independent %d)"
          % (planted["stale"] + planted["wrong_version"] + planted["not_independent"], planted["stale"],
             planted["wrong_version"], planted["not_independent"]))
    print("     defects found: %d of %d; hidden because the item was never asked for or the file looks fine: %d"
          % (b_total, d_total, hidden_b))
    print("  C. add date-only freshness and 'preparer equals developer unit' on every item")
    print("     stale found: %d of %d; not independent found: %d of %d; wrong version found: 0 of %d (no rule)"
          % (c_found["stale"], planted["stale"], c_found["not_independent"], planted["not_independent"],
             planted["wrong_version"]))
    print("     false alarms: reaffirmed items flagged stale: %d of %d; first-line items flagged as not independent: %d of %d"
          % (reaff_flag, reaff_total, line1_flag, line1_total))
    print("  KNOWN LIMIT, carried into step 4: %d hollow items are on time, current, the right version and prepared "
          "outside the developer's unit. No field shows that they say nothing." % hollow)
    write_json("step_03_summary.json", {
        "below_declared": below, "vendor_dependent": len(vendor_dep), "vendor_off_form": vendor_off, "class_low": class_low,
        "still_below_after_recompute": still_below, "planted": planted, "b_found": b_found, "c_found": c_found,
        "b_total": b_total, "defects": d_total, "reaffirmed_flagged": reaff_flag, "reaffirmed": reaff_total,
        "first_line_flagged": line1_flag, "first_line": line1_total, "hollow": hollow})
    print("Wrote step_03_summary.json in src/out/")


if __name__ == "__main__":
    main()
