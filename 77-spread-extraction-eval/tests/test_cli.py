import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import spread_eval as se


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = se.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.docs = self.write("docs.csv", [["doc_id", "layout"], ["D1", "alpha"], ["D2", "alpha"], ["D3", "beta"]])
        rows = [["doc_id", "field", "period", "value"]]
        for d in ("D1", "D2", "D3"):
            rows += [[d, "revenue", "current", "1000"], [d, "revenue", "prior", "900"]]
        self.truth = self.write("truth.csv", rows)
        self.good = self.write("good.csv", rows)

    def write(self, name, rows):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows(rows)
        return p

    def score(self, pred, *extra):
        return run(["score", "--docs", self.docs, "--truth", self.truth, "--predictions", pred, "--min-docs", "1", *extra])

    def test_pass_exits_0(self):
        code, out, _ = self.score(self.good)
        self.assertEqual(code, 0)
        self.assertIn("): PASS", out)

    def test_failing_gate_exits_1_and_names_the_layout(self):
        bad = self.write("bad.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "current", "1000"],
                                     ["D1", "revenue", "prior", "900"], ["D2", "revenue", "current", "1000"],
                                     ["D2", "revenue", "prior", "900"], ["D3", "revenue", "current", "1"], ["D3", "revenue", "prior", "0.9"]])
        code, out, _ = self.score(bad)
        self.assertEqual(code, 1)
        self.assertIn("beta: 0.0% is below the floor of 95.0%", out)

    def assert_exit_2(self, pred, *extra):
        code, out, err = self.score(pred, *extra)
        self.assertEqual(code, 2, out + err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_empty_file(self):
        p = os.path.join(self.dir.name, "empty.csv")
        open(p, "w").close()
        self.assert_exit_2(p)

    def test_header_only(self):
        self.assert_exit_2(self.write("h.csv", [["doc_id", "field", "period", "value"]]))

    def test_wrong_type_value(self):
        self.assert_exit_2(self.write("w.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "current", "abc"]]))

    def test_not_finite_value(self):
        self.assert_exit_2(self.write("n.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "current", "nan"]]))

    def test_truncated_row(self):
        self.assert_exit_2(self.write("t.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue"]]))

    def test_missing_column(self):
        self.assert_exit_2(self.write("c.csv", [["doc_id", "field", "value"], ["D1", "revenue", "1"]]))

    def test_missing_file(self):
        self.assert_exit_2(os.path.join(self.dir.name, "nope.csv"))

    def test_invalid_utf8(self):
        p = os.path.join(self.dir.name, "bin.csv")
        with open(p, "wb") as fh:
            fh.write(b"doc_id,field,period,value\n\xff\xfe\x00,x,current,1\n")
        self.assert_exit_2(p)

    def test_duplicate_row(self):
        self.assert_exit_2(self.write("d.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "current", "1"],
                                                ["D1", "revenue", "current", "2"]]))

    def test_bad_period(self):
        self.assert_exit_2(self.write("p.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "next", "1"]]))

    def test_predictions_that_match_nothing_are_not_a_silent_pass(self):
        code, out, err = self.score(self.write("z.csv", [["doc_id", "field", "period", "value"], ["Q9", "revenue", "current", "1"]]))
        self.assertEqual(code, 2)
        self.assertIn("no prediction row matches", err)

    def test_empty_value_means_no_prediction(self):
        p = self.write("e.csv", [["doc_id", "field", "period", "value"], ["D1", "revenue", "current", ""], ["D1", "revenue", "prior", "900"]])
        code, out, _ = self.score(p)
        self.assertEqual(code, 1)
        self.assertIn("no prediction 5", out)

    def test_bad_thresholds(self):
        self.assert_exit_2(self.good, "--floor", "101")
        self.assert_exit_2(self.good, "--max-gap", "-1")

    def test_usage_errors_exit_2_in_one_line(self):
        for args in (["score"], ["predict", "--extractor", "nope", "--docs", "x"], ["--bogus"]):
            code, out, err = run(args)
            self.assertEqual(code, 2, args)
            self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertEqual(run([])[0], 2)

    def test_duplicate_or_empty_doc_fields_in_the_docs_file(self):
        for rows in ([["doc_id", "layout"], ["D1", "a"], ["D1", "b"]], [["doc_id", "layout"], ["D1", ""]]):
            code, _, err = run(["score", "--docs", self.write("bd.csv", rows), "--truth", self.truth, "--predictions", self.good])
            self.assertEqual(code, 2)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_hostile_strings_cannot_start_a_new_log_line_or_command(self):
        hostile = "x\n::error::pwned\r%0A"
        docs = self.write("hdocs.csv", [["doc_id", "layout"], ["D1", hostile], ["D2", hostile], ["D3", hostile]])
        code, out, err = run(["score", "--docs", docs, "--truth", self.truth, "--predictions", self.good, "--min-docs", "1"])
        self.assertEqual(code, 0)
        self.assertFalse(any(line.lstrip().startswith("::") for line in out.splitlines()), out)
        self.assertIn("%0A", out)
        self.assertNotIn("\r", out)
        bad = self.write("hbad.csv", [["doc_id", "field", "period", "value"], [hostile, "revenue", "current", "abc"]])
        code, out, err = run(["score", "--docs", docs, "--truth", self.truth, "--predictions", bad])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\r", err)

    def test_demo_exits_0_and_prints_the_gate(self):
        code, out, err = run(["--demo"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("gate (floor 95.0%", out)

    def test_predict_round_trip(self):
        data = os.path.join(os.path.dirname(os.path.abspath(se.__file__)), "..", "data", "statements.csv")
        code, out, _ = run(["predict", "--extractor", "alias_aware", "--docs", data])
        self.assertEqual(code, 0)
        p = os.path.join(self.dir.name, "pred.csv")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(out)
        docs = se.load_docs(data, need_text=True)
        self.assertEqual(se.load_predictions(p), {k: float(v) for k, v in se.predictions_for(se.EXTRACTORS["alias_aware"], docs).items()})

    def test_predict_needs_a_text_column(self):
        code, _, err = run(["predict", "--extractor", "fixed_label", "--docs", self.docs])
        self.assertEqual(code, 2)
        self.assertIn("missing column(s) text", err)


if __name__ == "__main__":
    unittest.main()
