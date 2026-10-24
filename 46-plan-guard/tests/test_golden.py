"""Pin the numbers the README prints, so a change to a rule that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_script(name, *args):
    r = subprocess.run([sys.executable, name, *args], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_demo_output(self):
        out = run_script("plan_guard.py", "--demo").splitlines()
        self.assertEqual(out[0], "plan: example_plan.json   format_version 1.2   7 resource changes, 5 checked")
        self.assertEqual(out[-1], "decision: BLOCK")
        self.assertEqual(len(out), 6)

    def test_step_01(self):
        out = run_script("step_01_no_gate.py")
        for text in ("plans applied: 86", "resource changes in them: 388",
                     "42 should be blocked, 10 need a person to look, 34 are harmless",
                     "plans the current CI stops: 0 of 86", "plans that apply a risky resource unchecked: 42 of 86"):
            self.assertIn(text, out)

    def test_step_02(self):
        out = run_script("step_02_text_search.py")
        for text in ("plans flagged: 58 of 86", "flagged plans that are harmless: 23 of 58 (39.7%)",
                     "risky plans never flagged: 17 of 52"):
            self.assertIn(text, out)

    def test_step_03(self):
        out = run_script("step_03_deficiencies_exposed.py")
        for text in ("harmless plans blocked: 7 of 34", "harmless plans blocked, by planted change: delete_violating 4, noop_violating 3",
                     "plans that need a look, flagged (REVIEW or BLOCK): 3 of 10",
                     "pass silently, by planted change: unknown_encryption 4, unknown_policy 3",
                     "risky plans that neither gate blocks: 9 of 42", "the step 2 text search flags 6"):
            self.assertIn(text, out)

    def test_step_04_summary(self):
        run_script("step_04_with_guard.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["risky_blocked"], s["risky"]), (33, 42))
        self.assertEqual((s["review_flagged"], s["review"]), (10, 10))
        self.assertEqual((s["harmless_blocked"], s["harmless_reviewed"], s["harmless"]), (0, 4, 34))
        self.assertEqual((s["exact_match"], s["plans"]), (73, 86))
        self.assertEqual((s["to_read"], s["missed_risky"]), (47, 9))

    def test_step_04_prints_the_known_misses(self):
        out = run_script("step_04_with_guard.py")
        self.assertIn("risky plans that still pass: 9 of 42 (policy_weak_condition, queue_policy_world, split_world_cidr)", out)
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("    PLAN-")), 9)


if __name__ == "__main__":
    unittest.main()
