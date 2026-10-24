"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
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
    def test_step_01_router(self):
        out = run_step("step_01_keyword_router.py")
        self.assertIn("returned a canned passage: 3 of 30 (2 the right passage, 1 the wrong one)", out)
        self.assertIn("pointed to a fees, rates or lending page: 23 of 30", out)
        self.assertIn("handed to a banker: 4 of 30", out)
        self.assertIn("questions the knowledge base can answer: 17; the router answered 2 of them", out)

    def test_step_02_draft_only(self):
        out = run_step("step_02_draft_only.py")
        self.assertIn("drafts served: 28 of 30; 2 drafts decline on their own", out)
        self.assertIn("correct answers served: 10", out)
        self.assertIn("wrong answers served: 18 (60.0% of the 30 questions)", out)
        self.assertIn("ambiguous 3, answerable 6, not_in_kb 5, out_of_scope 3, state_specific 1", out)

    def test_step_03_each_check_alone(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("source check only                                  wrong served 12 of 18   correct served 10 of 10", out)
        self.assertIn("(the question only)    wrong served  9 of 18   correct served  9 of 10", out)
        self.assertIn("grounding only (the draft only)                    wrong served  5 of 18   correct served  8 of 10", out)
        self.assertIn("every claim must be supported (1.0)                wrong served  3 of 18   correct served  7 of 10", out)
        self.assertIn("half of the claims must be supported (0.5)         wrong served  5 of 18   correct served  7 of 10", out)
        self.assertIn("wrong drafts a loose threshold lets through: Q13 (fake_citation), Q14 (wrong_number)", out)
        for qid in ("Q05", "Q10", "Q16"):
            self.assertIn(f"    {qid} wrong_slot:", out)

    def test_step_04_gate(self):
        out = run_step("step_04_with_gate.py")
        self.assertIn("wrong answers served: 3 of 30 (step 2 served 18)", out)
        self.assertIn("wrong drafts held back: 15 of 18", out)
        self.assertIn("correct drafts served: 7 of 10; held back by mistake: 3", out)
        self.assertIn("handed to a banker in all: 20 of 30 (66.7%)", out)
        self.assertIn("held back by check: ambiguous 3, handoff 2, no_source 4, out_of_scope 3, ungrounded 7, unverifiable 1", out)
        self.assertIn("hard negatives (correct drafts a rule could flag): 6; served 3, held back 3", out)
        self.assertIn("hard misses planted (right number, different meaning): 3; served 3", out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["wrong_served"], s["wrong_served_draft_only"], s["caught"]), (3, 18, 15))
        self.assertEqual((s["served_ok"], s["false_abstain"], s["held"]), (7, 3, 20))

    def test_steps_are_repeatable(self):
        self.assertEqual(run_step("step_04_with_gate.py"), run_step("step_04_with_gate.py"))

    def test_demo_line(self):
        r = subprocess.run([sys.executable, "smb_faq_abstain.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines()[0], "question: Does the Business Credit Card have an annual fee?")
        self.assertIn("decision: ABSTAIN (ungrounded) yes or no disagrees with the source (source F07)", r.stdout)


if __name__ == "__main__":
    unittest.main()
