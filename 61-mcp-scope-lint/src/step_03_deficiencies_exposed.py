"""Step 3 - Where each simpler check stops, and the limit that stays.

Three checks, each a step up from the one before:
  blocklist              step 2: reject wildcard, delete and admin grants
  unused-grant report    remove a grant when no tool requires any scope it reaches
  plus narrowing         also replace a wildcard by the scopes the tools require
The truth is known, so each is scored on the same 260 reachable scopes. The full rule set (narrowing
plus the check of a tool's scopes against its own hints) is step 4.

KNOWN LIMIT, left in on purpose: the rules read hints. A tool with no hint that declares more than it
needs, a tool whose hint overstates what it needs, a tool nobody calls, and a wildcard on a tool with no hint
all pass. A tool whose read-only hint is wrong has a needed scope cut. This step prints each of them.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_servers, load_entitlement_truth, load_tool_scope_truth, score_cuts, fmt_counter, blocklist_cut
from mcp_scope_lint import propose

servers, truth, decl = load_servers(), load_entitlement_truth(), load_tool_scope_truth()


def show(name, cuts):
    s = score_cuts(cuts, truth)
    print(f"  {name}")
    print(f"    unneeded scopes cut: {s['cut_unneeded']} of {s['unneeded']}; needed scopes cut: {s['needed_cut']}")
    print(f"    unneeded scopes left: {fmt_counter(s['kept_unneeded_by'])}")
    return s


print("STEP 3 - each check alone")
show("blocklist", {m["name"]: blocklist_cut(m) for m in servers})
show("unused-grant report", {m["name"]: propose(m, narrow=False, hints=False)["cut"] for m in servers})
show("unused-grant report plus narrowing", {m["name"]: propose(m, hints=False)["cut"] for m in servers})
full = score_cuts({m["name"]: propose(m)["cut"] for m in servers}, truth)

print("KNOWN LIMIT (left in on purpose; step 4 has it too)")
print(f"  unneeded scopes the full rules leave reachable: {full['kept_unneeded']} of {full['unneeded']} ({fmt_counter(full['kept_unneeded_by'])})")
print("    overscoped_nohint: no hint, so a declared write scope on a tool that only reads looks like a need")
print("    overscoped_wrong_hint: the hint allows write, so a declared write scope is inside the tool's own limit")
print("    dead_tool: the manifest lists the tool, so its scope looks used; nobody calls it")
print("    wildcard_nohint: flagged as a warning, but with no hint there is nothing to narrow the wildcard by")
print(f"  needed scopes the full rules cut: {full['needed_cut']} ({fmt_counter(full['needed_cut_by'])})")
print("    hint_wrong_scope_right: the hint says read-only, the tool writes, the declared write scope is right")
print("  tools that declare a scope they do not need and carry no hint:")
for (server, tool, scope), (needed, planted) in sorted(decl.items()):
    if planted == "overscoped_nohint" and not needed:
        print(f"    {server} {tool} declares {scope}")
