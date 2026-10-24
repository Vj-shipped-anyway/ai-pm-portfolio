"""Step 2 - The common basic approach: look the retiring model up in the registry's model column.

A feature register usually has one model column per feature. When a notice arrives, someone filters
that column for the model id in the email. This step does exactly that over the primary model of
each feature and scores it against the planted truth.

Run (from src/):  python3 step_02_exact_match.py
"""
from common import load_truth, noticed_models, read_csv, score

truth = load_truth()
retiring = {m["model_id"].casefold() for m in noticed_models()}
flagged = {(u["feature_id"], u["role"]) for u in read_csv("usages.csv") if u["role"] == "primary" and u["model_ref"].casefold() in retiring}
s = score(flagged, truth)

print("STEP 2 - filter the primary model column for the id in the notice")
print(f"  rows flagged: {s['flagged']}; of those, truly affected: {s['found']}, not affected: {s['false']}")
print(f"  affected dependencies found: {s['found']} of {s['affected']}")
print(f"  affected dependencies not found: {s['missed']}")
print("  Every row it shows is a feature to move. The trouble is the rows it never shows.")
