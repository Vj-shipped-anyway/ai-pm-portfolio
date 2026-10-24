"""Pin the numbers the README prints, so a change to the tool or the data that moves them fails here first."""

from __future__ import annotations

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
import runbook_dryrun as rd

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = step("step_01_prose_runbook.py")
        for line in ("drill cases: 94 (33 complete, 8 park at a gate, 53 go wrong)",
                     "problems met only while following the runbook: 53 of 94",
                     "high-risk change goes ahead with no valid approval: 25",
                     "run stops part-way: 23; a command is sent with a parameter never filled in: 5",
                     "run stops or garbles after a write step has already gone through: 12 of 53",
                     "steps already done when the first problem shows, on average: 2.1"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = step("step_02_echo_dry_run.py")
        for line in ("plans printed: 94 of 94; exit status 0 on 94",
                     "problems a reader can see in the printed plan: 5 of 53",
                     "plans that look fine though a real run goes wrong: 48 of 53",
                     "invalid approvals noticed: 0 of 16", "false alarms: 0 of 41"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = step("step_03_deficiencies_exposed.py")
        self.assertEqual(out.count("blocked cases caught: 17 of 53"), 2)
        self.assertIn("blocked cases caught: 16 of 53", out)
        self.assertIn("clean or waiting cases blocked wrongly: 3 of 41", out)
        self.assertIn("blocked cases caught by at least one part: 46 of 53", out)
        self.assertIn("by planted change: mislabeled_effect 4, world_drift 3", out)

    def test_step_04_summary(self):
        out = step("step_04_with_dryrun.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["blocked_caught"], s["blocked"]), (46, 53))
        self.assertEqual((s["false_alarms"], s["clean_or_waiting"]), (3, 41))
        self.assertEqual((s["exact_match"], s["cases"]), (84, 94))
        self.assertEqual((s["waiting_held"], s["missed"]), (8, 7))
        for line in ("hard negatives that pass: 14 of 17", "missing rollback warned: 4 of 4; warnings on any other case: 0",
                     "blocked cases that still pass: 7 of 53 (mislabeled_effect, world_drift)"):
            self.assertIn(line, out)

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "runbook_dryrun.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "runbook: scorer-rollback   5 steps   requester: dana")
        self.assertIn("REJECTED", lines[3])
        self.assertIn("marta: digest_mismatch", lines[-2])
        self.assertEqual(lines[-1], "verdict: BLOCKED")

    def test_generator_reproduces_the_committed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(DATA, "_generate.py"), tmp)
            r = subprocess.run([sys.executable, "_generate.py"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-300:])
            for name in ("cases.csv", "truth.csv", "example_runbook.yml", "example_world.json", "example_approvals.json"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(tmp, name), shallow=False), name)

    def test_every_generated_runbook_loads(self):
        with open(os.path.join(DATA, "cases.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 94)
        for r in rows:
            rd.load_runbook(r["runbook_yaml"])


if __name__ == "__main__":
    unittest.main()
