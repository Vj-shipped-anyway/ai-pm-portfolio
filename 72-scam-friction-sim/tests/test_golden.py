"""Pin the numbers the README prints, so a change to the rules or the assumptions that moves them fails here first."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run(script: str, *args: str) -> str:
    r = subprocess.run([sys.executable, script, *args], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_demo_output(self):
        lines = run("scam_friction_sim.py", "--demo").splitlines()
        self.assertEqual(lines[0], "payments: 12000 (330 scam, 11670 legitimate); hold 20 minutes")
        self.assertIn("stopped   0.0% of scam value, legit held    0 (0.0%), legit lost 0", lines[1])
        self.assertIn("stopped  21.6% of scam value, legit held  336 (2.9%), legit lost 10", lines[2])
        self.assertIn("stopped  20.1% of scam value, legit held   52 (0.4%), legit lost 2", lines[3])

    def test_step_01(self):
        out = run("step_01_no_hold.py")
        self.assertIn("payments: 12000 (330 scam, 11670 legitimate)", out)
        self.assertIn("scam value passing: $403,678 of $3,202,027 moved (12.6%)", out)
        self.assertIn("scam payments stopped: 0 of 330", out)

    def test_step_02(self):
        out = run("step_02_blanket_hold.py")
        self.assertIn("scam payments held: 173 of 330; stopped: 51", out)
        self.assertIn("scam value stopped: $87,222 of $403,678 (21.6%)", out)
        self.assertIn("legitimate payments held: 336 of 11670 (2.9%)", out)
        self.assertIn("legitimate payments lost (customer gave up): 10", out)
        self.assertIn("minutes legitimate customers waited: 6720", out)
        self.assertIn("legitimate holds per scam payment stopped: 6.6", out)
        self.assertIn("(big_first_time): 262 of 330 held", out)

    def test_step_03(self):
        out = run("step_03_deficiencies_exposed.py")
        self.assertIn("hold every payment, no coaching: 29.7% of scam value stopped", out)
        self.assertIn("hold every payment, coaching at 0.2: 24.0%", out)
        self.assertIn("x0.5: 15.5%, x1: 21.6%, x1.5: 31.3%", out)
        self.assertIn("0: 26.2%, 0.2: 21.6%, 0.5: 15.5%, 0.8: 9.4%", out)
        self.assertIn("w=10  legitimate payments held per scam payment stopped: 65.9", out)
        self.assertIn("w=100 legitimate payments held per scam payment stopped: 658.8", out)
        self.assertIn("60 payments, $15,936, held by the blanket rule: 0", out)
        self.assertIn("which holds 3973 of 11670 legitimate payments (34.0%)", out)

    def test_step_04_summary(self):
        run("step_04_scored_hold.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["hold_score"], s["warn_score"]), (8, 6))
        self.assertEqual((s["stopped_pct"], s["blanket_stopped_pct"]), (20.1, 21.6))
        self.assertEqual((s["legit_held"], s["blanket_legit_held"], s["legit_n"]), (52, 336, 11670))
        self.assertEqual((s["legit_lost"], s["blanket_legit_lost"]), (2, 10))
        self.assertEqual((s["same_friction_score"], s["same_friction_stopped_pct"]), (6, 22.9))
        self.assertEqual((s["scam_passing_untouched"], s["scam_n"], s["hard_case_passing"]), (144, 330, 60))

    def test_step_04_grid_shape(self):
        run("step_04_scored_hold.py")
        with open(os.path.join(SRC, "out", "step_04_grid.csv"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 1 + 4 * 12 * 2)


if __name__ == "__main__":
    unittest.main()
