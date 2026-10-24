"""Step 1 - Status quo: nobody compares the grants with the calls.

A modeled bank runs 14 agents that call tools through scopes. Scopes are granted at launch and added
for one-off tasks, and some grants are groups such as accounts:* that stand for several scopes. Calls
are logged, but on a service account that several agents share the agent tag is logged on half the
calls only. This step describes the starting point and counts what the generator knows: which grants
the agent does not need. The data is synthetic (data/_generate.py).

Run (from src/):  python3 step_01_no_comparison.py
"""
from collections import Counter

from common import load_world, effective_by_agent

w = load_world()
grants, calls, groups, agents = w["grants"], w["calls"], w["groups"], w["agents"]
eff = effective_by_agent(grants, groups)
per_sa = Counter(agents.values())
shared = {sa for sa, n in per_sa.items() if n > 1}
untagged = [c for c in calls if not c["agent_id"]]
n_groups = sum(1 for g in grants if g["scope"] in groups)
entitlements = sum(len(v) for v in eff.values())
unneeded = [k for k, v in w["needed"].items() if not v["needed"]]
needed_scopes = {(a, s) for (a, _), v in w["needed"].items() if v["needed"] for s in v["needed_scopes"]}
ent_unneeded = entitlements - len(needed_scopes)

print("STEP 1 - the grants and the calls are never compared")
print(f"  agents: {len(agents)} on {len(per_sa)} service accounts; {sum(per_sa[sa] for sa in shared)} agents share {len(shared)} of them")
print(f"  grants: {len(grants)}, of which {n_groups} are group grants that each reach several scopes")
print(f"  effective entitlements (groups expanded): {entitlements}")
print(f"  calls in the log: {len(calls)} over {max(c['day'] for c in calls)} days")
print(f"  calls with no agent tag: {len(untagged)} ({len(untagged) / len(calls):.1%}); "
      f"on a service account with one agent: {sum(1 for c in untagged if c['service_account'] not in shared)}")
print(f"  grants with no ticket reference: {sum(1 for g in grants if not g['ticket_id'])}")
print(f"  truth (data/needed_truth.csv): {len(unneeded)} of {len(grants)} grants are not needed ({len(unneeded) / len(grants):.1%})")
print(f"  truth: {len(w['periodic'])} grants are needed but used once a quarter, so a 90-day log never shows them")
print(f"  truth: {ent_unneeded} of {entitlements} entitlements are not needed")
print(f"  grants checked against calls today: 0 of {len(grants)}")
print("  The access list shows names, dates and tickets. A grant nobody has used looks the same as one used every day.")
