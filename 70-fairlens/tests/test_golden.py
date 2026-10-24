"""Pin the numbers the README prints, so a change to a rule or to the data that moves them fails here first."""
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
    @classmethod
    def setUpClass(cls):
        cls.s1 = run("step_01_model_card_only.py")
        cls.s2 = run("step_02_reason_code_review.py")
        cls.s3 = run("step_03_deficiencies_exposed.py")
        cls.s4 = run("step_04_with_fairlens.py")
        cls.demo = run("fairlens_pack.py", "--demo")

    def test_step_01(self):
        self.assertIn("portfolios: 36   planted proxy: 14   no planted proxy: 22", self.s1)
        self.assertIn("applicants per portfolio: 760 to 830 (29,460 in all)", self.s1)
        self.assertIn("mean accuracy, planted proxy: 73.3%   no planted proxy: 75.4%", self.s1)
        self.assertIn("lowest group approves under 0.80 of the reference rate: 22 of 36", self.s1)

    def test_step_02(self):
        self.assertIn("planted proxy (14): PASS 13, REVIEW 1, FAIL 0", self.s2)
        self.assertIn("no planted proxy (22): PASS 18, REVIEW 4, FAIL 0 (REVIEW for too few matched pairs: 4)", self.s2)

    def test_step_03(self):
        self.assertIn("flags 22 of 36 portfolios; planted proxies among them: 10", self.s3)
        self.assertIn("flagged 6 of 6; with the 95% interval, T2 FAIL 0 and REVIEW 6", self.s3)
        self.assertIn("planted proxies called: 10 of 14", self.s3)
        self.assertIn("called 4 of 5; accuracy lost by removing it, in points: 3.3, 4.0, 5.1, 2.0, 1.8", self.s3)
        self.assertIn("false alarms on the 22 portfolios with no planted proxy: 5", self.s3)
        self.assertIn("planted proxies passed: 13 of 14", self.s3)

    def test_step_04_summary(self):
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["found_by_t4"], s["planted"]), (7, 14))
        self.assertEqual((s["false_t4"], s["others"]), (1, 22))
        self.assertEqual((s["t5_pass_t4_fail"], s["t4_fail"]), (6, 8))
        self.assertEqual((s["predictive_t4_fail"], s["predictive_t4_review"], s["predictive"]), (0, 4, 5))
        self.assertEqual((s["noise_point_air_flagged"], s["noise_t2_fail"], s["noise_t2_review"], s["noise"]), (6, 0, 6, 6))
        self.assertEqual((s["overall_fail_planted"], s["overall_fail_others"]), (10, 2))
        self.assertEqual(s["missed"], 7)
        self.assertEqual((s["t6_review"], s["overall_pass"]), (25, 0))

    def test_step_04_report(self):
        self.assertIn("planted proxies marked FAIL by the ablation (T4): 7 of 14", self.s4)
        self.assertIn("C18 proxy_gap    lowest AIR 0.818 -> 0.861, T4 PASS", self.s4)
        self.assertIn("reason naming (T6): FAIL 4, REVIEW 25, PASS 7 of 36; overall PASS: 0 of 36", self.s4)

    def test_demo_output(self):
        lines = self.demo.splitlines()
        self.assertEqual(lines[0], "fairlens: 830 applicants in 3 groups, cutoff 126, reference Group A")
        self.assertIn("T4 proxy ablation  FAIL    lowest AIR 0.702 -> 0.936, accuracy 71.8% -> 73.9%", lines[4])
        self.assertIn("T5 reason pairs    PASS    101 of 149 cross-group pairs differ in top reason (67.8%) against 66.3% within Group A (+1.5 points)", lines[5])
        self.assertEqual(lines[-1], "overall: FAIL (3 FAIL, 1 REVIEW, 2 PASS)")


if __name__ == "__main__":
    unittest.main()
