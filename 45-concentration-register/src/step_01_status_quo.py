"""Step 1 - Status quo: a register that says where each service runs and measures nothing about it.

Sixty-four services run on four invented cloud providers in eight regions. The register holds one
row per service with a provider and a region where the owner disclosed them, and a second table of
dependencies. Nobody adds either up. This step counts what the register holds and, because the data
is synthetic, what the generator's world would do in each outage. The truth is the loss the generator
computed (data/_generate.py), not anything this repo's tool reports.

Run (from src/):  python3 step_01_status_quo.py
"""
from __future__ import annotations

from common import LIMIT_PCT, load_register, load_truth, over_limit

services, edges, _ = load_register()
truth = load_truth()
critical = sorted(sid for sid, s in services.items() if s["criticality"] == "critical")
placed = [s for s in services.values() if s["primary"] is not None]
single_critical = [sid for sid in critical if services[sid]["primary"] is not None and services[sid]["second"] is None]
hard_sources = {a for a, _, k in edges if k == "hard"}
true_over = [sc["id"] for sc in truth["scenarios"] if over_limit(len(sc["lost"]), len(critical), LIMIT_PCT)]

print("STEP 1 - status quo: a register that lists placements and measures no concentration")
print(f"  services in the register: {len(services)}, of which critical: {len(critical)}")
print(f"  services with a provider and a region listed: {len(placed)} of {len(services)}")
print(f"  critical services with neither: {sum(1 for sid in critical if services[sid]['primary'] is None)} of {len(critical)}")
print(f"  critical services listed with one placement and no standby: {len(single_critical)} of {len(critical)}")
print(f"  hard dependencies listed: {sum(1 for _, _, k in edges if k == 'hard')}, across {len(hard_sources)} services")
print(f"  outage scenarios the process measures: 0 of {len(truth['scenarios'])}")
print(f"  scenarios that truly lose more than {LIMIT_PCT:g}% of critical services (generator's world): "
      f"{len(true_over)} of {len(truth['scenarios'])}")
print("  The register says where each service runs. It does not say what is left when a provider or a region goes dark.")
