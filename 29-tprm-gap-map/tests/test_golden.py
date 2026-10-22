"""Pin the numbers the README prints."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


class GoldenTests(unittest.TestCase):
    def test_step_04_summary(self):
        r = subprocess.run([sys.executable, "step_04_with_ai_fields.py"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["text_caught"], s["material"], s["text_flagged"], s["text_false"]), (17, 24, 30, 13))
        self.assertEqual((s["ai_caught"], s["ai_flagged"], s["ai_false"]), (22, 41, 19))


if __name__ == "__main__":
    unittest.main()
