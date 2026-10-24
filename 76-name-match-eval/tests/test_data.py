import csv
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import name_match_eval as nme

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FILES = ["watchlist.csv", "customers.csv", "truth.csv", "example_watchlist.csv", "example_customers.csv", "example_truth.csv"]


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class DataTests(unittest.TestCase):
    def test_rerun_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            subprocess.run([sys.executable, "_generate.py"], cwd=tmp, check=True, capture_output=True)
            for f in FILES:
                self.assertTrue(filecmp.cmp(os.path.join(DATA, f), os.path.join(tmp, f), shallow=False), f)

    def test_planted_counts(self):
        kinds = Counter(r["planted_as"] for r in rows("truth.csv"))
        truth = Counter(r["truth"] for r in rows("truth.csv"))
        self.assertEqual((truth["match"], truth["clear"]), (150, 250))
        self.assertEqual((kinds["alias_unlisted"], kinds["translit_heavy"], kinds["namesake"], kinds["near_name"]), (10, 10, 8, 30))
        self.assertEqual(len(rows("watchlist.csv")), 90)

    def test_generator_does_not_import_the_matchers(self):
        with open(os.path.join(DATA, "_generate.py"), encoding="utf-8") as fh:
            self.assertIsNone(re.search(r"^\s*(import|from)\s+name_match_eval", fh.read(), re.M))

    def test_only_namesakes_equal_a_listed_name(self):
        listed = {nme.normalize(r["listed_name"]) for r in rows("watchlist.csv")}
        names = {r["customer_id"]: r["name"] for r in rows("customers.csv")}
        for r in rows("truth.csv"):
            same = nme.normalize(names[r["customer_id"]]) in listed
            if r["planted_as"] == "namesake":
                self.assertTrue(same, r)
            elif r["truth"] == "clear":
                self.assertFalse(same, r)

    def test_the_hard_kinds_are_present_and_not_caught_by_exact(self):
        entries, customers, truth = nme.load_all(*(os.path.join(DATA, f) for f in ("watchlist.csv", "customers.csv", "truth.csv")))
        rec = nme.evaluate(nme.ExactMatcher(), entries, customers, truth)
        by = nme.by_kind_at(rec, 1.0)
        self.assertEqual(by["alias_unlisted"][0], 0)
        self.assertEqual(by["order_swap"][1], 24)


if __name__ == "__main__":
    unittest.main()
