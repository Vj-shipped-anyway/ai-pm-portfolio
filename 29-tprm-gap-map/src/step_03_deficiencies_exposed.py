"""Step 3 - What the text's examples miss, and why.

For the vendors the text's examples miss, this step lists the cause of each material incident from
the log, and then looks at what the vendors share: an upstream model provider. KNOWN LIMIT, left in
on purpose: the log is simulated from hazard rates I chose, so the causes show how the method reads
a log, not how often real vendors fail.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_all, tier_text, upstream_shares, passes_questionnaire

vendors, incidents, truth_rows, truth = load_all()
high = {v["vendor_id"] for v in vendors if tier_text(v) == "HIGH"}
missed = [v for v in vendors if v["vendor_id"] in truth - high]
causes = Counter(c for v in missed for c in truth_rows[v["vendor_id"]]["material_causes"].split(";"))
print("STEP 3 - the vendors the text's examples miss")
print(f"  missed: {len(missed)} of {len(truth)} material-incident vendors; of those, passing the step 1 questionnaire: {sum(1 for v in missed if passes_questionnaire(v))}")
print("  causes among the missed: " + ", ".join(f"{k} {n}" for k, n in sorted(causes.items())))
for v in missed:
    print(f"    {v['vendor_id']} {v['service_type']} share {v['activity_share_pct']}% upstream {v['upstream_provider'] or '-'} "
          f"notice {v['model_change_notice_days']} -> {truth_rows[v['vendor_id']]['material_causes']}")
shares = upstream_shares(vendors)
ai = [v for v in vendors if v["service_type"] == "ai_enabled_service"]
top = max((k for k in shares if k.startswith("P")), key=lambda k: shares[k])
on_top = [v for v in ai if v["upstream_provider"] == top]
print(f"  one upstream model provider ({top}) carries {shares[top]:.1%} of AI-enabled activity across {len(on_top)} of {len(ai)} AI-enabled vendors")
on_top_ids = {v["vendor_id"] for v in on_top}
reached = {}
for r in incidents:
    if r["cause"] == "upstream_outage" and r["vendor_id"] in on_top_ids:
        reached.setdefault(r["month"], {})[r["vendor_id"]] = r["material"]
if reached:
    m = max(reached, key=lambda k: (sum(1 for x in reached[k].values() if x == 'yes'), len(reached[k])))
    print(f"  in month {m}, an outage at {top} reached {len(reached[m])} of its {len(on_top)} vendors at once; "
          f"{sum(1 for x in reached[m].values() if x == 'yes')} of them took a material hit")
print("  The text covers concentration inside one third party. Several vendors sharing one provider is not named.")
