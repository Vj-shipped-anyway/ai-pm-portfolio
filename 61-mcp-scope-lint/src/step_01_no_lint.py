"""Step 1 - Status quo: nothing compares the scopes a manifest grants with what its tools ask for.

Thirty synthetic MCP server manifests each grant a set of scopes and list the tools behind them. The
review today reads the list of scope names and approves it. This step describes that starting point:
how many scopes the grants reach once wildcards are expanded, how many of those the generator marks as not
needed, and how many tools carry a hint a check could use. The truth file is the generator's, not a rule's.

Run (from src/):  python3 step_01_no_lint.py
"""
from common import load_servers, load_entitlement_truth, total_reach
from mcp_scope_lint import lint

servers, truth = load_servers(), load_entitlement_truth()
tools = sum(len(m["tools"]) for m in servers)
grants = sum(len(m["granted"]) for m in servers)
wildcards = sum(1 for m in servers for g in m["granted"] if m["by_id"][g]["access"] == "any")
reach_n = total_reach(servers)
unneeded = sum(1 for rows in truth.values() for needed, _p in rows.values() if not needed)
reports = [lint(m) for m in servers]
unjudged = sum(len(r["unjudged"]) for r in reports)
with_slack = sum(1 for r in reports if r["unneeded"] > 0)

print("STEP 1 - no scope lint on the manifests")
print(f"  manifests: {len(servers)}   tools: {tools}   granted scopes: {grants} ({wildcards} are wildcards)")
print(f"  scopes the grants reach, wildcards expanded: {reach_n}")
print(f"  scopes the generator marks as not needed: {unneeded} of {reach_n} ({100.0 * unneeded / reach_n:.1f}%)")
print(f"  tools whose hints would let a check compare them with their scopes: {tools - unjudged} of {tools}")
print(f"  manifests that grant a scope no tool asks for: {with_slack} of {len(servers)}")
print("  The review approves the list of names. Nothing reads the tools against the grant.")
