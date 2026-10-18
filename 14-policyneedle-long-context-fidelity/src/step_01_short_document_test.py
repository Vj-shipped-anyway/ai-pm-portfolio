"""Step 1 - Before: the short-document spot test.

A team wires an assistant to a policy document, writes ten questions against a
short excerpt, checks the answers, and sees everything pass. That is the test
that ships. This script runs exactly that test: a 6-page synthetic excerpt, ten
plain-clause questions (five depths, two each), against the four STUB readers.

None of the readers is a model. Three of them carry a fault on purpose (see
harness.py). The point of this step is that the short test cannot see any of
them.

Run (from src/):
    python3 step_01_short_document_test.py

Output: a table on screen and src/out/step_01_results.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path

import harness as h

OUT_DIR = Path(__file__).resolve().parent / "out"


def compute() -> dict:
    manuals = h.load_manuals()
    probes = h.short_probes(h.load_probes())
    rows = h.sweep(probes, manuals)
    text = manuals[probes[0]["manual_id"]]
    blocks = text.split("\n\n")
    structures = {
        "amendment register": 1 if "Appendix A." in text else 0,
        "footnote exceptions": sum(1 for b in blocks if b.startswith("Note to clause")),
        "tier tables": sum(1 for b in blocks if b.startswith("Table")),
        "cross-section discount clauses": sum(1 for b in blocks if "off the standard" in b),
    }
    multi = sum(1 for p in probes if len(h.candidate_blocks(manuals[p["manual_id"]], p["question"])) != 1)
    per_reader = {}
    for r in h.READERS:
        rr = [x for x in rows if x["reader"] == r["key"]]
        per_reader[r["key"]] = {"passed": sum(1 for x in rr if x["passed"]), "n": len(rr)}
    return {
        "doc_chars": len(text), "approx_pages": len(text) / float(h.PAGE_CHARS), "n_probes": len(probes),
        "structures": structures, "questions_with_more_than_one_match": multi,
        "per_reader": per_reader, "rows": rows,
    }


def main() -> None:
    res = compute()
    OUT_DIR.mkdir(exist_ok=True)
    print("\n" + "=" * 88)
    print("Step 1 - Before: the short-document spot test")
    print("=" * 88)
    print("Synthetic data. The four readers are STUBS, not models; three carry a known fault.\n")
    print("Test: a {:.1f}-page excerpt ({:,} characters), {} plain-clause questions, one per planted clause.".format(
        res["approx_pages"], res["doc_chars"], res["n_probes"]))
    print("Scoring: normalized exact match against one expected answer per question.\n")
    print("  {:<30} {:>8} {:>10}   {}".format("Reader", "Passed", "Pass rate", "Known fault of this stub"))
    print("  {} {} {}   {}".format("-" * 30, "-" * 8, "-" * 10, "-" * 40))
    for r in h.READERS:
        pr = res["per_reader"][r["key"]]
        print("  {:<30} {:>5}/{:<2} {:>9.0f}%   {}".format(
            r["label"], pr["passed"], pr["n"], 100.0 * pr["passed"] / pr["n"], r["fault_short"]))
    print()
    print("Everything passes, including the three stubs that were written to fail.\n")
    print("Why teams stop here")
    print("  1. A 100% result reads as done. There is no failing case to investigate.")
    print("  2. The excerpt is {:,} characters; the truncating stub reads {:,}. A short document fits any".format(
        res["doc_chars"], h.TRUNCATE_AT))
    print("     window, so a window limit never bites.")
    print("  3. A short excerpt holds one version of each clause and one product at a time. What it contains:")
    for name, count in res["structures"].items():
        print("       {:<40} {}".format(name, count))
    print("       {:<40} {} of {}".format("questions matching more than one block",
                                         res["questions_with_more_than_one_match"], res["n_probes"]))
    print("     No amendment to read, no footnote to find, no tier table, no pair of clauses, no sibling")
    print("     product. The faults need those structures; the test has none of them.\n")

    with open(OUT_DIR / "step_01_results.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["reader", "probe_id", "depth_pct", "expected", "answer", "passed"])
        for x in res["rows"]:
            w.writerow([x["reader"], x["probe_id"], x["depth"], x["expected"], x["answer"], int(x["passed"])])
    print("Wrote: src/out/step_01_results.csv")
    print("Next: step_02 runs the usual upgrade, a long-document test with one fixed needle position.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
