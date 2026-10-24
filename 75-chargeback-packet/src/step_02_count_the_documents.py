"""Step 2 - The common basic approach: does the packet look thick enough?

The check most teams add first is one rule for every dispute: the packet needs the order record (or
the billing history, for a subscription) and at least two other documents. It is quick, it needs no
reason-code table, and it feels like a control. The truth label is known, so this step scores it.

Run (from src/):  python3 step_02_count_the_documents.py
"""
from collections import Counter

from common import load_cases

items = load_cases()
ANCHORS = ("order_record", "billing_history")


def looks_thick(case) -> bool:
    types = [d["doc_type"] for d in case["docs"]]
    return any(t in ANCHORS for t in types) and len(types) >= 3


for it in items:
    it["sent"] = looks_thick(it["case"])

ready = [it for it in items if it["truth"] == "ready"]
faulty = [it for it in items if it["truth"] != "ready"]
sent_faulty = [it for it in faulty if it["sent"]]
held_ready = [it for it in ready if not it["sent"]]
needless = Counter(it["kind"] for it in held_ready)

print("STEP 2 - count the documents")
print(f"  packets held back: {sum(1 for it in items if not it['sent'])} of {len(items)}")
print(f"  faulty packets sent anyway: {len(sent_faulty)} of {len(faulty)}")
print(f"  ready packets held back: {len(held_ready)} of {len(ready)}")
print("  held back although ready, by planted case: " + (", ".join(f"{k} {v}" for k, v in sorted(needless.items())) or "none"))
print(f"  late packets it passes: {sum(1 for it in items if it['truth'] == 'late' and it['sent'])} of {sum(1 for it in items if it['truth'] == 'late')}")
print("  A count cannot tell a missing delivery proof from a missing optional message, and it never reads a date.")
