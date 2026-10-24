"""Step 3 - Where the direct share fails, and the one limit left in on purpose.

Four deficiencies of the step 2 view, each measured against the generator's loss per scenario:
  1. dependency blindness: a provider that hosts few critical services but sits under many
  2. failover blindness: services counted as lost that a standby would carry
  3. the other way to get it wrong: walk the dependencies but count a soft dependency as hard
  4. services with no placement are in no group at all
KNOWN LIMIT, left in on purpose: a hard dependency that nobody listed. No rule here can follow an
edge the register does not hold, and step 4 does not either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from __future__ import annotations

from collections import Counter

from common import LIMIT_PCT, flag_counts, fmt_pct, load_register, load_truth, score, with_truth

services, edges, reg = load_register()
truth = load_truth()
direct = score(reg, truth, deps=False, failover=False)
total = direct["rows"][0]["critical_total"]
by_id = {r["scenario"]: r for r in direct["rows"]}
f = flag_counts(direct, LIMIT_PCT)
t_by_id = {sc["id"]: len(sc["lost"]) for sc in truth["scenarios"]}

print("STEP 3 - the direct share, taken apart")
print("  (1) dependency blindness: truly over the limit and not flagged by the direct view")
for sid in f["missed"]:
    print(f"      {sid:<10} direct {fmt_pct(by_id[sid]['pred'], total):>6}   truth {fmt_pct(t_by_id[sid], total):>6}")
print(f"  (2) failover blindness: of {direct['pred']} pairs the direct view counts, {direct['fp']} survive on a standby that works")
naive = score(reg, truth, soft_as_hard=True)
nf = flag_counts(naive, LIMIT_PCT)
print(f"  (3) soft dependencies counted as hard: flags {len(nf['flagged'])} of {len(naive['rows'])} scenarios, "
      f"{len(nf['false'])} of them not over the limit in truth; counts {naive['fp']} pairs that are not lost")
unplaced = sorted(sid for sid, s in services.items() if s["criticality"] == "critical" and s["primary"] is None)
where = Counter(truth["services"][sid]["true_provider"] for sid in unplaced)
print(f"  (4) no placement: {len(unplaced)} of {total} critical services are in no group; "
      f"they truly sit on " + ", ".join(f"{p} {n}" for p, n in sorted(where.items())))
unlisted = [e for e in truth["edges"] if e["listed"] == "no"]
with_edges = score(with_truth(services, edges, truth, unlisted=True), truth)
base = score(reg, truth)
print(f"  KNOWN LIMIT: {len(unlisted)} hard dependencies exist that the register does not list. Following the dependencies it "
      f"does list, {base['fn']} critical pairs are still lost in truth and not found; listing the {len(unlisted)} would find "
      f"{base['fn'] - with_edges['fn']} of them (step 4 shows the rest).")
print("  A share by provider cannot see any of this; following dependencies and standbys can, up to what the register holds.")
