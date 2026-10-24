"""Step 4 - The fix: field-level scoring by layout, an error taxonomy and a drift gate.

Every value is scored against the truth, grouped by an explicit layout field. The gate fails a layout
that sits under a floor or too far under the best layout (both limits are assumptions of this
project). The tie-out check stays as a monitor for unlabeled traffic, with its limit stated.

KNOWN LIMIT, still open after this step: a labeled sample is the only thing that sees an error that
keeps the identities true. The tie-out check passes it (see step 3 and the last lines below).

Run (from src/):  python3 step_04_layout_scorer.py
Output: a report, plus out/step_04_results.json and out/step_04_summary.json
"""
from common import (EXTRACTORS, evaluate_on, gate_on, layouts_with_split, load_corpus, pct, predictions_for, write_json)
from spread_eval import ERROR_CLASSES

docs, truth = load_corpus()
dev, holdout = layouts_with_split(docs, "dev"), layouts_with_split(docs, "holdout")
everything = sorted(dev + holdout)
res = {name: evaluate_on(docs, truth, predictions_for(fn, docs)) for name, fn in sorted(EXTRACTORS.items())}
gates = {name: {"dev": gate_on(r, dev), "all": gate_on(r, everything)} for name, r in res.items()}

print("STEP 4 - field-level scoring by layout, with a gate (floor 95.0%, max gap 3.0 points, at least 10 documents)")
for name in sorted(res):
    for scope, label in (("dev", f"the {len(dev)} development layouts"), ("all", f"all {len(everything)} layouts")):
        g = gates[name][scope]
        print(f"  {name} on {label}: {g['verdict']}")
        for reason in g["reasons"]:
            print(f"    {reason}")

good = res["alias_aware"]
print("  alias_aware, the held-out layout:")
h = good["layouts"][holdout[0]]
weakest = sorted(((pct(c, n), f) for f, (n, c) in h["fields"].items()))
bad = [(a, f) for a, f in weakest if a < 100.0]
print(f"    {holdout[0]}: {len(bad)} of {len(h['fields'])} fields fall below 100.0%: " + ", ".join(f"{f} {a:.1f}%" for a, f in bad))
print("    wrong values by class: " + ", ".join(f"{c} {h['errors'][c]}" for c in ERROR_CLASSES if h["errors"][c]))

# Hard negatives: valid statements with a negative value (a loss, a deficit) in the development layouts.
neg_docs = {k[0] for k, v in truth.items() if v < 0}
dev_neg = sorted(d["doc_id"] for d in docs if d["layout"] in dev and d["doc_id"] in neg_docs)
keep = set(dev_neg)
sub = evaluate_on([d for d in docs if d["doc_id"] in keep], truth, predictions_for(EXTRACTORS["alias_aware"], docs), dev)
print(f"  hard negatives, alias_aware: {sub['documents']} development documents with a negative value (loss or deficit); "
      f"{sub['documents'] - sub['wrong_documents']} read with every field right; tie-out false alarms {sub['right_flagged']}")
weak_res = res["fixed_label"]
print("  KNOWN LIMIT, unchanged: the tie-out check on fixed_label passes "
      f"{weak_res['wrong_unflagged']} of {weak_res['wrong_documents']} documents that have a wrong value")
print(f"  tie-out on alias_aware: {good['wrong_unflagged']} of {good['wrong_documents']} "
      f"wrong documents pass every identity; false alarms on right documents {good['right_flagged']} of {good['documents'] - good['wrong_documents']}")

summary = {
    "alias_aware_dev_verdict": gates["alias_aware"]["dev"]["verdict"], "alias_aware_all_verdict": gates["alias_aware"]["all"]["verdict"],
    "fixed_label_all_verdict": gates["fixed_label"]["all"]["verdict"],
    "alias_aware_pooled": pct(good["correct"], good["values"]), "fixed_label_pooled": pct(weak_res["correct"], weak_res["values"]),
    "alias_aware_layout": {n: pct(s["correct"], s["values"]) for n, s in good["layouts"].items()},
    "fixed_label_layout": {n: pct(s["correct"], s["values"]) for n, s in weak_res["layouts"].items()},
    "hard_negative_documents": sub["documents"], "hard_negative_wrong": sub["wrong_documents"], "hard_negative_false_alarms": sub["right_flagged"],
    "fixed_label_wrong_unflagged": weak_res["wrong_unflagged"], "fixed_label_wrong_documents": weak_res["wrong_documents"],
}
write_json("step_04_summary.json", summary)
write_json("step_04_results.json", {"development": dev, "holdout": holdout, "extractors": res, "gates": gates})
