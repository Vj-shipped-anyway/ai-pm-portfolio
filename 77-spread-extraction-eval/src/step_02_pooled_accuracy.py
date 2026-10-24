"""Step 2 - The common basic approach: one pooled field accuracy on a mixed, labelled sample.

After the pilot, the team scores every extractor on all 120 statements at once and reads one number.
alias_aware was written after reading the errors fixed_label made on the other layouts. A tie-out
check (do the extracted figures obey the accounting identities) is added as a cheap production monitor.

Run (from src/):  python3 step_02_pooled_accuracy.py
"""
from common import EXTRACTORS, evaluate_on, load_corpus, pct, predictions_for, write_json

docs, truth = load_corpus()
results = {name: evaluate_on(docs, truth, predictions_for(fn, docs)) for name, fn in sorted(EXTRACTORS.items())}

print("STEP 2 - one pooled number")
for name, r in results.items():
    print(f"  {name}: {pct(r['correct'], r['values']):.1f}% pooled field accuracy ({r['correct']} of {r['values']} values, {r['documents']} documents)")
a, b = results["fixed_label"], results["alias_aware"]
print(f"  pooled gain from fixed_label to alias_aware: {pct(b['correct'], b['values']) - pct(a['correct'], a['values']):.1f} points")
print(f"  tie-out check on alias_aware: flags {b['tie_flagged']} of {b['documents']} documents")
write_json("step_02_pooled.json", {n: {"pooled": pct(r["correct"], r["values"]), "tie_flagged": r["tie_flagged"]} for n, r in results.items()})
