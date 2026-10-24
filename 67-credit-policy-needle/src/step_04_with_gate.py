"""Step 4 - The fix: audit the exception clauses, then gate the sweep.

credit_policy_needle.py does two things, and this step runs both on the synthetic manuals:
  1. audit: list the clauses that read as exceptions and say which do not name the rule they change.
     It is scored against the planted truth in data/exceptions_truth.csv, which the generator wrote
     without using the audit's cue words.
  2. score and gate: score each reader's answers to the 210 questions, flag the form x length x depth
     cells that fail, and print PASS or FAIL. The cells each faulty reader should fail are worked out
     from the planted offsets (common.oracle_fails) and compared with the cells the gate flags.

KNOWN LIMITS, left in on purpose and printed below: an exception worded as a restated limit has no cue
word and is not listed; a pointer that says "except" is listed though it is not an exception; and the
step 3 limit (right answer, exception never read) stays.

Run (from src/):  python3 step_04_with_gate.py
Output: a report, plus out/step_04_cells.csv and out/step_04_summary.json
"""
import csv
import json
import os
from collections import Counter

from common import DATA, OUT_DIR, READERS, READER_NOTE, ensure_out, load_manuals, load_sweep, oracle_fails, run_reader
from credit_policy_needle import audit_text, gate, score_probes

probes, manuals = load_sweep(), load_manuals()
with open(os.path.join(DATA, "exceptions_truth.csv"), newline="", encoding="utf-8") as fh:
    truth = list(csv.DictReader(fh))
kind_of = {(r["manual_id"], r["block_id"]): r["kind"] for r in truth}
is_exc = {k for r in truth for k in [(r["manual_id"], r["block_id"])] if r["is_exception"] == "1"}
NO_NAME = {"crossref", "restated", "register", "carve_out"}   # exception clauses that do not name their rule, by construction

flagged, unnamed = set(), set()
for mid, text in manuals.items():
    for f in audit_text(text)["flagged"]:
        flagged.add((mid, f["id"]))
        if f["relation"] in ("unnamed", "missing"):
            unnamed.add((mid, f["id"]))
decoys = {k for k in kind_of if k not in is_exc}
hit, miss, false_alarm = flagged & is_exc, is_exc - flagged, flagged & decoys
left_alone = decoys - flagged
no_name_truth = {k for k in is_exc if kind_of[k] in NO_NAME}

print("STEP 4 - audit the exception clauses, then gate the sweep")
print(f"  audit: {len(is_exc)} exception clauses planted, {len(decoys)} look-alikes that are not exceptions")
print(f"    exception clauses listed: {len(hit)} of {len(is_exc)}; missed: {len(miss)} ({', '.join(f'{k} {v}' for k, v in sorted(Counter(kind_of[m] for m in miss).items())) or 'none'})")
print(f"    look-alikes listed by mistake: {len(false_alarm)} of {len(decoys)} ({', '.join(f'{k} {v}' for k, v in sorted(Counter(kind_of[m] for m in false_alarm).items())) or 'none'});"
      f" left alone: {len(left_alone)} ({', '.join(f'{k} {v}' for k, v in sorted(Counter(kind_of[m] for m in left_alone).items()))})")
print(f"    exception clauses that do not name their rule: {len(no_name_truth)}; the audit lists {len(no_name_truth & unnamed)} of them as not named")

print(f"  gate: {len(probes)} questions, four readers")
print(f"    {'reader':<12}{'pass':>12}{'cells flagged':>16}{'known-fault cells':>20}{'other flags':>13}  gate")
cells_out, summary = [], {"readers": {}}
for name in READERS:
    answers = run_reader(name, probes, manuals)
    res = score_probes(probes, answers)
    decision, reasons = gate(res)
    flagged_cells = set(res["flagged"])
    should_fail = {(p["form"], p["length_pages"], p["depth_pct"]) for p in probes if oracle_fails(name, p)}
    both = flagged_cells & should_fail
    print(f"    {name:<12}{res['passed']:>7} of {res['total']}{len(flagged_cells):>10} of {len(res['cells'])}"
          f"{len(both):>14} of {len(should_fail)}{len(flagged_cells - should_fail):>13}  {decision}")
    for (form, pages, depth), (a, b) in sorted(res["cells"].items()):
        cells_out.append({"reader": name, "form": form, "length_pages": pages, "depth_pct": depth, "passed": a, "total": b})
    forms = sorted({c[0] for c in flagged_cells})
    summary["readers"][name] = {"passed": res["passed"], "total": res["total"], "cells_flagged": len(flagged_cells),
                                "cells": len(res["cells"]), "gate": decision, "reasons": len(reasons), "fault": READER_NOTE[name],
                                "flagged_forms": forms}
    if name != "control":
        print(f"      flagged forms: {', '.join(forms)}")
control = summary["readers"]["control"]
faulty = [n for n in READERS if n != "control"]
failed = [n for n in faulty if summary["readers"][n]["gate"] == "FAIL"]
print(f"  faulty readers the gate fails: {len(failed)} of {len(faulty)}; control: {control['gate']} with {control['cells_flagged']} cells flagged")

print("  KNOWN LIMITS")
print(f"    restated limits carry no cue word, so the audit misses {len([m for m in miss if kind_of[m] == 'restated'])} of {len([k for k in is_exc if kind_of[k] == 'restated'])}")
print(f"    pointers such as 'cite clause X, except for files closed with no decision' read as exceptions: {len(false_alarm)} false alarms")
print("    a reader that never opens an exception still passes every question where the exception does not apply (step 3)")

ensure_out()
with open(os.path.join(OUT_DIR, "step_04_cells.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(cells_out[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(cells_out)
summary["audit"] = {"exceptions": len(is_exc), "listed": len(hit), "missed": len(miss), "look_alikes": len(decoys),
                    "false_alarms": len(false_alarm), "no_name": len(no_name_truth), "no_name_listed": len(no_name_truth & unnamed)}
summary["probes"] = len(probes)
summary["manuals"] = sorted({p["length_pages"] for p in probes})
with open(os.path.join(OUT_DIR, "step_04_summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=1, sort_keys=True)
print("Wrote step_04_cells.csv and step_04_summary.json in src/out/")
