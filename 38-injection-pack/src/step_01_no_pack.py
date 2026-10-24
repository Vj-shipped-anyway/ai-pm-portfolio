"""Step 1 - Status quo: nobody runs injection tests when the gateway rules change.

The gateway is a set of rules in five layers. Fifty-one pull requests each change those rules: a
rule removed, a pattern narrowed or widened, a domain added to the allow-list, a cosmetic edit.
Today a reviewer reads the diff. This step merges all fifty-one in turn and measures what each one
does to a held-out population of 1,000 attacks and 500 benign cases (data/population.csv), which
stands in for real traffic and which the test pack never sees. Truth is defined on that
population: a change is harmful when it lowers the share of attacks blocked, or raises the share of
benign cases blocked, by at least one percentage point (an assumption; common.HARM_POINTS).

The data is synthetic (data/_generate.py).

Run (from src/):  python3 step_01_no_pack.py
"""
from collections import Counter

from common import load_world, score_prs, build_gateway, run_pack, summarize, write_json

world = load_world()
base = build_gateway(world["base"])
pop = summarize(run_pack(base, world["population"]))
pack = summarize(run_pack(base, world["pack"]))
rows = score_prs(world)
harmful = [r for r in rows if r["harmful"]]
types = Counter(r["harm_type"] for r in harmful)
worst = max(rows, key=lambda r: (r["lost"], r["gained"]))

print("STEP 1 - no pack in CI")
print(f"  base gateway on the held-out population: {pop['caught']} of {pop['attacks']} attacks blocked, "
      f"{pop['false_blocks']} of {pop['benign']} benign cases blocked")
print(f"  base gateway on the {len(world['pack'])}-case pack: {pack['caught']} of {pack['attacks']} attacks blocked, "
      f"{pack['false_blocks']} of {pack['benign']} benign cases blocked")
print(f"    hard attacks (written to slip past ordinary rules): {pack['hard_caught']} of {pack['hard_attacks']} blocked")
print(f"    hard benign cases (written to look like attacks): {pack['hard_false_blocks']} of {pack['hard_benign']} blocked")
print(f"  rule pull requests: {len(rows)}")
print(f"  harmful on the held-out population: {len(harmful)} of {len(rows)} "
      f"({types['catch']} lose attack coverage, {types['false_blocks']} add false blocks, {types['both']} do both)")
print(f"  harmless: {len(rows) - len(harmful)} of {len(rows)}")
print(f"  pull requests the current CI stops: 0 of {len(rows)}")
print(f"  harmful pull requests that merge: {len(harmful)} of {len(rows)}")
print(f"  worst single change: {worst['pr_id']} ({worst['note']}) lets through {worst['lost']} more of {pop['attacks']} attacks")
print("  A reviewer reading a regex diff cannot tell which of these moves the numbers.")

write_json("step_01_summary.json", {"pop_caught": pop["caught"], "pop_attacks": pop["attacks"], "pop_false_blocks": pop["false_blocks"],
                                    "pop_benign": pop["benign"], "pack_caught": pack["caught"], "pack_attacks": pack["attacks"],
                                    "pack_false_blocks": pack["false_blocks"], "pack_benign": pack["benign"],
                                    "hard_attacks": pack["hard_attacks"], "hard_caught": pack["hard_caught"],
                                    "hard_benign": pack["hard_benign"], "hard_false_blocks": pack["hard_false_blocks"],
                                    "prs": len(rows), "harmful": len(harmful)})
