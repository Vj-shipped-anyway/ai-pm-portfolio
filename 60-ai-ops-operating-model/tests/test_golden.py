"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_self_reported_status.py")
        for line in ("reported stage equals the true stage: 16 of 60",
                     "reported stage above the true stage: 36 of 60 (118 stages over in total)",
                     "reported stage below the true stage: 8 of 60",
                     "true stage below 6: 14 of 18"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_presence_checklist.py")
        for line in ("items asked of every program: 23; items a tier-1 program owes: 10",
                     "stage reached equals the true stage: 19 of 60",
                     "claims above the true stage that it flags: 28 of 36",
                     "flags as overclaims: 11 of 24",
                     "items flagged missing that the program's tier does not owe: 220 in 44 programs",
                     "blank_ref 9, future 2, hollow 19, lapsed 24, self_signed 5"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("all five checks: stage reached equals the true stage in 45 of 60; defective items accepted: 24",
                     "without tier-aware owed list            32 of 60; 24",
                     "without placeholder reference test      41 of 60; 33",
                     "without future-date test                45 of 60; 26",
                     "without freshness, 1.5 x cycle          37 of 60; 43",
                     "without independence from the builder   44 of 60; 29",
                     "lapsed       19 of 24", "hollow       0 of 19",
                     "planted-ok items the full review rejects: 8",
                     "KNOWN LIMIT - programs where the review reaches a higher stage than the truth: 14 of 60"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_step("step_04_evidence_review.py")
        for line in ("stage reached equals the true stage: 45 of 60",
                     "review stage above the truth: 14 of 60; below the truth: 1 of 60",
                     "claims above the true stage: 36 of 60; the review flags 30 of them",
                     "claims flagged as overclaims that were not: 0 of 24",
                     "decisions: CONFIRMED 19, OVERCLAIM 30, UNDERCLAIM 11",
                     "items judged: 1024 owed, 356 not owed",
                     "first 90 days, every owed item evidenced: review 18 of 60, planted truth 14 of 60",
                     "overclaims that still pass: 6 of 36",
                     "P-053 claimed 7, review 8, truth 3: hollow I08"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["stage_matches"], s["overclaims_flagged"], s["overclaims_passed"], s["confirmed"]), (45, 30, 6, 19))

    def test_the_command_line_agrees_with_step_04(self):
        r = subprocess.run([sys.executable, "ops_model_review.py", "review", "--checklist", "../data/checklist.csv",
                            "--programs", "../data/programs.csv", "--evidence", "../data/evidence.csv",
                            "--as-of", "2026-09-30", "--fail-on", "never"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("programs: 60   confirmed 19   overclaim 30   underclaim 11", r.stdout)

    def test_demo_output_is_the_one_in_the_readme(self):
        r = subprocess.run([sys.executable, "ops_model_review.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        self.assertIn(r.stdout.strip(), readme)


class DataTests(unittest.TestCase):
    def test_generator_reproduces_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in sorted(os.listdir(DATA)):
                if name.endswith((".csv", ".txt")):
                    with open(os.path.join(DATA, name), "rb") as a, open(os.path.join(tmp, name), "rb") as b:
                        self.assertEqual(a.read(), b.read(), name)

    def test_demo_page_carries_the_step_04_summary(self):
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            summary = json.load(fh)
        with open(os.path.join(ROOT, "demo.html"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn(json.dumps(summary), page)
        self.assertNotIn("innerHTML", page)
        self.assertTrue(re.search(r"prefers-color-scheme: dark", page))
        self.assertIn("width=device-width", page)


if __name__ == "__main__":
    unittest.main()
