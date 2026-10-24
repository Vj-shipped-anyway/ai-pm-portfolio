"""Step 3 - What the pooled number hides.

Four checks on alias_aware, the extractor that scored best in step 2, and one on fixed_label:
  1. accuracy by layout against the pooled number
  2. the same extractor under different mixes of incoming layouts
  3. how often a small random audit sample contains no statement of the weakest layout
  4. documents where every field is right, against fields right

KNOWN LIMIT, left in on purpose: the tie-out check cannot see an error that keeps the accounting
identities true. fixed_label reads a statement printed in thousands with the columns swapped and the
scale ignored; both columns still add up, so the check passes it. Step 4 does not close this.

Run (from src/):  python3 step_03_deficiencies_exposed.py
"""
import random

from common import EXTRACTORS, evaluate_on, layout_accuracy, layouts_with_split, load_corpus, pct, predictions_for, write_json

docs, truth = load_corpus()
good = evaluate_on(docs, truth, predictions_for(EXTRACTORS["alias_aware"], docs))
weak = evaluate_on(docs, truth, predictions_for(EXTRACTORS["fixed_label"], docs))
acc = layout_accuracy(good)
worst = min(sorted(acc), key=lambda n: acc[n])
best = max(sorted(acc), key=lambda n: acc[n])
holdout = layouts_with_split(docs, "holdout")[0]

print("STEP 3 - what one pooled number hides")
print(f"  alias_aware pooled: {pct(good['correct'], good['values']):.1f}%")
print(f"  alias_aware by layout: best {acc[best]:.1f}% ({best}), worst {acc[worst]:.1f}% ({worst}), spread {acc[best] - acc[worst]:.1f} points")

mixes = {}
for share in (5, 30, 60):
    w = {n: (100 - share) / (len(acc) - 1) if n != holdout else float(share) for n in acc}
    mixes[f"{holdout} {share}%"] = round(sum(w[n] * acc[n] for n in acc) / 100, 1)
mixes["even over six layouts"] = round(sum(acc.values()) / len(acc), 1)
print("  the same extractor under different mixes of incoming statements (assumed shares, pooled accuracy):")
for label in sorted(mixes, key=lambda m: -mixes[m]):
    print(f"    {label:<28} {mixes[label]:.1f}%")

rng = random.Random(77)
ids = sorted(d["doc_id"] for d in docs)
held = {d["doc_id"] for d in docs if d["layout"] == holdout}
draws, size = 1000, 10
empty = sum(1 for _ in range(draws) if not held & set(rng.sample(ids, size)))
print(f"  a random audit of {size} documents holds no {holdout} statement in {empty} of {draws} draws")
print(f"  documents with every field right: {sum(s['docs_all_right'] for s in good['layouts'].values())} of {good['documents']} "
      f"({pct(sum(s['docs_all_right'] for s in good['layouts'].values()), good['documents']):.1f}%), against {pct(good['correct'], good['values']):.1f}% of fields")

print("  KNOWN LIMIT - the tie-out check on fixed_label:")
print(f"    documents with a wrong value: {weak['wrong_documents']} of {weak['documents']}; "
      f"{weak['wrong_unflagged']} of them pass every accounting identity")
for n in sorted(weak["layouts"]):
    if weak["layouts"][n]["wrong_unflagged"]:
        print(f"    {n}: {weak['layouts'][n]['wrong_unflagged']} of {weak['layouts'][n]['docs']} documents read wrong and tie out")
write_json("step_03_hidden.json", {"mixes": mixes, "audit_empty": empty, "audit_draws": draws,
                                   "wrong_unflagged": weak["wrong_unflagged"], "wrong_documents": weak["wrong_documents"]})
