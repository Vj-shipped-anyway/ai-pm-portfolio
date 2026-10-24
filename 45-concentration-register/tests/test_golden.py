"""Pin the numbers the README prints, so a change to the model or the data that moves them fails here first."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_step(name: str) -> str:
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_status_quo.py")
        for line in ("services in the register: 64, of which critical: 25",
                     "services with a provider and a region listed: 55 of 64",
                     "critical services with neither: 3 of 25",
                     "critical services listed with one placement and no standby: 10 of 25",
                     "hard dependencies listed: 96, across 56 services",
                     "outage scenarios the process measures: 0 of 12"):
            self.assertIn(line, out)
        self.assertIn("(generator's world): 4 of 12", out)

    def test_step_02(self):
        out = run_step("step_02_direct_share.py")
        self.assertIn("scenarios flagged: 1 of 12 (P:CP-1)", out)
        self.assertIn("flagged and truly over: 1; flagged and not over: 0; truly over and not flagged: 3", out)
        self.assertIn("the direct view counts 44, of which 31 are real and 13 survive on a standby", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("P:CP-3     direct  12.0%   truth  52.0%", out)
        self.assertIn("flags 5 of 12 scenarios, 1 of them not over the limit in truth; counts 17 pairs", out)
        self.assertIn("they truly sit on CP-1 1, CP-2 1, CP-3 1", out)
        self.assertIn("KNOWN LIMIT: 6 hard dependencies exist that the register does not list", out)

    def test_step_04_summary(self):
        run_step("step_04_with_register_model.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["truth_over"], s["flagged"], s["caught"], s["false_flags"]), (4, 4, 4, 0))
        self.assertEqual(s["direct_caught"], 1)
        self.assertEqual((s["pairs_truth"], s["pairs_tool"], s["pairs_missed"]), (74, 64, 10))
        self.assertEqual([a["missed"] for a in s["ablation"]], [10, 4, 2, 0])
        self.assertEqual(s["unplaced_critical"], 3)
        self.assertEqual([(w["limit_pct"], w["truth"], w["caught"]) for w in s["sweep"] if w["limit_pct"] in (40.0, 50.0)],
                         [(40.0, 3, 2), (50.0, 3, 1)])


if __name__ == "__main__":
    unittest.main()
