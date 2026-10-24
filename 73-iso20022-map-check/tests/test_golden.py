"""Pin the numbers the README prints, so a change to a rule that moves them fails here first."""
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
    return r.stdout.splitlines()


class GoldenTests(unittest.TestCase):
    def assert_lines(self, lines, expected):
        for want in expected:
            self.assertIn(want, lines)

    def test_step_01(self):
        self.assert_lines(run_step("step_01_schema_check_only.py"), [
            "  pairs that pass ISO schema validation: 214 of 230",
            "  pairs with a planted converter or capacity defect: 129 of 230",
            "  defective pairs that still pass schema validation: 113 of 129",
            "  builds with a planted defect: 8; of those, builds with at least one schema failure: 1"])

    def test_step_02(self):
        self.assert_lines(run_step("step_02_exact_compare.py"), [
            "  rows compared: 11 of 19 mapping rows (the rest change the value on the way)",
            "  defective pairs caught: 78 of 129",
            "  pairs flagged with no planted defect: 20 of 230",
            "  harmless variations flagged (padding, trailing zeros): 154 of 162",
            "  planted defects on rows it cannot compare: 99 of 212"])

    def test_step_03(self):
        self.assert_lines(run_step("step_03_deficiencies_exposed.py"), [
            "    planted mapping defects found: 5 of 5; harmless rows flagged: 0 of 3",
            "    planted defects found: 131 of 131; false alarms on harmless variations: 0",
            "    planted defects found: 81 of 81; false alarms on harmless variations: 0",
            "    builds with a planted converter defect found: 5 of 8",
            "    builds with a planted converter defect found: 6 of 8",
            "  builds the typical messages miss: B03 cut_early, B04 cut_early, B10 cond_drop",
            "  of those, found by the probes: B03, B04"])

    def test_step_04(self):
        lines = run_step("step_04_with_check.py")
        self.assert_lines(lines, [
            "  planted mapping defects found: 5 of 5; harmless rows flagged: 0 of 3",
            "  reverse exposure (warning): 10 of 12 text rows could cut data on the way back to the legacy format",
            "  planted converter defects found in pairs: 212 of 212",
            "  harmless variations flagged: 0 of 162; false alarms: 0",
            "  mapping gaps seen in pairs (value lost, value invented, code fallback): 390 of 390",
            "  builds with a planted defect found: typical messages alone 5 of 8, with probes 7 of 8",
            "    B10 cond_drop      MISSED"])
        self.assertTrue(any(ln.startswith("  NOT FOUND: B10 cond_drop") and ln.endswith("fired in the data: 0") for ln in lines))
        self.assertIn("  coverage: code combinations (TYP, CHGS) never in any message: 2 of 9 (15/S, 16/S)", lines)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["builds_found"], s["builds_planted"], s["builds_found_typical"]), (7, 8, 5))
        self.assertEqual((s["mapping_defects_found"], s["mapping_defects"], s["pairs"]), (5, 5, 230))

    def test_demo_output_matches_the_readme(self):
        r = subprocess.run([sys.executable, "iso20022_map_check.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "mapping: 19 rows | 20 legacy fields | 20 ISO elements | 1 dropped on purpose (INTNOTE)")
        self.assertEqual(lines[-1], "decision: FAIL (5 mapping errors, 10 pair findings)")


if __name__ == "__main__":
    unittest.main()
