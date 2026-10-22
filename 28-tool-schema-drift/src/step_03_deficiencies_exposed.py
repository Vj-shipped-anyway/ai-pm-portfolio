"""Step 3 - Where each half fails when used alone.

Two gates, each with one idea:
  replay only       run recorded calls against the new schema and block when any fails
  structure only    classify the schema change and block on a breaking one, with no description check
                    and no replay

The truth is known, so each gate is scored on the same sixty pull requests. KNOWN LIMIT, left in on
purpose: a change in meaning with no number and no unit ("exclusive of the end date") is caught by
neither gate, and step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_cases, calls_by_tool, replay_counts, diff_schemas
from collections import Counter

cases, calls = load_cases(), calls_by_tool()
broken = replay_counts(cases, calls)


def structure_only(c) -> str:
    fs = [f for f in diff_schemas(c["old"], c["new"], use_heuristic=False) if f["kind"] != "unit_or_number_changed"]
    cls = {f["class"] for f in fs}
    return "BLOCK" if "breaking" in cls else "REVIEW" if "behavior_risk" in cls else "ALLOW"


def score(name, decide):
    got = {c["pr_id"]: decide(c) for c in cases}
    b = [c for c in cases if c["truth"] == "breaking"]
    r = [c for c in cases if c["truth"] == "behavior_risk"]
    n = [c for c in cases if c["truth"] == "non_breaking"]
    print(f"  {name}")
    print(f"    breaking blocked: {sum(1 for c in b if got[c['pr_id']] == 'BLOCK')} of {len(b)}")
    print(f"    behavior-risk flagged (REVIEW or BLOCK): {sum(1 for c in r if got[c['pr_id']] != 'ALLOW')} of {len(r)}")
    print(f"    harmless pull requests blocked: {sum(1 for c in n if got[c['pr_id']] == 'BLOCK')} of {len(n)}")
    return got


print("STEP 3 - each gate alone")
by_replay = score("replay only", lambda c: "BLOCK" if broken[c["pr_id"]] > 0 else "ALLOW")
by_struct = score("structure only", structure_only)
missed = [c for c in cases if c["truth"] == "behavior_risk" and by_replay[c["pr_id"]] == "ALLOW" and by_struct[c["pr_id"]] == "ALLOW"]
print(f"  behavior-risk pull requests that pass both gates: {len(missed)} of {sum(1 for c in cases if c['truth'] == 'behavior_risk')}")
print("  by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(c['kind'] for c in missed).items())))
# Replay is only as good as the calls you recorded. Keep 3 calls per tool instead of 40.
thin = {tool: v[:3] for tool, v in calls.items()}
thin_broken = replay_counts(cases, thin)
b = [c for c in cases if c["truth"] == "breaking"]
print(f"  replay with only 3 recorded calls per tool: breaking blocked {sum(1 for c in b if thin_broken[c['pr_id']] > 0)} of {len(b)}")
print(f"  structure only does not depend on the recorded calls: {sum(1 for c in b if by_struct[c['pr_id']] == 'BLOCK')} of {len(b)}")
print("  Replay cannot see a change that leaves every recorded call valid; structure alone cannot see a unit swap.")
