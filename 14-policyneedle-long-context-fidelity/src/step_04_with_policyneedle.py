"""Step 4 - The fix: PolicyNeedle, the full sweep, fault localization, a CI-style gate.

Runs 270 probes (6 forms x 5 depths x 3 lengths x 3 per cell) through the four STUB
readers, then:

  1. audits the probe set (each question must match exactly the blocks it was built around)
  2. builds the per-slice pass matrix
  3. localizes each fault: which form, which length, which depth, and what kind of wrong answer
  4. applies a CI-style gate with thresholds
  5. measures harness validity: does it flag every known fault slice and stay quiet on the control
  6. computes the catch rates behind the utility number
  7. prints the known limit: exact-match scoring on synthetic wording

Every reader here is a STUB, not a model. The validity numbers describe this harness against
stubs with known faults. They say nothing about how it would do on a real model.

Run (from src/):
    python3 step_04_with_policyneedle.py

Output: tables on screen and src/out/step_04_*.csv / .json.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import harness as h

OUT_DIR = Path(__file__).resolve().parent / "out"
ASSISTANTS_PER_YEAR = 8            # modeled assumption, see README (range 4-12)
ASSISTANTS_RANGE = (4, 12)
STUBS = ["truncating", "first_match", "last_match"]
SINGLE_NEEDLE = ("plain", 50)      # what step 2 tests: form, depth


def verbose_control(document_text: str, question: str) -> str:
    """STUB. The control's correct answer wrapped in a sentence. Used only to show the exact-match limit."""
    a = h.full_scan_control(document_text, question)
    return "According to the manual, the answer is {}.".format(a) if a else ""


def merged_localization(cells: dict, rk: str, form: str) -> str:
    per = [h.localize(cells, rk, form, L) for L in h.LENGTHS]
    if len(set(per)) == 1:
        return "{} at every length".format(per[0]) if per[0] != "none" else "none"
    return " | ".join("{}pp: {}".format(L, d) for L, d in zip(h.LENGTHS, per))


def boundary_bracket(cells: dict, probes: list, rk: str, form: str, length: int) -> tuple:
    """Character range the pass/fail staircase puts the reader's limit in: (last passing evidence end, first failing evidence start of end)."""
    passing = [d for d in h.DEPTHS if cells[(rk, form, length, d)][0] == cells[(rk, form, length, d)][1]]
    failing = [d for d in h.DEPTHS if d not in passing]
    sel = [p for p in probes if p["form"] == form and p["length_pages"] == length]
    lo = max([p["evidence_end"] for p in sel if p["depth_pct"] in passing] or [0])
    hi = min([p["evidence_end"] for p in sel if p["depth_pct"] in failing] or [sel[0]["doc_chars"]])
    return lo, hi


