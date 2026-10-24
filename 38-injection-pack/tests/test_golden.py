"""Pin the numbers the README prints, so a change to the rules, the engine or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_step(script):
    r = subprocess.run([sys.executable, script], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(script + ": " + r.stderr[-300:])
    return r.stdout


def summary(name):
    with open(os.path.join(SRC, "out", name), encoding="utf-8") as fh:
        return json.load(fh)


class GoldenTests(unittest.TestCase):
    def test_step_01_status_quo(self):
        out = run_step("step_01_no_pack.py")
        s = summary("step_01_summary.json")
        self.assertEqual((s["pop_caught"], s["pop_attacks"], s["pop_false_blocks"], s["pop_benign"]), (790, 1000, 37, 500))
        self.assertEqual((s["pack_caught"], s["pack_attacks"], s["pack_false_blocks"], s["pack_benign"]), (74, 100, 8, 60))
        self.assertEqual((s["hard_caught"], s["hard_attacks"], s["hard_false_blocks"], s["hard_benign"]), (4, 14, 8, 30))
        self.assertEqual((s["harmful"], s["prs"]), (25, 51))
        self.assertIn("harmful pull requests that merge: 25 of 51", out)

    def test_step_02_smoke_test(self):
        run_step("step_02_smoke_test.py")
        s = summary("step_02_summary.json")
        self.assertEqual((s["harmful_blocked"], s["harmful"], s["harmless_blocked"], s["harmless"]), (3, 25, 0, 26))

    def test_step_03_shortcut_gates(self):
        run_step("step_03_deficiencies_exposed.py")
        s = summary("step_03_summary.json")
        g = {k: (v["harmful_blocked"], v["harmless_blocked"]) for k, v in s["gates"].items()}
        self.assertEqual(g, {"floor only": (5, 0), "attacks only": (16, 1), "thin pack (every 4th case)": (12, 0)})
        self.assertEqual(s["passed_all"], 6)

    def test_step_04_full_pack(self):
        out = run_step("step_04_with_pack.py")
        s = summary("step_04_summary.json")
        self.assertEqual((s["harmful_stopped"], s["harmful"]), (21, 25))
        self.assertEqual((s["harmless_stopped"], s["harmless"]), (1, 26))
        self.assertEqual((s["exact"], s["pull_requests"]), (46, 51))
        self.assertEqual((s["missed"], s["missed_with_note"], s["false_alarms"]), (4, 1, 1))
        self.assertIn("held-out attack techniques with no pack case: doc_encoded_blob", out)

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "injection_pack.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("decision: BLOCK (4 regressions)", r.stdout)
        self.assertIn("before: 74 of 100 attacks blocked, 8 of 60 benign cases blocked", r.stdout)
        self.assertIn("after:  70 of 100 attacks blocked, 8 of 60 benign cases blocked", r.stdout)


if __name__ == "__main__":
    unittest.main()
