"""Step 1 - Status quo: nothing in CI looks at the tool schema.

Sixty pull requests each change one tool schema. The unit tests pass on all of them, because the
tests exercise the code behind the tool, not the schema the agent was told. This step merges all
sixty in turn and replays the 400 recorded calls against each new schema, to show what the agent
would have met. The data is synthetic (data/_generate.py), and the truth label of each pull
request is the change that was planted.

Run (from src/):  python3 step_01_no_gate.py
"""
from common import load_cases, calls_by_tool, replay_counts, TRUTH_TO_DECISION
from collections import Counter

cases, calls = load_cases(), calls_by_tool()
broken = replay_counts(cases, calls)
total_calls = sum(len(v) for v in calls.values())
truth = Counter(c["truth"] for c in cases)
breaks_any = sum(1 for c in cases if broken[c["pr_id"]] > 0)
calls_broken = sum(broken.values())
pairs = sum(len(calls.get(c["tool"], [])) for c in cases)
risk_silent = sum(1 for c in cases if c["truth"] == "behavior_risk" and broken[c["pr_id"]] == 0)

print("STEP 1 - no schema gate in CI")
print(f"  pull requests merged: {len(cases)}   recorded calls: {total_calls}")
print(f"  truth: {truth['breaking']} breaking, {truth['behavior_risk']} behavior-risk, {truth['non_breaking']} non-breaking")
print(f"  pull requests the current CI stops: 0 of {len(cases)}")
print(f"  pull requests that break at least one recorded call: {breaks_any} of {len(cases)}")
print(f"  failing (recorded call, pull request) pairs: {calls_broken} of {pairs}")
print(f"  behavior-risk pull requests that break no recorded call: {risk_silent} of {truth['behavior_risk']}")
print("  The agent finds out from failed calls in production, or not at all for the behavior-risk changes.")
