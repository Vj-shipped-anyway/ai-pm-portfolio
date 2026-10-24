import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import name_match_eval as nme

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
WATCH = "entity_id,listed_name\nE1,Hasan Karimov\nE2,Nadia Hadani\n"
CUST = "customer_id,name\nC1,\"Karimov, Hasan\"\nC2,Viktor Dalmen\n"
TRUTH = "customer_id,truth,entity_id\nC1,match,E1\nC2,clear,\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = nme.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def trio(self, watch=WATCH, cust=CUST, truth=TRUTH):
        return [self.write("w.csv", watch), self.write("c.csv", cust), self.write("t.csv", truth)]

    def sweep(self, files, *extra):
        return run(["sweep"] + files + list(extra))

    def assert_input_error(self, result):
        code, out, err = result
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_demo_prints_three_lines(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 3)

    def test_score(self):
        code, out, _ = run(["score", "Hasan Karimov", "Karimov, Hassan"])
        self.assertEqual(code, 0)
        self.assertIn("exact 0.00", out)
        self.assertIn("tokens 1.00", out)

    def test_hostile_name_in_score_cannot_start_a_workflow_command(self):
        _, out, _ = run(["score", "x\n::error::forged\r::warning::x", "y"])
        self.assertFalse(any(ln.startswith("::") for ln in out.splitlines()))
        self.assertIn("%0A", out)
        self.assertIn("%0D", out)

    def test_sweep_exit_0_when_targets_are_met(self):
        code, out, _ = self.sweep(self.trio(), "--min-recall", "0.5", "--max-false-alerts", "0.5")
        self.assertEqual(code, 0)
        self.assertIn("both targets met at one threshold: yes", out)

    def test_sweep_exit_1_when_no_threshold_meets_the_targets(self):
        code, out, _ = self.sweep(self.trio(), "--matcher", "exact", "--min-recall", "1.0")
        self.assertEqual(code, 1)
        self.assertIn("not reachable", out)

    def test_no_match_rows_says_so(self):
        files = self.trio(truth="customer_id,truth,entity_id\nC1,clear,\nC2,clear,\n")
        code, out, _ = self.sweep(files)
        self.assertEqual(code, 1)
        self.assertIn("recall is not defined", out)

    def test_nothing_scores_says_so(self):
        files = self.trio(watch="entity_id,listed_name\nE1,Aaaa Bbbb\n", cust="customer_id,name\nC1,Zzzz Qqqq\nC2,Wwww Xxxx\n",
                          truth="customer_id,truth,entity_id\nC1,match,E1\nC2,clear,\n")
        _, out, _ = self.sweep(files)
        self.assertIn("no customer scored 0.50 or more", out)

    def test_missing_file(self):
        self.assert_input_error(run(["sweep", "nope.csv", "nope2.csv", "nope3.csv"]))

    def test_empty_and_header_only_files(self):
        self.assert_input_error(self.sweep(self.trio(watch="")))
        self.assert_input_error(self.sweep(self.trio(cust="customer_id,name\n")))

    def test_wrong_columns(self):
        self.assert_input_error(self.sweep(self.trio(watch="id,name\nE1,Hasan Karimov\n")))

    def test_truncated_row(self):
        self.assert_input_error(self.sweep(self.trio(cust="customer_id,name\nC1,Hasan\nC2\n")))
        self.assert_input_error(self.sweep(self.trio(watch="entity_id,listed_name\nE1,Hasan,Karimov\n")))

    def test_not_utf8(self):
        w = self.write("w.csv", b"entity_id,listed_name\nE1,Has\xff\xfe\n", mode="wb")
        self.assert_input_error(run(["sweep", w, self.write("c.csv", CUST), self.write("t.csv", TRUTH)]))

    def test_bad_names(self):
        self.assert_input_error(self.sweep(self.trio(cust="customer_id,name\nC1,---\nC2,Viktor\n")))
        self.assert_input_error(self.sweep(self.trio(cust="customer_id,name\nC1,%s\nC2,Viktor\n" % ("a" * 500))))
        self.assert_input_error(run(["score", "", "x"]))

    def test_bad_truth(self):
        self.assert_input_error(self.sweep(self.trio(truth="customer_id,truth,entity_id\nC1,maybe,E1\nC2,clear,\n")))
        self.assert_input_error(self.sweep(self.trio(truth="customer_id,truth,entity_id\nC1,match,\nC2,clear,\n")))
        self.assert_input_error(self.sweep(self.trio(truth="customer_id,truth,entity_id\nC1,match,E9\nC2,clear,\n")))

    def test_customer_and_truth_must_line_up(self):
        self.assert_input_error(self.sweep(self.trio(truth="customer_id,truth,entity_id\nC1,match,E1\n")))
        self.assert_input_error(self.sweep(self.trio(truth=TRUTH + "C3,clear,\n")))
        self.assert_input_error(self.sweep(self.trio(cust="customer_id,name\nC1,Hasan\nC1,Hasan\n")))

    def test_hostile_id_is_escaped_in_the_error(self):
        code, _, err = self.sweep(self.trio(truth=TRUTH + '"bad\n::error::forged",clear,\n'))
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("%0A", err)

    def test_option_out_of_range(self):
        self.assert_input_error(self.sweep(self.trio(), "--min-recall", "2"))

    def test_unknown_matcher_is_a_usage_error(self):
        self.assertEqual(self.sweep(self.trio(), "--matcher", "nope")[0], 2)

    def test_example_files_are_valid(self):
        files = [os.path.join(DATA, f) for f in ("example_watchlist.csv", "example_customers.csv", "example_truth.csv")]
        self.assertEqual(self.sweep(files, "--min-recall", "0.6", "--max-false-alerts", "0.3")[0], 0)


if __name__ == "__main__":
    unittest.main()
