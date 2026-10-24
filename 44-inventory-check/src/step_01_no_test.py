"""Step 1 - Status quo: the inventory is a file that people maintain and nobody tests.

A model risk reviewer opens the inventory once a quarter and reads the rows that look odd. This step does not
test anything. It reads the planted truth (data/inventory_truth.csv, data/shadow_truth.csv) to show what is
wrong in the file as it stands and how much traffic runs outside it. The data is synthetic (data/_generate.py);
the truth label of each record is the case it was built as.

Run (from src/):  python3 step_01_no_test.py
"""
from collections import Counter

from common import load_world, load_truth, load_shadows, split_truth, parse_tier

as_of, records, usage = load_world()
truth, shadows = load_truth(), load_shadows()
defective, clean = split_truth(truth)
by_id = {r["system_id"]: r for r in records}
high = [sid for sid, r in by_id.items() if r.get("status") == "production" and parse_tier(r.get("risk_tier")) in (3, 4)]
high_bad = [sid for sid in high if truth[sid]["truth_class"] == "defective"]
total_calls = sum(u["calls"] for u in usage)
unlisted_calls = sum(s["calls"] for s in shadows)
kinds = Counter(shadow["shadow_kind"] for shadow in shadows)

print("STEP 1 - the inventory as it stands, with no test run on it")
print(f"  records: {len(records)}   usage rows: {len(usage)}   as of {as_of.isoformat()}")
print("  tests run on the inventory today: 0")
print(f"  truth: {len(defective)} defective records, {len(clean)} clean")
print(f"  defective records among production systems at tier 3 or 4: {len(high_bad)} of {len(high)}")
print(f"  records flagged for a reviewer today: 0 of {len(records)}")
print(f"  shadow systems in the usage export: {len(shadows)} ({kinds['unregistered_visible']} under their own name, "
      f"{kinds['untagged']} with no system id, {kinds['hidden_behind_registered']} under a listed system's id)")
print(f"  calls from those shadow systems: {unlisted_calls} of {total_calls} ({100.0 * unlisted_calls / total_calls:.1f}%)")
print("  The reviewer finds a stale or missing field by reading the row, or finds out when an incident forces the question.")
