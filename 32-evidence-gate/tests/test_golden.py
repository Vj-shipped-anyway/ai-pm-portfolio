"""Pin the numbers the README prints, so a change to the parser or the data that moves them fails here first."""
import csv
import filecmp
import json
import os
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
        out = run_step("step_01_no_gate.py")
        self.assertIn("pull requests merged: 107   use cases: 36", out)
        self.assertIn("truth: 59 lack evidence the true tier requires, 6 carry the wrong tier label, 42 are fine", out)
        self.assertIn("pull requests the current process stops: 0 of 107", out)
        self.assertIn("evidence items owed across all pull requests: 642; missing, stale or unusable: 129", out)

    def test_step_02(self):
        out = run_step("step_02_checklist_rule.py")
        self.assertIn("pull requests that pass the check: 98 of 107", out)
        self.assertIn("should-block pull requests stopped: 8 of 59", out)
        self.assertIn("should-block pull requests that pass: 51 of 59", out)
        self.assertIn("fine pull requests stopped: 1 of 42", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("without the registry\n    should-block pull requests blocked: 41 of 59",
                     "without the file listing\n    should-block pull requests blocked: 44 of 59",
                     "without the dates\n    should-block pull requests blocked: 37 of 59",
                     "parser only\n    should-block pull requests blocked: 24 of 59",
                     "KNOWN LIMIT - should-block pull requests the full gate allows: 7 of 59",
                     "should-block pull requests the full gate only sends to review: 3 of 59 (unregistered_understated)"):
            self.assertIn(line, out)

    def test_step_04_and_summary_file(self):
        out = run_step("step_04_with_gate.py")
        for line in ("should-block pull requests blocked: 49 of 59",
                     "blocked ones that name exactly the planted bad items: 46 of 46 (the 3 with no record name none)",
                     "fine pull requests blocked: 3 of 42 (table_format); sent to review: 7 of 42 (external_link, unregistered_honest)",
                     "hard negatives allowed: at_limit 2 of 2, complete_formatted 8 of 8",
                     "wrong-tier-label pull requests sent to review: 6 of 6",
                     "decision matches the planted truth: 87 of 107",
                     "pull requests a reviewer is asked to look at: 16 of 107 (the author fixes the 52 blocked ones)",
                     "should-block that still pass: 7 of 59 (stale_registry, wrong_content)"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["blocked"], s["should_block"], s["missed"], s["review_only"], s["to_review"]), (49, 59, 7, 3, 16))

    def test_data_reproduces_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in sorted(os.listdir(DATA)):
                if name.endswith((".csv", ".json", ".txt", ".md")) and name != "README.md":
                    self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_planted_set_has_the_hard_cases_the_readme_names(self):
        with open(os.path.join(DATA, "pr_cases.csv"), newline="", encoding="utf-8") as fh:
            bodies = {r["pr_id"]: r["body"] for r in csv.DictReader(fh)}
        with open(os.path.join(DATA, "pr_truth.csv"), newline="", encoding="utf-8") as fh:
            truth = list(csv.DictReader(fh))
        kinds = {}
        for t in truth:
            kinds.setdefault(t["defect_kind"], []).append(t["pr_id"])
        self.assertEqual(len(bodies), 107)
        self.assertTrue(all("\r\n" in bodies[p] for p in kinds["complete_formatted"]))
        fenced = [p for p in kinds["comment_only"] if "```" in bodies[p]]
        self.assertEqual((len(fenced), len(kinds["comment_only"])), (2, 4))
        self.assertEqual({t["truth_class"] for t in truth if t["defect_kind"] == "wrong_content"}, {"should_block"})


if __name__ == "__main__":
    unittest.main()
