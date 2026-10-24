import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import eval_gate as eg

PROBES = "probe_id,severity,baseline_rate\nP1,high,1.0\nP2,low,0.9\n"
RESULTS = "probe_id,passes,trials,served_model\nP1,10,10,m1\nP2,9,10,m1\n"


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, text, name="f.csv", mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def bad_probes(self, text):
        with self.assertRaises(ValueError):
            eg.load_probes(self.write(text))

    def bad_results(self, text, run_id=None):
        with self.assertRaises(ValueError):
            eg.load_results(self.write(text), run_id)

    def test_good_files_load(self):
        self.assertEqual(len(eg.load_probes(self.write(PROBES))), 2)
        rows, label = eg.load_results(self.write(RESULTS))
        self.assertEqual((len(rows), label), (2, "single run"))

    def test_empty_and_header_only_files_are_rejected(self):
        for text in ("", "probe_id,severity,baseline_rate\n"):
            self.bad_probes(text)
        for text in ("", "probe_id,passes,trials,served_model\n"):
            self.bad_results(text)

    def test_missing_column_is_rejected(self):
        self.bad_probes("probe_id,severity\nP1,high\n")
        self.bad_results("probe_id,passes,trials\nP1,1,1\n")

    def test_truncated_row_is_rejected(self):
        self.bad_probes("probe_id,severity,baseline_rate\nP1,high,1.0\nP2,lo")
        self.bad_results("probe_id,passes,trials,served_model\nP1,10,10,m1\nP2,9,10")

    def test_row_with_an_extra_field_is_rejected(self):
        self.bad_results("probe_id,passes,trials,served_model\nP1,10,10,m1,extra\n")

    def test_binary_file_is_rejected(self):
        p = self.write(b"\xff\xfe\x00\x01" * 8, mode="wb")
        with self.assertRaises(ValueError):
            eg.load_probes(p)

    def test_wrong_types_in_probe_file(self):
        self.bad_probes("probe_id,severity,baseline_rate\nP1,high,abc\n")
        self.bad_probes("probe_id,severity,baseline_rate\nP1,high,1.5\n")
        self.bad_probes("probe_id,severity,baseline_rate\nP1,high,nan\n")
        self.bad_probes("probe_id,severity,baseline_rate\nP1,critical,0.9\n")
        self.bad_probes("probe_id,severity,baseline_rate\n,high,0.9\n")

    def test_duplicate_probe_id_is_rejected(self):
        self.bad_probes("probe_id,severity,baseline_rate\nP1,high,1.0\nP1,low,0.9\n")
        self.bad_results("probe_id,passes,trials,served_model\nP1,10,10,m1\nP1,9,10,m1\n")

    def test_wrong_types_in_results_file(self):
        head = "probe_id,passes,trials,served_model\n"
        self.bad_results(head + "P1,x,10,m1\n")
        self.bad_results(head + "P1,-1,10,m1\n")
        self.bad_results(head + "P1,3.5,10,m1\n")
        self.bad_results(head + "P1,11,10,m1\n")
        self.bad_results(head + "P1,0,0,m1\n")
        self.bad_results(head + "P1,5,10,\n")

    def test_multi_run_file_needs_a_run_id(self):
        text = ("run_id,probe_id,passes,trials,served_model\nA,P1,10,10,m1\nB,P1,9,10,m1\n")
        self.bad_results(text)
        rows, label = eg.load_results(self.write(text), "B")
        self.assertEqual((rows[0]["passes"], label), (9, "B"))
        self.bad_results(text, "C")

    def test_run_id_without_a_run_id_column_is_rejected(self):
        self.bad_results(RESULTS, "A")

    def test_results_that_match_no_probe_are_rejected(self):
        probes = eg.load_probes(self.write(PROBES))
        rows = [{"probe_id": "Z9", "passes": 1, "trials": 1, "served_model": "m1"}]
        with self.assertRaises(ValueError):
            eg.evaluate(probes, rows, "m1")

    def test_empty_pin_and_bad_thresholds_are_rejected(self):
        probes = eg.load_probes(self.write(PROBES))
        rows, _ = eg.load_results(self.write(RESULTS))
        with self.assertRaises(ValueError):
            eg.evaluate(probes, rows, "")
        for limits in ({"review_drop": 0.1, "block_drop": 0.05}, {"review_drop": float("nan")}, {"collapse_drop": 0}):
            with self.assertRaises(ValueError):
                eg.evaluate(probes, rows, "m1", **limits)


if __name__ == "__main__":
    unittest.main()
