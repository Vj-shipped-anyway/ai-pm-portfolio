"""Step 4 - The fix: replay the full pack on the old and the new rules and fail on any regression.

The pack has 100 attack cases across five channels (the largest group is retrieved documents, the
indirect path) and 60 benign cases, many of them written to look like attacks. For each pull
request the check runs the pack on the base rules and on the new rules and fails when a case the
base rules got right is now wrong: an attack that used to be blocked and is allowed, or a benign
case that used to be allowed and is blocked. This is `injection_pack.py compare`, the command the
GitHub Action in action/ wraps.

KNOWN LIMIT, left in on purpose: the pack does not contain an attack technique that is in the
held-out population (an encoded payload with a decode cue). A change that only affects that
technique passes. The tool cannot block it, but it does print a blind-spot note when no pack case
matches a rule that changed; this script says how many of the misses came with that note.

Run (from src/):  python3 step_04_with_pack.py
Output: a report, plus out/step_04_decisions.csv and out/step_04_summary.json
"""
import csv
import os
from collections import Counter

from common import load_world, score_prs, pack_decisions, tally, write_json, ensure_out, OUT_DIR

world = load_world()
rows = score_prs(world)
dec = pack_decisions(world, world["pack"])
decisions = {k: v[0] for k, v in dec.items()}
t = tally(rows, decisions)
pack_techniques = Counter(c["technique"] for c in world["pack"])

out_rows = []
for r in rows:
    d, n, blind = dec[r["pr_id"]]
    out_rows.append({"pr_id": r["pr_id"], "kind": r["kind"], "layer": r["layer"], "note": r["note"], "lost": r["lost"], "gained": r["gained"],
                     "truth": "harmful" if r["harmful"] else "harmless", "decision": d, "pack_regressions": n, "blind_spot_note": "yes" if blind else "no"})
missed = [r for r in rows if r["harmful"] and decisions[r["pr_id"]] == "ALLOW"]
false_alarms = [r for r in rows if not r["harmful"] and decisions[r["pr_id"]] == "BLOCK"]
by_type = {ty: [r for r in rows if r["harmful"] and r["harm_type"] == ty] for ty in ("catch", "false_blocks", "both")}
caught_type = {ty: sum(1 for r in rs if decisions[r["pr_id"]] == "BLOCK") for ty, rs in by_type.items()}
warned = sum(1 for r in missed if dec[r["pr_id"]][2])

print("STEP 4 - full pack, case-by-case comparison")
print(f"  harmful pull requests stopped: {t['harmful_blocked']} of {t['harmful']}")
print(f"    that lose attack coverage: {caught_type['catch']} of {len(by_type['catch'])}")
print(f"    that add false blocks: {caught_type['false_blocks']} of {len(by_type['false_blocks'])}")
print(f"    that do both: {caught_type['both']} of {len(by_type['both'])}")
print(f"  harmless pull requests stopped: {t['harmless_blocked']} of {t['harmless']}")
print(f"  decision matches the held-out truth: {t['exact']} of {len(rows)}")
print(f"  harmful pull requests that still pass: {len(missed)} of {t['harmful']}")
for r in missed:
    techs = ", ".join(f"{k} {v:+d} (pack cases: {pack_techniques[k]})" for k, v in sorted(r["delta"].items(), key=lambda kv: (abs(kv[1]) * -1, kv[0]))[:3])
    print(f"    {r['pr_id']} {r['note']}: held-out change, attacks blocked {-r['lost']:+d}, benign blocked {r['gained']:+d}; {techs}")
print(f"  of those, the tool printed a blind-spot note for: {warned} of {len(missed)}")
print(f"  harmless pull requests it stopped (false alarms): {len(false_alarms)} of {t['harmless']}")
for r in false_alarms:
    print(f"    {r['pr_id']} {r['note']}: held-out change, attacks blocked {-r['lost']:+d}, benign blocked {r['gained']:+d}")
print("  held-out attack techniques with no pack case: " + (", ".join(sorted(k for k in {c['technique'] for c in world['population'] if c['expected'] == 'block'} if not pack_techniques[k])) or "none"))

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_decisions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(out_rows)
write_json("step_04_summary.json", {"harmful": t["harmful"], "harmful_stopped": t["harmful_blocked"], "harmless": t["harmless"],
                                    "harmless_stopped": t["harmless_blocked"], "exact": t["exact"], "pull_requests": len(rows),
                                    "missed": len(missed), "missed_with_note": warned, "false_alarms": len(false_alarms)})
print("Wrote step_04_decisions.csv and step_04_summary.json in src/out/")
