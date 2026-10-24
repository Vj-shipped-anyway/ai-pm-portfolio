"""Pin the numbers the README prints, so a change to the classifier that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


class GoldenTests(unittest.TestCase):
    def test_step_04_summary(self):
        r = subprocess.run([sys.executable, "step_04_with_gate.py"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["breaking_blocked"], s["breaking"]), (25, 25))
        self.assertEqual((s["behavior_risk_flagged"], s["behavior_risk"]), (9, 15))
        self.assertEqual((s["harmless_blocked"], s["harmless"]), (0, 27))
        self.assertEqual((s["exact_match"], s["pull_requests"]), (61, 67))
        self.assertEqual(s["to_read"], 34)


if __name__ == "__main__":
    unittest.main()
