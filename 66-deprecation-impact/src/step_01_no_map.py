"""Step 1 - Status quo: a retirement notice names a model, and nothing maps it to features.

Sixty features call seventeen model snapshots. The vendor notices that matter arrive by email, one
model at a time. This step reads the planted truth (data/truth_dependencies.csv), not the registry,
to show what the notices cover and how much time they leave. The data is synthetic
(data/_generate.py); the as-of date is fixed so the day counts do not drift.

Run (from src/):  python3 step_01_no_map.py
"""
import datetime
import statistics
from collections import Counter

from common import DEMO_AS_OF, load_truth, noticed_models

truth = load_truth()
aff = [r for r in truth if r["affected"] == "yes"]
notices = noticed_models()
warning = sorted((datetime.date.fromisoformat(m["retire_date"]) - datetime.date.fromisoformat(m["notice_date"])).days for m in notices)
retired = [m for m in notices if m["retire_date"] < DEMO_AS_OF]
failing = [r for r in aff if r["true_retire_date"] < DEMO_AS_OF]
roles = Counter(r["role"] for r in aff)

print("STEP 1 - a notice names a model, not a feature")
print(f"  as of {DEMO_AS_OF}: {len(notices)} retirement notices, {len(retired)} already past their retirement date")
print(f"  vendor warning, notice to retirement: {warning[0]} to {warning[-1]} days, median {statistics.median(warning):g}")
print(f"  dependencies on a retiring model while the feature is still running: {len(aff)} in {len({r['feature_id'] for r in aff})} of {len({r['feature_id'] for r in truth})} features")
print(f"  by role: {roles['primary']} primary, {roles['fallback']} fallback, {roles['judge']} judge")
print(f"  monthly calls on those dependencies: {sum(int(r['monthly_calls']) for r in aff):,}")
print(f"  dependencies whose model is already retired, so calls fail now: {len(failing)}")
print("  Nobody holds a list of which feature calls which snapshot, so each notice starts a search.")
