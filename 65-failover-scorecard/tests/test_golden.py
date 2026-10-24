"""Pin the numbers the README prints, and check that the data regenerates byte for byte."""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_self_reported.py")
        for line in ("services whose owner states a documented failover plan: 42 of 48",
                     "of those, services that would recover: 16 of 42",
                     "services with at least one drill on record: 39 of 48; with a live drill: 37 of 48"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_last_drill_passed.py")
        for line in ("green: 36 of 48   red: 12 of 48",
                     "green services that would not recover: 20 of 36",
                     "red services that are not a gap (accepted risk): 4 of 12",
                     "tier-1 services shown green that would not recover: 10 of 15"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("services that would not recover: 28 of 48",
                     "full rule: 3 of 28 pass as READY",
                     "without type_and_scenario  5 of 28 pass, 2 more: tabletop_only",
                     "without rto                5 of 28 pass, 2 more: slow_pass",
                     "without version_and_region 8 of 28 pass, 5 more: changed_since_drill, wrong_region_drill",
                     "without age                6 of 28 pass, 3 more: stale_drill",
                     "without dependencies       6 of 28 pass, 3 more: dependency_gap",
                     "known limit: 3 services pass every check and would not recover"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_step("step_04_with_scorecard.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["not_ready_flagged"], s["not_ready"]), (25, 28))
        self.assertEqual((s["ready_flagged"], s["ready"]), (0, 16))
        self.assertEqual((s["accepted_kept"], s["accepted"]), (4, 4))
        self.assertEqual((s["exact_match"], s["services"]), (45, 48))
        self.assertEqual((s["tier1_ready"], s["tier1"], s["tier1_ready_wrong"]), (7, 18, 2))
        self.assertEqual((s["sent_to_owner"], s["missed"]), (25, 3))
        self.assertEqual(s["tier1_window_sensitivity"], {"90": 6, "180": 7, "365": 8})
        self.assertEqual(s["by_status"], {"CHANGED": 5, "DEPENDENCY": 3, "FAILED": 3, "NOT_REQUIRED": 4, "NO_PATH": 2,
                                          "READY": 19, "SLOW": 2, "STALE": 3, "UNTESTED": 7})
        self.assertIn("known limit: 3 services score READY and would not recover", out)

    def test_demo_output_is_pinned(self):
        r = subprocess.run([sys.executable, "failover_scorecard.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "as of 2026-10-24: 8 services, 2 ready, 1 not required, 5 not ready")
        self.assertEqual(lines[-1], "decision: NOT READY (3 of 5 tier-1 services have no tested way back)")

    def test_data_regenerates_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in ("services.csv", "drills.csv", "service_truth.csv", "example_services.csv", "example_drills.csv"):
                with open(os.path.join(tmp, name), "rb") as a, open(os.path.join(DATA, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_planted_data_shape(self):
        with open(os.path.join(DATA, "service_truth.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 48)
        classes = {c: sum(1 for r in rows if r["truth_class"] == c) for c in ("ready", "not_ready", "accepted")}
        self.assertEqual(classes, {"ready": 16, "not_ready": 28, "accepted": 4})
        self.assertEqual(sum(1 for r in rows if r["hidden_depends_on"]), 3)
        with open(os.path.join(DATA, "drills.csv"), newline="", encoding="utf-8") as fh:
            self.assertLessEqual(max(r["drill_date"] for r in csv.DictReader(fh)), "2026-10-24")


if __name__ == "__main__":
    unittest.main()
