"""Pin the numbers the README prints, so a change to the scorer or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_script(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_script("step_01_self_report.py")
        self.assertIn("runs accepted because the agent returned a final answer: 236 of 240", out)
        self.assertIn("accepted runs that were defective: 92 of 236", out)

    def test_step_02(self):
        out = run_script("step_02_final_answer_check.py")
        self.assertIn("runs that pass: 228 of 240", out)
        self.assertIn("defective runs it catches: 12 of 96", out)
        self.assertIn("sound runs it fails: 0 of 144", out)

    def test_step_03(self):
        out = run_script("step_03_deficiencies_exposed.py")
        self.assertIn("defective runs flagged: 74 of 96", out)
        self.assertIn("defective runs flagged: 24 of 96", out)
        self.assertIn("hard negatives flagged (sound, but unlike the reference): 64 of 64", out)
        self.assertIn("hard negatives flagged (sound, but unlike the reference): 6 of 64", out)
        self.assertIn("KNOWN LIMIT: sensitive text in a free-text argument passes every check here and in step 4: 6 of 6", out)

    def test_step_04_summary_and_known_misses(self):
        out = run_script("step_04_trajectory_scorer.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["defective_caught"], s["defective"]), (90, 96))
        self.assertEqual((s["defective_caught_by_answer"], s["defective"]), (12, 96))
        self.assertEqual((s["answer_blind_caught"], s["answer_blind"]), (78, 84))
        self.assertEqual((s["hard_negatives_failed"], s["hard_negatives"]), (6, 64))
        self.assertEqual((s["trajectory_passes"], s["final_answer_passes"], s["runs"]), (144, 228, 240))
        self.assertIn("KNOWN MISS: defective runs that pass: 6 of 96 (note_leak)", out)
        self.assertIn("sound runs sitting exactly at the call budget: 7 of 7 pass", out)
        self.assertIn("mean score of those 78 runs: 0.82", out)

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "trajectory_eval.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines()[-1], "final answer matches in 3 of 3 runs; the whole trajectory passes in 1 of 3 runs")


if __name__ == "__main__":
    unittest.main()
