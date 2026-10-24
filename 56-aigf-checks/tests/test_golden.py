"""Pin the numbers the README prints, so a change to a rule or to the data that moves them fails here first."""
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
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_recheck.py")
        for line in ("risks: 24   checks: 20   crosswalk rows: 73   captured outputs: 17",
                     "rows that hold up today: 28 of 73",
                     "rows with a planted defect: 45 of 73",
                     "rows the sheet itself flags: 0 of 73",
                     "risks with at least one row: 21 of 24",
                     "risks a reader who trusts every full row would call covered: 20 of 24",
                     "planted truth by status: CHECKED 16, PARTIAL 3, UNVERIFIED 2, GAP 3"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_link_and_grep.py")
        for line in ("rows flagged: 17 of 73", "defective rows flagged: 11 of 45",
                     "harmless rows flagged by mistake: 6 of 28", "ok_reformatted: 6 of 6",
                     "risks with the right status: 18 of 24"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("(a) a short number is found inside a longer one: 5 of 10 stale rows pass",
                     "(b) the label is ignored, so a renamed line passes: 4 of 4 rows pass",
                     "(c) no output file means the row is skipped, silently: 4 of 4 rows pass",
                     "(d) the aspects are not read, so a row marked full passes: 7 of 7 rows pass",
                     "(g) a harmless difference in print format is flagged: 6 of 6 rows",
                     "risks given the wrong status: 6 of 24"):
            self.assertIn(line, out)
        known = out.split("KNOWN LIMIT")[1]
        self.assertEqual(sum(1 for ln in known.splitlines() if ln.startswith("  ROW-")), 7)

    def test_step_04(self):
        out = run_step("step_04_with_checks.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["found"], s["defective"]), (38, 45))
        self.assertEqual((s["false_alarms"], s["clean"]), (0, 28))
        self.assertEqual((s["to_read"], s["rows"]), (38, 73))
        self.assertEqual((s["risks_right"], s["risks"]), (23, 24))
        self.assertEqual((s["missed"], s["compared"]), (7, 62))
        for line in ("wording_paraphrase  0 of 3", "false_declaration   0 of 4", "stale_value         10 of 10",
                     "R-18 CHECKED, truth PARTIAL"):
            self.assertIn(line, out)


if __name__ == "__main__":
    unittest.main()
