"""Pin the numbers the README prints, so a change to the reader or the formulas that moves them fails here first."""
import csv
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = step("step_01_no_tieout.py")
        self.assertIn("figures in the memos: 308 (124 wrong, 184 fine)", out)
        self.assertIn("memos that carry at least one wrong figure: 28 of 28", out)

    def test_step_02(self):
        out = step("step_02_value_anywhere.py")
        self.assertIn("wrong figures caught: 98 of 124", out)
        self.assertIn("fine figures flagged by mistake: 107 of 184", out)
        self.assertIn("percents and multiples flagged, right or wrong: wrong 71 of 71, fine 100 of 100", out)

    def test_step_03(self):
        out = step("step_03_deficiencies_exposed.py")
        for expected in ("caught  98 of 124   false alarms 107 of 184", "caught  40 of 124   false alarms   0 of 184",
                         "caught  72 of 124   false alarms  22 of 184", "caught  88 of 124   false alarms   0 of 184",
                         "caught 104 of 124   false alarms  12 of 184"):
            self.assertIn(expected, out)
        self.assertIn("KNOWN LIMIT: prose_tag_mismatch passes d and e: 10 of 10; unparsed_form is never read: 10 of 10 pass", out)

    def test_step_04_summary(self):
        out = step("step_04_with_memo_tieout.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["caught"], s["wrong"]), (104, 124))
        self.assertEqual((s["false_alarms"], s["fine"]), (12, 184))
        self.assertEqual((s["to_open"], s["figures"]), (116, 308))
        self.assertEqual((s["step_02_caught"], s["step_02_false_alarms"]), (98, 107))
        self.assertEqual(s["missed"], 20)
        self.assertIn("flags outside every planted figure: 0", out)
        self.assertIn("still missed, by planted kind: prose_tag_mismatch 10, unparsed_form 10", out)
        self.assertIn("false alarms, by planted kind: term_untagged 12", out)

    def test_every_planted_figure_sits_at_its_recorded_position(self):
        with open(os.path.join(DATA, "memos.json"), encoding="utf-8") as fh:
            memos = {m["memo_id"]: m["memo"].split("\n") for m in json.load(fh)}
        with open(os.path.join(DATA, "truth.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 308)
        for r in rows:
            line, col = memos[r["memo_id"]][int(r["line"]) - 1], int(r["col"]) - 1
            self.assertEqual(line[col:col + len(r["text"])], r["text"], r)

    def test_the_demo_output_is_what_the_readme_shows(self):
        out = subprocess.run([sys.executable, "memo_tieout.py", "--demo"], cwd=SRC, capture_output=True, text=True).stdout
        self.assertIn("figures: 10 read: 4 tie, 2 do not tie, 1 unresolved, 2 untied, 1 set aside as terms", out)
        self.assertTrue(out.rstrip().endswith("result: FAIL"))


if __name__ == "__main__":
    unittest.main()
