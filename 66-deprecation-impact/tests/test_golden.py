"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401
import deprecation_impact as di

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_map.py")
        self.assertIn("7 retirement notices, 2 already past", out)
        self.assertIn("42 in 36 of 60 features", out)
        self.assertIn("by role: 28 primary, 10 fallback, 4 judge", out)

    def test_step_02(self):
        out = run_step("step_02_exact_match.py")
        self.assertIn("affected dependencies found: 7 of 42", out)
        self.assertIn("not affected: 0", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("family search: found 30 of 42 affected, flagged 62, not affected 32, features to open 46", out)
        self.assertIn("KNOWN LIMIT: affected dependencies that no registry row records: 6", out)

    def test_step_04_summary(self):
        run_step("step_04_with_map.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["found"], s["affected"], s["queued"], s["missed"]), (29, 42, 6, 7))
        self.assertEqual((s["hits"], s["false_hits"], s["checks"]), (29, 0, 13))
        self.assertEqual((s["features_opened"], s["family_features"]), (35, 46))
        self.assertEqual(s["tiers"], {"PAST": 1, "LATE": 6, "TIGHT": 3, "ROOM": 19, "SUNSETS": 3})
        self.assertEqual((s["cost_now"], s["cost_after"]), (96964.34, 82901.51))
        self.assertEqual(sorted({m["kind"] for m in s["missed_items"]}), ["fallback_unrecorded", "stale_alias_missed"])

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "deprecation_impact.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        lines = r.stdout.splitlines()
        self.assertEqual(lines[0], "as of 2026-09-01: 7 usages read, 5 hit a retiring model, 1 to check, 1 clear")
        self.assertEqual(lines[-1], "decision: LATE")

    def test_policy_file_matches_the_built_in_policy(self):
        self.assertEqual(di.load_policy(os.path.join(DATA, "policy.json")), di.DEFAULT_POLICY)

    def test_demo_date_matches_the_generator(self):
        with open(os.path.join(DATA, "_generate.py"), encoding="utf-8") as fh:
            self.assertIn("AS_OF = datetime.date(2026, 9, 1)", fh.read())
        self.assertEqual(di.DEMO_AS_OF, "2026-09-01")


if __name__ == "__main__":
    unittest.main()
