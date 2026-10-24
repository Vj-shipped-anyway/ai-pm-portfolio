import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import memo_tieout as mt

SPREAD = ("period,period_end,line,value,unit\n"
          "FY2023,2023-12-31,revenue,43850,usd_thousands\nFY2024,2024-12-31,revenue,47320,usd_thousands\n"
          "FY2023,2023-12-31,cash,3300,usd_thousands\nFY2024,2024-12-31,cash,4100,usd_thousands\n")
GOOD = "Revenue was [$47.3 million](spread:revenue/FY2024) and cash [$4.1 million](spread:cash/FY2024).\n"
BAD = "Revenue was [$43.9 million](spread:revenue/FY2024).\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = mt.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.spread = self.write("s.csv", SPREAD)

    def write(self, name, content, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(content)
        return p

    def one_line_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertNotIn("Traceback", err)
        return err

    def test_everything_tied_exits_0(self):
        code, out, _ = run(["check", self.write("m.md", GOOD), "--spread", self.spread])
        self.assertEqual(code, 0)
        self.assertIn("result: PASS", out)
        self.assertIn("2 read: 2 tie", out)

    def test_a_figure_that_does_not_tie_exits_1_and_names_the_line_and_column(self):
        code, out, _ = run(["check", self.write("m.md", BAD), "--spread", self.spread])
        self.assertEqual(code, 1)
        self.assertIn("line 1", out)
        self.assertIn("does not tie", out)
        self.assertIn("revenue/FY2023", out)
        self.assertIn("result: FAIL", out)

    def test_fail_on_never_reports_but_exits_0(self):
        code, out, _ = run(["check", self.write("m.md", BAD), "--spread", self.spread, "--fail-on", "never"])
        self.assertEqual(code, 0)
        self.assertIn("result: FAIL", out)

    def test_github_format_emits_error_annotations_with_position(self):
        _, out, _ = run(["check", self.write("m.md", BAD), "--spread", self.spread, "--format", "github"])
        first = out.splitlines()[0]
        self.assertTrue(first.startswith("::error file="), first)
        self.assertIn(",line=1,col=14,", first)
        self.assertTrue(out.splitlines()[-1].startswith("::notice"))

    def test_a_memo_with_no_figures_says_so_and_does_not_pass(self):
        memo = self.write("m.md", "# Memo\n\nRevenue was USD 47.3m.\n")
        code, out, _ = run(["check", memo, "--spread", self.spread])
        self.assertEqual(code, 1)
        self.assertIn("nothing was checked", out)
        self.assertIn("result: NOTHING CHECKED", out)
        _, gh, _ = run(["check", memo, "--spread", self.spread, "--format", "github"])
        self.assertIn("nothing was checked", gh)
        self.assertEqual(run(["check", memo, "--spread", self.spread, "--fail-on", "never"])[0], 0)

    def test_a_memo_of_only_terms_is_not_a_pass(self):
        code, out, _ = run(["check", self.write("m.md", "Loan of [$5.0 million](term:facility).\n"), "--spread", self.spread])
        self.assertEqual(code, 1)
        self.assertIn("NOTHING CHECKED", out)

    def test_malformed_inputs_exit_2_with_one_line(self):
        good = self.write("m.md", GOOD)
        header = "period,period_end,line,value,unit\n"
        self.one_line_error(["check", self.write("empty.md", ""), "--spread", self.spread])
        self.one_line_error(["check", self.write("blank.md", "\n  \n"), "--spread", self.spread])
        self.one_line_error(["check", good, "--spread", self.write("e.csv", "")])
        self.one_line_error(["check", good, "--spread", self.write("h.csv", header)])
        self.one_line_error(["check", good, "--spread", self.write("j.json", '{"revenue": 5}')])
        self.one_line_error(["check", good, "--spread", self.write("t.csv", header + "FY2024,2024-12-31,revenue,47320,usd_thousands\nFY20")])
        self.one_line_error(["check", good, "--spread", self.write("v.csv", header + "FY2024,2024-12-31,revenue,lots,usd_thousands\n")])
        self.one_line_error(["check", self.write("bin.md", b"\xff\xfe\x00\x01", "wb"), "--spread", self.spread])
        self.one_line_error(["check", self.write("nul.md", "a\x00b $5 million"), "--spread", self.spread])
        self.one_line_error(["check", os.path.join(self.dir.name, "none.md"), "--spread", self.spread])
        self.one_line_error(["check", self.dir.name, "--spread", self.spread])
        self.one_line_error(["check", good, "--spread", os.path.join(self.dir.name, "none.csv")])

    def test_an_unclosed_code_fence_exits_2(self):
        err = self.one_line_error(["check", self.write("f.md", "Revenue $5 million\n```\nnever closed\n"), "--spread", self.spread])
        self.assertIn("never closes", err)

    def test_usage_errors_exit_2(self):
        for args in (["check", "m.md"], ["check", "m.md", "--spread", "s.csv", "--format", "xml"], ["nonsense"]):
            code, out, err = run(args)
            self.assertEqual(code, 2, args)
            self.assertNotIn("Traceback", err)
        self.assertEqual(run([])[0], 2)

    def test_hostile_text_cannot_forge_an_annotation(self):
        memo = self.write("m.md", "[::error title=forged::approved 100% \r::error::x](spread:revenue/FY2024) then [$1 million](spread:cash/FY2024) %0A\n")
        _, out, _ = run(["check", memo, "--spread", self.spread, "--format", "github", "--fail-on", "never"])
        for ln in out.splitlines():
            self.assertTrue(ln.startswith(("::error file=", "::notice title=memo-tieout::")), ln)
        self.assertIn("%25", out)
        self.assertNotIn("\r", out)

    def test_hostile_file_name_is_escaped_in_the_annotation(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            mt.run_check(self.write("m.md", BAD), self.spread, "never", "github", shown_memo="a\n::error::forged,line=9.md")
        self.assertEqual(len(out.getvalue().splitlines()), 2)
        self.assertIn("a%0A%3A%3Aerror%3A%3Aforged%2Cline=9.md", out.getvalue())

    def test_text_output_strips_control_characters(self):
        memo = self.write("m.md", "[bad \x1b link](spread:revenue/FY2024)\n")
        _, out, _ = run(["check", memo, "--spread", self.spread])
        self.assertIn("bad   link", out)
        self.assertNotIn("\x1b", out)

    def test_demo_runs_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("ebitda/FY2024 recomputes to $7,120 thousand", out)
        self.assertIn("result: FAIL", out)


if __name__ == "__main__":
    unittest.main()
