"""Step 4 - The fix: mapping checks, transform-aware pair checks and boundary probes together.

  1. check_mapping: gaps, code coverage, capacity and reverse exposure from the catalogues alone
  2. check_pair on the 20 typical messages per build: dropped, truncated, altered, untraced
  3. check_pair on the 3 boundary probes, which fill every field to its limit
  4. coverage: what no message ever exercised

The command-line tool (iso20022_map_check.py) runs exactly this code.

KNOWN LIMIT, left in on purpose: build B10 drops the beneficiary account only for TYP 16 with CHGS S.
No message carries that combination (the probes cycle the code values together, they do not cross
them), so the defect never fires and is not found. The script prints the build and the coverage gap.

Run (from src/):  python3 step_04_with_check.py
Output: a report, plus out/step_04_builds.csv, out/step_04_static.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import (all_pairs, builds, truth_events, bundle, tool, mapping_truth, findings_of, row_flags, score,
                    detected_builds, static_score, ensure_out, OUT_DIR, FOOTPRINT_KIND)

pairs, truth, bun, blds = all_pairs(), truth_events(), bundle(), builds()
static = tool.check_mapping(bun)
found_pairs = findings_of(pairs, bun)
flags = {k: row_flags(v) for k, v in found_pairs.items()}
typical_pairs = [p for p in pairs if not p["probe"]]
typical = detected_builds(blds, typical_pairs, flags)
both = detected_builds(blds, pairs, flags)
s = score(pairs, truth, flags)
planted_builds = [b for b in blds if b["defect"] != "none"]
sf, sp, nf, nn = static_score(static, mapping_truth())
reverse = [f for f in static if f["kind"] == "reverse_exposure"]
text_rows = [r for r in bun["rows"] if r["transform"] in ("copy", "join_lines")]

foot_total = foot_found = 0
for p in pairs:
    kinds = {(f["kind"], f["subject"]) for f in found_pairs[(p["build"], p["msg"])]}
    for subject, kind, cat in truth.get((p["build"], p["msg"]), []):
        if cat == "mapping":
            foot_total += 1
            foot_found += 1 if (FOOTPRINT_KIND[kind], subject) in kinds else 0
cov = tool.coverage([p["source"] for p in pairs], bun)
missed = [b for b in planted_builds if b["build"] not in both]

print("STEP 4 - mapping checks, pair checks and boundary probes together")
print(f"  planted mapping defects found: {sf} of {sp}; harmless rows flagged: {nf} of {nn}")
print(f"  reverse exposure (warning): {len(reverse)} of {len(text_rows)} text rows could cut data on the way back to the legacy format")
print(f"  planted converter defects found in pairs: {s['found']} of {s['events']}")
print(f"  harmless variations flagged: {s['benign_flagged']} of {s['benign']}; false alarms: {s['false_alarms']}")
print(f"  mapping gaps seen in pairs (value lost, value invented, code fallback): {foot_found} of {foot_total}")
print(f"  builds with a planted defect found: typical messages alone {len(typical)} of {len(planted_builds)}, with probes {len(both)} of {len(planted_builds)}")
for b in missed:
    fired = sum(1 for (build, _m), ev in truth.items() if build == b["build"] for _s, _k, c in ev if c == "converter")
    print(f"  NOT FOUND: {b['build']} {b['defect']} on {b['iso_path']} ({b['description']}); times the defect fired in the data: {fired}")
if cov["combos"]:
    c = cov["combos"]
    print(f"  coverage: code combinations ({', '.join(c['fields'])}) never in any message: {c['missing']} of {c['total']} ({c['examples']})")
print("  result by build:")
for b in blds:
    print(f"    {b['build']} {b['defect']:<14} {'FOUND' if b['build'] in both else ('clean' if b['defect'] == 'none' else 'MISSED')}")

ensure_out()
rows = []
for b in blds:
    own = [p for p in pairs if p["build"] == b["build"]]
    seen = sorted({f"{f['kind']}:{f['subject']}" for p in own for f in found_pairs[(p["build"], p["msg"])]
                   if f["kind"] in ("dropped", "truncated", "altered")})
    rows.append({"build": b["build"], "defect": b["defect"], "element": b["iso_path"], "benign": b["benign"],
                 "description": b["description"], "typical_finds": "yes" if b["build"] in typical else "no",
                 "probes_add": "yes" if b["build"] in both and b["build"] not in typical else "no",
                 "findings": "; ".join(seen) or "none"})
with open(os.path.join(OUT_DIR, "step_04_builds.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT_DIR, "step_04_static.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["severity", "kind", "subject", "detail"], lineterminator="\n")
    w.writeheader()
    w.writerows([{k: f[k] for k in ("severity", "kind", "subject", "detail")} for f in static if f["severity"] == "error"])
summary = {"mapping_defects_found": sf, "mapping_defects": sp, "harmless_rows_flagged": nf, "harmless_rows": nn,
           "converter_events_found": s["found"], "converter_events": s["events"], "false_alarms": s["false_alarms"],
           "builds_found": len(both), "builds_planted": len(planted_builds), "builds_found_typical": len(typical),
           "reverse_exposure_rows": len(reverse), "pairs": s["pairs"]}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_builds.csv, step_04_static.csv and step_04_summary.json in src/out/")
