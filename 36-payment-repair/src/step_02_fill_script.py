"""Step 2 - The common basic approach: one script fills every empty field and releases the message.

The usual first automation fills a missing value from whichever table has one, falls back to a
default when no table answers, completes the optional fields too, and releases everything. I wrote
this one script to stand for that (basic_fill in common.py); what it does wrong is a property of
this script, not of every script. It uses a seeded random generator only to invent a UETR when no
payment order has one.

Run (from src/):  python3 step_02_fill_script.py
"""
from __future__ import annotations

import random
from collections import Counter

from common import basic_fill, load_messages, load_world
from payment_repair import LABELS, OPTIONAL, PURP, REQUIRED, RMT

messages, world = load_messages(), load_world()
rng = random.Random(2)
wrote = Counter()
touched = 0
incomplete = 0
for m in messages:
    out, paths = basic_fill(m, world, rng)
    wrote.update(paths)
    touched += bool(paths)
    incomplete += any((out.get(p) or "") == "" for p in REQUIRED)

req_fills = sum(n for p, n in wrote.items() if p in REQUIRED)
opt_fills = sum(n for p, n in wrote.items() if p in OPTIONAL)
print("STEP 2 - one script fills every empty field and releases")
print(f"  Done. {len(messages)} messages released.")
print("What it actually did (counted from the messages it wrote):")
print(f"  messages it changed: {touched} of {len(messages)}")
print(f"  required fields filled: {req_fills}   optional fields filled: {opt_fills}")
for p in REQUIRED:
    if wrote[p]:
        print(f"    {LABELS[p]:<26} {wrote[p]}")
for p, label in ((PURP, "purpose code (optional)"), (RMT, "remittance text (optional)")):
    print(f"    {label:<26} {wrote[p]}")
print(f"  messages released with a required field still absent or empty: {incomplete} of {len(messages)}")
print("It finishes without an error and reports a count. Step 3 measures what the count does not say.")
