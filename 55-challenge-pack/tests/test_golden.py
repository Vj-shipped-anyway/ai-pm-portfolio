"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
from __future__ import annotations

import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")


def run_step(script):
    r = subprocess.run([sys.executable, script], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


def summary(name):
    with open(os.path.join(SRC, "out", name), encoding="utf-8") as fh:
        return json.load(fh)


class GoldenTests(unittest.TestCase):
    def test_demo_output(self):
        r = subprocess.run([sys.executable, "challenge_pack.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.stdout.splitlines(), [
            "EX-02  Merchant risk scoring  tier 3 (declared 2, raised by the rubric)  scope: in (ml)  overlays: vendor",
            "  GAP  CH08 Outcomes analysis: stale (latest 2025-02-11, window 12 months, as of 2026-10-01)",
            "checked 6 use cases: 1 with gaps, 5 complete; 55 plan items, 54 on file and current"])

    def test_step_01(self):
        run_step("step_01_generic_checklist.py")
        s = summary("step_01_summary.json")
        self.assertEqual((s["covered"], s["required"], s["missed"], s["over"]), (876, 1486, 610, 24))
        self.assertEqual((s["missed_independent"], s["high_tier_no_independent"], s["high_tier"]), (436, 83, 83))
        self.assertEqual(s["defects"], 437)

    def test_step_02(self):
        run_step("step_02_tier_table.py")
        s = summary("step_02_summary.json")
        self.assertEqual((s["covered"], s["required"], s["over"]), (1080, 1486, 7))
        self.assertEqual((s["declared_below"], s["declared_above"]), (42, 2))
        self.assertEqual((s["missed_tier"], s["missed_overlay"]), (158, 248))

    def test_step_03(self):
        run_step("step_03_deficiencies_exposed.py")
        s = summary("step_03_summary.json")
        self.assertEqual((s["below_declared"], s["vendor_off_form"], s["vendor_dependent"], s["class_low"]), (42, 14, 91, 23))
        self.assertEqual(s["still_below_after_recompute"], 16)
        self.assertEqual(s["planted"], {"missing": 248, "stale": 92, "wrong_version": 71, "not_independent": 26})
        self.assertEqual((s["b_found"]["missing"], s["b_total"], s["defects"]), (87, 87, 437))
        self.assertEqual((s["c_found"]["stale"], s["c_found"]["not_independent"], s["c_found"]["wrong_version"]), (80, 26, 0))
        self.assertEqual((s["reaffirmed_flagged"], s["reaffirmed"], s["first_line_flagged"], s["first_line"]), (129, 145, 626, 626))
        self.assertEqual(s["hollow"], 32)

    def test_step_04(self):
        run_step("step_04_with_the_pack.py")
        s = summary("step_04_summary.json")
        self.assertEqual((s["tier_below"], s["declared_below"], s["tier_above"], s["declared_above"]), (16, 42, 2, 2))
        self.assertEqual((s["covered"], s["required"], s["over"]), (1403, 1486, 7))
        self.assertEqual((s["found_total"], s["defects"]), (360, 437))
        self.assertEqual(s["found"], {"missing": 176, "stale": 88, "wrong_version": 70, "not_independent": 26})
        self.assertEqual((s["unasked_tier"], s["unasked_overlay"], s["asked_not_found"]), (49, 24, 4))
        self.assertEqual((s["fine_flagged"], s["not_owed_flagged"]), (0, 6))
        self.assertEqual(s["hard"], {"reaffirmed": [0, 152], "boundary": [0, 34], "first_line": [0, 632]})
        self.assertEqual((s["use_cases"], s["with_gaps"], s["plan_items"], s["current"]), (150, 130, 1410, 1044))
        self.assertEqual((s["hollow_pass"], s["hollow"], s["hollow_unasked"], s["below_unasked"]), (30, 32, 2, 68))

    def test_the_known_limits_are_printed(self):
        out = run_step("step_04_with_the_pack.py")
        self.assertIn("KNOWN LIMIT 1", out)
        self.assertIn("KNOWN LIMIT 2", out)
        self.assertIn("KNOWN LIMIT", run_step("step_03_deficiencies_exposed.py"))

    def test_the_generator_reproduces_every_data_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in sorted(os.listdir(DATA)):
                if name.endswith(".csv"):
                    self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
