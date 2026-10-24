"""Step 1 - Status quo: nothing repairs a message, the next hop rejects it and a person fixes it by hand.

Five hundred pacs.008-style messages arrive. Each was built complete and then damaged by a named
recipe (data/_generate.py), so the answer key knows which fields were damaged and what the true
value was. The status quo is a presence check at the next hop: a required field that is absent or
an empty string sends the message to a repair queue. This step counts what that check sends and
what it lets through.

Run (from src/):  python3 step_01_no_repair.py
"""
from __future__ import annotations

from collections import Counter

from common import load_messages, load_truth, presence_rejects

messages = load_messages()
routes, defects = load_truth()
rows = [d for ds in defects.values() for d in ds]
rejected = [m for m in messages if presence_rejects(m)]
by_kind = Counter(d["kind"] for d in rows)
caught = by_kind["missing"] + by_kind["blank"]
held_by_table = [d for d in rows if d["source_available"] != "none"]
source = Counter(d["source_available"] for d in rows)

print("STEP 1 - no repair step: the next hop rejects, a person repairs")
print(f"  messages: {len(messages)}   with at least one planted defect: {len(defects)}")
print(f"  rejected by the presence check (a required field is absent or empty): {len(rejected)} of {len(messages)}")
print(f"  planted defective fields: {len(rows)}")
print("    by kind: " + ", ".join(f"{k} {by_kind[k]}" for k in sorted(by_kind)))
print(f"    caught by the presence check (missing or blank): {caught} of {len(rows)}")
print(f"    let through as if complete (placeholder, malformed, or well-formed and wrong): {len(rows) - caught} of {len(rows)}")
print(f"  where the true value of those {len(rows)} fields can be found (the answer key):")
print("    " + ", ".join(f"{k} {source[k]}" for k in sorted(source)))
print(f"    a bank table or the message itself holds it: {len(held_by_table)} of {len(rows)}; only the originator can say: {source['none']}")
print("  Every rejected message waits for a person, whether the true value sits in a table or only the originator knows it.")
