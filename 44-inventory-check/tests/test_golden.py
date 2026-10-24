"""Pin the numbers the README prints, so a change to a rule or to the data that moves them fails here first."""
import contextlib
import csv
import io
import json
import os
import re
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
import inventory_check as ic

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
ROOT = os.path.join(SRC, "..")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout.splitlines()


class GoldenTests(unittest.TestCase):
    def assert_lines(self, lines, expected):
        for want in expected:
            self.assertIn(want, lines)

    def test_step_01(self):
        self.assert_lines(step("step_01_no_test.py"), [
            "  records: 100   usage rows: 105   as of 2026-09-30",
            "  truth: 57 defective records, 43 clean",
            "  defective records among production systems at tier 3 or 4: 21 of 35",
            "  records flagged for a reviewer today: 0 of 100",
            "  shadow systems in the usage export: 7 (4 under their own name, 1 with no system id, 2 under a listed system's id)",
            "  calls from those shadow systems: 85916 of 4167034 (2.1%)"])

    def test_step_02(self):
        lines = step("step_02_blank_cells.py")
        self.assert_lines(lines, [
            "  records flagged: 10 of 100",
            "  defective records flagged: 8 of 57",
            "  clean records flagged: 2 of 43 (retired_old_traffic 2)",
            "    missing_required     6 of 6",
            "    review_overdue       2 of 6"])

    def test_step_03(self):
        self.assert_lines(step("step_03_deficiencies_exposed.py"), [
            "    defective records flagged: 29 of 57; clean records flagged: 0 of 43",
            "    defective records flagged: 22 of 57; clean records flagged: 2 of 43",
            "    defective records flagged: 39 of 57; clean records flagged: 0 of 43",
            "  every one of the 20 columns required on every row",
            "    defective records flagged: 53 of 57; clean records flagged: 41 of 43",
            "  defective records only the usage file can show: 12 of 57",
            "    defective records that pass every test: 6 of 57 (placeholder_novel 3, rubber_stamp 3)",
            "    clean records the tests flag: 2 of 43 (seasonal_quiet 2)",
            "    shadow systems the usage export cannot name: 3 of 7 (1 with no system id, 2 under a listed system's id)"])

    def test_step_04_report_and_summary(self):
        lines = step("step_04_with_checks.py")
        self.assert_lines(lines, [
            "  defective records flagged: 51 of 57",
            "  clean records flagged: 2 of 43 (seasonal_quiet; hard negatives left alone: 25 of 27)",
            "  records with a fail finding: 29; review only: 24; no finding: 47",
            "  records a person has to open: 53 of 100 (step 1: all 100 or none; step 2 flagged 10)",
            "  findings: 65 (completeness 36, staleness 15, coverage 14)",
            "  defective records that still pass: 6 of 57 (placeholder_novel 3, rubber_stamp 3)"])
        self.assertTrue(any(ln.startswith("  shadow systems named from the usage export: 4 of 7;") for ln in lines))
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["defective_flagged"], s["defective"]), (51, 57))
        self.assertEqual((s["clean_flagged"], s["clean"]), (2, 43))
        self.assertEqual((s["to_open"], s["records"]), (53, 100))
        self.assertEqual((s["shadows_named"], s["shadows"]), (4, 7))
        self.assertEqual(s["decision"], "FAIL")

    def test_every_planted_defect_the_rules_should_find_is_found_and_the_two_misses_are_the_known_ones(self):
        step("step_04_with_checks.py")
        with open(os.path.join(SRC, "out", "step_04_systems.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        passed = sorted({r["case_kind"] for r in rows if r["truth"] == "defective" and r["verdict"] == "OK"})
        self.assertEqual(passed, ["placeholder_novel", "rubber_stamp"])

    def test_readme_demo_block_is_the_real_output(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        block = re.search(r"It prints:\n\n```text\n(.*?)\n```", readme, re.S).group(1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ic.main(["--demo"]), 0)
        self.assertEqual(block, out.getvalue().rstrip("\n"))

    def test_the_cadences_in_the_data_readme_are_the_ones_in_the_code(self):
        with open(os.path.join(ROOT, "data", "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("tier 1: 365 days, tier 2: 270, tier 3: 180, tier 4: 90", text)
        self.assertEqual(ic.CADENCE_DAYS, {1: 365, 2: 270, 3: 180, 4: 90})
        self.assertEqual((ic.IDLE_DAYS, ic.RETIRED_QUIET_DAYS), (90, 30))


if __name__ == "__main__":
    unittest.main()
