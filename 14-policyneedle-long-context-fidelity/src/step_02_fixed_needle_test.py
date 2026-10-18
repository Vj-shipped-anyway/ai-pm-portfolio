"""Step 2 - Basic approach: a long-document test with one fixed needle position.

The usual upgrade after a short test passes: plant one fact in a long document,
always at the same depth (here the middle, 50 percent), at the three lengths
(40, 120, 240 pages), and see whether the reader finds it. Plain clauses only.

The readers are STUBS, not models; see harness.py.

Run (from src/):
    python3 step_02_fixed_needle_test.py

Output: a table on screen and src/out/step_02_results.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import harness as h

OUT_DIR = Path(__file__).resolve().parent / "out"
FIXED_DEPTH = 50


def compute() -> dict:
    manuals = h.load_manuals()
    probes = [p for p in h.long_probes(h.load_probes())
              if p["form"] == "plain" and p["depth_pct"] == FIXED_DEPTH]
    rows = h.sweep(probes, manuals)
    table = {}
    for r in h.READERS:
        per_len = {}
        for length in h.LENGTHS:
            rr = [x for x in rows if x["reader"] == r["key"] and x["length"] == length]
            per_len[length] = {"passed": sum(1 for x in rr if x["passed"]), "n": len(rr)}
        total_p = sum(v["passed"] for v in per_len.values())
        total_n = sum(v["n"] for v in per_len.values())
        table[r["key"]] = {"per_length": per_len, "passed": total_p, "n": total_n}
    flagged_stubs = [r["key"] for r in h.READERS
                     if r["key"] != "control" and table[r["key"]]["passed"] < table[r["key"]]["n"]]
    flagged_cells = sorted((rk, length) for rk in table for length in h.LENGTHS
                           if rk != "control" and table[rk]["per_length"][length]["passed"] < table[rk]["per_length"][length]["n"])
    return {"n_probes": len(probes), "table": table, "flagged_stubs": flagged_stubs,
            "flagged_cells": flagged_cells, "rows": rows}


def main() -> None:
    res = compute()
    OUT_DIR.mkdir(exist_ok=True)
    print("\n" + "=" * 88)
    print("Step 2 - Basic approach: a long-document test with one fixed needle position")
    print("=" * 88)
    print("Synthetic data. The four readers are STUBS, not models; three carry a known fault.\n")
    print("Test: plain-clause questions planted at depth {}% in the 40, 120 and 240 page manuals".format(FIXED_DEPTH))
    print("({} questions: 3 per length). Normalized exact match.\n".format(res["n_probes"]))
    print("  {:<30} {:>8} {:>8} {:>8} {:>10} {:>10}".format("Reader", "40 pp", "120 pp", "240 pp", "Total", "Pass rate"))
    print("  {} {} {} {} {} {}".format("-" * 30, "-" * 8, "-" * 8, "-" * 8, "-" * 10, "-" * 10))
    for r in h.READERS:
        t = res["table"][r["key"]]
        cells = ["{}/{}".format(t["per_length"][L]["passed"], t["per_length"][L]["n"]) for L in h.LENGTHS]
        print("  {:<30} {:>8} {:>8} {:>8} {:>7}/{:<2} {:>9.0f}%".format(
            r["label"], cells[0], cells[1], cells[2], t["passed"], t["n"], 100.0 * t["passed"] / t["n"]))
    print()
    names = [h.READER_BY_KEY[k]["short"] for k in res["flagged_stubs"]]
    print("What this test finds: {} of 3 faulty stubs flagged ({}).".format(len(names), ", ".join(names) or "none"))
    print("  The truncating stub fails at 120 and 240 pages: the middle of those manuals is past its limit.")
    print("  The keyword-window and recency stubs pass 9 of 9. Their faults are not about where the")
    print("  fact sits, so a single fixed position cannot see them.")
    print("What it still cannot say: which depth fails (only one is tested), and nothing about the")
    print("other five forms of fact. The aggregate pass rate looks like a result; it is a spot check.\n")

    with open(OUT_DIR / "step_02_results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reader", "probe_id", "length_pages", "depth_pct", "expected", "answer", "passed"])
        for x in res["rows"]:
            w.writerow([x["reader"], x["probe_id"], x["length"], x["depth"], x["expected"], x["answer"], int(x["passed"])])
    print("Wrote: src/out/step_02_results.csv")
    print("Next: step_03 plants six forms of fact at five depths and shows where each stub breaks.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
