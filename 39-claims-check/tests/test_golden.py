"""Pin the numbers the README prints, and run the tool on its own README."""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

import _bootstrap  # noqa: F401
import claims_check as cc

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")
STEPS = ["step_01_no_check.py", "step_02_grep_for_the_number.py", "step_03_deficiencies_exposed.py", "step_04_with_claims_check.py"]


class GoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = {}
        for name in STEPS:
            r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
            assert r.returncode == 0, (name, r.stderr[-300:])
            cls.out[name] = r.stdout

    def test_step_01(self):
        out = self.out[STEPS[0]]
        self.assertIn("green bullets: 284 (98 cite a number no script prints, 186 are fine)", out)
        self.assertIn("bullets the current CI stops: 0 of 98", out)

    def test_step_02(self):
        out = self.out[STEPS[1]]
        self.assertIn("unsupported bullets caught: 38 of 98", out)
        self.assertIn("fine bullets flagged by mistake: 19 of 186", out)

    def test_step_03(self):
        out = self.out[STEPS[2]]
        for line in ("grep, one line at a time     caught 38 of 98   false alarms 19 of 186",
                     "grep on extracted claims     caught 46 of 98   false alarms 0 of 186",
                     "whole numbers, no pairs      caught 68 of 98   false alarms 0 of 186",
                     "whole numbers and pairs      caught 80 of 98   false alarms 8 of 186",
                     "the same, single digits too  caught 88 of 98   false alarms 16 of 186",
                     "pair_broken 0 of 12 without, 12 of 12 with",
                     "coincidence 10 of 10 pass"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = self.out[STEPS[3]]
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["caught"], s["unsupported"]), (80, 98))
        self.assertEqual((s["false_alarms"], s["supported"]), (8, 186))
        self.assertEqual((s["grep_caught"], s["grep_false_alarms"]), (38, 19))
        self.assertEqual((s["to_open"], s["bullets"]), (88, 284))
        self.assertIn("flags outside every planted bullet: 0", out)
        self.assertIn("still missed, by planted kind: coincidence 10, single_digit 8", out)
        self.assertIn("false alarms, by planted kind: pair_split 8", out)

    def test_planted_kinds(self):
        with open(os.path.join(DATA, "truth.csv"), encoding="utf-8") as fh:
            kinds = Counter(ln.split(",")[3] for ln in fh.read().splitlines()[1:])
        self.assertEqual(kinds, Counter({
            "exact": 90, "comma": 12, "trailing_period": 12, "trailing_zero": 10, "inert_digits": 24,
            "wrapped_ok": 10, "not_green": 12, "small_numeral": 8, "pair_split": 8, "typo": 14, "stale": 14,
            "invented": 10, "substring_trap": 14, "rounded": 8, "pair_broken": 12, "wrapped_bad": 8,
            "coincidence": 10, "single_digit": 8}))

    def test_generator_reproduces_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = os.path.join(tmp, "data")
            os.makedirs(work)
            shutil.copy(os.path.join(DATA, "_generate.py"), work)
            subprocess.run([sys.executable, "_generate.py"], cwd=work, check=True, capture_output=True)
            for name in ("projects.json", "truth.csv", "example_claims.md", "example_output.txt"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(work, name), shallow=False), name)

    def test_readme_shows_the_real_demo_output(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        shown = readme.split("It prints:\n\n```text\n", 1)[1].split("```", 1)[0]
        with open(os.path.join(SRC, "out", "demo_run.txt"), encoding="utf-8") as fh:
            self.assertEqual(shown, fh.read())

    def test_the_tool_checks_its_own_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name in STEPS:
                p = os.path.join(tmp, name + ".txt")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(self.out[name])
                paths.append(p)
            paths.append(os.path.join(DATA, "README.md"))
            r = subprocess.run([sys.executable, os.path.join(SRC, "claims_check.py"), "check", os.path.join(ROOT, "README.md"),
                                "--evidence"] + paths, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout[-600:])
            self.assertIn("result: PASS", r.stdout)
            self.assertEqual(cc.MIN_DIGITS, 2)


if __name__ == "__main__":
    unittest.main()
