"""Step 4 - The fix: three tests run together over the inventory and the usage export.

  completeness   required fields, valid values, the fields an agent needs, the evidence a tier needs
  staleness      review and evaluation dates against a cadence per tier; the model the record names against the
                 model recent traffic used
  coverage       usage with no record, a retired system still running, a production system with no traffic

The command-line tool in inventory_check.py runs exactly this code. A record is FAIL when any finding is a
fail, REVIEW when its findings are all reviews, OK when it has none.

KNOWN LIMITS, left in on purpose: a placeholder the word list does not hold, a review date refreshed in bulk,
a quarterly system that looks idle, and shadow traffic that carries a listed id or none. The script prints them.

Run (from src/):  python3 step_04_with_checks.py
Output: a report, plus out/step_04_systems.csv, out/step_04_shadows.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import (load_world, load_truth, load_shadows, split_truth, case_counts, check, decide, ensure_out,
                    blank_cell_flags, OUT_DIR)

as_of, records, usage = load_world()
truth, shadows = load_truth(), load_shadows()
defective, clean = split_truth(truth)
findings = check(records, usage, as_of)
by_id = {}
for f in findings:
    by_id.setdefault(f["system_id"], []).append(f)
flagged = {r["system_id"] for r in records if r["system_id"] in by_id}
rows = []
for r in records:
    fs = by_id.get(r["system_id"], [])
    verdict = "FAIL" if any(f["severity"] == "fail" for f in fs) else "REVIEW" if fs else "OK"
    t = truth[r["system_id"]]
    rows.append({"system_id": r["system_id"], "name": r.get("name", ""), "status": r.get("status", ""),
                 "risk_tier": r.get("risk_tier", ""), "kind": r.get("kind", ""), "case_kind": t["case_kind"], "truth": t["truth_class"], "verdict": verdict,
                 "findings": "; ".join(f"{f['kind']}:{f['field']}" for f in fs) or "none"})

bad_flagged = [s for s in defective if s in flagged]
clean_flagged = [s for s in clean if s in flagged]
missed = [s for s in defective if s not in flagged]
verdicts = Counter(r["verdict"] for r in rows)
hard = [s for s in clean if truth[s]["case_kind"] != "clean"]
hard_flagged = [s for s in hard if s in flagged]
tests = Counter(f["test"] for f in findings)
basic = sum(1 for r in records if blank_cell_flags(r, as_of))
unregistered = {f["system_id"] for f in findings if f["kind"] == "unregistered_system"}
untagged = any(f["kind"] == "untagged_traffic" for f in findings)

print("STEP 4 - completeness, staleness and coverage together")
print(f"  defective records flagged: {len(bad_flagged)} of {len(defective)}")
print(f"  clean records flagged: {len(clean_flagged)} of {len(clean)} ({', '.join(sorted(Counter(truth[s]['case_kind'] for s in clean_flagged))) or 'none'}; "
      f"hard negatives left alone: {len(hard) - len(hard_flagged)} of {len(hard)})")
print(f"  records with a fail finding: {verdicts['FAIL']}; review only: {verdicts['REVIEW']}; no finding: {verdicts['OK']}")
print(f"  records a person has to open: {len(flagged)} of {len(records)} (step 1: all {len(records)} or none; step 2 flagged {basic})")
print(f"  findings: {len(findings)} (completeness {tests['completeness']}, staleness {tests['staleness']}, coverage {tests['coverage']})")
named = [s for s in shadows if s["shadow_kind"] == "unregistered_visible" and s["shadow_name"] in unregistered]
hidden = [s for s in shadows if s["shadow_kind"] == "hidden_behind_registered"]
print(f"  shadow systems named from the usage export: {len(named)} of {len(shadows)}; "
      f"traffic with no system id reported but not attributed: {'yes' if untagged else 'no'}; "
      f"hidden under a listed id: {len(hidden)} not found")
print(f"  inventory decision: {decide(findings)}")
print(f"  defective records that still pass: {len(missed)} of {len(defective)} "
      f"({', '.join(f'{k} {v}' for k, v in sorted(Counter(truth[s]['case_kind'] for s in missed).items())) or 'none'})")
for s in missed:
    print(f"    {s} {truth[s]['case_kind']}: {truth[s]['detail']}")
print("  decisions by planted case (flagged of total):")
for cls in ("defective", "clean"):
    for kind, hit, total in case_counts(truth, flagged, cls):
        print(f"    {cls:<10} {kind:<26} {hit} of {total}")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_systems.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT_DIR, "step_04_shadows.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["shadow_name", "shadow_kind", "tagged_as", "calls", "result"])
    for s in shadows:
        result = ("named" if s["shadow_name"] in unregistered else "not found" if s["shadow_kind"] == "unregistered_visible"
                  else "reported, not attributed" if s["shadow_kind"] == "untagged" and untagged else "not found")
        w.writerow([s["shadow_name"], s["shadow_kind"], s["tagged_as"], s["calls"], result])
summary = {"defective_flagged": len(bad_flagged), "defective": len(defective), "clean_flagged": len(clean_flagged),
           "clean": len(clean), "records": len(records), "to_open": len(flagged), "missed": len(missed),
           "shadows_named": len(named), "shadows": len(shadows), "decision": decide(findings), "as_of": as_of.isoformat()}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_systems.csv, step_04_shadows.csv and step_04_summary.json in src/out/")
