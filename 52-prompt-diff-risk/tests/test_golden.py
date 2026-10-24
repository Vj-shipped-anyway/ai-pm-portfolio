"""Pin the numbers the README prints, so a change to the classifier that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_gate.py")
        for line in ("prompt pull requests merged: 70   probes in the set: 54 in 9 slices",
                     "truth: 22 high, 30 medium, 18 low",
                     "pull requests with at least one planted failing probe: 52 of 70",
                     "planted failing probes that reach users unseen: 74"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_basic_approach.py")
        for line in ("pull requests flagged: 70 of 70", "share of flags that are harmless: 25.7%",
                     "probes run: 3780 (70 pull requests x 54 probes)", "probes run on harmless pull requests: 972"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("high-risk flagged: 15 of 22", "medium-risk flagged: 1 of 30", "harmless pull requests flagged: 7 of 18",
                     "high-risk flagged: 4 of 22", "medium-risk flagged: 5 of 30", "harmless pull requests flagged: 0 of 18",
                     "risky pull requests that pass both rules: 27 of 52"):
            self.assertIn(line, out)

    def test_step_04_summary(self):
        run_step("step_04_with_gate.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["high_blocked"], s["high_flagged"], s["high"]), (19, 21, 22))
        self.assertEqual((s["medium_flagged"], s["medium"]), (24, 30))
        self.assertEqual((s["harmless_blocked"], s["harmless_review"], s["harmless"]), (2, 5, 18))
        self.assertEqual((s["exact_match"], s["pull_requests"]), (54, 70))
        self.assertEqual(s["to_read"], 52)
        self.assertEqual((s["caught"], s["risky"], s["risky_passing"], s["high_not_blocked"]), (45, 52, 7, 2))
        self.assertEqual((s["probes_run"], s["probes_full"]), (504, 3780))

    def test_step_04_names_the_known_misses(self):
        out = run_step("step_04_with_gate.py")
        self.assertIn("risky pull requests that still pass: 7 of 52 (constraint_quiet, route_swap, tone_offlist)", out)
        self.assertIn("harmless pull requests blocked: PR-048 reword_keep, PR-057 reword_keep", out)


if __name__ == "__main__":
    unittest.main()
