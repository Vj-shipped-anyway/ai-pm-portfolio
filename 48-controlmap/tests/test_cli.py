import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import controlmap as cm
from fixtures import CT_HEADER, OB_HEADER, TERMS_HEADER, control, write

OB = [["OB-1", "human oversight", "s", "credit_decision"]]
TERMS = [["human oversight", "override log"]]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cm.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def files(self, ob=OB, ctl=None, terms=TERMS):
        ctl = [control()] if ctl is None else ctl
        return (write(self.dir.name, "o.csv", OB_HEADER, ob), write(self.dir.name, "c.csv", CT_HEADER, ctl),
                write(self.dir.name, "t.csv", TERMS_HEADER, terms))

    def check(self, ob=OB, ctl=None, terms=TERMS, extra=()):
        o, c, t = self.files(ob, ctl, terms)
        return run(["check", o, c, "--terms", t, "--as-of", "2026-06-30"] + list(extra))

    def raw(self, name, data: bytes):
        path = os.path.join(self.dir.name, name)
        with open(path, "wb") as fh:
            fh.write(data)
        return path


class ExitCodeTests(CliCase):
    def test_demo_runs_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("statuses: COVERED 1, STALE 1, PARTIAL 1, UNCOVERED 2, UNMAPPED 1", out)

    def test_covered_exits_0(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0)
        self.assertIn("COVERED", out)

    def test_uncovered_exits_1_by_default_and_a_total_miss_is_said(self):
        code, out, _ = self.check(ctl=[control(name="Fire drill", desc="x")])
        self.assertEqual(code, 1)
        self.assertIn("note: no control matched any obligation", out)

    def test_stale_passes_by_default_and_fails_on_gap(self):
        self.assertEqual(self.check(ctl=[control(age=900)])[0], 0)
        self.assertEqual(self.check(ctl=[control(age=900)], extra=["--fail-on", "gap"])[0], 1)

    def test_unmapped_counts_as_uncovered_for_the_exit_code(self):
        self.assertEqual(self.check(terms=[["other theme", "override log"]])[0], 1)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.check(ctl=[control(name="Fire drill", desc="x")], extra=["--fail-on", "never"])[0], 0)

    def test_csv_format_has_one_row_per_obligation(self):
        _, out, _ = self.check(extra=["--format", "csv"])
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[0], ["obligation_id", "theme", "status", "controls", "reason"])
        self.assertEqual((len(rows), rows[1][2], rows[1][3]), (2, "COVERED", "CT-1"))

    def test_grace_option_changes_the_result(self):
        c = [control(cycle=100, age=151)]
        self.assertIn("STALE", self.check(ctl=c)[1])
        self.assertIn("COVERED", self.check(ctl=c, extra=["--grace", "2"])[1])


