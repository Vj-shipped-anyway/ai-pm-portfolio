"""Step 4 - The fix: follow hard dependencies and standbys (concentration_register.py).

For every provider and every region, take the services whose placement is hit, drop the ones with a
second placement outside the outage, then add every service that hard-depends on a lost one. The
command-line tool and this script run the same functions. The result is scored against the loss the
generator computed from the true world.

KNOWN LIMIT, left in on purpose: the tool only sees what the register holds. A service with no
placement, a hard dependency nobody listed and a standby that does not take over all make a scenario
look better than it is. The script prints the pairs it misses and where each miss comes from.

Run (from src/):  python3 step_04_with_register_model.py
Output: a report, plus out/step_04_scenarios.csv and out/step_04_summary.json
"""
from __future__ import annotations

import csv
import json
import os

from common import (LIMIT_PCT, OUT_DIR, ensure_out, flag_counts, fmt_pct, load_register, load_truth, score,
                    with_truth)

services, edges, reg = load_register()
truth = load_truth()
tool = score(reg, truth)
direct = score(reg, truth, deps=False, failover=False)
rows = tool["rows"]
total = rows[0]["critical_total"]
f = flag_counts(tool, LIMIT_PCT)
fd = flag_counts(direct, LIMIT_PCT)
n_unlisted = sum(1 for e in truth["edges"] if e["listed"] == "no")
n_broken = sum(1 for t in truth["services"].values() if t["failover_works"] == "no")

print("STEP 4 - hard dependencies and standbys followed")
print(f"  scenarios over {LIMIT_PCT:g}% in truth: {len(f['truth'])} of {len(rows)}; flagged by the tool: {len(f['flagged'])}")
print(f"  correctly flagged: {len(f['caught'])}; flagged and not over: {len(f['false'])}; over and not flagged: {len(f['missed'])}")
print(f"  the direct view of step 2 caught {len(fd['caught'])} of {len(fd['truth'])}")
print(f"  critical (scenario, service) pairs lost in truth: {tool['truth']}; the tool reports {tool['pred']}, "
      f"{tool['tp']} real and {tool['fp']} not")
print(f"  pairs the tool misses: {tool['fn']} of {tool['truth']} (recall {100.0 * tool['tp'] / tool['truth']:.1f}%)")
print("  where the misses come from, giving the tool what the register lacks, one thing at a time:")
steps = [("as registered", {}),
         ("+ true placement of unplaced services", {"placements": True}),
         (f"+ the {n_unlisted} unlisted hard dependencies", {"placements": True, "unlisted": True}),
         (f"+ standbys that do not take over ({n_broken})", {"placements": True, "unlisted": True, "failovers": True})]
ablation = []
for label, kw in steps:
    s = score(with_truth(services, edges, truth, **kw), truth)
    ablation.append({"step": label, "missed": s["fn"], "false": s["fp"]})
    print(f"    {label:<42} missed {s['fn']:>2}, not real {s['fp']}")
print("  the tool understates the loss in these scenarios (tool vs truth, share of critical services):")
for r in sorted(rows, key=lambda r: (-r["fn"], r["scenario"])):
    if r["fn"]:
        print(f"    {r['scenario']:<10} {fmt_pct(r['pred'], total):>6} vs {fmt_pct(r['truth'], total):>6}")
print(f"  limit sensitivity (scenarios, of {len(rows)}):")
print(f"    {'limit':<7}{'over in truth':>14}{'tool flags':>12}{'tool correct':>14}{'direct correct':>16}{'tool false flags':>18}")
sweep = []
for lim in (20.0, 25.0, 30.0, 35.0, 40.0, 50.0):
    a, b = flag_counts(tool, lim), flag_counts(direct, lim)
    sweep.append({"limit_pct": lim, "truth": len(a["truth"]), "flagged": len(a["flagged"]), "caught": len(a["caught"]),
                  "false": len(a["false"]), "direct_caught": len(b["caught"])})
    print(f"    {f'{lim:g}%':<7}{len(a['truth']):>14}{len(a['flagged']):>12}{len(a['caught']):>14}{len(b['caught']):>16}{len(a['false']):>18}")
unplaced = sum(1 for s in services.values() if s["criticality"] == "critical" and s["primary"] is None)
print(f"  critical services with no placement, outside every scenario: {unplaced} of {total}")

ensure_out()
by_direct = {r["scenario"]: r for r in direct["rows"]}
with open(os.path.join(OUT_DIR, "step_04_scenarios.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["scenario", "kind", "critical_total", "direct_lost", "tool_lost", "truth_lost"])
    for r in rows:
        w.writerow([r["scenario"], r["kind"], total, by_direct[r["scenario"]]["pred"], r["pred"], r["truth"]])
summary = {"critical": total, "scenarios": len(rows), "limit_pct": LIMIT_PCT, "truth_over": len(f["truth"]),
           "flagged": len(f["flagged"]), "caught": len(f["caught"]), "false_flags": len(f["false"]),
           "direct_caught": len(fd["caught"]), "pairs_truth": tool["truth"], "pairs_tool": tool["pred"],
           "pairs_missed": tool["fn"], "unplaced_critical": unplaced, "unlisted_edges": n_unlisted,
           "ablation": ablation, "sweep": sweep}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_scenarios.csv and step_04_summary.json in src/out/")
