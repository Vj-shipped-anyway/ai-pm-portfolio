"""Step 3 - Where a parser and rules still fail when built the obvious way.

Two gates, each one idea short of step 4:
  state scan      the ten rules over every resource in the plan, whatever its action
  known values    the rules over created and updated resources only, but a value the plan does not
                  know yet is treated as fine

The truth is known, so each gate is scored on the same 86 plans. KNOWN LIMIT, left in on purpose: nine
risky plans pass every gate here and in step 4, because the rules read exact CIDRs, exact policy
conditions and a fixed list of resource types.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from collections import Counter

from common import load_plans, check_plan, decide, flagged_by_search, HARD_MISS_KINDS

plans = load_plans()


def score(name, **options):
    got = {p["plan_id"]: decide(check_plan(p["plan"], **options)["findings"]) for p in plans}
    b = [p for p in plans if p["truth"] == "block"]
    r = [p for p in plans if p["truth"] == "review"]
    n = [p for p in plans if p["truth"] == "ok"]
    print(f"  {name}")
    print(f"    risky plans blocked: {sum(1 for p in b if got[p['plan_id']] == 'BLOCK')} of {len(b)}")
    print(f"    plans that need a look, flagged (REVIEW or BLOCK): {sum(1 for p in r if got[p['plan_id']] != 'ALLOW')} of {len(r)}")
    print(f"    harmless plans blocked: {sum(1 for p in n if got[p['plan_id']] == 'BLOCK')} of {len(n)}")
    return got


print("STEP 3 - each gate one idea short")
scan = score("state scan (ignores the action)", changed_only=False)
blocked_harmless = Counter(p["kind"] for p in plans if p["truth"] == "ok" and scan[p["plan_id"]] == "BLOCK")
print("    harmless plans blocked, by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(blocked_harmless.items())))
known = score("known values only (unknowns pass)", flag_unknown=False)
silent = Counter(p["kind"] for p in plans if p["truth"] == "review" and known[p["plan_id"]] == "ALLOW")
print("    plans that need a look and pass silently, by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(silent.items())))
both = [p for p in plans if p["truth"] == "block" and scan[p["plan_id"]] != "BLOCK" and known[p["plan_id"]] != "BLOCK"]
print(f"  risky plans that neither gate blocks: {len(both)} of {sum(1 for p in plans if p['truth'] == 'block')}")
print("    by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(p['kind'] for p in both).items())))
hard = [p for p in plans if p["kind"] in HARD_MISS_KINDS]
print(f"  of those {len(hard)}, the step 2 text search flags {sum(1 for p in hard if flagged_by_search(p['plan']))}")
print("  Acting on the plan's own action and on its unknown marks is what separates step 4 from a scanner pointed at the plan text.")
