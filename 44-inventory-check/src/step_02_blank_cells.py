"""Step 2 - The common check: no blank cell, and reviewed within the last year.

Most inventories get this far. A filter finds rows with an empty required column, and one rule asks for a
review date inside 365 days, the same for every tier. It reads no usage data and has no rule that depends on
the kind of system. Scored against the same planted truth as steps 3 and 4.

Run (from src/):  python3 step_02_blank_cells.py
"""
from common import load_world, load_truth, split_truth, case_counts, blank_cell_flags

as_of, records, _ = load_world()
truth = load_truth()
defective, clean = split_truth(truth)
flagged = {r["system_id"] for r in records if blank_cell_flags(r, as_of)}
bad_flagged = [s for s in defective if s in flagged]
clean_flagged = [s for s in clean if s in flagged]
looks_complete = [r["system_id"] for r in records if r["system_id"] not in flagged]
looks_complete_bad = [s for s in looks_complete if truth[s]["truth_class"] == "defective"]

print("STEP 2 - the common check: no blank cell in the 13 required columns, reviewed within 365 days")
print(f"  records flagged: {len(flagged)} of {len(records)}")
print(f"  defective records flagged: {len(bad_flagged)} of {len(defective)}")
print(f"  clean records flagged: {len(clean_flagged)} of {len(clean)} ("
      + (", ".join(f"{k} {h}" for k, h, _ in case_counts(truth, flagged, "clean") if h) or "none") + ")")
print(f"  records that look complete: {len(looks_complete)}; of those, defective: {len(looks_complete_bad)}")
print("  defective records flagged, by planted case:")
for kind, hit, total in case_counts(truth, flagged, "defective"):
    print(f"    {kind:<20} {hit} of {total}")
print("  It never reads the usage file, so it cannot see a system that runs without a record, a model that changed,")
print("  or an agent with no tool list. One review limit for every tier lets a tier 4 record go 365 days.")
