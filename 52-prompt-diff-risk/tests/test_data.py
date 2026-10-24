"""Checks on the committed data: no pull request is a no-op, and the planted truth is internally consistent."""
import csv
import os
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
from common import DATA, load_cases, load_world


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class DataTests(unittest.TestCase):
    def test_every_pull_request_changes_the_text(self):
        cases = load_cases()
        self.assertEqual(len(cases), 70)
        self.assertEqual(len({c["pr_id"] for c in cases}), 70)
        self.assertTrue(all(c["old"] != c["new"] for c in cases))

    def test_truth_classes(self):
        self.assertEqual(Counter(c["truth"] for c in load_cases()), {"high": 22, "medium": 30, "low": 18})

    def test_planted_failures_sit_inside_the_truth_slices(self):
        by_id = {p["probe_id"]: p["slice"] for p in rows("probes.csv")}
        slices = {r["slice"] for r in rows("slices.csv")}
        for c in load_cases():
            self.assertTrue(set(c["slices"]) <= slices, c["pr_id"])
            self.assertTrue(all(by_id[p] in c["slices"] for p in c["fails"]), c["pr_id"])
            self.assertEqual(bool(c["fails"]), c["truth"] != "low", c["pr_id"])

    def test_probe_and_slice_tables_agree(self):
        probes = Counter(r["slice"] for r in rows("probes.csv"))
        for r in rows("slices.csv"):
            self.assertEqual(probes[r["slice"]], int(r["n_probes"]))
        self.assertEqual(len(load_world()[1]), 54)


if __name__ == "__main__":
    unittest.main()
