"""Step 2 - The common basic approach: a blocklist of risky-looking grants.

The usual first control on a scope list is a rule that rejects what looks dangerous: every wildcard
grant and every grant of delete or admin access. It reads the `access` field of the catalog and never
looks at the tools. This step applies it to the thirty manifests, removes the flagged grants and scores the
result against the generator's truth.

Run (from src/):  python3 step_02_blocklist.py
"""
from common import load_servers, load_entitlement_truth, score_cuts, fmt_counter, total_reach, blocklist_cut, RISKY_ACCESS

servers, truth = load_servers(), load_entitlement_truth()
grants = sum(len(m["granted"]) for m in servers)
flagged = sum(1 for m in servers for g in m["granted"] if m["by_id"][g]["access"] in RISKY_ACCESS)
s = score_cuts({m["name"]: blocklist_cut(m) for m in servers}, truth)

print("STEP 2 - blocklist: reject every wildcard, delete and admin grant")
print(f"  grants flagged and removed: {flagged} of {grants}")
print(f"  scopes reached: {total_reach(servers)}; cut by the blocklist: {s['cut_unneeded'] + s['needed_cut']}")
print(f"  unneeded scopes cut: {s['cut_unneeded']} of {s['unneeded']}")
print(f"  needed scopes cut: {s['needed_cut']} ({fmt_counter(s['needed_cut_by'])})")
print(f"  unneeded scopes still reachable: {s['kept_unneeded']} of {s['unneeded']}")
print("  The rule looks at the access level of a grant, not at what the tools use, so it cuts a wildcard every tool uses along with one a single tool uses.")
