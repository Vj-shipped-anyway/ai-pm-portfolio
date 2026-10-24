import csv
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
FILES = ("rules.json", "cases.json", "case_truth.csv", "as_of.txt", "example_case.json")


class GeneratorTests(unittest.TestCase):
    def test_rerun_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in FILES:
                with open(os.path.join(DATA, name), "rb") as a, open(os.path.join(tmp, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_truth_counts_match_the_quota(self):
        with open(os.path.join(DATA, "case_truth.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(Counter(r["truth_class"] for r in rows), {"ready": 43, "defective": 43, "late": 14})
        self.assertEqual(sum(1 for r in rows if r["visible_in_metadata"] == "no"), 9)
        self.assertEqual(len({r["case_id"] for r in rows}), 100)


if __name__ == "__main__":
    unittest.main()
