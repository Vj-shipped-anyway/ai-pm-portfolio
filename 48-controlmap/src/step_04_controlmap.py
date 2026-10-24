"""Step 4 - The fix: a dictionary with a negation rule, a scope check, a freshness check and an UNMAPPED status.

This step runs the command-line tool's own analyze() on the full register and library and scores it against
the planted truth. Each rule is added in turn so the numbers show what each one earns:

  dictionary alone     any active control that contains a phrase for the theme counts, covered or not
  + negation           a phrase preceded within three words by no, not, without and the like does not count
  + scope              full, partial or none, by the classes the obligation applies to
  + freshness          newest evidence within 1.5 test cycles of the as-of date; this makes STALE
  UNMAPPED             a theme with no dictionary row is reported as such, not as a gap

The dictionary was written by the same person who wrote the data, so the scores are a ceiling for this
method, not a rate on a real library. KNOWN LIMITS, left in on purpose and printed: six controls worded
outside the dictionary, one control whose text denies a phrase it actually meets, two controls that use a
phrase in another sense.

Run (from src/):  python3 step_04_controlmap.py
Output: a report, plus out/step_04_rows.csv and out/step_04_summary.json
"""
import csv
import json
import os

from common import (load_all, sheet_links, covered_or_not, pair_scores, truth_orphans, count_by, pct, ensure_out, OUT_DIR)
from controlmap import analyze, reason, STATUSES

data = load_all()
obs, truth, kind, claimed = data["obligations"], data["truth_status"], data["kind"], data["claimed"]
grace = data["meta"]["grace"]
res = analyze(obs, data["controls"], data["terms"], grace)
raw = analyze(obs, data["controls"], data["terms"], grace, negation=False)
rows = {r["obligation_id"]: r for r in res["rows"]}
n = len(obs)
sheet = sheet_links(data)

# right status, one rule at a time
dictionary = sum(1 for r in raw["rows"] if covered_or_not(r["links"]) == truth[r["obligation_id"]])
negation = sum(1 for r in res["rows"] if covered_or_not(r["links"]) == truth[r["obligation_id"]])


def scope_only(r):
    cov = {l["coverage"] for l in r["links"]}
    return "COVERED" if "full" in cov else "PARTIAL" if "partial" in cov else "UNCOVERED"


scope = sum(1 for r in res["rows"] if scope_only(r) == truth[r["obligation_id"]])
final = sum(1 for r in res["rows"] if r["status"] == truth[r["obligation_id"]])
sheet_right = sum(1 for o in obs if covered_or_not(sheet[o["obligation_id"]]) == truth[o["obligation_id"]])
register_right = sum(1 for o in obs if covered_or_not(claimed[o["obligation_id"]]) == truth[o["obligation_id"]])

print("STEP 4 - ControlMap")
print(f"  right status: {final} of {n} ({pct(final, n)}); keyword sheet {sheet_right} of {n}; typed register column {register_right} of {n}")
print(f"  by rule: dictionary alone {dictionary}, with negation {negation}, with scope {scope}, with freshness and UNMAPPED {final}")
print("  right status by true status:")
for s in ("COVERED", "STALE", "PARTIAL", "UNCOVERED"):
    ids = [o["obligation_id"] for o in obs if truth[o["obligation_id"]] == s]
    print(f"    {s:<10} {sum(1 for i in ids if rows[i]['status'] == s)} of {len(ids)}")
wrong = [r for r in res["rows"] if r["status"] != truth[r["obligation_id"]]]
loud = sum(1 for r in wrong if r["status"] == "UNMAPPED")
print(f"  wrong status: {len(wrong)} of {n}; {loud} are UNMAPPED, which the tool says out loud, so {len(wrong) - loud} are silent")
truth_pairs = data["truth_pairs"]
causes = {}
for r in wrong:
    oid = r["obligation_id"]
    got = {l["control_id"] for l in r["links"] if l["coverage"] != "none"}
    want = {c for (o, c), cov in truth_pairs.items() if o == oid and cov != "none"}
    if r["status"] == "UNMAPPED":
        why = ["theme not in the dictionary"]
    else:
        why = (["missed " + k for k in sorted({kind[c] for c in want - got})] + ["false link " + k for k in sorted({kind[c] for c in got - want})]) or ["scope or date"]
    for w in why:
        causes[w] = causes.get(w, 0) + 1
    print(f"    {oid} {r['theme']}: truth {truth[oid]}, tool {r['status']} ({'; '.join(why)})")
