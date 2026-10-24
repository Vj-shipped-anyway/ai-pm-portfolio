"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01_relevance_only(self):
        out = step("step_01_relevance_only.py")
        for line in ("unchanged main: 424 results, 86.3% relevant, 0 returned",
                     "exhaustive probe: 28 of 50 pull requests",
                     "leaking pull requests the eval stops: 7 of 28",
                     "clean pull requests the eval stops: 9 of 22",
                     "leaked results in those eval runs: 923; scored as correct answers: 739"):
            self.assertIn(line, out)

    def test_step_02_string_match(self):
        out = step("step_02_string_match.py")
        for line in ("already firing on the unchanged main: 2", "leaking pull requests caught: 3 of 28",
                     "clean pull requests flagged: 5 of 22"):
            self.assertIn(line, out)

    def test_step_03_variants(self):
        out = step("step_03_deficiencies_exposed.py")
        for line in ("A random pack, unprimed: leaking caught 15 of 28; clean flagged 5 of 22",
                     "B stratified pack, unprimed: leaking caught 15 of 28; clean flagged 5 of 22",
                     "C stratified pack, primed: leaking caught 20 of 28; clean flagged 5 of 22",
                     "D C plus every returned document checked: leaking caught 27 of 28; clean flagged 0 of 22",
                     "canaries in the stratified pack aimed at those pairs: 1"):
            self.assertIn(line, out)

    def test_step_04_summary(self):
        step("step_04_with_canary.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["leaking_blocked"], s["leaking"]), (27, 28))
        self.assertEqual((s["clean_blocked"], s["clean"]), (0, 22))
        self.assertEqual(s["clean_reviewed"], 3)
        self.assertEqual((s["to_read"], s["pull_requests"]), (30, 50))
        self.assertEqual((s["incidental"], s["passed"], s["pack"]), (7, 1, 62))

    def test_demo_command_output(self):
        r = subprocess.run([sys.executable, "entitlement_canary.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.splitlines()[-1], "decision: BLOCK")
        self.assertIn("leaks 1;", r.stdout)


if __name__ == "__main__":
    unittest.main()
