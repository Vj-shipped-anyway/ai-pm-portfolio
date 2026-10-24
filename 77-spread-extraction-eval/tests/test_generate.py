import csv
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import spread_eval as se

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = se.load_docs(os.path.join(DATA, "statements.csv"), need_text=True)
        cls.truth = se.load_truth(os.path.join(DATA, "truth.csv"))

    def test_rerun_reproduces_every_file_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in ("statements.csv", "truth.csv"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_shape(self):
        self.assertEqual(len(self.docs), 120)
        self.assertEqual(len(self.truth), 120 * len(se.FIELDS) * 2)
        counts = {}
        for d in self.docs:
            counts[d["layout"]] = counts.get(d["layout"], 0) + 1
        self.assertEqual(sorted(counts.values()), [20] * 6)
        self.assertEqual({d["split"] for d in self.docs if d["layout"] == "note_column"}, {"holdout"})
        self.assertEqual(len({d["company"] for d in self.docs}), 120)

    def test_truth_obeys_every_identity_in_both_periods(self):
        self.assertEqual(sum(1 for problems in se.tie_out(self.truth, sorted({k[0] for k in self.truth})).values() if problems), 0)

    def test_thousands_layout_states_its_scale_and_its_truth_is_in_dollars(self):
        ids = {d["doc_id"] for d in self.docs if d["layout"] == "thousands_parens"}
        for d in self.docs:
            self.assertEqual("in thousands of dollars" in d["text"], d["layout"] == "thousands_parens")
        self.assertTrue(all(v % 1000 == 0 for k, v in self.truth.items() if k[0] in ids))

    def test_hard_cases_are_present(self):
        text = {d["layout"]: [x["text"] for x in self.docs if x["layout"] == d["layout"]] for d in self.docs}
        self.assertTrue(any(re.search(r"\(\d", t) for t in text["thousands_parens"]))
        self.assertTrue(any(re.search(r"(?m)(^|\s)-(\s|$)", t) for t in text["thousands_parens"]))
        self.assertTrue(any("liabilities and\nequity" in t for t in text["wrapped_footnotes"]))
        self.assertTrue(any(v < 0 for k, v in self.truth.items() if k[1] == "total_equity"))
        self.assertTrue(any(v < 0 for k, v in self.truth.items() if k[1] == "net_income"))

    def test_statements_are_not_in_doc_id_order_of_layout(self):
        first_ten = [d["layout"] for d in self.docs[:10]]
        self.assertGreater(len(set(first_ten)), 3)

    def test_csv_round_trips(self):
        with open(os.path.join(DATA, "statements.csv"), newline="", encoding="utf-8") as fh:
            self.assertEqual(len(list(csv.DictReader(fh))), 120)


if __name__ == "__main__":
    unittest.main()
