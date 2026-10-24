"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import filecmp
import json
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def run(script, *args):
    r = subprocess.run([sys.executable, script, *args], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_demo_first_lines(self):
        lines = run("shadow_score.py", "--demo").splitlines()
        self.assertEqual(lines[0], "shadow-score: 986 matched cases (14 proposals have no outcome yet, 3 outcomes have no proposal)")
        self.assertIn("91.5%  (agreed on 851 of 930 proposals; 56 abstentions dropped)", lines[1])
        self.assertIn("89.5% to 93.1%", lines[2])
        self.assertIn("86.3%", lines[3])
        self.assertEqual(lines[-1], "decision: HOLD  (6 of 10 checks fail, 0 skipped)")

    def test_step_01(self):
        out = run("step_01_one_number.py")
        self.assertIn("cases with both: 986   proposals still waiting for an outcome: 14   outcomes with no proposal: 3", out)
        self.assertIn("agreed on 851 of 930 proposals (91.5%)", out)
        self.assertIn("disagreements a person would have to read to find out why: 79", out)

    def test_step_02(self):
        out = run("step_02_overall_agreement.py")
        self.assertIn("851 of 930 = 91.5%", out)
        self.assertIn("meets the bar: yes", out)
        self.assertIn("off-diagonal cells, abstentions left out: 69 cases", out)

    def test_step_03(self):
        out = run("step_03_deficiencies_exposed.py")
        self.assertIn("56 abstentions; first-report rate 91.5%; counting them as misses 86.3%", out)
        self.assertIn("ESCALATE_FRAUD 25 of 74", out)
        self.assertIn("89.5% to 93.1%", out)
        self.assertIn("always proposing REFUND agrees on 60.1% of matched cases", out)
        self.assertIn("11 of 930 proposals (1.2%)", out)
        self.assertIn("groups flagged (any size): 6   planted problems 3, planted look-alikes 3, unplanted 0", out)
        self.assertIn("groups flagged (at least 30 proposals): 3   planted problems 3, planted look-alikes 0, unplanted 0", out)
        self.assertIn("weeks 12 and 13: 82.4% on 131 proposals; the other weeks: 93.0%; all weeks: 91.5%", out)
        self.assertIn("of 69 outcome disagreements, the truth sides with the agent in 19, with the person in 50, with neither in 0", out)
        self.assertIn("17 of the 851 agreements", out)

    def test_step_04_scorecard(self):
        run("step_04_with_scorecard.py")
        with open(os.path.join(SRC, "out", "step_04_scorecard.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        s = d["score"]
        self.assertEqual((s["matched"], s["pending"], s["orphans"]), (986, 14, 3))
        self.assertEqual((s["agree"], s["proposed"], s["abstained"]), (851, 930, 56))
        self.assertEqual(s["kinds"], {"abstained": 56, "agree": 851, "disagree_outcome": 69, "disagree_value": 10})
        self.assertEqual(round(s["headline"], 3), 0.915)
        self.assertEqual([round(x, 3) for x in s["interval"]], [0.895, 0.931])
        self.assertEqual(round(s["end_to_end"], 3), 0.863)
        self.assertEqual(s["risky"], 11)
        self.assertEqual(d["decision"], "HOLD")
        self.assertEqual({c["id"]: c["result"] for c in d["checks"]},
                         {"C01": "PASS", "C02": "PASS", "C03": "FAIL", "C04": "FAIL", "C05": "PASS", "C06": "FAIL",
                          "C07": "FAIL", "C08": "FAIL", "C09": "PASS", "C10": "FAIL"})
        self.assertEqual((d["planted_found"], d["planted"]), (4, 5))
        self.assertEqual((d["look_alikes_failed"], d["look_alikes"]), (0, 3))
        self.assertEqual(d["agreements_both_wrong"], 17)

    def test_step_04_prints_the_known_limits(self):
        out = run("step_04_with_scorecard.py")
        self.assertIn("week 13 is a planted problem and passes: 85.5% against a floor of 85.0%", out)
        self.assertIn("17 of 851 agreements are cases where both the agent and the person are wrong", out)
        self.assertIn("REQUEST_DOCS sits at 82.8% on 87 proposals", out)

    def test_generator_reproduces_the_committed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, os.path.join(DATA, "_generate.py")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in ("proposals.csv", "outcomes.csv", "case_truth.csv", "planted_problems.csv"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
