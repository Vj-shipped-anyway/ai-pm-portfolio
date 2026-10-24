"""Pin the numbers the README prints, so a change to the parser or the rubric that moves them fails here first."""
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
        out = run_step("step_01_declared_label.py")
        self.assertIn("declared tier equals the reference tier: 103 of 151", out)
        self.assertIn("tier 3-4 issues declared at tier 1-2: 21 of 55", out)

    def test_step_02(self):
        out = run_step("step_02_form_and_regex.py")
        self.assertIn("tier equals the reference tier: 124 of 160", out)
        self.assertIn("tier 3-4 issues labeled tier 1-2: 18 of 57", out)
        self.assertIn("labeled with fewer than 5 of the 5 required inputs read: 14 of 160", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("14 of 160 bodies lack at least one of the 5 required inputs",
                     "35 forms declare a class below the true class; on 9 of those",
                     "3 blank or unreadable, 10 'unsure', 5 'no' on a customer-facing case: 18 of 160",
                     "the registry lists 13 of those 24",
                     "the regex reads the pasted value on 4 of them",
                     "With add-only labels, 8 of them end with two tier labels",
                     "Comments posted: 184 for 160 issues",
                     "5 of 160 bodies carry a line that starts with '::'",
                     "still reads a data class below the true class on 11 of 35 understated forms"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_step("step_04_with_action.py")
        with open(os.path.join(SRC, "out", "step_04_results.json"), encoding="utf-8") as fh:
            s = json.load(fh)["summary"]
        self.assertEqual((s["tiered"], s["needs_info"], s["issues"]), (142, 18, 160))
        self.assertEqual((s["correct"], s["step2_correct"]), (129, 124))
        self.assertEqual((s["high_found"], s["high_tier"]), (46, 57))
        self.assertEqual((s["mismatch"], s["known_limit"]), (39, 11))
        for line in ("tier below the reference: 7; above: 6",
                     "needs-info by kind of body: no_form 3 of 3, renamed_heading 5 of 5, truncated 6 of 6, pasted_heading 4 of 4, ok 0 of 142",
                     "tier-mismatch raised on 39 issues; on 36 of them",
                     "CUSTOMER_FACING_CUE raised 33, truly customer-facing on 3",
                     "exactly one tier-or-needs-info label on 160 of 160 issues",
                     "14 of 24 before the edit, 24 of 24 after",
                     "workflow commands forged in the log: 0; comments that echo a mention, tag, link or command: 0 of 160",
                     "the tier is wrong on 2 of them"):
            self.assertIn(line, out)


if __name__ == "__main__":
    unittest.main()
