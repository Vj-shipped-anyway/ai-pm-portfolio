import csv
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def rows(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class DataTests(unittest.TestCase):
    def test_a_rerun_of_the_generator_reproduces_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, os.path.join(DATA, "_generate.py")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            names = [n for n in os.listdir(DATA) if n.endswith((".csv", ".json"))]
            self.assertGreaterEqual(len(names), 11)
            for n in names:
                with open(os.path.join(DATA, n), "rb") as a, open(os.path.join(tmp, n), "rb") as b:
                    self.assertEqual(a.read(), b.read(), n)

    def test_every_row_has_a_planted_label_and_the_hard_cases_are_present(self):
        truth = {r["row_id"]: r for r in rows("row_truth.csv")}
        self.assertEqual(set(truth), {r["row_id"] for r in rows("crosswalk.csv")})
        kinds = {t["kind"] for t in truth.values()}
        for hard in ("ok_reformatted", "ok_negated_word", "ok_partial", "wording_paraphrase", "false_declaration"):
            self.assertIn(hard, kinds)

    def test_the_two_false_declarations_are_in_the_registry_and_in_the_truth_file(self):
        declared = {r["check_id"]: r for r in rows("check_truth.csv")}
        differ = [c for c, r in declared.items() if r["declared"] != r["really_exercises"]]
        self.assertEqual(sorted(differ), ["C-18", "C-19"])


if __name__ == "__main__":
    unittest.main()
