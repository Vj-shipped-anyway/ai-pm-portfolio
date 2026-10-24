"""Step 1 - Status quo: the question set most teams start with asks what the policy says.

A policy owner writes a golden set of plain-rule questions ("What is the maximum loan term for X?") and
an assistant is released when it answers them. This step runs that set, 30 plain-rule questions over three
synthetic manuals of 50, 150 and 300 pages, and then runs the same four readers on the exception questions
that set never contains. The readers are stubs with known faults (src/common.py), not models.

Run (from src/):  python3 step_01_plain_rule_questions.py
"""
import csv
import os

from common import DATA, READERS, load_manuals, load_sweep, run_reader
from credit_policy_needle import score_probes

probes, manuals = load_sweep(), load_manuals()
plain = [p for p in probes if p["form"] == "plain"]
asked_about_exception = [p for p in probes if p["form"] != "plain"]
with open(os.path.join(DATA, "exceptions_truth.csv"), newline="", encoding="utf-8") as fh:
    truth = list(csv.DictReader(fh))
exception_ids = {(r["manual_id"], r["block_id"]) for r in truth if r["is_exception"] == "1"}
touched = {(p["manual_id"], p["base_id"]) for p in plain} & exception_ids

print("STEP 1 - the plain-rule question set")
print(f"  manuals: {len(manuals)}   plain-rule questions: {len(plain)}   exception questions it does not contain: {len(asked_about_exception)}")
print(f"  exception clauses planted in the manuals: {len(exception_ids)}   touched by a plain-rule question: {len(touched)}")
print(f"  {'reader':<12}{'plain-rule set':>16}{'exception questions':>22}")
rows = {}
for name in READERS:
    answers = run_reader(name, probes, manuals)
    a = score_probes(plain, answers)["passed"]
    b = score_probes(asked_about_exception, answers)["passed"]
    rows[name] = (a, b)
    print(f"  {name:<12}{a:>10} of {len(plain)}{b:>16} of {len(asked_about_exception)}")
faulty = [n for n in READERS if n != "control"]
caught = [n for n in faulty if rows[n][0] < len(plain)]
slipped = [n for n in faulty if rows[n][0] == len(plain) and rows[n][1] < len(asked_about_exception)]
print(f"  faulty readers the plain-rule set catches: {len(caught)} of {len(faulty)} ({', '.join(caught) or 'none'})")
print(f"  faulty readers that pass it and still fail exception questions: {len(slipped)} of {len(faulty)} ({', '.join(slipped) or 'none'})")
print("  A reader that never opens an exception looks the same as one that does, until someone asks about the exception.")
