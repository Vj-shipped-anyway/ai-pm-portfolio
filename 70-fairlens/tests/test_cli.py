"""The command line: exit codes, bad input, hostile strings, and the silent-no-op rule."""
import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import fairlens_pack as fp

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
EXAMPLE = os.path.join(DATA, "example_scores.csv")
HEAD = ["group", "score", "bad_outcome", "postcode_points", "reason_1", "reason_2", "reason_3"]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = fp.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, rows, head=HEAD):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(head)
            w.writerows(rows)
        return p

    def raw(self, name, data: bytes):
        p = os.path.join(self.dir.name, name)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    def two_groups(self, b_name="B", n=40):
        rows = [["A", 100 + i, 0, 5, "R1", "R2", "R3"] for i in range(n)]
        rows += [[b_name, 60 + i, 1 if i % 3 == 0 else 0, 5, "R1", "R2", "R3"] for i in range(n)]
        return self.write("two.csv", rows)

    def assert_exit_2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_demo_runs_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("overall: FAIL", out)

    def test_bundled_example_exits_1_when_overall_is_fail(self):
        args = ["check", EXAMPLE, "--cutoff", "126", "--proxy-column", "postcode_points", "--proxy-code", "R05"]
        self.assertEqual(run(args)[0], 1)
        self.assertEqual(run(args + ["--fail-on", "never"])[0], 0)

    def test_fail_on_review_exits_1_on_the_example(self):
        args = ["check", EXAMPLE, "--cutoff", "126", "--fail-on", "review"]
        self.assertEqual(run(args)[0], 1)

    def test_same_input_same_output(self):
        path = self.two_groups()
        self.assertEqual(run(["check", path, "--cutoff", "100"]), run(["check", path, "--cutoff", "100"]))

    def test_missing_optional_columns_are_reported_not_skipped_silently(self):
        path = self.write("plain.csv", [["A", 100 + i, 0] for i in range(30)] + [["B", 80 + i, 1] for i in range(30)],
                          head=["group", "score", "bad_outcome"])
        code, out, _ = run(["check", path, "--cutoff", "100"])
        self.assertIn("NOT RUN", out)
        self.assertIn("not run: T4, T5, T6", out)
        self.assertEqual(code, 1 if "overall: FAIL" in out else 0)

    def test_empty_file_exits_2(self):
        self.assert_exit_2(["check", self.raw("empty.csv", b""), "--cutoff", "1"])

    def test_header_only_exits_2(self):
        self.assert_exit_2(["check", self.write("h.csv", []), "--cutoff", "1"])

    def test_missing_file_and_directory_exit_2(self):
        self.assert_exit_2(["check", os.path.join(self.dir.name, "nope.csv"), "--cutoff", "1"])
        self.assert_exit_2(["check", self.dir.name, "--cutoff", "1"])

    def test_binary_file_exits_2(self):
        self.assert_exit_2(["check", self.raw("bin.csv", b"\xff\xfe\x00\x01group"), "--cutoff", "1"])

    def test_missing_required_column_exits_2(self):
        self.assert_exit_2(["check", self.write("nc.csv", [["A", 1]], head=["group", "score"]), "--cutoff", "1"])

    def test_wrong_type_values_exit_2(self):
        for bad in (["A", "high", 0], ["A", "nan", 0], ["A", "inf", 0], ["A", 5, 2], ["", 5, 0]):
            path = self.write("w.csv", [bad, ["B", 5, 0]], head=["group", "score", "bad_outcome"])
            self.assert_exit_2(["check", path, "--cutoff", "1"])

    def test_truncated_row_exits_2(self):
        path = self.raw("t.csv", b"group,score,bad_outcome\nA,100,0\nB,90")
        self.assert_exit_2(["check", path, "--cutoff", "1"])

    def test_one_group_exits_2(self):
        path = self.write("one.csv", [["A", 5, 0], ["A", 6, 1]], head=["group", "score", "bad_outcome"])
        self.assert_exit_2(["check", path, "--cutoff", "1"])

    def test_cutoff_that_approves_nobody_exits_2(self):
        self.assert_exit_2(["check", self.two_groups(), "--cutoff", "9999"])

    def test_bad_options_exit_2(self):
        path = self.two_groups()
        self.assert_exit_2(["check", path])
        self.assert_exit_2(["check", path, "--cutoff", "abc"])
        self.assert_exit_2(["check", path, "--cutoff", "nan"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--resamples", "3"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--seed", "x"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--proxy-code", "R05"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--proxy-column", "nope"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--reason-columns", "reason_1,nope"])
        self.assert_exit_2(["check", path, "--cutoff", "100", "--format", "xml"])

    def test_no_command_exits_2(self):
        self.assertEqual(run([])[0], 2)

    def test_hostile_group_name_cannot_forge_an_annotation(self):
        hostile = "B\n::error title=forged::approved\r%0A"
        path = self.two_groups(b_name=hostile)
        code, out, _ = run(["check", path, "--cutoff", "100", "--proxy-column", "postcode_points", "--proxy-code", "R05",
                            "--format", "github", "--fail-on", "never"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertTrue(lines)
        for ln in lines:
            self.assertTrue(ln.startswith(("::error title=fairlens ", "::warning title=fairlens ", "::notice title=fairlens::")), ln)
        self.assertNotIn("\n::error title=forged", out)
        self.assertNotIn("\r", out)
        self.assertIn("%25", out)                       # the percent sign in the name was escaped

    def test_hostile_group_name_is_escaped_in_text_output(self):
        path = self.two_groups(b_name="B\x1b[31m\nfake line")
        _, out, _ = run(["check", path, "--cutoff", "100", "--fail-on", "never"])
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\nfake line", out)

    def test_hostile_path_in_error_is_one_line(self):
        code, _, err = run(["check", "no\nsuch\r::error::file.csv", "--cutoff", "1"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_helpers_escape_workflow_command_characters(self):
        self.assertEqual(fp.gh_data("a%b\r\nc"), "a%25b%0D%0Ac")
        self.assertEqual(fp.gh_prop("a:b,c"), "a%3Ab%2Cc")
        self.assertEqual(fp.clean("x\ny"), "x\\x0ay")


if __name__ == "__main__":
    unittest.main()
