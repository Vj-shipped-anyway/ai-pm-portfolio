"""Step 2 - The common basic approach: group the bill by the cost-center tag, exactly as written.

This is the report most teams build first. Take the tag value on each line, total the dollars per
value, and call the lines with no tag "Unallocated". It does not check a value against the cost
center registry, so a misspelled or closed value becomes a bucket of its own. Scored against the
planted owner of every line.

Run (from src/):  python3 step_02_exact_tag_report.py
"""
from common import load_world, fmt_usd, pct

w = load_world()
bill, registry, truth = w["bill"], w["registry"], w["truth"]
exact_ids = {rec["cost_center"]: rec for rec in registry.values()}
total = sum(b["usd"] for b in bill)

buckets = {}
for b in bill:
    raw = b["tags"].get("cost-center", "")
    value = raw if raw.strip() else "Unallocated"
    buckets[value] = buckets.get(value, 0) + b["usd"]

right = wrong = phantom = unalloc = on_closed = 0
for b in bill:
    value = b["tags"].get("cost-center", "")
    if not value.strip():
        unalloc += b["usd"]
    elif value not in exact_ids:
        phantom += b["usd"]
    else:
        if not exact_ids[value]["active"]:
            on_closed += b["usd"]
        if value == truth[b["line_id"]]["cc"]:
            right += b["usd"]
        else:
            wrong += b["usd"]

not_registry = sorted(v for v in buckets if v != "Unallocated" and v not in exact_ids)
print("STEP 2 - group by the cost-center tag as written")
print(f"  distinct values in the report: {len(buckets)} (the registry has {len(registry)} cost centers)")
print(f"  values that are not a registry id: {len(not_registry)}, for example {', '.join(repr(v) for v in not_registry[:4])}")
print(f"  charged to the planted owner: {fmt_usd(right)} ({pct(right, total)} of net spend)")
print(f"  charged to another cost center: {fmt_usd(wrong)} ({pct(wrong, total)}), of which on closed cost centers: {fmt_usd(on_closed)}")
print(f"  sitting in buckets that are not cost centers: {fmt_usd(phantom)} ({pct(phantom, total)})")
print(f"  'Unallocated' (no tag value, shared services included): {fmt_usd(unalloc)} ({pct(unalloc, total)})")
print("  The report looks complete. The money in the phantom buckets and on closed cost centers has no one to bill.")
