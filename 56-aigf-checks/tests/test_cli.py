import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import aigf_checks as ac

RISKS = [("risk_id", "title", "aspects"), ("R-1", "t", "a;b"), ("R-2", "u", "z")]
CHECKS = [("check_id", "project", "command", "exercises"), ("C-1", "p", "cmd", "a;b")]
CROSSWALK = [("row_id", "risk_id", "check_id", "covers", "claim_label", "claim_value", "note"),
             ("ROW-1", "R-1", "C-1", "full", "caught", "25 of 25", "")]
OUTPUTS = {"C-1": "  caught: 25 of 25\n"}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ac.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def csv(self, name, rows):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, lineterminator="\n").writerows(rows)
        return self.path(name)

    def raw(self, name, text, mode="w"):
        with open(self.path(name), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return self.path(name)

    def files(self, risks=RISKS, checks=CHECKS, crosswalk=CROSSWALK, outputs=OUTPUTS):
        out = self.raw("o.json", json.dumps(outputs)) if not isinstance(outputs, str) else self.raw("o.json", outputs)
        return [self.csv("r.csv", risks), self.csv("c.csv", checks), self.csv("x.csv", crosswalk), out]

    def check(self, *extra, **kw):
        return run(["check"] + self.files(**kw) + list(extra))

    def assert_input_error(self, **kw):
        code, out, err = self.check(**kw)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_clean_crosswalk_exits_0(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)
        self.assertIn("R-2 GAP", out)

    def test_a_finding_exits_1_and_never_keeps_0(self):
        bad = [CROSSWALK[0], ("ROW-1", "R-1", "C-1", "full", "caught", "24 of 25", "")]
        self.assertEqual(self.check(crosswalk=bad)[0], 1)
        code, out, _ = self.check("--fail-on", "never", crosswalk=bad)
        self.assertEqual(code, 0)
        self.assertIn("stale_value", out)

    def test_github_format_uses_error_for_a_stale_claim_and_warning_for_a_note(self):
        bad = [CROSSWALK[0], ("ROW-1", "R-1", "C-1", "full", "caught", "24 of 25", "Certified."), ]
        _, out, _ = self.check("--format", "github", crosswalk=bad)
        self.assertIn("::error title=aigf-checks stale_value::", out)
        self.assertIn("::warning title=aigf-checks overclaim_wording::", out)
        self.assertIn("::notice title=aigf-checks::2 findings in 1 of 1 rows", out)

    def test_malformed_input_exits_2_with_one_line(self):
        self.assert_input_error(risks=[])                                       # empty file
        self.assert_input_error(risks=[RISKS[0]])                               # header only
        self.assert_input_error(crosswalk=[CROSSWALK[0]])                       # nothing to check
        self.assert_input_error(outputs=["not", "an", "object"])                # wrong type
        self.assert_input_error(outputs='{"C-1": "caught: 25 of')               # truncated json
        self.assert_input_error(outputs={"C-1": 5})                             # wrong value type
        self.assert_input_error(crosswalk=[CROSSWALK[0], ("ROW-1", "R-1", "C-1")])   # truncated row
        self.assert_input_error(risks=[("risk_id", "title"), ("R-1", "t")])     # missing column
        self.assert_input_error(risks=RISKS + [RISKS[1]])                       # duplicate id
        self.assert_input_error(risks=[RISKS[0], ("R-1", "t", " ; ")])          # no aspects
        self.assert_input_error(crosswalk=[CROSSWALK[0], ("ROW-1", "R-1", "C-1", "mostly", "caught", "25 of 25", "")])
        self.assert_input_error(crosswalk=[CROSSWALK[0], ("ROW-1", "R-1", "C-1", "full", "", "25 of 25", "")])

    def test_missing_and_binary_files_exit_2(self):
        self.assertEqual(run(["check", "no1.csv", "no2.csv", "no3.csv", "no4.json"])[0], 2)
        files = self.files()
        files[0] = self.raw("bin.csv", b"\xff\xfe\x00\x01", mode="wb")
        code, _, err = run(["check"] + files)
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("input error: "))

    def test_no_output_at_all_says_so_instead_of_passing_quietly(self):
        code, out, _ = self.check(outputs={})
        self.assertEqual(code, 1)
        self.assertIn("no_output", out)
        self.assertIn("no number was verified", out)

    def test_hostile_values_cannot_forge_a_command_or_a_line(self):
        hostile = "ROW-1\n::error title=forged::approved\r%"
        bad = [CROSSWALK[0], (hostile, "R-1", "C-1", "full", "caught", "24 of 25", "")]
        _, gh, _ = self.check("--format", "github", crosswalk=bad)
        commands = [ln for ln in gh.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 2)            # the finding and the notice, nothing forged
        self.assertIn("%0A", commands[0])
        self.assertIn("%25", commands[0])
        _, text, _ = self.check(crosswalk=bad)
        self.assertEqual(sum(1 for ln in text.splitlines() if ln.startswith("::")), 0)
        self.assertEqual(len(text.splitlines()), 4)

    def test_demo_runs_and_exits_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        for kind in ("stale_value", "aspect_gap", "duplicate_row", "overclaim_wording"):
            self.assertIn(kind, out)
        self.assertIn("risk status: R-01 CHECKED, R-02 UNVERIFIED, R-09 CHECKED, R-15 PARTIAL", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


class SignoffTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def msg(self, text):
        p = os.path.join(self.dir.name, "m.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_signed_message_passes(self):
        code, out, _ = run(["signoff", self.msg("Add a crosswalk table\n\nBody.\n\nSigned-off-by: A Person <a.person@example.org>\n")])
        self.assertEqual(code, 0)
        self.assertIn("ok", out)

    def test_missing_trailer_fails(self):
        code, out, _ = run(["signoff", self.msg("Add a crosswalk table\n\nBody.\n")])
        self.assertEqual(code, 1)
        self.assertIn("git commit -s", out)

    def test_malformed_trailer_and_long_subject_fail(self):
        code, out, _ = run(["signoff", self.msg("x" * 73 + "\n\nSigned-off-by: A Person a.person@example.org\n")])
        self.assertEqual(code, 1)
        self.assertIn("73 characters", out)
        self.assertIn("line 3", out)

    def test_hostile_message_text_is_not_echoed(self):
        code, out, _ = run(["signoff", self.msg("::error title=forged::x\n\nSigned-off-by: ::error <bad>\n")])
        self.assertEqual(code, 1)
        self.assertNotIn("::error", out)

    def test_empty_missing_and_binary_files_exit_2(self):
        self.assertEqual(run(["signoff", self.msg("  \n")])[0], 2)
        self.assertEqual(run(["signoff", os.path.join(self.dir.name, "nope.txt")])[0], 2)
        p = os.path.join(self.dir.name, "b.txt")
        with open(p, "wb") as fh:
            fh.write(b"\xff\xfe\x00")
        self.assertEqual(run(["signoff", p])[0], 2)


if __name__ == "__main__":
    unittest.main()
