"""Step 4 - The fix: resolve every model string, then build the calendar, the hit list and the cost view.

deprecation_impact.py does four things the lookups in steps 2 and 3 do not:
  1. resolves a string by an explicit id, an alias table (with the date each alias was recorded),
     or the family column, and follows base_model_id from a fine-tune to the model it was built on
  2. covers every role: primary, fallback and judge
  3. sends what it cannot resolve to a check queue instead of calling it clear (an unpinned family
     with a retiring snapshot, an unknown string, a stale alias, a feature with no model recorded)
  4. dates each hit: days left, lead time needed, tier, and cost per month on the named successor

KNOWN LIMIT, left in on purpose: a dependency no registry row records, and a recent alias entry that
is wrong, pass as clear. The script prints each one.

Run (from src/):  python3 step_04_with_map.py
Output: a report, plus out/step_04_dependencies.csv, out/step_04_calendar.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import OUT_DIR, affected_keys, ensure_out, family_search, kinds, load_truth, tool_result

truth = load_truth()
aff = affected_keys(truth)
by_key = {(r["feature_id"], r["role"]): r for r in truth}
res = tool_result()
deps = res["dependencies"]
migrate = {(d["feature_id"], d["role"]) for d in deps if d["verdict"] == "hit" and d["tier"] != "SUNSETS"}
sunsets = [d for d in deps if d["tier"] == "SUNSETS"]
checks = [d for d in deps if d["verdict"] == "check"]
check_keys = {(d["feature_id"], d["role"]) for d in checks}
no_model = {d["feature_id"] for d in checks if d["role"] == "unknown"}
queued = {k for k in aff - migrate if k in check_keys or k[0] in no_model}
missed = aff - migrate - queued
false_hits = migrate - aff
proved = {(d["feature_id"], d["role"]) for d in checks if d["role"] != "unknown" and (d["feature_id"], d["role"]) in aff}
sunset_truth = [r for r in truth if r["true_retire_date"] and r["affected"] == "no"]
family = family_search()
reads = {d["feature_id"] for d in deps if d["tier"] != "SUNSETS"}
tiers = Counter(d["tier"] for d in deps if d["verdict"] == "hit")

print("STEP 4 - resolve, date and price every dependency")
print(f"  affected dependencies found and dated: {len(aff & migrate)} of {len(aff)}")
print(f"  affected dependencies in the check queue: {len(queued)}")
print(f"  affected dependencies missed with no flag: {len(missed)}")
print(f"  hits that are not affected: {len(false_hits)} of {len(migrate)}")
no_model_aff = sum(1 for f in no_model if any(k[0] == f for k in aff))
print(f"  check queue: {len(checks)} entries, of which {len(proved)} proved affected and {len(checks) - len(proved) - len(no_model)} did not; "
      f"{len(no_model)} are features with no model recorded ({no_model_aff} of them affected)")
fs_false = family - aff
cleared_right = {k for k in fs_false if k not in migrate and k not in check_keys}
print(f"  rows family search flags that are not affected and this tool leaves alone: {len(cleared_right)} of {len(fs_false)}")
print(f"  features a person opens: {len(reads)} (family search: {len({k[0] for k in family})})")
print(f"  dependencies of a feature that sunsets before its model retires, recognised: {len(sunsets)} of {len(sunset_truth)}")
print("  tiers: " + ", ".join(f"{t} {tiers[t]}" for t in ("PAST", "LATE", "TIGHT", "ROOM", "SUNSETS")))
print(f"  retirement calendar: {len(res['calendar'])} notices, {sum(1 for c in res['calendar'] if c['features'] == 0)} with no registered feature")
print(f"  cost per month on the named successors: ${res['cost_now']:,.2f} -> ${res['cost_after']:,.2f}, {res['unpriced']} dependencies have no priced successor")
print(f"  KNOWN LIMIT, still missed: {len(missed)} ({kinds(missed, truth)})")
for k in sorted(missed):
    print(f"    {k[0]} {k[1]} {by_key[k]['kind']} on {by_key[k]['true_model_id']}")
print(f"  family search flagged and this tool did not: {len((family & aff) - migrate - queued)} ({kinds((family & aff) - migrate - queued, truth)})")

ensure_out()
rows = []
for d in deps:
    t = by_key.get((d["feature_id"], d["role"]))
    truly = ("yes" if (d["feature_id"], d["role"]) in aff else "no") if t else ("yes" if any(k[0] == d["feature_id"] for k in aff) else "no")
    rows.append({"feature_id": d["feature_id"], "feature_name": d["feature_name"], "criticality": d["criticality"], "role": d["role"],
                 "model_ref": d["model_ref"], "verdict": d["verdict"], "tier": d["tier"], "model_id": d["model_id"],
                 "root_model_id": d["root_model_id"], "retire_date": d["retire_date"],
                 "days_left": "" if d["days_left"] is None else d["days_left"], "slack_days": "" if d["slack_days"] is None else d["slack_days"],
                 "monthly_calls": d["monthly_calls"], "cost_now": "" if d["cost_now"] is None else d["cost_now"],
                 "cost_after": "" if d["cost_after"] is None else d["cost_after"], "note": d["note"], "truly_affected": truly})
with open(os.path.join(OUT_DIR, "step_04_dependencies.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(OUT_DIR, "step_04_calendar.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(res["calendar"][0]), lineterminator="\n")
    w.writeheader()
    w.writerows(res["calendar"])
summary = {"as_of": res["as_of"], "affected": len(aff), "found": len(aff & migrate), "queued": len(queued), "missed": len(missed),
           "hits": len(migrate), "false_hits": len(false_hits), "checks": len(checks), "features_opened": len(reads),
           "family_features": len({k[0] for k in family}), "cost_now": res["cost_now"], "cost_after": res["cost_after"],
           "tiers": {t: tiers[t] for t in ("PAST", "LATE", "TIGHT", "ROOM", "SUNSETS")},
           "missed_items": [{"feature_id": k[0], "role": k[1], "kind": by_key[k]["kind"], "true_model": by_key[k]["true_model_id"]} for k in sorted(missed)]}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_dependencies.csv, step_04_calendar.csv and step_04_summary.json in src/out/")