print("  causes (an obligation can have more than one): " + ", ".join(f"{k} {v}" for k, v in sorted(causes.items())))

found = {(r["obligation_id"], l["control_id"]) for r in res["rows"] for l in r["links"]}
found_raw = {(r["obligation_id"], l["control_id"]) for r in raw["rows"] for l in r["links"]}
tp, n_found, n_truth = pair_scores(found, data)
print(f"  pairs: precision {pct(tp, n_found)} ({tp} of {n_found} links), recall {pct(tp, n_truth)} ({tp} of {n_truth} true pairs)")
agree = sum(1 for (o, c) in found if (o, c) in truth_pairs and next(l for l in rows[o]["links"] if l["control_id"] == c)["coverage"] == truth_pairs[(o, c)])
print(f"  full, partial or none label agrees with the truth on {agree} of {tp} true links (a shared definition, so this holds by construction)")

denied_true = sum(1 for p in truth_pairs if p in found_raw and p not in found)
final_raw = sum(1 for r in raw["rows"] if r["status"] == truth[r["obligation_id"]])
print(f"  negation rule: drops {len(found_raw - found)} links, of which {denied_true} are true pairs; right status {final} of {n} with it, {final_raw} of {n} without")

print("  hard cases the rules should miss:")
by_kind = {}
for k in sorted(set(kind.values())):
    ids = [c for c, kk in kind.items() if kk == k]
    sheet_linked = {c for v in sheet.values() for c in v} & set(ids)
    cm_linked = {c for _o, c in found} & set(ids)
    by_kind[k] = (len(ids), len(sheet_linked), len(cm_linked))
for k in ("off_dictionary", "negated_true"):
    t, s, c = by_kind[k]
    missed_pairs = sum(1 for (o, cid), cov in truth_pairs.items() if kind[cid] == k and (o, cid) not in found)
    print(f"    {k}: {t} controls, linked by ControlMap {c}, true pairs missed {missed_pairs}")
print("  hard negatives that could raise a false alarm:")
for k in ("negated_decoy", "lookalike", "orphan", "retired"):
    t, s, c = by_kind[k]
    print(f"    {k}: {t} controls, linked by the sheet {s}, linked by ControlMap {c}")
t, s, c = by_kind["wrong_sense"]
print(f"  KNOWN LIMIT wrong_sense: {t} controls, linked by the sheet {s}, linked by ControlMap {c} (false links the rules cannot see)")

true_orph = set(truth_orphans(data))
listed = set(res["orphans"])
bad_orph = count_by(kind[c] for c in listed - true_orph)
print(f"  orphan controls: {len(listed & true_orph)} of {len(true_orph)} true orphans listed; {len(listed - true_orph)} others listed wrongly ("
      + ", ".join(f"{k} {v}" for k, v in sorted(bad_orph.items())) + ")")
unmatched = res["unmatched_phrases"]
print(f"  dictionary phrases that match no active control: {len(unmatched)} of {sum(len(v) for v in data['terms'].values())}")
print(f"  evidence requests: {len(res['requests'])} controls to ask for {res['stale_obligations']} STALE obligations (one ask per control, not per obligation)")
print("  statuses: " + ", ".join(f"{s} {res['counts'][s]}" for s in STATUSES))

ensure_out()
fields = ["obligation_id", "theme", "applies_to", "statement", "truth", "register", "sheet", "controlmap", "right", "reason"]
with open(os.path.join(OUT_DIR, "step_04_rows.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in res["rows"]:
        o = r["obligation_id"]
        w.writerow({"obligation_id": o, "theme": r["theme"], "applies_to": ";".join(r["applies_to"]), "statement": r["statement"],
                    "truth": truth[o], "register": covered_or_not(claimed[o]), "sheet": covered_or_not(sheet[o]),
                    "controlmap": r["status"], "right": "yes" if r["status"] == truth[o] else "no", "reason": reason(r)})
summary = {"obligations": n, "right_controlmap": final, "right_sheet": sheet_right, "right_register": register_right,
           "wrong_unmapped": loud, "wrong": len(wrong),
           "precision": pct(tp, n_found), "recall": pct(tp, n_truth),
           "orphans_found": len(listed & true_orph), "orphans_true": len(true_orph), "orphans_wrong": len(listed - true_orph),
           "requests": len(res["requests"]), "stale": res["stale_obligations"], "counts": res["counts"],
           "by_rule": {"dictionary": dictionary, "negation": negation, "scope": scope, "freshness": final}}
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
    fh.write("\n")
print("Wrote step_04_rows.csv and step_04_summary.json in src/out/")
