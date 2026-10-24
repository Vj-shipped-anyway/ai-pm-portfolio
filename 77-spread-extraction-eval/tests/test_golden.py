"""Pin the numbers the README prints, so a change to a rule or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run(script, *args):
    r = subprocess.run([sys.executable, script, *args], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01_pilot(self):
        out = run("step_01_pilot_only.py")
        self.assertIn("fixed_label: 880 of 880 values correct (100.0%), 20 of 20 documents with every field right", out)
        self.assertIn("documents the pilot never touched: 100 of 120 (83.3%)", out)

    def test_step_02_pooled(self):
        out = run("step_02_pooled_accuracy.py")
        self.assertIn("alias_aware: 94.7% pooled field accuracy (5002 of 5280 values, 120 documents)", out)
        self.assertIn("fixed_label: 43.2% pooled field accuracy (2282 of 5280 values, 120 documents)", out)
        self.assertIn("pooled gain from fixed_label to alias_aware: 51.5 points", out)
        self.assertIn("tie-out check on alias_aware: flags 20 of 120 documents", out)

    def test_step_03_hidden(self):
        out = run("step_03_deficiencies_exposed.py")
        self.assertIn("best 100.0% (plain_two_column), worst 68.4% (note_column), spread 31.6 points", out)
        for line in ("note_column 5%               98.4%", "even over six layouts        94.7%",
                     "note_column 30%              90.5%", "note_column 60%              81.0%"):
            self.assertIn(line, out)
        self.assertIn("a random audit of 10 documents holds no note_column statement in 146 of 1000 draws", out)
        self.assertIn("documents with every field right: 100 of 120 (83.3%), against 94.7% of fields", out)
        self.assertIn("documents with a wrong value: 100 of 120; 15 of them pass every accounting identity", out)
        self.assertIn("thousands_parens: 15 of 20 documents read wrong and tie out", out)

    def test_step_04_gate(self):
        out = run("step_04_layout_scorer.py")
        self.assertIn("alias_aware on the 5 development layouts: PASS", out)
        self.assertIn("alias_aware on all 6 layouts: FAIL", out)
        self.assertIn("note_column: 68.4% is below the floor of 95.0% and 31.6 points below plain_two_column", out)
        self.assertIn("fixed_label on the 5 development layouts: FAIL", out)
        self.assertIn("note_column: 7 of 22 fields fall below 100.0%", out)
        self.assertIn("wrong values by class: wrong_period 136, other 142", out)
        self.assertIn("24 development documents with a negative value (loss or deficit); 24 read with every field right; tie-out false alarms 0", out)
        self.assertIn("the tie-out check on fixed_label passes 15 of 100 documents that have a wrong value", out)
        self.assertIn("tie-out on alias_aware: 0 of 20 wrong documents pass every identity; false alarms on right documents 0 of 100", out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual(s["alias_aware_layout"]["thousands_parens"], 100.0)
        self.assertEqual(s["fixed_label_layout"], {"note_column": 68.4, "plain_two_column": 100.0, "relabelled": 18.2,
                                                   "side_by_side": 72.7, "thousands_parens": 0.0, "wrapped_footnotes": 0.0})

    def test_demo_prints_the_bundled_result(self):
        out = run("spread_eval.py", "--demo")
        self.assertIn("plain_two_column      20     880      880     100.0%             20 of 20", out)
        self.assertIn("all layouts pooled    120    5280     2282      43.2%", out)
        self.assertIn("gate (floor 95.0%, max gap 3.0 points, at least 10 documents per layout): FAIL", out)


if __name__ == "__main__":
    unittest.main()
