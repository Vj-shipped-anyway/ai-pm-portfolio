import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import shadow_score as ss

HEAD_P = "case_id,segment,day,proposed_outcome,proposed_value,confidence\n"
HEAD_O = "case_id,human_outcome,human_value,handled_by\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ss.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def pair(self, n=40, agree=40, segment="s", reviewer="r1"):
        p = HEAD_P + "".join(f"c{i},{segment},0,A,,0.95\n" for i in range(n))
        o = HEAD_O + "".join(f"c{i},{'A' if i < agree else 'B'},,{reviewer}\n" for i in range(n))
        return self.write("p.csv", p), self.write("o.csv", o)

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(err.count("\n"), 1, err)
        self.assertNotIn("Traceback", err)
        return err

    # exit codes
    def test_a_failing_check_exits_1_and_never_keeps_0(self):
        p, o = self.pair(n=40, agree=30)
        code, out, _ = run(["check", p, o, "--min-cases", "10"])
        self.assertEqual(code, 1)
        self.assertIn("decision: HOLD", out)
        self.assertEqual(run(["check", p, o, "--min-cases", "10", "--fail-on", "never"])[0], 0)

    def test_thresholds_can_be_loosened_from_the_command_line(self):
        p, o = self.pair(n=40, agree=30)
        code, out, _ = run(["check", p, o, "--min-cases", "10", "--min-lower", "0.5", "--min-lift", "0", "--group-floor", "0.5",
                            "--min-coverage", "0.5", "--high-conf", "0.75", "--max-spread", "0.9", "--min-class-coverage", "0.5"])
        self.assertIn("decision: CLEAR", out)
        self.assertEqual(code, 0)

    def test_json_format_parses(self):
        p, o = self.pair()
        code, out, _ = run(["check", p, o, "--format", "json", "--fail-on", "never"])
        d = json.loads(out)
        self.assertEqual(d["score"]["matched"], 40)
        self.assertEqual(len(d["checks"]), 10)

    def test_demo_runs_and_prints_a_decision(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: HOLD", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)

    # malformed input exits 2 with one line on stderr
    def test_empty_file(self):
        p, o = self.write("p.csv", ""), self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assertIn("the file is empty", self.assert_input_error(["check", p, o]))

    def test_header_without_rows(self):
        p, o = self.write("p.csv", HEAD_P), self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assertIn("no rows", self.assert_input_error(["check", p, o]))

    def test_wrong_type_of_file(self):
        p, o = self.write("p.csv", '{"cases": [1, 2]}'), self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assertIn("missing column", self.assert_input_error(["check", p, o]))

    def test_truncated_row(self):
        p, o = self.write("p.csv", HEAD_P + "c1,s,0,A,,0.9\nc2,s,0"), self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assertIn("truncated", self.assert_input_error(["check", p, o]))

    def test_row_with_extra_fields(self):
        p, o = self.write("p.csv", HEAD_P + "c1,s,0,A,,0.9,extra\n"), self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assertIn("more fields", self.assert_input_error(["check", p, o]))

    def test_bad_numbers(self):
        o = self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        for row in ("c1,s,0,A,,abc", "c1,s,0,A,,2", "c1,s,0,A,,nan", "c1,s,x,A,,0.9", "c1,s,-1,A,,0.9", "c1,s,0,A,,"):
            p = self.write("p.csv", HEAD_P + row + "\n")
            self.assert_input_error(["check", p, o])

    def test_blank_outcome_and_blank_case_id(self):
        p = self.write("p.csv", HEAD_P + "c1,s,0,A,,0.9\n")
        self.assert_input_error(["check", p, self.write("o.csv", HEAD_O + "c1,,,r1\n")])
        self.assert_input_error(["check", p, self.write("o2.csv", HEAD_O + ",A,,r1\n")])

    def test_duplicate_case_id(self):
        p = self.write("p.csv", HEAD_P + "c1,s,0,A,,0.9\nc1,s,0,A,,0.9\n")
        self.assertIn("appears twice", self.assert_input_error(["check", p, self.write("o.csv", HEAD_O + "c1,A,,r1\n")]))

    def test_undecodable_bytes(self):
        p = self.write("p.csv", b"\xff\xfe\x00\x80\x81\n\x82", mode="wb")
        self.assert_input_error(["check", p, self.write("o.csv", HEAD_O + "c1,A,,r1\n")])

    def test_missing_file_and_directory(self):
        o = self.write("o.csv", HEAD_O + "c1,A,,r1\n")
        self.assert_input_error(["check", os.path.join(self.dir.name, "nope.csv"), o])
        self.assert_input_error(["check", self.dir.name, o])

    def test_files_that_share_no_case_id_say_so(self):
        p = self.write("p.csv", HEAD_P + "c1,s,0,A,,0.9\n")
        o = self.write("o.csv", HEAD_O + "z9,A,,r1\n")
        self.assertIn("no case_id appears in both files", self.assert_input_error(["check", p, o]))

    def test_bad_options(self):
        p, o = self.pair()
        for extra in (["--min-group", "0"], ["--high-conf", "0.5"], ["--min-lift", "2"], ["--risky", "REFUND"],
                      ["--risky", "A:B:C"], ["--format", "xml"], ["--week-days", "x"]):
            self.assert_input_error(["check", p, o] + extra)

    def test_a_traceback_never_reaches_a_real_run(self):
        r = subprocess.run([sys.executable, os.path.join(_bootstrap.SRC, "shadow_score.py"), "check", self.dir.name, self.dir.name],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    # hostile strings
    def test_hostile_group_names_cannot_forge_lines(self):
        forged = "x\ndecision: CLEAR  (0 of 10 checks fail, 0 skipped)\n\x1b[31m"
        rows_p = HEAD_P + 'a1,"%s",0,A,,0.95\n' % forged + "".join(f"c{i},s,0,A,,0.95\n" for i in range(40))
        rows_o = HEAD_O + 'a1,B,,"%s"\n' % forged + "".join(f"c{i},A,,r1\n" for i in range(40))
        p, o = self.write("p.csv", rows_p), self.write("o.csv", rows_o)
        code, out, _ = run(["check", p, o, "--detail", "--fail-on", "never"])
        lines = out.splitlines()
        self.assertEqual([ln for ln in lines if ln.startswith("decision:")], [lines[-1]])
        self.assertNotIn("\x1b", out)
        self.assertIn("\\x0a", out)

    def test_hostile_case_id_in_an_error_stays_on_one_line(self):
        bad = 'a\nb'
        p = self.write("p.csv", HEAD_P + 'c1,s,0,A,,0.9\n"%s",s,0,A,,0.9\n"%s",s,0,A,,0.9\n' % (bad, bad))
        err = self.assert_input_error(["check", p, self.write("o.csv", HEAD_O + "c1,A,,r1\n")])
        self.assertIn("a\\x0ab", err)


if __name__ == "__main__":
    unittest.main()