def compute() -> dict:
    manuals = h.load_manuals()
    all_probes = h.load_probes()
    probes = h.long_probes(all_probes)
    rows = h.sweep(probes, manuals)
    cells = h.cell_counts(rows)

    audit = h.audit_probes(all_probes, manuals)
    chars_per_sweep = sum(len(manuals[p["manual_id"]]) for p in probes)  # each probe sends its whole manual
    control_ok = sum(1 for r in rows if r["reader"] == "control" and r["passed"])

    per_reader = {}
    for rk in h.READER_KEYS:
        rr = [r for r in rows if r["reader"] == rk]
        known = h.known_fault_cells(probes, rk)
        flagged = h.flagged_cells(cells, rk)
        low = h.flagged_cells(cells, rk, floor=0.50)
        wrong = [r for r in rr if not r["passed"]]
        designed = [r for r in rr if r["designed_fail"]]
        per_reader[rk] = {
            "n": len(rr), "passed": len(rr) - len(wrong), "wrong": len(wrong), "designed_wrong": len(designed),
            "wrong_and_designed": sum(1 for r in wrong if r["designed_fail"]),
            "known_cells": len(known), "flagged_cells": len(flagged),
            "true_flags": len(known & flagged), "misses": len(known - flagged), "false_flags": len(flagged - known),
            "misses_at_floor_50": len(known - low),
            "gate": h.gate(rr),
            "gate_by_length": {L: h.gate([r for r in rr if r["length"] == L]) for L in h.LENGTHS},
            "kinds": dict(Counter(r["diagnosis"] for r in wrong)),
            "localization": {f: merged_localization(cells, rk, f) for f in h.FORMS},
            "fault_forms": sorted({f for (f, _l, _d) in known}, key=h.FORMS.index),
        }

    # catch rates behind the utility number: share of known failing cells each test flags
    known_total = sum(per_reader[rk]["known_cells"] for rk in STUBS)
    pn_caught = sum(per_reader[rk]["true_flags"] for rk in STUBS)
    needle_caught = 0
    for rk in STUBS:
        known = h.known_fault_cells(probes, rk)
        flagged = h.flagged_cells(cells, rk)
        needle_caught += sum(1 for (f, L, d) in known & flagged if (f, d) == SINGLE_NEEDLE)
    classes_total = sum(len(per_reader[rk]["fault_forms"]) for rk in STUBS)
    classes_needle = sum(1 for rk in STUBS if SINGLE_NEEDLE[0] in per_reader[rk]["fault_forms"]
                         and any((SINGLE_NEEDLE[0], L, SINGLE_NEEDLE[1]) in h.flagged_cells(cells, rk) for L in h.LENGTHS))
    utility = {
        "failing_cells": known_total, "short_caught": 0, "needle_caught": needle_caught, "pn_caught": pn_caught,
        "fault_classes": classes_total, "classes_short": 0, "classes_needle": classes_needle,
        "classes_pn": sum(1 for rk in STUBS for f in per_reader[rk]["fault_forms"]
                          if any((f, L, d) in h.flagged_cells(cells, rk) for L in h.LENGTHS for d in h.DEPTHS)),
        "catch_short": 0.0, "catch_needle": needle_caught / float(known_total), "catch_pn": pn_caught / float(known_total),
        "assistants_per_year": ASSISTANTS_PER_YEAR, "assistants_range": list(ASSISTANTS_RANGE),
    }
    utility["utility"] = (utility["catch_pn"] - utility["catch_short"]) * ASSISTANTS_PER_YEAR
    utility["utility_low"] = (utility["catch_pn"] - utility["catch_short"]) * ASSISTANTS_RANGE[0]
    utility["utility_high"] = (utility["catch_pn"] - utility["catch_short"]) * ASSISTANTS_RANGE[1]

    brackets = {L: boundary_bracket(cells, probes, "truncating", "plain", L) for L in h.LENGTHS}
    bracket_hits = sum(1 for lo, hi in brackets.values() if lo <= h.TRUNCATE_AT <= hi)

    # the known limit
    types = h.load_probe_types()
    unscorable = [t["probe_type"] for t in types if t["scorable_by_exact_match"] == "no"]
    scorable = [t["probe_type"] for t in types if t["scorable_by_exact_match"] == "yes"]
    vrows = []
    for p in probes:
        row = h.run_probe(verbose_control, p, manuals)
        row["reader"] = "verbose_control"
        vrows.append(row)
    vcells = h.cell_counts(vrows)
    limit = {
        "unscorable": unscorable, "scorable": scorable, "n_types": len(types),
        "verbose_passed": sum(1 for r in vrows if r["passed"]), "verbose_n": len(vrows),
        "verbose_flagged_cells": len(h.flagged_cells(vcells, "verbose_control")),
        "verbose_cells": len(vcells), "verbose_gate": h.gate(vrows)["verdict"],
    }
    return {"rows": rows, "cells": cells, "audit": audit, "control_ok": control_ok, "n_probes": len(probes),
            "per_reader": per_reader, "utility": utility, "limit": limit,
            "brackets": brackets, "bracket_hits": bracket_hits, "chars_per_sweep": chars_per_sweep}


def print_matrix(res: dict, rk: str) -> None:
    print("{} - probes passed out of 3".format(h.READER_BY_KEY[rk]["label"]))
    head1 = "    {:<12}".format("")
    head2 = "    {:<12}".format("depth %")
    for L in h.LENGTHS:
        head1 += "{:<25}".format("{} pages".format(L))
        head2 += "{:<25}".format("  ".join("{:>3}".format(d) for d in h.DEPTHS))
    print(head1)
    print(head2)
    for f in h.FORMS:
        line = "    {:<12}".format(f)
        for L in h.LENGTHS:
            line += "{:<25}".format("  ".join("{:>3}".format(res["cells"][(rk, f, L, d)][0]) for d in h.DEPTHS))
        print(line)
    print()


