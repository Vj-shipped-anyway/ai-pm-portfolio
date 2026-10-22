"""Step 4 - The same tiering with four AI-specific characteristics added.

The characteristics come from the gap map (data/guidance_map.csv, rows marked 'not mentioned'):
  concentrated_upstream     one upstream model provider carries 30% or more of its group's activity
  no_model_change_notice    the contract gives zero days' notice before a model change
  trains_on_bank_data       the vendor trains on bank data
  long_data_retention       bank data is kept 365 days or more
A vendor is HIGH under the text's examples or when any characteristic holds. KNOWN LIMIT, left in
on purpose: more flags means more false alarms, and the two material-incident vendors that stay
LOWER are printed.

Run (from src/):  python3 step_04_with_ai_fields.py
Output: a report, plus out/step_04_vendors.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import load_all, tier_text, tier_ai, indicators, upstream_shares, score, ensure_out, OUT_DIR

vendors, incidents, truth_rows, truth = load_all()
shares = upstream_shares(vendors)
high_text = {v["vendor_id"] for v in vendors if tier_text(v) == "HIGH"}
high_ai = {v["vendor_id"] for v in vendors if tier_ai(v, shares) == "HIGH"}
s0, s1 = score(high_text, truth), score(high_ai, truth)
print("STEP 4 - with AI-specific characteristics")
print(f"  vendors marked HIGH: {s1['flagged']} of {len(vendors)} (text examples alone: {s0['flagged']})")
print(f"  material-incident vendors caught: {s1['caught']} of {s1['truth']} (text examples alone: {s0['caught']})")
print(f"  false alarms: {s1['false_alarms']} (text examples alone: {s0['false_alarms']})")
print("  each characteristic added alone to the text's examples:")
for name in ("concentrated_upstream", "no_model_change_notice", "trains_on_bank_data", "long_data_retention"):
    extra = {v["vendor_id"] for v in vendors if indicators(v, shares).get(name)}
    s = score(high_text | extra, truth)
    print(f"    {name:<24} catches {s['caught']} of {s['truth']}, false alarms {s['false_alarms']}")
print("  concentration threshold sensitivity (catches, false alarms):")
import tprm_gap_map as t
for thr in (0.20, 0.30, 0.50):
    t.CONCENTRATION_HIGH = thr
    sh = t.upstream_shares(vendors)
    h = {v["vendor_id"] for v in vendors if t.tier_ai(v, sh) == "HIGH"}
    s = score(h, truth)
    print(f"    {thr:.0%}: {s['caught']} of {s['truth']}, {s['false_alarms']}")
t.CONCENTRATION_HIGH = 0.30
left = [v for v in vendors if v["vendor_id"] in truth - high_ai]
print(f"  still LOWER but had a material incident: {len(left)} of {len(truth)}")
for v in left:
    print(f"    {v['vendor_id']} {v['service_type']} share {v['activity_share_pct']}% -> {truth_rows[v['vendor_id']]['material_causes']}")

ensure_out()
cols = ["vendor_id", "service_type", "activity_share_pct", "upstream_provider", "tier_text_examples", "tier_with_ai", "material_incident", "causes"]
with open(os.path.join(OUT_DIR, "step_04_vendors.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    for v in vendors:
        w.writerow([v["vendor_id"], v["service_type"], v["activity_share_pct"], v["upstream_provider"], tier_text(v), tier_ai(v, shares),
                    "yes" if v["vendor_id"] in truth else "no", truth_rows[v["vendor_id"]]["material_causes"]])
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump({"vendors": len(vendors), "material": len(truth), "text_flagged": s0["flagged"], "text_caught": s0["caught"],
               "text_false": s0["false_alarms"], "ai_flagged": s1["flagged"], "ai_caught": s1["caught"], "ai_false": s1["false_alarms"]},
              fh, indent=1, sort_keys=True)
print("Wrote step_04_vendors.csv and step_04_summary.json in src/out/")
