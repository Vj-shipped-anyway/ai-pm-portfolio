"""Step 2 - The characteristics the proposed text itself names.

The text's examples of relationships likely to be higher risk are core processing providers and
services that support essential functions (cloud processing, cloud storage, compliance tools),
plus fintech partners; a limited share of the business points lower. This step marks a vendor
HIGH when it is one of those service types or carries 30% of activity or more.

Run (from src/):  python3 step_02_text_examples.py
"""
from common import load_all, tier_text, score

vendors, incidents, truth_rows, truth = load_all()
high = {v["vendor_id"] for v in vendors if tier_text(v) == "HIGH"}
s = score(high, truth)
missed = [v for v in vendors if v["vendor_id"] in truth - high]
print("STEP 2 - the text's own examples")
print(f"  vendors marked HIGH: {s['flagged']} of {len(vendors)}")
print(f"  material-incident vendors caught: {s['caught']} of {s['truth']}")
print(f"  missed: {s['missed']} ({sum(1 for v in missed if v['service_type'] == 'ai_enabled_service')} are AI-enabled services)")
print(f"  false alarms: {s['false_alarms']}")
