"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import json
import os
import re
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
        out = run_step("step_01_no_check.py")
        self.assertIn("dispute cases: 100   disputed value: $103,404.68", out)
        self.assertIn("planted truth: 43 ready, 43 defective (clock still running), 14 late", out)
        self.assertIn("packets that go out with a planted fault: 57 of 100", out)
        self.assertIn("disputed value inside those packets: $58,502.91 of $103,404.68", out)

    def test_step_02(self):
        out = run_step("step_02_count_the_documents.py")
        self.assertIn("packets held back: 22 of 100", out)
        self.assertIn("faulty packets sent anyway: 37 of 57", out)
        self.assertIn("ready packets held back: 2 of 43", out)
        self.assertIn("late packets it passes: 8 of 14", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        blocks = {m.group(1): m.group(0) for m in re.finditer(r"  (completeness|clock|consistency) only\n(?:    .*\n){3}", out)}
        self.assertIn("defective flagged: 10 of 43 (10 of 34 visible in metadata)", blocks["completeness"])
        self.assertIn("late flagged: 3 of 14", blocks["completeness"])
        self.assertIn("defective flagged: 0 of 43", blocks["clock"])
        self.assertIn("late flagged: 14 of 14", blocks["clock"])
        self.assertIn("defective flagged: 24 of 43 (24 of 34 visible in metadata)", blocks["consistency"])
        self.assertIn("late flagged: 0 of 14", blocks["consistency"])
        for b in blocks.values():
            self.assertIn("ready packets flagged: 0 of 43", b)
        self.assertIn("faulty packets that pass all three parts: 9 of 57", out)

    def test_step_04_summary(self):
        run_step("step_04_with_check.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["caught"], s["visible_defective"]), (34, 34))
        self.assertEqual((s["late_caught"], s["late"]), (14, 14))
        self.assertEqual((s["false_alarms"], s["ready"]), (0, 43))
        self.assertEqual((s["exact_match"], s["cases"]), (91, 100))
        self.assertEqual(s["to_open"], 48)
        self.assertEqual((s["urgent_fix"], s["fix_drafts"]), (7, 34))
        self.assertEqual((s["hidden_passing"], s["hidden"]), (9, 9))

    def test_step_04_hard_negatives_all_stay_ready(self):
        out = run_step("step_04_with_check.py")
        for kind, n in (("ready_alt_branch", 8), ("ready_partial", 5), ("ready_on_deadline", 5), ("ready_draft", 5), ("ready_extra_doc", 3)):
            self.assertRegex(out, rf"{kind}\s+{n} of {n}")
        self.assertIn("drafts due today that stayed READY: 2 of 2", out)


if __name__ == "__main__":
    unittest.main()