def main() -> None:
    res = compute()
    OUT_DIR.mkdir(exist_ok=True)
    pr, ut, lim = res["per_reader"], res["utility"], res["limit"]
    print("\n" + "=" * 88)
    print("Step 4 - The fix: PolicyNeedle (full sweep, localization, gate, harness validity)")
    print("=" * 88)
    print("Synthetic data. The four readers are STUBS, not models. Nothing here calls a model.\n")

    print("1. Probe-set audit")
    print("   {} probes checked. Questions that match more or fewer blocks than their form is built around: {}.".format(
        res["audit"]["checked"], len(res["audit"]["ambiguous"])))
    print("   Full-scan control answers {} of {} long-sweep probes correctly, so every probe is answerable.\n".format(
        res["control_ok"], res["n_probes"]))

    print("2. Per-slice pass matrix ({} reads: 4 readers x {} probes)".format(4 * res["n_probes"], res["n_probes"]))
    print("   Each probe sends its whole manual to the reader: {:,} characters of manual text per reader per sweep.\n".format(
        res["chars_per_sweep"]))
    for rk in h.READER_KEYS:
        print_matrix(res, rk)

    print("3. Fault localization (a cell is flagged when fewer than 90% of its 3 probes pass, so one miss flags it)")
    for rk in STUBS:
        print("   {}  [{}]".format(h.READER_BY_KEY[rk]["label"], h.READER_BY_KEY[rk]["fault"]))
        for f in h.FORMS:
            print("     {:<12} fails: {}".format(f, pr[rk]["localization"][f]))
        kinds = ", ".join("{} {}".format(k, v) for k, v in sorted(pr[rk]["kinds"].items(), key=lambda kv: (-kv[1], kv[0])))
        print("     kind of wrong answer: {}".format(kinds))
    print("   Full-scan control (stub)  fails: none\n")

    print("4. CI-style gate  (PASS needs: overall >= {:.0f}%, every form x length slice >= {:.0f}%, every depth band >= {:.0f}%)".format(
        100 * h.GATE_OVERALL, 100 * h.GATE_FORM_LENGTH, 100 * h.GATE_DEPTH))
    for rk in h.READER_KEYS:
        g = pr[rk]["gate"]
        print("   {:<30} {}   overall {:.1f}%".format(h.READER_BY_KEY[rk]["label"], g["verdict"], 100 * g["overall"]))
        for b in g["broken"]:
            print("       - {}".format(b))
    print()

    print("5. Harness validity: does it flag every known fault cell and stay quiet on the control?")
    print("   A cell is form x length x depth (90 per reader). 'Known fault' = the stub was written to fail it.")
    print("   {:<30} {:>11} {:>8} {:>11} {:>7} {:>12}".format("Reader", "Known cells", "Flagged", "True flags", "Misses", "False flags"))
    for rk in h.READER_KEYS:
        r = pr[rk]
        print("   {:<30} {:>11} {:>8} {:>11} {:>7} {:>12}".format(
            h.READER_BY_KEY[rk]["label"], r["known_cells"], r["flagged_cells"], r["true_flags"], r["misses"], r["false_flags"]))
    tot_true = sum(pr[rk]["true_flags"] for rk in STUBS)
    tot_known = sum(pr[rk]["known_cells"] for rk in STUBS)
    tot_miss = sum(pr[rk]["misses"] for rk in STUBS)
    tot_false = sum(pr[rk]["false_flags"] for rk in h.READER_KEYS)
    print("   Total over the 3 faulty stubs: {} of {} known fault cells flagged, {} missed; false flags across all 4 readers: {}.".format(
        tot_true, tot_known, tot_miss, tot_false))
    wrong = sum(pr[rk]["wrong"] for rk in h.READER_KEYS)
    both = sum(pr[rk]["wrong_and_designed"] for rk in h.READER_KEYS)
    des = sum(pr[rk]["designed_wrong"] for rk in h.READER_KEYS)
    print("   Probe level: {} wrong answers observed, {} designed, {} in both.".format(wrong, des, both))
    print("   Boundary check (truncating stub, plain clause): the pass/fail staircase brackets its true limit of")
    print("   {:,} characters at {} of 3 lengths:  {}.".format(
        h.TRUNCATE_AT, res["bracket_hits"],
        "; ".join("{} pp {:,} to {:,}".format(L, lo, hi) for L, (lo, hi) in res["brackets"].items())))
    print("   The five-point depth grid cannot place the limit more tightly than the gap between two depths.")
    miss50 = sum(pr[rk]["misses_at_floor_50"] for rk in STUBS)
    print("   Threshold matters: with a cell floor of 50% instead of 90%, {} known fault cells would be missed".format(miss50))
    print("   (cells where two of three probes still pass). With 3 probes per cell, 90% means one miss flags.")
    print("   This validates the scoring, slicing and flagging against stubs with known faults. It is not a")
    print("   recall estimate for faults nobody planted, and not a statement about any real model.\n")

    print("6. Catch rates on the {} known failing cells (of 270 stub cells, the ones a faulty stub was built to fail)".format(
        ut["failing_cells"]))
    print("   {:<44} {:>10} {:>10}".format("Test", "Flagged", "Share"))
    print("   {:<44} {:>10} {:>9.1f}%".format("Short-document spot test (step 1)", "{}/{}".format(ut["short_caught"], ut["failing_cells"]), 100 * ut["catch_short"]))
    print("   {:<44} {:>10} {:>9.1f}%".format("Fixed-needle long test (step 2)", "{}/{}".format(ut["needle_caught"], ut["failing_cells"]), 100 * ut["catch_needle"]))
    print("   {:<44} {:>10} {:>9.1f}%".format("PolicyNeedle sweep (this step)", "{}/{}".format(ut["pn_caught"], ut["failing_cells"]), 100 * ut["catch_pn"]))
    print("   Fault classes (stub x form) flagged: short {}/{}, fixed needle {}/{}, PolicyNeedle {}/{}.\n".format(
        ut["classes_short"], ut["fault_classes"], ut["classes_needle"], ut["fault_classes"], ut["classes_pn"], ut["fault_classes"]))
    print("   Utility = (catch rate with PolicyNeedle - catch rate with short-document testing) x assistants launched per year")
    print("           = ({:.0f}% - {:.0f}%) x {}   [assistants per year: modeled assumption, range {}-{}]".format(
        100 * ut["catch_pn"], 100 * ut["catch_short"], ut["assistants_per_year"], ut["assistants_range"][0], ut["assistants_range"][1]))
    print("           = {:.0f} assistant launches per year whose long-document faults are caught before launch (range {:.0f}-{:.0f}).".format(
        ut["utility"], ut["utility_low"], ut["utility_high"]))
    print("   The catch rates are measured on stubs with known faults. They are not a claim about any real model,")
    print("   and the multiplication assumes each launch carries at least one fault of the kinds modeled here.\n")

    print("7. Known limit left in: exact-match scoring on synthetic wording")
    print("   Probe types the harness can score: {} ({}).".format(len(lim["scorable"]), ", ".join(lim["scorable"])))
    print("   Probe types it cannot score:       {} ({}).".format(len(lim["unscorable"]), ", ".join(lim["unscorable"])))
    print("   Demonstration: the control's correct answers wrapped in one sentence score {} of {} under exact match;".format(
        lim["verbose_passed"], lim["verbose_n"]))
    print("   {} of {} cells flagged, gate {}. A correct but wordy reader would be flagged as broken.".format(
        lim["verbose_flagged_cells"], lim["verbose_cells"], lim["verbose_gate"]))
    print("   Paraphrase and verbosity are not covered. Scoring a real assistant needs a tolerant scorer first.\n")

    with open(OUT_DIR / "step_04_sweep.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reader", "probe_id", "form", "length_pages", "depth_pct", "expected", "answer", "passed", "kind_of_wrong", "designed_fail"])
        for r in res["rows"]:
            w.writerow([r["reader"], r["probe_id"], r["form"], r["length"], r["depth"], r["expected"], r["answer"],
                        int(r["passed"]), r["diagnosis"], int(r["designed_fail"])])
    with open(OUT_DIR / "step_04_cells.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reader", "form", "length_pages", "depth_pct", "passed", "n", "flagged", "known_fault"])
        known = {rk: h.known_fault_cells(h.long_probes(h.load_probes()), rk) for rk in h.READER_KEYS}
        for rk in h.READER_KEYS:
            for f in h.FORMS:
                for L in h.LENGTHS:
                    for d in h.DEPTHS:
                        p, n = res["cells"][(rk, f, L, d)]
                        w.writerow([rk, f, L, d, p, n, int(p / float(n) < h.SLICE_FLOOR), int((f, L, d) in known[rk])])
    summary = {
        "probes": res["n_probes"], "reads": 4 * res["n_probes"], "audit_ambiguous": len(res["audit"]["ambiguous"]),
        "control_correct": res["control_ok"], "bracket_hits": res["bracket_hits"], "chars_per_sweep": res["chars_per_sweep"],
        "brackets": {str(L): list(v) for L, v in res["brackets"].items()},
        "readers": {rk: {k: v for k, v in pr[rk].items() if k not in ("gate_by_length",)} for rk in h.READER_KEYS},
        "utility": ut, "limit": lim,
    }
    with open(OUT_DIR / "step_04_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        fh.write("\n")
    print("Wrote: src/out/step_04_sweep.csv, step_04_cells.csv, step_04_summary.json")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