class BadInputTests(CliCase):
    def assert_exit_2(self, result):
        code, out, err = result
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertTrue(err.startswith("input error: "), err)
        self.assertNotIn("Traceback", err)

    def test_missing_file_and_directory(self):
        _, c, t = self.files()
        self.assert_exit_2(run(["check", os.path.join(self.dir.name, "nope.csv"), c, "--terms", t]))
        self.assert_exit_2(run(["check", self.dir.name, c, "--terms", t]))

    def test_empty_file(self):
        _, c, t = self.files()
        self.assert_exit_2(run(["check", self.raw("e.csv", b""), c, "--terms", t]))

    def test_header_only_files_say_no_rows(self):
        code, _, err = self.check(ob=[])
        self.assertEqual(code, 2)
        self.assertIn("no rows", err)
        self.assert_exit_2(self.check(ctl=[]))
        self.assert_exit_2(self.check(terms=[]))

    def test_wrong_type_json_in_place_of_csv(self):
        _, c, t = self.files()
        self.assert_exit_2(run(["check", self.raw("o.json", b'{"obligations": []}'), c, "--terms", t]))
        self.assert_exit_2(run(["check", self.raw("o2.json", b"[1, 2, 3]"), c, "--terms", t]))

    def test_binary_input(self):
        _, c, t = self.files()
        self.assert_exit_2(run(["check", self.raw("b.csv", b"\xff\xfe\x00\x01\x80\x81"), c, "--terms", t]))

    def test_truncated_and_overlong_rows(self):
        _, c, t = self.files()
        head = ",".join(OB_HEADER) + "\n"
        self.assert_exit_2(run(["check", self.raw("t.csv", (head + "OB-1,human oversight").encode()), c, "--terms", t]))
        self.assert_exit_2(run(["check", self.raw("x.csv", (head + "OB-1,human oversight,s,credit_decision,extra").encode()), c, "--terms", t]))

    def test_missing_column(self):
        o, _, t = self.files()
        self.assert_exit_2(run(["check", o, self.raw("c.csv", b"control_id,name\nCT-1,x\n"), "--terms", t]))

    def test_duplicate_ids(self):
        self.assert_exit_2(self.check(ob=OB + OB))
        self.assert_exit_2(self.check(ctl=[control(), control()]))

    def test_bad_control_fields(self):
        for bad in (control(cycle="x"), control(cycle=0), control(cycle=-5), control(status="paused"), control(scope=" ; "),
                    control(age=None)[:6] + ["2026-02-30", "active"], control(age=None)[:6] + ["30/06/2026", "active"],
                    control(age=None)[:6] + ["2027-01-01", "active"]):
            self.assert_exit_2(self.check(ctl=[bad]))

    def test_bad_obligation_and_terms_fields(self):
        self.assert_exit_2(self.check(ob=[["OB-1", "human oversight", "s", " ; "]]))
        self.assert_exit_2(self.check(ob=[["OB-1", "", "s", "credit_decision"]]))
        self.assert_exit_2(self.check(terms=[["human oversight", "!!!"]]))

    def test_bad_options(self):
        for extra in (["--grace", "abc"], ["--grace", "0"], ["--grace", "nan"], ["--grace", "inf"], ["--as-of", "yesterday"]):
            o, c, t = self.files()
            args = ["check", o, c, "--terms", t, "--as-of", "2026-06-30"] + extra
            self.assert_exit_2(run(args))


class HostileStringTests(CliCase):
    FORGED = "Real name\nOB-99   COVERED  forged line\r\x1b[31mred\x1b[0m ‮"

    def test_text_output_cannot_be_forged(self):
        ob = [["OB-1", "human oversight", "s", "credit_decision"], ["OB-2", "retired theme\nOB-98   COVERED  forged", "s", "credit_decision"]]
        ctl = [control(name=self.FORGED, desc="override log kept.", scope="credit_decision")]
        code, out, _ = self.check(ob=ob, ctl=ctl, extra=["--fail-on", "never"])
        self.assertEqual(code, 0)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\r", out)
        self.assertNotIn("‮", out)
        starts = [ln.split()[0] for ln in out.splitlines() if ln.startswith("OB-")]
        self.assertEqual(starts, ["OB-1", "OB-2"])
        self.assertIn("\\x1b[31mred", out)

    def test_errors_stay_on_one_line(self):
        code, _, err = self.check(ob=OB + [["OB-1\nforged line", "human oversight", "s", "credit_decision"]] + [["OB-1\nforged line", "x", "s", "credit_decision"]])
        self.assertEqual(code, 2)
        self.assertEqual(err.count("\n"), 1)

    def test_csv_cells_are_not_formulas(self):
        ob = [["=HYPERLINK(\"http://x\")", "@theme", "s", "credit_decision"], ["+1", "-2", "s", "credit_decision"]]
        _, out, _ = self.check(ob=ob, extra=["--format", "csv"])
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(len(rows), 3)
        for row in rows[1:]:
            self.assertNotIn(row[0][:1], "=+-@")
            self.assertNotIn(row[1][:1], "=+-@")
        self.assertEqual(rows[1][0], "'=HYPERLINK(\"http://x\")")

    def test_csv_output_survives_quotes_and_newlines(self):
        ctl = [control(name='He said "stop"\nnow', desc="override log kept.")]
        _, out, _ = self.check(ctl=ctl, extra=["--format", "csv"])
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(len(rows), 2)
        self.assertIn('He said "stop"\\nnow', rows[1][4])


if __name__ == "__main__":
    unittest.main()
