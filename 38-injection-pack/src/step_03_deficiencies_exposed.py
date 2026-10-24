"""Step 3 - Where a pack-based gate fails when it is built the easy way.

Three gates, each one a shortcut:
  floor only      run the full pack on the new rules and fail when the catch rate or the false-block
                  rate crosses a fixed line (the line is the base rate, five points of slack either way)
  attacks only    compare old and new rules case by case, but keep only the attack cases
  thin pack       compare old and new rules case by case on every fourth case of the pack

Each is scored on the same fifty-one pull requests against the held-out truth from step 1.

KNOWN LIMIT, left in on purpose: a change that only touches an attack technique the pack does not
contain passes all three of these, and it still passes step 4. The script prints those changes.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
from common import load_world, score_prs, pack_decisions, tally, build_gateway, run_pack, summarize, write_json
from injection_pack import floor_problems

world = load_world()
rows = score_prs(world)
pack = world["pack"]
base_sum = summarize(run_pack(build_gateway(world["base"]), pack))
min_catch = 100.0 * base_sum["caught"] / base_sum["attacks"] - 5
max_fp = 100.0 * base_sum["false_blocks"] / base_sum["benign"] + 5


def floor_decision(pr: dict) -> str:
    s = summarize(run_pack(build_gateway(pr["rules"]), pack))
    return "BLOCK" if floor_problems(s, min_catch, max_fp) else "ALLOW"


gates = {
    "floor only": {pr["pr_id"]: floor_decision(pr) for pr in world["prs"]},
    "attacks only": {k: v[0] for k, v in pack_decisions(world, [c for c in pack if c["expected"] == "block"]).items()},
    "thin pack (every 4th case)": {k: v[0] for k, v in pack_decisions(world, pack[::4]).items()},
}
tallies = {name: tally(rows, d) for name, d in gates.items()}

print("STEP 3 - each shortcut gate alone")
print(f"  floors used: catch at least {min_catch:.1f} percent, false blocks at most {max_fp:.1f} percent")
for name, t in tallies.items():
    print(f"  {name}")
    print(f"    harmful stopped: {t['harmful_blocked']} of {t['harmful']}")
    print(f"    harmless stopped: {t['harmless_blocked']} of {t['harmless']}")
fp_only = [r for r in rows if r["harmful"] and r["harm_type"] == "false_blocks"]
print(f"  harmful pull requests that add false blocks and no attack loss: {len(fp_only)} of {tallies['floor only']['harmful']}; "
      f"attacks only stops {sum(1 for r in fp_only if gates['attacks only'][r['pr_id']] == 'BLOCK')} of them")
passed_all = [r for r in rows if r["harmful"] and all(d[r["pr_id"]] == "ALLOW" for d in gates.values())]
print(f"  harmful pull requests that pass all three gates: {len(passed_all)} of {tallies['floor only']['harmful']}")
for r in passed_all:
    print(f"    {r['pr_id']} {r['kind']}: {r['note']}")
print("  A floor hides a small loss under a big total; an attacks-only pack cannot see a new false block;")
print("  a thin pack misses the changes that touch the few cases it dropped.")

write_json("step_03_summary.json", {"floor_catch": round(min_catch, 1), "floor_fp": round(max_fp, 1),
                                    "gates": tallies, "passed_all": len(passed_all)})
