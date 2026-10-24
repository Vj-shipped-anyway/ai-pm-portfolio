"""Step 3 - Where each half of the check fails when used alone.

Three runs on the same 230 pairs, all with the transform-aware rules (padding and number formats are
ignored, amounts compared as numbers):
  mapping only        the catalogue and mapping checks, no messages
  typical messages    the 20 ordinary legacy messages per build
  boundary probes     the 3 messages with every field at its limit

KNOWN LIMIT, left in on purpose: build B10 drops the beneficiary account only when TYP is 16 and CHGS
is S. No message has that combination, so no run sees it; the coverage line says so, and step 4 does
not find it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import (all_pairs, builds, truth_events, bundle, tool, mapping_truth, findings_of, row_flags,
                    score, detected_builds, static_score)

pairs, truth, bun, blds = all_pairs(), truth_events(), bundle(), builds()
planted_builds = [b for b in blds if b["defect"] != "none"]
static_found, static_planted, neg_flagged, negatives = static_score(tool.check_mapping(bun), mapping_truth())

print("STEP 3 - each part alone")
print("  mapping only")
print(f"    planted mapping defects found: {static_found} of {static_planted}; harmless rows flagged: {neg_flagged} of {negatives}")
print("    converter defects: not visible, this run has no converter output to look at")


def run(name, subset):
    flags = {k: row_flags(v) for k, v in findings_of(subset, bun).items()}
    s = score(subset, truth, flags)
    found = detected_builds(blds, subset, flags)
    print(f"  {name}")
    print(f"    planted defects found: {s['found']} of {s['events']}; false alarms on harmless variations: {s['false_alarms']}")
    print(f"    builds with a planted converter defect found: {len(found)} of {len(planted_builds)}")
    return found


typical = run("typical messages only", [p for p in pairs if not p["probe"]])
probes = run("boundary probes only", [p for p in pairs if p["probe"]])
missed_typical = sorted(b["build"] + " " + b["defect"] for b in planted_builds if b["build"] not in typical)
print(f"  builds the typical messages miss: {', '.join(missed_typical)}")
print(f"  of those, found by the probes: {', '.join(sorted(b['build'] for b in planted_builds if b['build'] not in typical and b['build'] in probes))}")
never = [b for b in planted_builds if b["build"] not in typical and b["build"] not in probes]
for b in never:
    cov = tool.coverage([p["source"] for p in pairs], bun)["combos"]
    print(f"  found by neither: {b['build']} {b['defect']} ({b['description']}); "
          f"code combinations never in any message: {cov['missing']} of {cov['total']} ({cov['examples']})")
