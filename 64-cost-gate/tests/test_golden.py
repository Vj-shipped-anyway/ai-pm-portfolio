"""Pin the numbers the README prints, so a change to the gate or the data that moves them fails here first."""
import csv
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
    def test_step_01(self):
        out = run_step("step_01_no_gate.py")
        for line in ("change requests merged: 40   eval items per run: 236",
                     "truth, from the generating parameters: 21 over budget, 19 within budget",
                     "change requests the current CI stops: 0 of 40",
                     "over budget on the whole run: 15 of 21; over only inside one slice: 6 of 21"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_cost_per_call.py")
        for line in ("change requests failed: 12 of 40",
                     "over budget and failed: 8 of 21",
                     "over budget and passed: 13 of 21",
                     "within budget and failed (false alarms): 4 of 19",
                     "over budget although cost per call fell below the baseline: 6 of 21"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("over budget and failed: 18 of 21", "within budget and failed: 2 of 19",
                     "over budget and failed: 9 of 21", "within budget and failed: 0 of 19",
                     "over budget only inside a slice, so the whole-run gate passes it: 6 of 21",
                     "with every fourth item (59 items) the interval gate fails 5 of 21 over-budget change requests, against 13 on the full set",
                     "slices judged alone on the smaller set: 0 of 5",
                     "over budget and passed by both gates: 3 of 21"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run_step("step_04_with_cost_gate.py")
        for line in ("over budget: FAIL 13, WARN 5, PASS 3 (of 21)",
                     "within budget: FAIL 0, WARN 2, PASS 17 (of 19)",
                     "change requests that stop the build: 13 of 40; that a person reads (FAIL or WARN): 20 of 40",
                     "planted slice regressions failed on a slice ceiling: 4 of 4; the whole-run status was PASS on 4 of them",
                     "with --fail-on warn the build would also stop on the WARN ones: 18 of 21 over budget, 2 of 19 within budget",
                     "over budget and still PASS: 3 of 21",
                     "CR-010 thin_slice_regression", "CR-024 thin_slice_regression", "CR-029 small_overshoot"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["over_fail"], s["over_warn"], s["over_pass"]), (13, 5, 3))
        self.assertEqual((s["within_fail"], s["within_warn"], s["within_pass"]), (0, 2, 17))

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "cost_gate.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "run: 236 items, 5 slices")
        self.assertIn("overall              236      201    0.00655  0.00600 to 0.00711   0.00670  PASS", lines)
        self.assertIn("card_services         48       42    0.00823  0.00703 to 0.00943   0.00610  FAIL", lines)
        self.assertEqual(lines[-1], "decision: FAIL")


class DataTests(unittest.TestCase):
    def test_shape_of_the_committed_data(self):
        with open(os.path.join(DATA, "eval_runs.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        runs = {}
        for r in rows:
            runs.setdefault(r["cr_id"], []).append(r["item_id"])
        self.assertEqual(len(runs), 41)
        self.assertTrue(all(len(v) == 236 and len(set(v)) == 236 for v in runs.values()))
        with open(os.path.join(DATA, "cr_truth.csv"), newline="", encoding="utf-8") as fh:
            truth = list(csv.DictReader(fh))
        self.assertEqual(len(truth), 40)
        self.assertEqual(sum(1 for t in truth if t["truth_class"] == "over_budget"), 21)


if __name__ == "__main__":
    unittest.main()
