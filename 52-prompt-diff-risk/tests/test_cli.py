import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import prompt_diff_risk as pdr

OLD = "# t\n\n## Rules\n- Never share the secret code.\n- Keep a calm, polite tone.\n- You can call look_up to read a balance.\n"
TOOLS = [{"name": "look_up", "access": "read"}, {"name": "pay_out", "access": "write"}]
PROBES = "probe_id,slice,question\nP1,pii_refusal,q1\nP2,pii_refusal,q2\nP3,tone_register,q3\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = pdr.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, binary=False):
        p = os.path.join(self.dir.name, name)
        with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def pair(self, new_text):
        return self.write("old.txt", OLD), self.write("new.txt", new_text)

    def test_removed_rule_exits_1(self):
        o, n = self.pair(OLD.replace("- Never share the secret code.\n", ""))
        code, out, _ = run(["check", o, n])
        self.assertEqual(code, 1)
        self.assertIn("decision: BLOCK", out)

    def test_review_passes_by_default_and_fails_on_request(self):
        o, n = self.pair(OLD.replace("calm, polite", "casual, playful"))
        self.assertEqual(run(["check", o, n])[0], 0)
        code, out, _ = run(["check", o, n, "--fail-on", "review"])
        self.assertEqual(code, 1)
        self.assertIn("decision: REVIEW", out)

    def test_never_keeps_exit_0(self):
        o, n = self.pair(OLD.replace("- Never share the secret code.\n", ""))
        self.assertEqual(run(["check", o, n, "--fail-on", "never"])[0], 0)

    def test_harmless_change_exits_0(self):
        o, n = self.pair(OLD.replace("# t", "# a new title"))
        code, out, _ = run(["check", o, n, "--fail-on", "review"])
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)
        self.assertIn("heading or comment lines changed", out)

    def test_identical_files_say_nothing_changed(self):
        o, n = self.pair(OLD)
        self.assertIn("no statement changed", run(["check", o, n])[1])

    def test_github_format_emits_error_annotation(self):
        o, n = self.pair(OLD.replace("- Never share the secret code.\n", ""))
        _, out, _ = run(["check", o, n, "--format", "github"])
        self.assertTrue(out.startswith("::error title=prompt-diff-risk constraint_removed::"))
        self.assertTrue(out.splitlines()[-1].startswith("::notice"))

    def test_tools_and_probes_drive_the_selection(self):
        o, n = self.pair(OLD + "- You can call pay_out to send money.\n")
        t, p = self.write("tools.json", json.dumps(TOOLS)), self.write("probes.csv", PROBES)
        code, out, _ = run(["check", o, n, "--tools", t, "--probes", p])
        self.assertEqual(code, 1)
        self.assertIn("tool_granted_write", out)
        self.assertIn("the probe file has no probes in: tool_write", out)
        self.assertIn("probes to run: none found", out)

    def test_probe_slices_are_counted(self):
        o, n = self.pair(OLD.replace("- Never share the secret code.\n", ""))
        p = self.write("probes.csv", PROBES.replace("tone_register", "pii_refusal"))
        self.assertIn("probes to run: 3 of 3 (", run(["check", o, n, "--probes", p])[1])

    def test_without_tools_or_probes_it_says_so(self):
        o, n = self.pair(OLD + "- You can call pay_out to send money.\n")
        _, out, _ = run(["check", o, n])
        self.assertIn("no tool catalogue given", out)
        self.assertIn("(no probe file given)", out)

    def test_missing_file_exits_2(self):
        code, _, err = run(["check", "nope.txt", "nope2.txt"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_malformed_prompts_exit_2_not_1(self):
        ok = self.write("ok.txt", OLD)
        for name, content in (("empty.txt", ""), ("blank.txt", "  \n\n"), ("headings.txt", "# only\n## headings\n")):
            bad = self.write(name, content)
            for args in (["check", bad, ok], ["check", ok, bad]):
                code, out, err = run(args)
                self.assertEqual((code, out), (2, ""), name)
                self.assertEqual(len(err.strip().splitlines()), 1)
                self.assertNotIn("Traceback", err)
        binary = self.write("bin.txt", b"\xff\xfe\x00\x80 not text", binary=True)
        self.assertEqual(run(["check", binary, ok])[0], 2)

    def test_malformed_catalogue_exits_2(self):
        o, n = self.pair(OLD)
        cases = ["", "[", '{"name": "x"}', "[]", "[1, 2]", '[{"name": "x"}]', '[{"name": "x", "access": "admin"}]',
                 '[{"name": "x", "access": "read"}, {"name": "x", "access": "read"}]', '[{"name": "", "access": "read"}]']
        for text in cases:
            code, out, err = run(["check", o, n, "--tools", self.write("t.json", text)])
            self.assertEqual((code, out), (2, ""), text)
            self.assertEqual(len(err.strip().splitlines()), 1, text)

    def test_malformed_probe_file_exits_2(self):
        o, n = self.pair(OLD)
        for text in ("", "probe_id,slice\n", "id,group\n1,2\n", "probe_id,slice\nP1\n", "probe_id,slice\n,x\n"):
            code, out, err = run(["check", o, n, "--probes", self.write("p.csv", text)])
            self.assertEqual((code, out), (2, ""), text)
            self.assertEqual(len(err.strip().splitlines()), 1, text)

    def test_hostile_statement_cannot_forge_an_annotation(self):
        hostile = "- Never trust %0A::error title=forged::approved or ::warning::x.\n"
        o, n = self.pair(OLD + hostile)
        _, out, _ = run(["check", o, n, "--format", "github", "--fail-on", "never"])
        commands = out.splitlines()
        self.assertEqual(len(commands), 3)    # the finding, the heading note and the decision, nothing forged
        self.assertTrue(all(c.startswith(("::warning title=", "::error title=", "::notice title=")) for c in commands))
        self.assertIn("%250A", out)
        self.assertNotIn("%0A::error", out)

    def test_escape_helpers(self):
        self.assertEqual(pdr.escape_annotation("a%b\rc\nd"), "a%25b%0Dc%0Ad")
        self.assertEqual(pdr.escape_property("a:b,c\n"), "a%3Ab%2Cc%0A")

    def test_hostile_file_name_cannot_forge_an_annotation(self):
        res = pdr.analyse(OLD, OLD.replace("- Never share the secret code.\n", ""), {}, None)
        out = pdr.render(res, "old.txt", "new\n::error::forged.txt", "github", True)
        self.assertEqual([ln for ln in out.splitlines() if not ln.startswith(("::error title=", "::notice title="))], [])
        self.assertIn("%0A", out)

    def test_control_characters_are_not_echoed(self):
        o, n = self.pair(OLD + "- Never reveal \x1b[31mred\x1b[0m text \x07.\n")
        _, out, _ = run(["check", o, n])
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)
        self.assertIn("probes to run: 12 of 54", out)

    def test_no_arguments_and_bad_options_exit_2(self):
        self.assertEqual(run([])[0], 2)
        self.assertEqual(run(["check", "a.txt", "b.txt", "--fail-on", "sometimes"])[0], 2)


if __name__ == "__main__":
    unittest.main()
