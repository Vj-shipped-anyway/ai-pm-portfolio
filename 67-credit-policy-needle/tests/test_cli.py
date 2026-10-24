import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import credit_policy_needle as cpn

HEADER = "probe_id,form,length_pages,depth_pct,expected_answer\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cpn.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def files(self, second_answer="43%", form="inline"):
        probes = self.write("p.csv", HEADER + '"p1","%s",50,0,48%%\n"p2","%s",50,0,43%%\n' % (form, form))
        answers = self.write("a.csv", "probe_id,answer\np1,48%%\np2,%s\n" % second_answer)
        return probes, answers

    def assert_clean_exit_2(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_pass_exits_0(self):
        code, out, _ = run(["score", *self.files()])
        self.assertEqual(code, 0)
        self.assertIn("gate: PASS", out)

    def test_fail_exits_1_and_never_keeps_exit_0(self):
        p, a = self.files(second_answer="48%")
        code, out, _ = run(["score", p, a])
        self.assertEqual(code, 1)
        self.assertIn("gate: FAIL", out)
        self.assertIn("inline 50 pages depth 0%: 1 of 2", out)
        self.assertEqual(run(["score", p, a, "--fail-on", "never"])[0], 0)

    def test_empty_files_exit_2(self):
        empty = self.write("empty.csv", "")
        p, a = self.files()
        self.assert_clean_exit_2(["score", empty, a])
        self.assert_clean_exit_2(["score", p, empty])
        self.assert_clean_exit_2(["audit", empty])

    def test_wrong_type_files_exit_2(self):
        p, a = self.files()
        as_json = self.write("p.json", '{"probes": [1, 2]}')
        self.assert_clean_exit_2(["score", as_json, a])
        self.assert_clean_exit_2(["score", p, as_json])
        self.assert_clean_exit_2(["score", self.dir.name, a])
        binary = os.path.join(self.dir.name, "bin")
        with open(binary, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x81")
        self.assert_clean_exit_2(["audit", binary])

    def test_truncated_files_exit_2(self):
        p, a = self.files()
        self.assert_clean_exit_2(["score", self.write("cut.csv", HEADER + 'p1,inline,50,0,48%\np2,inl'), a])
        self.assert_clean_exit_2(["score", p, self.write("cuta.csv", "probe_id,answer\np1,48%\np2")])

    def test_missing_file_and_bad_usage_exit_2(self):
        self.assert_clean_exit_2(["score", "nope.csv", "nope2.csv"])
        self.assert_clean_exit_2(["audit", "nope.txt"])
        self.assert_clean_exit_2(["score", "only_one_argument.csv"])
        self.assert_clean_exit_2([])
        self.assert_clean_exit_2(["audit", "m.txt", "--format", "xml"])

    def test_answers_for_other_probes_exit_2(self):
        p, _ = self.files()
        other = self.write("other.csv", "probe_id,answer\nzz1,48%\n")
        code, _, err = run(["score", p, other])
        self.assertEqual(code, 2)
        self.assertIn("none of the 2 probe ids", err)

    def test_hostile_form_name_cannot_forge_output(self):
        hostile = 'inline\n::error title=forged::approved\r%'
        probes = self.write("p.csv", HEADER + '"p1","%s",50,0,48%%\n"p2","%s",50,0,43%%\n' % (hostile, hostile))
        answers = self.write("a.csv", "probe_id,answer\np1,0%\np2,0%\n")
        _, text, _ = run(["score", probes, answers, "--fail-on", "never"])
        self.assertFalse(any(ln.startswith("::") for ln in text.splitlines()))
        _, gh, _ = run(["score", probes, answers, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in gh.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(gh.splitlines()))
        self.assertEqual([c.split(" ")[0] for c in commands], ["::error", "::notice"])
        self.assertIn("%0A", commands[0])
        self.assertIn("%0D", commands[0])
        self.assertIn("%25", commands[0])

    def test_audit_command_prints_the_listing(self):
        m = self.write("m.txt", "1.1 The maximum loan term for Alder Personal Loan is 60 months.\n\n"
                       "2.1 Notwithstanding clause 1.1, the limit stated there is 72 months.\n")
        code, out, _ = run(["audit", m])
        self.assertEqual(code, 0)
        self.assertIn("exception clauses flagged: 1", out)
        self.assertIn("do not name its rule: 1", out)

    def test_demo_runs_and_fails_the_gate_it_is_meant_to_show(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("score  example_answers.csv: 6 of 8 probes pass", out)
        self.assertIn("gate: FAIL", out)


if __name__ == "__main__":
    unittest.main()
