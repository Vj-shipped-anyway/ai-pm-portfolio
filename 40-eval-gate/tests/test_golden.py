"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_script(*args):
    r = subprocess.run([sys.executable, *args], cwd=SRC, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


class GoldenTests(unittest.TestCase):
    def lines(self, script, expected):
        code, out, err = run_script(script)
        self.assertEqual(code, 0, err[-300:])
        for line in expected:
            self.assertIn(line, out)

    def test_step_01(self):
        self.lines("step_01_no_gate.py", [
            "planted truth: 25 should be blocked, 8 should be reviewed, 31 are fine",
            "deploys the current pipeline stops: 0 of 64",
            "served by an id other than the pin: 17 of 64",
            "partial rollouts that reached only some probes: 7",
            "more than 5 points under the baseline: 11 of 64",
            "results file is short of probes: 4 of 64"])

    def test_step_02(self):
        self.lines("step_02_pass_rate_floor.py", [
            "should-block runs stopped: 13 of 25", "should-review runs stopped: 3 of 8", "fine runs stopped: 1 of 31",
            "silent_swap_flat 6"])

    def test_step_03(self):
        self.lines("step_03_deficiencies_exposed.py", [
            "should-block runs stopped: 23 of 25", "fine runs stopped: 6 of 31",
            "should-block runs stopped: 17 of 25",
            "should-review runs flagged (REVIEW or BLOCK): 5 of 8",
            "pass both halves: 3 of 33", "by planted event: drift_subtle 3",
            "worst 3.3 points, 1 over the 3-point review line"])

    def test_step_04_summary(self):
        code, out, err = run_script("step_04_with_gate.py")
        self.assertEqual(code, 0, err[-300:])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["should_block_stopped"], s["should_block"]), (25, 25))
        self.assertEqual((s["should_review_flagged"], s["should_review"]), (5, 8))
        self.assertEqual((s["fine_blocked"], s["fine_review"], s["fine"]), (0, 1, 31))
        self.assertEqual((s["exact_match"], s["runs"]), (59, 64))
        self.assertEqual(s["missed"], 3)
        for rid in ("RUN-042", "RUN-052", "RUN-061"):
            self.assertIn(rid + " drift_subtle", out)

    def test_demo_output(self):
        code, out, err = run_script("eval_gate.py", "--demo")
        self.assertEqual(code, 0, err[-300:])
        self.assertIn("pass rate 0.89 against a baseline of 0.93 (-3.7 points)", out)
        self.assertIn("snapshot_changed", out)
        self.assertIn("probe_collapse   high-severity probe P005 fell from 1.00 to 0.50.", out)
        self.assertTrue(out.rstrip().endswith("decision: BLOCK"))


if __name__ == "__main__":
    unittest.main()
