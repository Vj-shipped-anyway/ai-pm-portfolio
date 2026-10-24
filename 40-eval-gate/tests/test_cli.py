import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import eval_gate as eg

HERE = os.path.dirname(os.path.abspath(__file__))
PROBES = "probe_id,severity,baseline_rate\n" + "".join("P%d,%s,1.0\n" % (i, "high" if i < 3 else "low") for i in range(10))


def results(model="m1", passes=None):
    passes = passes or {}
    quoted = '"' + model.replace('"', '""') + '"'
    return "probe_id,passes,trials,served_model\n" + "".join("P%d,%d,10,%s\n" % (i, passes.get(i, 10), quoted) for i in range(10))


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = eg.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.probes = self.write("probes.csv", PROBES)

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def check(self, res, *extra, pin="m1"):
        return run(["check", self.probes, self.write("results.csv", res), "--pin", pin, *extra])

    def test_clean_run_exits_0(self):
        code, out, _ = self.check(results())
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)

    def test_swapped_snapshot_exits_1(self):
        code, out, _ = self.check(results("m2"))
        self.assertEqual(code, 1)
        self.assertIn("decision: BLOCK", out)
        self.assertIn("snapshot_changed", out)

    def test_review_fails_only_when_asked(self):
        res = results(passes={3: 9, 4: 9, 5: 9, 6: 9})
        self.assertEqual(self.check(res)[0], 0)
        self.assertEqual(self.check(res, "--fail-on", "review")[0], 1)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.check(results("m2"), "--fail-on", "never")[0], 0)

    def test_action_style_arguments_work(self):
        res = self.write("r.csv", results("m2"))
        code, out, _ = run(["check", "--pin=m1", "--fail-on=block", "--format=github", "--", self.probes, res])
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("::error title=eval-gate snapshot_changed::"))

    def test_a_pin_that_looks_like_an_option_is_still_a_value(self):
        code, out, _ = run(["check", "--pin=--demo", "--", self.probes, self.write("r.csv", results("m1"))])
        self.assertEqual(code, 1)
        self.assertIn("pin --demo", out)

    def test_bad_input_exits_2_with_one_line_and_no_traceback(self):
        cases = {"empty": "", "header only": "probe_id,passes,trials,served_model\n",
                 "wrong type": "probe_id,passes,trials,served_model\nP0,many,10,m1\n",
                 "truncated": "probe_id,passes,trials,served_model\nP0,10,10,m1\nP1,10",
                 "matches nothing": "probe_id,passes,trials,served_model\nZ,1,1,m1\n"}
        for name, text in cases.items():
            code, out, err = self.check(text)
            self.assertEqual(code, 2, name)
            self.assertEqual(out, "", name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
            self.assertNotIn("Traceback", err, name)
        bad_probes = run(["check", self.write("p.csv", "probe_id,severity\nP0,high\n"), self.write("r.csv", results()), "--pin", "m1"])
        self.assertEqual(bad_probes[0], 2)

    def test_missing_file_and_missing_pin_exit_2(self):
        self.assertEqual(run(["check", "nope.csv", "nope2.csv", "--pin", "m1"])[0], 2)
        self.assertEqual(run(["check", self.probes, self.write("r.csv", results())])[0], 2)

    def test_empty_pin_exits_2(self):
        self.assertEqual(self.check(results(), pin="")[0], 2)

    def test_run_id_picks_one_run(self):
        a, b = results().splitlines(), results("m2").splitlines()
        text = "run_id," + a[0] + "\n" + "".join("A," + ln + "\n" for ln in a[1:]) + "".join("B," + ln + "\n" for ln in b[1:])
        self.assertEqual(self.check(text)[0], 2)
        self.assertEqual(self.check(text, "--run-id", "A")[0], 0)
        self.assertEqual(self.check(text, "--run-id", "B")[0], 1)

    def test_hostile_snapshot_id_cannot_forge_an_annotation(self):
        hostile = "x%0A\n::error title=forged::approved\r::warning::more"
        code, out, _ = self.check(results(hostile), "--format", "github", "--fail-on", "never")
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertTrue(all(ln.startswith(("::error title=eval-gate ", "::warning title=eval-gate ", "::notice title=eval-gate::")) for ln in commands))
        self.assertEqual(sum(1 for ln in commands if "title=forged" in ln.split("::", 2)[1]), 0)
        self.assertIn("%0A", commands[0])
        self.assertIn("%250A", commands[0])

    def test_hostile_pin_and_id_cannot_start_a_line_in_the_text_output(self):
        code, out, _ = self.check(results("a\n::error::boom"), pin="p\r\n::warning::x")
        self.assertEqual(code, 1)
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::")])
        self.assertIn("\\n::error::boom", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)

    def test_action_passes_inputs_through_env_not_the_shell_line(self):
        with open(os.path.join(HERE, "..", "action", "action.yml"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("run: |", text)
        self.assertNotIn("${{", text.split("run: |", 1)[1])


if __name__ == "__main__":
    unittest.main()
