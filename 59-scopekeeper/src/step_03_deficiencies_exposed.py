"""Step 3 - Where the basic approaches fail.

Two things are scored against the generator's truth (data/needed_truth.csv):

  A. A log-count report, the step teams take after the annual review: flag a grant when none of the
     scopes it reaches was called under the holder's own agent tag. A group grant counts as used
     when any member was called.
  B. The call-count threshold. Treat a grant with one or two calls as noise (a smoke test, a
     mistake) and the report gets stricter. The same knob also hits needed grants that are rarely
     called. The diff in src/scopekeeper.py takes it as --min-calls.

KNOWN LIMIT, left in on purpose: a grant used once a quarter shows no call in a 90-day log. Every
approach in this step flags it, and step 4 does not fix it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_world, analyze, effective_by_agent, reach_of, replay

w = load_world()
grants, calls, groups, agents, needed = w["grants"], w["calls"], w["groups"], w["agents"], w["needed"]
unneeded = {k for k, v in needed.items() if not v["needed"]}
periodic = {k for k, v in needed.items() if v["basis"] == "quarterly_cycle"}
stray = {k for k, v in needed.items() if v["basis"] == "stray_use"}

# A. log-count report: own-tag calls only
tagged = {(c["agent_id"], c["scope"]) for c in calls if c["agent_id"]}
flagged = {(g["agent_id"], g["scope"]) for g in grants
           if not any((g["agent_id"], m) in tagged for m in reach_of(g["scope"], groups))}
left = [g for g in grants if (g["agent_id"], g["scope"]) not in flagged]
denied = len(replay(calls, effective_by_agent(left, groups), agents))
false_alarms = flagged - unneeded
via_untagged = false_alarms - periodic
whole_groups = [g for g in grants if g["scope"] in groups and (g["agent_id"], g["scope"]) not in flagged
                and any((g["agent_id"], m) not in tagged for m in groups[g["scope"]])]
left_over = sum(1 for g in whole_groups for m in groups[g["scope"]] if (g["agent_id"], m) not in tagged)

print("STEP 3 - where the basic approaches fail")
print("  A. log-count report (own agent tag only; a group counts as used when any member was called)")
print(f"    grants flagged as unused: {len(flagged)} of {len(grants)}")
print(f"    of those, not needed: {len(flagged & unneeded)} of {len(unneeded)} unneeded grants")
print(f"    of those, needed (false alarms): {len(false_alarms)}; used once a quarter: {len(false_alarms & periodic)}; "
      f"used only through calls with no agent tag: {len(via_untagged)}")
print(f"    calls the flagged removals would deny: {denied} of {len(calls)}")
print(f"    group grants kept whole although the agent calls only some members: {len(whole_groups)}; "
      f"entitlements left under them that nobody calls: {left_over}")
print("  B. the call-count threshold (the diff's --min-calls)")
for k in (1, 2, 3):
    res = analyze(grants, calls, groups, agents, min_calls=k)
    removed = {(r["agent_id"], r["scope"]) for r in res["grants"] if r["action"] == "remove"}
    print(f"    {k} call{'s' if k > 1 else ''} to count as used: unneeded removed {len(removed & unneeded)} of {len(unneeded)}; "
          f"stray-use grants removed {len(removed & stray)} of {len(stray)}; "
          f"needed grants removed (quarterly excluded) {len(removed - unneeded - periodic)}; "
          f"calls newly denied {res['summary']['newly_denied']}")
print("  A stricter threshold removes the grants a smoke test touched. It also removes needed grants that are called rarely.")
base = analyze(grants, calls, groups, agents)
periodic_removed = {(r["agent_id"], r["scope"]) for r in base["grants"] if r["action"] == "remove"} & periodic
print("  KNOWN LIMIT (left in on purpose)")
print(f"    {len(periodic)} grants are legitimate and used once a quarter, so the 90-day log shows no call for them.")
print(f"    The log-count report flags {len(flagged & periodic)} of {len(periodic)}; the diff with --min-calls 1 removes {len(periodic_removed)} of {len(periodic)}.")
print("    A longer log would see them. A log of the same length cannot.")
