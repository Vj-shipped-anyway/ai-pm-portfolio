import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import claims_check as cc

G = "\U0001F7E2"
README = f"- {G} Routed: 25 of 40\n- {G} Median days: 3.4\n"
GOOD = "routed: 25 of 40\nmedian days: 3.4\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, content, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(content)
        return p

    def one_line_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertNotIn("Traceback", err)
        return err

    def test_everything_printed_exits_0(self):
        code, out, _ = run(["check", self.write("r.md", README), "--evidence", self.write("e.txt", GOOD)])
        self.assertEqual(code, 0)
        self.assertIn("result: PASS", out)

    def test_an_unsupported_number_exits_1_and_names_the_line(self):
        code, out, _ = run(["check", self.write("r.md", README), "--evidence", self.write("e.txt", "routed: 25 of 40\nmedian days: 3.42\n")])
        self.assertEqual(code, 1)
        self.assertIn('line 2', out)
        self.assertIn('"3.4"', out)
        self.assertIn("result: FAIL", out)

    def test_fail_on_never_reports_but_exits_0(self):
        code, out, _ = run(["check", self.write("r.md", README), "--evidence", self.write("e.txt", "nothing: 12\n"), "--fail-on", "never"])
        self.assertEqual(code, 0)
        self.assertIn("result: FAIL", out)

    def test_truncated_evidence_is_a_finding_not_a_crash(self):
        code, out, err = run(["check", self.write("r.md", README), "--evidence", self.write("e.txt", "routed: 25 of 4")])
        self.assertEqual((code, err), (1, ""))
        self.assertIn("not supported", out)

    def test_evidence_glob_and_several_patterns(self):
        self.write("a.txt", "routed: 25 of 40\n")
        self.write("b.txt", "median days: 3.4\n")
        pattern = os.path.join(self.dir.name, "*.txt")
        code, out, _ = run(["check", self.write("r.md", README), "--evidence", pattern])
        self.assertEqual(code, 0)
        self.assertIn("against 2 evidence files", out)
        both = os.path.join(self.dir.name, "a.txt") + "\n" + os.path.join(self.dir.name, "b.txt")
        self.assertEqual(run(["check", os.path.join(self.dir.name, "r.md"), "--evidence", both])[0], 0)

    def test_pattern_that_matches_nothing_exits_2(self):
        err = self.one_line_error(["check", self.write("r.md", README), "--evidence", os.path.join(self.dir.name, "none*.txt")])
        self.assertIn("no evidence file matches", err)

    def test_missing_directory_and_empty_inputs_exit_2(self):
        r, e = self.write("r.md", README), self.write("e.txt", GOOD)
        self.one_line_error(["check", os.path.join(self.dir.name, "nope.md"), "--evidence", e])
        self.one_line_error(["check", self.dir.name, "--evidence", e])
        self.one_line_error(["check", self.write("blank.md", "  \n\n"), "--evidence", e])
        self.one_line_error(["check", r, "--evidence", self.write("blank.txt", "")])
        self.one_line_error(["check", r, "--evidence", self.dir.name])

    def test_wrong_type_and_truncated_files_exit_2(self):
        e = self.write("e.txt", GOOD)
        cut = (README.encode("utf-8"))[:5]       # ends inside the 4-byte circle
        self.one_line_error(["check", self.write("cut.md", cut, "wb"), "--evidence", e])
        self.one_line_error(["check", self.write("bin.md", b"\x89PNG\r\n\x00\x00", "wb"), "--evidence", e])
        self.one_line_error(["check", self.write("nul.md", "ok\x00ok"), "--evidence", e])
        self.one_line_error(["check", self.write("r.md", README), "--evidence", self.write("bad.txt", b"\xff\xfe\xfa", "wb")])

    def test_usage_errors_are_one_line_and_exit_2(self):
        r = self.write("r.md", README)
        self.one_line_error(["check", r])
        self.one_line_error(["check", r, "--evidence", "x", "--min-digits", "0"])
        self.one_line_error(["check", r, "--evidence", "x", "--min-digits", "two"])

    def test_no_green_numbers_says_so_instead_of_passing_silently(self):
        code, out, _ = run(["check", self.write("r.md", "# Title\n\n- plain 12\n"), "--evidence", self.write("e.txt", GOOD)])
        self.assertEqual(code, 0)
        self.assertIn("nothing was checked", out)
        self.assertIn("result: NOTHING CHECKED", out)
        _, gh, _ = run(["check", os.path.join(self.dir.name, "r.md"), "--evidence", os.path.join(self.dir.name, "e.txt"), "--format", "github"])
        self.assertTrue(gh.startswith("::warning"))

    def test_only_short_numbers_also_says_nothing_was_checked(self):
        code, out, _ = run(["check", self.write("r.md", f"- {G} 7 tools\n"), "--evidence", self.write("e.txt", GOOD)])
        self.assertEqual(code, 0)
        self.assertIn("1 skipped", out)
        self.assertIn("result: NOTHING CHECKED", out)

    def test_github_format_emits_one_error_per_unsupported_claim(self):
        code, out, _ = run(["check", self.write("r.md", README), "--evidence", self.write("e.txt", "nothing: 12\n"), "--format", "github"])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual([ln.split(" ")[0] for ln in lines], ["::error", "::error", "::notice"])
        self.assertIn(",line=1,", lines[0])

    def test_hostile_readme_path_cannot_forge_a_workflow_command(self):
        hostile = self.write("r%e,a:d\n::error title=forged::approved.md", README)
        e = self.write("e.txt", "nothing: 12\n")
        _, out, _ = run(["check", hostile, "--evidence", e, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))        # no line the path could have started
        self.assertEqual(len(commands), 3)
        self.assertIn("%0A", commands[0])
        self.assertIn("%25", commands[0])
        self.assertIn("%2C", commands[0])
        self.assertIn("%3A", commands[0])
        _, text, _ = run(["check", hostile, "--evidence", e, "--fail-on", "never"])
        self.assertEqual(len(text.splitlines()), 5)                   # header, 2 findings, claims, result

    def test_hostile_text_in_error_messages_stays_on_one_line(self):
        err = self.one_line_error(["check", self.write("r.md", README), "--evidence", "no\n::error::forged*.txt"])
        self.assertNotIn("\n::", err)
        err = self.one_line_error(["check", os.path.join(self.dir.name, "x\r\n::error::y.md"), "--evidence", "e"])
        self.assertTrue(err.startswith("input error:"))

    def test_escape_helpers(self):
        self.assertEqual(cc.escape_data("a%b\r\nc"), "a%25b%0D%0Ac")
        self.assertEqual(cc.escape_property("a:b,c"), "a%3Ab%2Cc")

    def test_demo_runs_and_reports_the_planted_problems(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("6 checked, 3 supported, 3 not supported, 1 skipped", out)
        self.assertIn("result: FAIL", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
