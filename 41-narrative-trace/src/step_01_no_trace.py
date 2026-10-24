"""Step 1 - Status quo: a person checks each sentence against the ledger by hand.

Forty cases, each with a ledger and a narrative that cites its transactions as [txn: ID]. Nothing in
the process looks at the citations before a reviewer does. This step counts what that reviewer faces.
The data is synthetic (data/_generate.py); the truth label of each sentence is the defect, or the
harmless variation, that was planted.

Run (from src/):  python3 step_01_no_trace.py
"""
from collections import Counter

from common import load_corpus
from narrative_trace import CITE

ledger, narratives, truth = load_corpus()
rows = [r for rs in truth.values() for r in rs]
defects = [r for r in rows if r["expected"] == "flag"]
cited = sum(1 for n in narratives for m in CITE.finditer(n["text"]) for part in m.group(1).split(",") if part.strip())
kinds = Counter(r["kind"] for r in defects)

print("STEP 1 - no trace: a reviewer checks each sentence against the ledger by hand")
print(f"  narratives: {len(narratives)}   sentences: {len(rows)}   transaction records: {len(ledger.by_id)}")
print(f"  citations a reviewer looks up by hand: {cited}")
print(f"  sentences with a planted defect: {len(defects)} of {len(rows)}")
print(f"  narratives with at least one planted defect: {len({r['case_id'] for r in defects})} of {len(narratives)}")
print("  by planted defect: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
print(f"  planted defects stopped before a reviewer reads them: 0 of {len(defects)}")
print("  The reviewer finds a wrong amount only by opening the record, one citation at a time.")
