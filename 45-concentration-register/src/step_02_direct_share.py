"""Step 2 - The common basic approach: count critical services by provider and by region.

Group the critical services by the provider and region on their own row, compute each group's share,
and flag a group above the limit. This is the vendor-by-vendor concentration view that project 18
(VendorLens) applies to upstream model providers, applied to cloud providers and regions. It reads
only the placement on each service's own row: no dependency, no standby. The limit is 30%, an
assumption (no rule names a number). The truth is the generator's own loss per scenario.

Run (from src/):  python3 step_02_direct_share.py
"""
from __future__ import annotations

from common import LIMIT_PCT, flag_counts, fmt_pct, load_register, load_truth, over_limit, score

services, _, reg = load_register()
truth = load_truth()
direct = score(reg, truth, deps=False, failover=False)
rows = direct["rows"]
total = rows[0]["critical_total"]
unplaced = sum(1 for s in services.values() if s["criticality"] == "critical" and s["primary"] is None)
f = flag_counts(direct, LIMIT_PCT)

print(f"STEP 2 - direct share of critical services, flag above {LIMIT_PCT:g}%")
print(f"  share of the {total} critical services by primary provider:")
for r in rows:
    if r["kind"] == "provider":
        mark = "  <- flagged" if over_limit(r["pred"], total, LIMIT_PCT) else ""
        print(f"    {r['provider']:<6} {r['pred']:>2} of {total}  {fmt_pct(r['pred'], total):>6}{mark}")
print(f"    no placement listed: {unplaced} of {total}")
print(f"  scenarios flagged: {len(f['flagged'])} of {len(rows)} ({', '.join(f['flagged']) or 'none'})")
print(f"  scenarios that truly lose more than {LIMIT_PCT:g}%: {len(f['truth'])} of {len(rows)}")
print(f"  flagged and truly over: {len(f['caught'])}; flagged and not over: {len(f['false'])}; truly over and not flagged: {len(f['missed'])}")
print(f"  critical (scenario, service) pairs lost in truth: {direct['truth']}; the direct view counts {direct['pred']}, "
      f"of which {direct['tp']} are real and {direct['fp']} survive on a standby")
print("  The share of one provider says nothing about what depends on it, or what a standby would carry.")
