"""Pin the numbers the README prints, so a change to the readers, the data or the tool that moves them fails here first."""
import csv
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return " ".join(r.stdout.split())


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = step("step_01_plain_rule_questions.py")
        self.assertIn("plain-rule questions: 30 exception questions it does not contain: 180", out)
        self.assertIn("exception clauses planted in the manuals: 105 touched by a plain-rule question: 0", out)
        self.assertIn("control 30 of 30 180 of 180 truncating 10 of 30 46 of 180 base_only 30 of 30 90 of 180 retrieval 30 of 30 120 of 180", out)
        self.assertIn("catches: 1 of 3 (truncating)", out)
        self.assertIn("still fail exception questions: 2 of 3 (base_only, retrieval)", out)

    def test_step_02(self):
        out = step("step_02_exception_beside_rule.py")
        self.assertIn("questions: 12 of 210", out)
        self.assertIn("control 12 of 12 truncating 4 of 12 base_only 6 of 12 retrieval 12 of 12", out)
        self.assertIn("faulty readers flagged: 2 of 3 (truncating, base_only)", out)

    def test_step_03(self):
        out = step("step_03_deficiencies_exposed.py")
        self.assertIn("all 210 56 120 150", out)
        self.assertIn("crossref 30 7 15 15", out)
        self.assertIn("0%: 33 25%: 10 50%: 13 75%: 0 100%: 0", out)
        self.assertIn("passes 0 of 90 questions where an exception applies", out)
        self.assertIn("passes 30 of 30 with the exception beside the rule, 0 of 45 with it elsewhere, 0 of 15 when a far clause cancels it", out)
        self.assertIn("KNOWN LIMIT", out)
        self.assertIn("passes 90 of 90 questions where the exception does not apply", out)

    def test_step_04(self):
        out = step("step_04_with_gate.py")
        self.assertIn("exception clauses listed: 90 of 105; missed: 15 (restated 15)", out)
        self.assertIn("look-alikes listed by mistake: 12 of 36 (decoy_pointer 12)", out)
        self.assertIn("left alone: 24 (decoy_generic 12, decoy_prohibition 12)", out)
        self.assertIn("the audit lists 45 of them as not named", out)
        self.assertIn("control 210 of 210 0 of 105 0 of 0 0 PASS", out)
        self.assertIn("truncating 56 of 210 84 of 105 84 of 84 0 FAIL", out)
        self.assertIn("base_only 120 of 210 90 of 105 90 of 90 0 FAIL", out)
        self.assertIn("retrieval 150 of 210 60 of 105 60 of 60 0 FAIL", out)
        self.assertIn("faulty readers the gate fails: 3 of 3; control: PASS with 0 cells flagged", out)
        self.assertIn("KNOWN LIMITS", out)

    def test_step_outputs_are_the_same_on_a_second_run(self):
        self.assertEqual(step("step_04_with_gate.py"), step("step_04_with_gate.py"))

    def test_data_files_have_the_rows_the_data_readme_states(self):
        def rows(name):
            with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        self.assertEqual(len(rows("probes.csv")), 210)
        self.assertEqual(len(rows("exceptions_truth.csv")), 141)
        self.assertEqual(len(rows("example_probes.csv")), 8)
        self.assertEqual(len(rows("manuals.csv")), 3)


if __name__ == "__main__":
    unittest.main()
