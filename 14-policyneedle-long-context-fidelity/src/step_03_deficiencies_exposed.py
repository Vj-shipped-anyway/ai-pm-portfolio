"""Step 3 - Where this still breaks: six named deficiencies, each with a depth-by-length grid.

Plants six forms of fact at five depths in the 40, 120 and 240 page manuals and
runs the four STUB readers. For each deficiency, one grid: rows are depths,
columns are reader x document length, each cell is the number of probes passed
out of 3.

  (a) position sensitivity            a plain clause, at depth
  (b) superseded clause               answered from the old version
  (c) exception or negation clause    in a footnote, missed
  (d) table value                     read from the wrong column
  (e) two-section synthesis fact      needs two clauses, one is used
  (f) near-duplicate distractor       a sibling product's clause is answered

The readers are STUBS, not models; see harness.py.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: grids on screen and src/out/step_03_grid.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import harness as h

OUT_DIR = Path(__file__).resolve().parent / "out"
GRID_READERS = ["truncating", "first_match", "last_match", "control"]


def compute() -> dict:
    manuals = h.load_manuals()
    probes = h.long_probes(h.load_probes())
    rows = h.sweep(probes, manuals)
    cells = h.cell_counts(rows)
    summary = {}
    for form in h.FORMS:
        for rk in GRID_READERS:
            rr = [x for x in rows if x["reader"] == rk and x["form"] == form]
            summary[(form, rk)] = (sum(1 for x in rr if x["passed"]), len(rr))
    # one worked wrong answer per deficiency, from the stub whose designed fault it is, at 120 pages and depth 50
    example_reader = {"plain": "truncating", "superseded": "first_match", "exception": "first_match",
                      "table": "first_match", "two_section": "first_match", "distractor": "first_match"}
    examples = {}
    for form in h.FORMS:
        rk = example_reader[form]
        bad = [x for x in rows if x["reader"] == rk and x["form"] == form and not x["passed"]
               and x["length"] == 120 and x["depth"] == 50]
        if bad:
            examples[form] = (rk, bad[0])
    return {"rows": rows, "cells": cells, "summary": summary, "examples": examples, "probes": probes}


def print_grid(res: dict, form: str) -> None:
    letter, name = h.DEFICIENCY[form]
    print("({}) {}   [form: {}]".format(letter, name, form))
    print("    cell = probes passed out of 3")
    head1 = "    {:<14}".format("")
    head2 = "    {:<14}".format("depth \\ pages")
    for rk in GRID_READERS:
        head1 += "{:<17}".format(h.READER_BY_KEY[rk]["short"])
        head2 += "{:<17}".format("  ".join("{:>3}".format(L) for L in h.LENGTHS))
    print(head1)
    print(head2)
    for d in h.DEPTHS:
        line = "    {:<14}".format("{}%".format(d))
        for rk in GRID_READERS:
            line += "{:<17}".format("  ".join("{:>3}".format(res["cells"][(rk, form, L, d)][0]) for L in h.LENGTHS))
        print(line)
    print()


def main() -> None:
    res = compute()
    OUT_DIR.mkdir(exist_ok=True)
    print("\n" + "=" * 88)
    print("Step 3 - Where this still breaks: six deficiencies, depth by length, per stub")
    print("=" * 88)
    print("Synthetic data. The four readers are STUBS, not models; three carry a known fault.")
    print("{} probes: 6 forms x 5 depths x 3 per cell, at each of 3 lengths.\n".format(len(res["probes"])))

    for form in h.FORMS:
        print_grid(res, form)

    print("Pass rate by deficiency across all depths and lengths (45 probes each)")
    head = "  {:<50}".format("Deficiency")
    for rk in GRID_READERS:
        head += "{:>13}".format(h.READER_BY_KEY[rk]["short"])
    print(head)
    print("  " + "-" * (50 + 13 * len(GRID_READERS)))
    for form in h.FORMS:
        letter, name = h.DEFICIENCY[form]
        line = "  {:<50}".format("({}) {}".format(letter, name))
        for rk in GRID_READERS:
            p, n = res["summary"][(form, rk)]
            line += "{:>13}".format("{}/{} {:.0f}%".format(p, n, 100.0 * p / n))
        print(line)
    print()

    print("One wrong answer per deficiency (120 pages, depth 50%, from the stub built to fail it)")
    for form in h.FORMS:
        letter, name = h.DEFICIENCY[form]
        if form not in res["examples"]:
            continue
        rk, x = res["examples"][form]
        probe = next(p for p in res["probes"] if p["probe_id"] == x["probe_id"])
        print("  ({}) {} - {}, {} pages, depth {}%".format(letter, h.READER_BY_KEY[rk]["short"], x["probe_id"],
                                                          x["length"], x["depth"]))
        print("      Q: {}".format(probe["question"]))
        print("      expected: {:<12} got: {:<12} kind of wrong answer: {}".format(
            x["expected"], x["answer"] or "(no answer)", x["diagnosis"]))
    print()
    print("Reading the grids")
    print("  - A staircase (pass at the top, fail below a depth that moves with length) is a position fault.")
    print("    Only the truncating stub has one. The boundary is its limit: {:,} characters.".format(h.TRUNCATE_AT))
    print("  - A flat row (the same result at every depth and length) is a fault in how that form is read.")
    print("    The keyword-window and recency stubs fail whole forms at every depth, so no position test sees them.")
    print("  - The control passes every cell, so the probes are answerable from the text.\n")

    with open(OUT_DIR / "step_03_grid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reader", "form", "length_pages", "depth_pct", "passed", "n"])
        for (rk, form, length, depth), (p, n) in sorted(
                res["cells"].items(), key=lambda kv: (GRID_READERS.index(kv[0][0]), h.FORMS.index(kv[0][1]), kv[0][2], kv[0][3])):
            w.writerow([rk, form, length, depth, p, n])
    print("Wrote: src/out/step_03_grid.csv")
    print("Next: step_04 turns the grids into a per-slice matrix, fault localization and a gate.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
