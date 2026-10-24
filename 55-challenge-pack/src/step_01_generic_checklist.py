"""Step 1 - Status quo: one generic checklist for every use case.

A challenger builds the request list from the last review they did: inventory record, purpose,
limitations, developmental testing, input data and documentation (CH01 to CH06). Nobody reads the tier,
and nobody reconciles what comes back. The planted truth says which items each use case really owes and
which of them carry a defect; this step counts what the generic list asks for and what it can find.

Run (from src/):  python3 step_01_generic_checklist.py
Output: a report, plus out/step_01_summary.json
"""
from __future__ import annotations

from common import DEFECTS, ITEM_BY_ID, defects, load_world, pct, required, score_requests, write_json

GENERIC = ["CH01", "CH02", "CH03", "CH04", "CH05", "CH06"]


def main() -> None:
    world = load_world()
    forms = world["forms"]
    requested = {f["use_case_id"]: set(GENERIC) for f in forms}
    s = score_requests(world, requested)
    high = [f["use_case_id"] for f in forms if world["true_tier"][f["use_case_id"]] >= 3]
    planted = {d: 0 for d in DEFECTS}
    for f in forms:
        for status in defects(world, f["use_case_id"]).values():
            planted[status] += 1
    d_total = sum(planted.values())
    missed_indep = sum(1 for f in forms for i in required(world, f["use_case_id"]) - requested[f["use_case_id"]]
                       if ITEM_BY_ID[i]["independent"])
    no_indep = sum(1 for uid in high if not any(ITEM_BY_ID[i]["independent"] for i in requested[uid]))
    print("STEP 1 - one generic checklist (%s) for every use case" % ", ".join(GENERIC))
    print("  use cases: %d; items they truly owe, in all: %d" % (len(forms), s["required"]))
    print("  owed items the list asks for: %d of %d (%s)" % (s["covered"], s["required"], pct(s["covered"], s["required"])))
    print("  owed items never asked for: %d, of which independent challenge items: %d"
          % (s["missed"], missed_indep))
    print("  items asked for that the use case does not owe: %d" % s["over"])
    print("  tier 3 and 4 use cases whose list has no independent challenge item: %d of %d" % (no_indep, len(high)))
    print("  planted evidence defects on owed items: %d (missing %d, stale %d, wrong version %d, not independent %d)"
          % (d_total, planted["missing"], planted["stale"], planted["wrong_version"], planted["not_independent"]))
    print("  defects the process finds by reading the evidence: 0 of %d (nothing is reconciled)" % d_total)
    write_json("step_01_summary.json", {"use_cases": len(forms), "required": s["required"], "covered": s["covered"],
                                        "missed": s["missed"], "over": s["over"], "high_tier": len(high), "high_tier_no_independent": no_indep,
                                        "missed_independent": missed_indep, "defects": d_total})
    print("Wrote step_01_summary.json in src/out/")


if __name__ == "__main__":
    main()
