"""Step 3 - What each rule adds, what the account-default rule costs, and the miss no rule can see.

The allocation rules are switched on one at a time and each set is scored against the planted owner
of every line: correct (the spend landed on the owner), wrong (it landed on another cost center) and
left (the tool refused and a person must decide). KNOWN LIMIT, left in on purpose: a valid tag that
names the wrong cost center. Every rule sees an active cost center, so the line is allocated, the
tag compliance check passes it, and step 4 does not catch it either.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_world, allocate, score, line_compliance, fmt_usd, pct, EXTRAS

w = load_world()
bill, policy, registry, accounts, truth = w["bill"], w["policy"], w["registry"], w["accounts"], w["truth"]
total = sum(b["usd"] for b in bill)

SETS = [("exact tag only", frozenset(), False),
        ("+ alias and format repair", frozenset(), True),
        ("+ inherit from the same resource", frozenset({"inherit"}), True),
        ("+ account default", frozenset({"inherit", "account_default"}), True),
        ("+ shared split (the tool)", EXTRAS, True)]

print("STEP 3 - each rule alone, then together")
print(f"  {'rule set':<34}{'correct':>22}{'wrong':>20}{'left for a person':>24}")
for name, extras, repair in SETS:
    s = score(bill, allocate(bill, policy, registry, accounts, extras, repair), truth)
    print(f"  {name:<34}{fmt_usd(s['correct']) + ' ' + pct(s['correct'], total):>22}{fmt_usd(s['wrong']) + ' ' + pct(s['wrong'], total):>20}"
          f"{fmt_usd(s['left']) + ' ' + pct(s['left'], total):>24}")

results = allocate(bill, policy, registry, accounts)
s = score(bill, results, truth)
default_usd = sum(r["usd"] for r in results if r["rule"] == "account_default")
default_wrong = s["wrong_by_rule"].get("account_default", 0)
print("  wrong spend in the full tool, by the rule that placed it: "
      + ", ".join(f"{k} {fmt_usd(v)}" for k, v in sorted(s["wrong_by_rule"].items())))
print(f"  account default placed {fmt_usd(default_usd)}; {fmt_usd(default_wrong)} ({pct(default_wrong, default_usd)}) of it belongs to another team")

limit_lines = [i for i, b in enumerate(bill) if truth[b["line_id"]]["defect"] == "wrong_valid"]
limit_usd = sum(bill[i]["usd"] for i in limit_lines)
limit_pass = sum(1 for i in limit_lines if line_compliance(bill[i], policy, registry, False))
print(f"  KNOWN LIMIT: {len(limit_lines)} lines ({fmt_usd(limit_usd)}) carry a valid tag for the wrong cost center.")
print(f"    The tool charges {s['by_defect']['wrong_valid']['n_wrong']} of {len(limit_lines)} to that tag, and {limit_pass} of {len(limit_lines)} pass the tag compliance check.")
print("    Only a person who knows the application can catch this; a tag check cannot.")
