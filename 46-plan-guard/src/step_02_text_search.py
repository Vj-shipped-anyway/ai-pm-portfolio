"""Step 2 - The common basic approach: search the plan text for known-bad strings.

A grep over the plan JSON is the first check a team adds: world CIDRs, public canned ACLs, a wildcard
principal, an explicit `false` on an encryption flag, a plain HTTP listener. A plan that matches is
flagged and a person reads it. The truth is known, so this step counts how many of those reads were
needed and which risky plans it never flags.

Run (from src/):  python3 step_02_text_search.py
"""
from collections import Counter

from common import load_plans, flagged_by_search, PATTERNS

plans = load_plans()
flag = [p for p in plans if flagged_by_search(p["plan"])]
risky = [p for p in plans if p["truth"] != "ok"]
harmless_flagged = [p for p in flag if p["truth"] == "ok"]
missed = [p for p in risky if not flagged_by_search(p["plan"])]
miss_kinds = Counter(p["kind"] for p in missed)
false_kinds = Counter(p["kind"] for p in harmless_flagged)

print("STEP 2 - search the plan text for known-bad strings")
print(f"  patterns: {len(PATTERNS)}   plans flagged: {len(flag)} of {len(plans)}")
print(f"  flagged plans that are harmless: {len(harmless_flagged)} of {len(flag)} ({len(harmless_flagged) / len(flag):.1%})")
print("    by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(false_kinds.items())))
print(f"  risky plans never flagged: {len(missed)} of {len(risky)}")
print("    by planted change: " + ", ".join(f"{k} {v}" for k, v in sorted(miss_kinds.items())))
print("  A string match cannot tell a deleted bucket from a created one, or a Deny from an Allow, and it does not see an unset flag.")
