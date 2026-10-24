import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import review_capacity as rc

HEADER = ",".join(rc.QUEUE_COLUMNS)
GOOD = "alerts,8,4,30,15,0.8,1,45,0.9,0.85,0.25,{held}"
LOG_HEADER = ",".join(rc.LOG_COLUMNS)


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def queues(self, *rows):
        return self.write("queues.csv", HEADER + "\n" + "\n".join(rows) + "\n")

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith("input error:") or err.startswith("usage error:"), err)
        self.assertNotIn("Traceback", err)
        return err


class SizeTests(CliTestCase):
    def test_demo_prints_a_table_and_a_decision(self):
        code, out, err = run(["--demo"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("morning_batch_review", out)
        self.assertTrue(out.strip().splitlines()[-1].startswith("decision: SHORT on 2 of 3"))

    def test_short_queue_exits_1(self):
        code, out, _ = run(["size", self.queues(GOOD.format(held=6))])
        self.assertEqual(code, 1)
        self.assertIn("SHORT by 4", out)

    def test_never_mode_exits_0(self):
        self.assertEqual(run(["size", self.queues(GOOD.format(held=6)), "--fail-on", "never"])[0], 0)

    def test_covered_queue_exits_0(self):
        code, out, _ = run(["size", self.queues(GOOD.format(held=10))])
        self.assertEqual(code, 0)
        self.assertIn("covered on all 1 queues", out)

    def test_no_headcount_is_said_and_not_silent(self):
        code, out, _ = run(["size", self.queues(GOOD.format(held=""))])
        self.assertEqual(code, 0)
        self.assertIn("nothing was compared", out)
        self.assertIn("nothing was compared", run(["size", self.queues(GOOD.format(held="")), "--format", "github"])[1])

    def test_github_format_annotates_a_short_queue(self):
        code, out, _ = run(["size", self.queues(GOOD.format(held=6)), "--format", "github"])
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("::error title=review-capacity::alerts: 6 on the roster, 10 needed (7 at the desk)"))

    def test_annotation_escapes_a_hostile_string(self):
        hostile = "x%\r\n::error::pwned"
        self.assertEqual(rc.escape_annotation(hostile), "x%25%0D%0A::error::pwned")
        self.assertNotIn("\n", rc.safe(hostile))
        self.assertNotIn("\r", rc.safe(hostile))
        self.assertEqual(rc.safe("a\x00b\x1bc"), "a?b?c")
        self.assertEqual(len(rc.safe("z" * 500)), 80)

    def test_hostile_queue_id_is_refused_on_one_line(self):
        for qid in ("::error::pwned", "a\n::error::pwned", "a%0Ab", "", "x" * 65):
            row = GOOD.replace("alerts", '"%s"' % qid.replace('"', '""'), 1).format(held=3)
            err = self.assert_input_error(["size", self.queues(row)])
            self.assertNotIn("\n::", err)

    def test_missing_file_and_directory(self):
        self.assert_input_error(["size", os.path.join(self.dir.name, "nope.csv")])
        self.assert_input_error(["size", self.dir.name])

    def test_empty_and_header_only(self):
        self.assert_input_error(["size", self.write("empty.csv", "")])
        self.assert_input_error(["size", self.write("head.csv", HEADER + "\n")])

    def test_missing_column(self):
        self.assert_input_error(["size", self.write("m.csv", "queue_id,hours_open\nq,8\n")])

    def test_truncated_row_and_extra_fields(self):
        self.assert_input_error(["size", self.queues("alerts,8,4,30,15")])
        self.assert_input_error(["size", self.queues(GOOD.format(held=3) + ",extra")])

    def test_wrong_type_and_out_of_range_values(self):
        bad = ["alerts,8,four,30,15,0.8,1,45,0.9,0.85,0.25,",       # not a number
               "alerts,8,4,30,15,0.8,1,45,1.2,0.85,0.25,",          # share above 1
               "alerts,8,4,30,15,0.8,1,45,0.9,0,0.25,",             # utilization cap of 0
               "alerts,8,4,30,15,0.8,1,45,0.9,0.85,1,",             # shrinkage of 100%
               "alerts,8,-4,30,15,0.8,1,45,0.9,0.85,0.25,",         # negative rate
               "alerts,8,4,30,0,0.8,1,45,0.9,0.85,0.25,",           # zero handling time
               "alerts,8,nan,30,15,0.8,1,45,0.9,0.85,0.25,",        # not finite
               "alerts,25,4,30,15,0.8,1,45,0.9,0.85,0.25,",         # shift longer than a day
               "alerts,8,4,30,15,0.8,1,45,0.9,0.85,0.25,2.5",       # fractional headcount
               "alerts,8,0,0,15,0.8,1,45,0.9,0.85,0.25,"]           # no work at all
        for row in bad:
            self.assert_input_error(["size", self.queues(row)])

    def test_duplicate_queue_id(self):
        self.assert_input_error(["size", self.queues(GOOD.format(held=3), GOOD.format(held=4))])

    def test_input_that_needs_more_than_the_limit(self):
        self.assert_input_error(["size", self.queues("alerts,8,100000,0,15,1,1,45,0.9,0.85,0.25,")])

    def test_not_text(self):
        self.assert_input_error(["size", self.write("bin.csv", b"\xff\xfe\x00\x01" * 50, mode="wb")])

    def test_usage_errors_are_one_line(self):
        self.assert_input_error(["size"])
        self.assert_input_error(["size", "q.csv", "--format", "xml"])
        self.assert_input_error(["fit", "log.csv", "--hours-open", "abc"])

    def test_no_command_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


class FitTests(CliTestCase):
    def log(self, *rows):
        return self.write("log.csv", LOG_HEADER + "\n" + "\n".join(rows) + "\n")

    def rows(self, queue="alerts", days=(1, 2)):
        out = []
        for d in days:
            out.append(f"{queue},{d},0.00,10.00,batch")
            out += [f"{queue},{d},{t}.00,{12 + t % 5}.00,live" for t in (5, 20, 33, 47, 71, 90)]
        return out

    def test_fit_output_feeds_size(self):
        code, out, err = run(["fit", self.log(*self.rows())])
        self.assertEqual(code, 0)
        self.assertIn("target columns are defaults", err)
        fitted = self.write("fitted.csv", out)
        with open(fitted, newline="", encoding="utf-8") as fh:
            row = next(csv.DictReader(fh))
        self.assertEqual((row["queue_id"], row["opening_batch"], row["arrivals_per_hour"]), ("alerts", "1.000", "0.750"))
        self.assertEqual(run(["size", fitted])[0], 0)

    def test_days_window(self):
        rows = self.rows(days=(1, 2, 3, 4))
        code, out, _ = run(["fit", self.log(*rows), "--days", "3-4"])
        self.assertEqual(code, 0)
        self.assertIn("alerts,8,0.750,1.000", out)

    def test_window_with_no_cases_is_an_error(self):
        self.assert_input_error(["fit", self.log(*self.rows()), "--days", "7-9"])

    def test_bad_days_and_bad_hours(self):
        for days in ("5-2", "abc", "0-3", "1-"):
            self.assert_input_error(["fit", self.log(*self.rows()), "--days", days])
        self.assert_input_error(["fit", self.log(*self.rows()), "--hours-open", "0"])
        self.assert_input_error(["fit", self.log(*self.rows()), "--hours-open", "nan"])

    def test_bad_log_rows(self):
        self.assert_input_error(["fit", self.write("e.csv", "")])
        self.assert_input_error(["fit", self.log("alerts,1,0.00,10.00,batchy")])
        self.assert_input_error(["fit", self.log("alerts,1,0.00,10.00")])
        self.assert_input_error(["fit", self.log("alerts,1.5,0.00,10.00,live")])
        self.assert_input_error(["fit", self.log("alerts,1,-3,10.00,live")])
        self.assert_input_error(["fit", self.log("alerts,1,0,0,live")])
        self.assert_input_error(["fit", self.log("::error::x,1,0.00,10.00,live")])

    def test_two_queues_are_fitted_separately_and_sorted(self):
        code, out, _ = run(["fit", self.log(*(self.rows("zeta") + self.rows("alpha")))])
        self.assertEqual(code, 0)
        self.assertEqual([ln.split(",")[0] for ln in out.splitlines()[1:]], ["alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
