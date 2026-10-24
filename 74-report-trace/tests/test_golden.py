"""Pin the numbers the README prints, so a change to the tool or the data that moves them fails here first."""
import filecmp
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


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_trace.py")
        for line in ("cells with a recorded path to source rows: 0 of 71", "rows in the loan table a reviewer reads to find the loans behind one cell: 3724",
                     "median 15.5, largest 467", "reproduces the filed value on 5 of 48 leaf cells"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_mapping_sheet.py")
        for line in ("leaf cells whose re-run equals the filed value: 17 of 48", "leaf cells flagged: 31 of 48",
                     "planted problems among the leaf cells that the re-run flags: 15 of 18",
                     "flagged but not a problem: 16  (logged_adjustment 4, new_after_asof 12)", "planted problems that pass: 3  (offsetting 3)",
                     "median 28", "derived cells flagged: 23 of 23  (planted footing errors: 3)"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("12 cells are flagged only because rows booked after 2026-06-30", "3 of 3 cells with offsetting changes pass",
                     "14 cells have a source change; a reviewer reads a median of 28 rows per cell to find a cause in a median of 1 row(s)",
                     "4 flagged cells differ by exactly a logged adjustment and 4 by an unlogged amount",
                     "a live re-run flags 23 of 23 derived cells", "finds 3 (ROW.student, COL.d60_89, RATE.overdraft)",
                     "7 open loans sit in no cell", "offsetting found 3 of 3, restated 5 of 5, removed 3 of 3",
                     "late arrivals found 0 of 3", "4 of 4 cells flagged for a note nobody reports"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_step("step_04_with_lineage.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["found"], s["problems"]), (21, 21))
        self.assertEqual((s["false_alarms"], s["benign"]), (0, 46))
        self.assertEqual((s["exact"], s["exact_of"]), (67, 67))
        self.assertEqual((s["named_ok"], s["source_change_cells"]), (14, 14))
        self.assertEqual((s["traced"], s["adjusted"], s["unexplained"], s["source_changed"], s["foot"], s["do_not_foot"]), (26, 4, 4, 14, 20, 3))
        self.assertEqual((s["orphans"], s["known_limit_cells"]), (7, 4))
        for line in ("18 named, against 611 with the mapping sheet", "KNOWN LIMIT: 4 of 4 cells holding a wrong source row verify as TRACED",
                     "12 of 12 cells with rows booked after the as-of date, 4 of 4 cells where only a note changed",
                     "7 found, 7 planted, 7 match"):
            self.assertIn(line, out)

    def test_generator_reproduces_every_committed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "data")
            shutil.copytree(os.path.join(ROOT, "data"), work)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=work, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in sorted(os.listdir(os.path.join(ROOT, "data"))):
                if name.endswith((".csv", ".json")):
                    self.assertTrue(filecmp.cmp(os.path.join(ROOT, "data", name), os.path.join(work, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
