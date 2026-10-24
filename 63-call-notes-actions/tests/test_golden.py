"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_data_shape(self):
        out = run_step("step_01_no_check.py")
        self.assertIn("notes: 120   sentences: 705   actions the notes commit to: 258", out)
        self.assertIn("candidate actions proposed: 440 (184 grounded, 256 not)", out)

    def test_step_01_no_check(self):
        out = run_step("step_01_no_check.py")
        self.assertIn("ungrounded actions written to the CRM: 256 of 440 (58.2%)", out)
        self.assertIn("planted actions that reach the CRM correctly: 184 of 258", out)

    def test_step_02_citation_present(self):
        out = run_step("step_02_citation_present.py")
        self.assertIn("ungrounded actions stopped: 0 of 256; still written: 256", out)
        self.assertIn("ungrounded actions stopped: 6 of 256; still written: 250", out)
        self.assertIn("grounded actions wrongly rejected: 29 of 184", out)

    def test_step_03_deficiencies_exposed(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("ungrounded stopped (held or dropped): 14 of 256; still written: 242", out)
        self.assertIn("ungrounded stopped (held or dropped): 187 of 256; still written: 69", out)
        self.assertIn("still written, by planted cause: clause_swap 13, conditional 31, hedged_soft 17, negated_phrasal 8", out)

    def test_step_04_summary(self):
        out = run_step("step_04_with_grounding_check.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["ungrounded_written"], s["ungrounded"]), (38, 256))
        self.assertEqual((s["ungrounded_held"], s["ungrounded_rejected"]), (166, 52))
        self.assertEqual((s["grounded_written"], s["grounded"]), (175, 184))
        self.assertEqual((s["grounded_held"], s["grounded_rejected"]), (9, 0))
        self.assertEqual((s["actions_written"], s["actions"], s["to_read"], s["candidates"]), (175, 258, 175, 440))
        self.assertIn("ungrounded actions that still pass: 38 of 256 (clause_swap 13, hedged_soft 17, negated_phrasal 8)", out)
        self.assertIn("planted actions the extractor never put out correctly: 74 of 258", out)
        self.assertIn("grounded actions held, by planted cause: valid_negation_elsewhere 4, valid_spelled_amount 5", out)

    def test_planted_truth_lines_up(self):
        with open(os.path.join(DATA, "candidate_truth.csv"), encoding="utf-8") as fh:
            truth = [ln.rstrip("\n").split(",") for ln in fh][1:]
        with open(os.path.join(DATA, "candidates.csv"), encoding="utf-8") as fh:
            n_cands = len(fh.readlines()) - 1
        self.assertEqual(len(truth), n_cands)
        self.assertTrue(all((row[2] == "1") == row[1].startswith("valid") for row in truth))
        overreach = {"conditional", "negated", "negated_phrasal", "past", "declined", "declined_phrasal", "hedged", "hedged_soft"}
        self.assertTrue(all(row[3] == "" for row in truth if row[1] in overreach))
        self.assertTrue(all(row[3] != "" for row in truth if row[2] == "1"))


if __name__ == "__main__":
    unittest.main()
