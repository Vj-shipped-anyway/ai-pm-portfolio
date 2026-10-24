"""Pin the numbers the README prints, so a change to a rule or to the data that moves them fails here first."""
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
    def test_step_01_the_person_on_a_schedule(self):
        out = run_step("step_01_no_breaker.py")
        self.assertIn("harmful calls with no stop at all: 312, every one served", out)
        self.assertIn("switch engaged for 6 of 14 must-trip faults, 6 of them while the fault was still running", out)
        self.assertIn("harmful calls served 247 of 312", out)

    def test_step_02_the_common_breaker(self):
        out = run_step("step_02_consecutive_count.py")
        self.assertIn("must-trip faults tripped: 9 of 14   must-not-trip faults tripped: 2 of 7", out)
        self.assertIn("harmful calls served: 168 of 312 (144 avoided)", out)

    def test_step_03_the_deficiencies(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("Scope-violation faults tripped: 0 of 3", out)
        self.assertIn("15 closes, 3 followed by a new trip within 15 min", out)
        self.assertIn("k=3: must-trip tripped 10 of 14, must-not-trip tripped 6 of 7", out)
        self.assertIn("k=8: must-trip tripped 3 of 14, must-not-trip tripped 0 of 7", out)
        self.assertIn("3 of 3 logs are still well formed", out)
        self.assertIn("33 of 312 harmful calls were reported ok by the agent. Silent-error faults tripped: 0 of 2", out)

    def test_step_04_the_breaker(self):
        out = run_step("step_04_with_breaker.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["must_trip_tripped"], s["must_trip"]), (12, 14))
        self.assertEqual((s["must_not_trip_tripped"], s["must_not_trip"]), (2, 7))
        self.assertEqual((s["hard_miss_tripped"], s["hard_miss"]), (0, 4))
        self.assertEqual((s["harm_total"], s["harm_person"], s["harm_common"], s["harm_breaker"]), (312, 247, 168, 142))
        self.assertEqual((s["held_harmless_common"], s["held_harmless_breaker"]), (140, 267))
        self.assertEqual((s["audit_events"], s["tamper_detected_with_head"], s["tamper_tests"]), (7599, 4, 4))
        self.assertIn("calls that reached the agent while open: 0", out)
        self.assertIn("detected without the stored head hash: 3 of 4; with it: 4 of 4", out)
        self.assertIn("trips by rule: critical 3, consecutive 10, rate 2", out)

    def test_demo_command_matches_the_readme(self):
        r = subprocess.run([sys.executable, "agent_breaker.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "agent payment-repair   90 calls: 47 to the agent, 43 held for a person")
        self.assertEqual(lines[-1], "decision: TRIPPED 1 time")


if __name__ == "__main__":
    unittest.main()
