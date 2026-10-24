"""Step 4 - The fix: plant. A seed, planted behaviors, and a separate answer key.

src/plant.py reads data/demo_spec.json and writes the data, a key (one line per planted row: behavior,
role, the exact change) and a manifest. Failures have role positive; look-alikes, which a careless rule
would flag, have role negative. Rows not in the key are clean by construction. The counts are exact, so
the denominators do not move between seeds.

Both rule sets from step 1 are scored on the same key.

KNOWN LIMIT, left in on purpose: the key measures the variants I planted. The paraphrased injection uses
three sentences; a checker that memorizes them scores full marks. The script prints that.

Run (from src/):  python3 step_04_with_a_key.py
Output: a report, plus out/step_04_rows.csv and out/step_04_summary.json for the demo page
"""
import csv
import json
import os

from common import LEVELS, OUT_DIR, build, demo_spec, flag_rows, score

spec = demo_spec()
res = build(spec)
m = res["manifest"]
rows, truth = res["rows"], res["truth"]
by_id = {t["row_id"]: t for t in truth}
fails = sum(1 for t in truth if t["role"] == "positive")
flags = {lvl: flag_rows(rows, lvl) for lvl in LEVELS}
sc = {lvl: score(truth, m["rows"], set(flags[lvl])) for lvl in LEVELS}

print("STEP 4 - plant: a seed, planted behaviors, a separate key")
print(f"  spec {m['name']} seed {m['seed']}: {m['rows']} rows, {m['planted_rows']} in the key ({fails} failures, {m['planted_rows'] - fails} look-alikes), {sc['naive']['clean']} clean by construction")
same = build(spec)["manifest"]["data_sha256"] == m["data_sha256"]
other = build(dict(spec, seed=spec["seed"] + 1))["manifest"]["data_sha256"] != m["data_sha256"]
print(f"  rerun with the same seed gives identical bytes: {'yes' if same else 'no'}; seed {spec['seed'] + 1} gives different bytes: {'yes' if other else 'no'}")
extra = set(rows[0]) - {c["name"] for c in spec["columns"]} - {"row_id"}
print(f"  columns in the data file: {len(rows[0])}; label columns among them: {len(extra)} (the key is a separate file)")
print(f"  {'behavior':<28} {'role':<9} {'planted':>7} {'naive':>6} {'tuned':>6}")
for a, b in zip(sc["naive"]["behaviors"], sc["tuned"]["behaviors"]):
    print(f"  {a['behavior']:<28} {a['role']:<9} {a['planted']:>7} {a['flagged']:>6} {b['flagged']:>6}")
for lvl in LEVELS:
    s = sc[lvl]
    print(f"  {lvl}: found {s['found']} of {s['positives']} failures (recall {s['recall']:.2f}); look-alikes flagged {s['look_alikes_flagged']} of {s['look_alikes']}; "
          f"clean rows flagged {s['clean_flagged']} of {s['clean']}; precision {s['precision']:.2f}")
n = sc["naive"]
print(f"  naive precision with the look-alikes taken out of the file: {n['found'] / (n['flagged'] - n['look_alikes_flagged']):.2f} (with them: {n['precision']:.2f})")
print(f"  one rule change, same key: recall {n['recall']:.2f} -> {sc['tuned']['recall']:.2f}, precision {n['precision']:.2f} -> {sc['tuned']['precision']:.2f}")
clean_hits = [i for i in flags["tuned"] if i not in by_id]
merchants = sorted({rows[i - 1]["merchant"] for i in clean_hits})
print(f"  clean rows the tuned rules flag: {len(clean_hits)}, all in merchant {', '.join(merchants)}")
missed = [e for e in sc["tuned"]["behaviors"] if e["role"] == "positive" and e["flagged"] < e["planted"]]
print("  failures the tuned rules miss: " + (", ".join(f"{e['behavior']} {e['planted'] - e['flagged']}" for e in missed) or "none"))

# the same spec under five seeds: the denominators are fixed, so recall moves little
recall = {lvl: [] for lvl in LEVELS}
planted = set()
for k in range(5):
    r = build(dict(spec, seed=spec["seed"] + k))
    for lvl in LEVELS:
        one = score(r["truth"], r["manifest"]["rows"], set(flag_rows(r["rows"], lvl)))
        recall[lvl].append(one["recall"])
        planted.add(one["positives"])
print(f"  same spec under seeds {spec['seed']} to {spec['seed'] + 4}: failures planted in each: {', '.join(str(p) for p in sorted(planted))}; "
      + "; ".join(f"{lvl} recall {min(recall[lvl]):.2f} to {max(recall[lvl]):.2f}" for lvl in LEVELS))

# known limit: the key covers the variants that were planted
variants = {b["id"]: b["distinct_effects"] for b in m["behaviors"] if b["role"] == "positive"}
print("  distinct changes planted per failure: " + ", ".join(f"{k} {v}" for k, v in sorted(variants.items())))
memo = {rows[t["row_id"] - 1]["memo"] for t in truth if t["behavior"] == "memo_injection_paraphrase"}
memorizer = {r["row_id"] for r in rows if r["memo"] in memo}
mem = next(e for e in score(truth, m["rows"], memorizer)["behaviors"] if e["behavior"] == "memo_injection_paraphrase")
print(f"KNOWN LIMIT: a checker that only memorizes the {len(memo)} planted paraphrase sentences finds {mem['flagged']} of {mem['planted']}. The key scores the variants I planted, not the ones people write.")

# files for the demo page: every planted row, plus every clean row either rule set flagged
def outcome(role, flagged):
    if role == "positive":
        return "found" if flagged else "missed"
    if role == "negative":
        return "look-alike flagged" if flagged else "look-alike left alone"
    return "clean row flagged" if flagged else "clean"


keep = sorted(set(by_id) | set(flags["naive"]) | set(flags["tuned"]))
fields = ["row_id", "ref", "merchant", "amount", "day", "posted_day", "memo", "behavior", "role", "naive", "tuned"]
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, "step_04_rows.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for i in keep:
        t, r = by_id.get(i), rows[i - 1]
        role = t["role"] if t else "clean"
        w.writerow({"row_id": i, "ref": r["ref"], "merchant": r["merchant"], "amount": r["amount"], "day": r["day"], "posted_day": r["posted_day"],
                    "memo": r["memo"], "behavior": t["behavior"] if t else "", "role": role,
                    "naive": outcome(role, i in flags["naive"]), "tuned": outcome(role, i in flags["tuned"])})
summary = {"rows": m["rows"], "key_rows": m["planted_rows"], "failures": fails, "seed": m["seed"],
           "behaviors": [{"behavior": a["behavior"], "role": a["role"], "planted": a["planted"], "naive": a["flagged"], "tuned": b["flagged"]}
                         for a, b in zip(sc["naive"]["behaviors"], sc["tuned"]["behaviors"])],
           "checkers": {lvl: {k: sc[lvl][k] for k in ("found", "positives", "look_alikes_flagged", "look_alikes", "clean_flagged", "clean", "flagged")}
                        for lvl in LEVELS}}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_rows.csv and step_04_summary.json in src/out/")
