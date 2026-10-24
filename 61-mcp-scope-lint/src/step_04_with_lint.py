"""Step 4 - The fix: the full lint and a least-privilege proposal.

Four rules read each manifest, all plain rules and no model:
  unused_grant            a granted scope that no tool requires
  wildcard_narrowable     a wildcard grant of which the tools require only part
  tool_scope_above_hint   a tool asks for more access than its own hints allow
  tool_requires_wildcard  a tool with no hint asks for a wildcard
The proposal keeps what a tool requires after the tools are cut back to their hints, narrows a wildcard
to the scopes required and removes the rest. It never adds a scope.

KNOWN LIMIT, left in on purpose: the rules read hints. This script prints what that leaves behind (an
over-asking tool with no hint, a hint that overstates, a tool nobody calls) and the needed scope cut
because a read-only hint was wrong.

Run (from src/):  python3 step_04_with_lint.py
Output: a report, plus out/step_04_servers.csv, step_04_findings.csv, step_04_changes.csv and step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import (load_servers, load_entitlement_truth, load_tool_scope_truth, score_cuts, fmt_counter,
                    ensure_out, OUT_DIR)
from mcp_scope_lint import lint, propose, members

servers, truth, decl = load_servers(), load_entitlement_truth(), load_tool_scope_truth()
reports = {m["name"]: lint(m) for m in servers}
proposals = {m["name"]: propose(m) for m in servers}

kinds = Counter(f["kind"] for r in reports.values() for f in r["findings"])
errors = sum(1 for r in reports.values() for f in r["findings"] if f["severity"] == "error")
warns = sum(1 for r in reports.values() for f in r["findings"] if f["severity"] == "warn")
reach_before = sum(p["reach_before"] for p in proposals.values())
reach_after = sum(p["reach_after"] for p in proposals.values())
manifest_unneeded = sum(r["unneeded"] for r in reports.values())
score = score_cuts({name: p["cut"] for name, p in proposals.items()}, truth)

# declared tool scopes the proposal removes or swaps, scored against the generator's truth
removed = {(m["name"], c["tool"], s) for m in servers for c in proposals[m["name"]]["tool_changes"] for s in c["from"] if s not in c["to"]}
decl_unneeded = sum(1 for needed, _p in decl.values() if not needed)
removed_unneeded = sum(1 for k in removed if not decl[k][0])
removed_needed = sorted(k for k in removed if decl[k][0])
emptied = sum(len(p["tools_emptied"]) for p in proposals.values())

# hard negatives: findings that touch a grant or a tool that was built to look risky and is needed
hard = ("wildcard_fully_used", "multi_resource_reader", "legit_admin")
touched, population = Counter(), Counter()
for label in hard:
    population[label] = len({(s, t) for (s, t, _sc), (_n, p) in decl.items() if p == label})
for m in servers:
    for f in reports[m["name"]]["findings"]:
        if f["tool"]:
            labels = {decl[(m["name"], f["tool"], f["scope"])][1]}
        else:
            labels = {truth[m["name"]][s][1] for s in members(m, f["scope"])}
        for label in hard:
            if label in labels:
                touched[label] += 1

print("STEP 4 - the lint and the least-privilege proposal")
print(f"  manifests linted: {len(servers)}; findings: {errors} errors, {warns} warnings ({fmt_counter(kinds)})")
print(f"  scopes no tool requires, as the manifests show them: {manifest_unneeded} of {reach_before} ({100.0 * manifest_unneeded / reach_before:.1f}%)")
print(f"  reachable scopes: {reach_before} before, {reach_after} after the proposal ({100.0 * (reach_before - reach_after) / reach_before:.1f}% cut)")
print(f"  unneeded scopes cut: {score['cut_unneeded']} of {score['unneeded']} (generator truth)")
print(f"  declared tool scopes cut back: {removed_unneeded} of {decl_unneeded} unneeded ones, {len(removed_needed)} needed ones")
print(f"  tools left with no scope by the proposal: {emptied}")
print("  hard negatives (built to look risky, and needed): findings raised")
for label in hard:
    print(f"    {label}: {touched[label]} findings on {population[label]} tools")
print("KNOWN LIMIT (left in on purpose)")
print(f"  unneeded scopes still reachable: {score['kept_unneeded']} of {score['unneeded']} ({fmt_counter(score['kept_unneeded_by'])})")
print(f"  needed scopes cut: {score['needed_cut']} ({fmt_counter(score['needed_cut_by'])})")
for server, tool, scope in removed_needed:
    print(f"    {server} {tool}: the hint says read-only, the scope `{scope}` is needed and the proposal removes it")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_servers.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["server", "tools", "granted", "reach_before", "reach_after", "breadth_pct", "errors", "warnings", "unneeded_truth", "unneeded_cut", "needed_cut"])
    for m in servers:
        r, p, rows = reports[m["name"]], proposals[m["name"]], truth[m["name"]]
        w.writerow([m["name"], r["tools"], r["granted"], r["reach"], p["reach_after"], r["breadth"],
                    sum(1 for f in r["findings"] if f["severity"] == "error"), sum(1 for f in r["findings"] if f["severity"] == "warn"),
                    sum(1 for n, _p in rows.values() if not n), sum(1 for s in p["cut"] if not rows[s][0]), sum(1 for s in p["cut"] if rows[s][0])])
with open(os.path.join(OUT_DIR, "step_04_findings.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["server", "severity", "kind", "tool", "scope", "message"])
    for m in servers:
        for f in reports[m["name"]]["findings"]:
            w.writerow([m["name"], f["severity"], f["kind"], f["tool"], f["scope"], f["message"]])
with open(os.path.join(OUT_DIR, "step_04_changes.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["server", "level", "subject", "action", "detail"])
    for m in servers:
        p = proposals[m["name"]]
        for g in p["grants"]:
            w.writerow([m["name"], "grant", g["scope"], g["action"], ", ".join(g["to"]) if g["action"] == "narrow" else ""])
        for c in p["tool_changes"]:
            w.writerow([m["name"], "tool", c["tool"], "change", ", ".join(c["from"]) + " -> " + (", ".join(c["to"]) or "(nothing)")])
summary = {"manifests": len(servers), "errors": errors, "warnings": warns, "reach_before": reach_before, "reach_after": reach_after,
           "manifest_unneeded": manifest_unneeded, "truth_unneeded": score["unneeded"], "unneeded_cut": score["cut_unneeded"],
           "unneeded_kept": score["kept_unneeded"], "needed_cut": score["needed_cut"], "declared_unneeded": decl_unneeded,
           "declared_unneeded_cut": removed_unneeded, "declared_needed_cut": len(removed_needed), "tools_emptied": emptied,
           "hard_negative_findings": {label: touched[label] for label in hard}}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_servers.csv, step_04_findings.csv, step_04_changes.csv and step_04_summary.json in src/out/")
