"""Step 1 - The status quo: a pilot on the one layout the extractor was written against.

fixed_label was written by reading statements in plain_two_column. The pilot checks it on 20 of them,
finds every value right, and reports one number. Nothing in the pilot says what happens on a layout
it has not seen.

Run (from src/):  python3 step_01_pilot_only.py
"""
from common import EXTRACTORS, evaluate_on, load_corpus, pct, predictions_for, write_json

PILOT = "plain_two_column"

docs, truth = load_corpus()
preds = predictions_for(EXTRACTORS["fixed_label"], docs)
res = evaluate_on(docs, truth, preds, [PILOT])
pilot = res["layouts"][PILOT]
layouts = sorted({d["layout"] for d in docs})
others = [d for d in docs if d["layout"] != PILOT]

print("STEP 1 - a pilot on one layout")
print(f"  pilot sample: {PILOT}, {pilot['docs']} documents, {pilot['values']} values")
print(f"  fixed_label: {pilot['correct']} of {pilot['values']} values correct ({pct(pilot['correct'], pilot['values']):.1f}%), "
      f"{pilot['docs_all_right']} of {pilot['docs']} documents with every field right")
print(f"  layouts in the corpus: {len(layouts)}; layouts the pilot saw: 1")
print(f"  documents the pilot never touched: {len(others)} of {len(docs)} ({pct(len(others), len(docs)):.1f}%)")
write_json("step_01_pilot.json", {"pilot_layout": PILOT, "pilot_accuracy": pct(pilot["correct"], pilot["values"]),
                                  "untouched_documents": len(others), "documents": len(docs), "layouts": len(layouts)})
