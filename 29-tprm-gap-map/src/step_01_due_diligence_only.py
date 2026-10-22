"""Step 1 - Status quo: the due-diligence questionnaire and nothing else.

The proposed guidance lists what due diligence may cover: financial condition, key personnel,
legal and regulatory compliance, insurance, and information security. This step treats a vendor
as passing when it has all four documents on file (SOC report, insurance, financial condition,
key personnel). The incident log is synthetic (data/_generate.py); a vendor is high risk when it
caused at least one material incident in 36 months.

Run (from src/):  python3 step_01_due_diligence_only.py
"""
from common import load_all, passes_questionnaire

vendors, incidents, truth_rows, truth = load_all()
passing = [v for v in vendors if passes_questionnaire(v)]
ai = [v for v in vendors if v["service_type"] == "ai_enabled_service"]
ai_pass = [v for v in ai if passes_questionnaire(v)]
print("STEP 1 - questionnaire only")
print(f"  vendors: {len(vendors)}   with a material incident in 36 months: {len(truth)}")
print(f"  questionnaire passes {len(passing)} of {len(vendors)} vendors, and {sum(1 for v in passing if v['vendor_id'] in truth)} of those passes had a material incident")
print(f"  AI-enabled vendors: {len(ai)}; passing: {len(ai_pass)}; of those passing, with a material incident: {sum(1 for v in ai_pass if v['vendor_id'] in truth)}")
print("  The documents say a vendor exists and is insured. They do not say what its model does when it changes.")
