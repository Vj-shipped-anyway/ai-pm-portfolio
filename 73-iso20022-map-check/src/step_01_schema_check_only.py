"""Step 1 - Status quo: the only gate is validation against the ISO 20022 element rules.

Ten converter builds each convert the same 23 legacy messages (20 typical, 3 boundary probes). A
build is a small converter that implements the mapping and then, for eight of the ten, carries one
planted defect. The converter output is checked the way most pipelines check it: mandatory elements
present, lengths within the limit, dates and codes well formed. Nothing reads the mapping and nothing
compares the ISO value with the legacy value it came from. The truth is the list of defects each
converter recorded as it ran (data/truth_events.csv); the data is synthetic (data/_generate.py).

Run (from src/):  python3 step_01_schema_check_only.py
"""
from common import all_pairs, builds, truth_events, bundle, tool, CONVERTER

pairs, truth, bun, blds = all_pairs(), truth_events(), bundle(), builds()
valid = {(p["build"], p["msg"]): not tool.schema_issues(p["target"], bun) for p in pairs}
defective = [p for p in pairs if any(c in CONVERTER for _s, _k, c in truth.get((p["build"], p["msg"]), []))]
passing_defective = [p for p in defective if valid[(p["build"], p["msg"])]]
defect_builds = [b["build"] for b in blds if b["defect"] != "none"]
failing_builds = {p["build"] for p in pairs if not valid[(p["build"], p["msg"])]}

print("STEP 1 - ISO schema validation is the only gate")
print(f"  converter builds: {len(blds)}   legacy messages per build: {len({p['msg'] for p in pairs})}   pairs: {len(pairs)}")
print(f"  pairs that pass ISO schema validation: {sum(valid.values())} of {len(pairs)}")
print(f"  pairs with a planted converter or capacity defect: {len(defective)} of {len(pairs)}")
print(f"  defective pairs that still pass schema validation: {len(passing_defective)} of {len(defective)}")
print(f"  builds with a planted defect: {len(defect_builds)}; of those, builds with at least one schema failure: "
      f"{len([b for b in defect_builds if b in failing_builds])}")
print("  schema validation takes no mapping as input, so a gap in the mapping is out of its reach")
print("  A cut-short name, a dropped field and a rounded amount are all valid ISO values.")
