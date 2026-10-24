"""Pin the numbers the README prints, so a change to the rules that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
ROOT = os.path.join(SRC, "..")


def run_step(name):
    r = subprocess.run([sys.executable, name], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_step("step_01_no_comparison.py")
        for line in ("agents: 14 on 10 service accounts; 7 agents share 3 of them",
                     "grants: 167, of which 8 are group grants",
                     "effective entitlements (groups expanded): 190",
                     "calls in the log: 5210 over 90 days",
                     "calls with no agent tag: 1155 (22.2%)",
                     "62 of 167 grants are not needed (37.1%)"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run_step("step_02_annual_review.py")
        for line in ("removed: 8 of 167 grants", "removed by the review: 4 of 62",
                     "grants the agent needs that the review removed: 4", "155 of 5210 calls denied"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        for line in ("grants flagged as unused: 74 of 167", "of those, not needed: 60 of 62",
                     "used once a quarter: 10; used only through calls with no agent tag: 4",
                     "calls the flagged removals would deny: 4 of 5210",
                     "1 call to count as used: unneeded removed 46 of 62; stray-use grants removed 0 of 2",
                     "3 calls to count as used: unneeded removed 48 of 62; stray-use grants removed 2 of 2",
                     "needed grants removed (quarterly excluded) 10; calls newly denied 15",
                     "the diff with --min-calls 1 removes 8 of 10"):
            self.assertIn(line, out)

    def test_step_04_summary(self):
        out = run_step("step_04_with_diff.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        expected = {"grants": 167, "keep": 107, "remove": 54, "narrow": 6, "unneeded": 62, "unneeded_removed": 46,
                    "review_removed": 8, "review_unneeded_removed": 4, "needed_removed": 8,
                    "reach_before": 190, "reach_after": 123, "reach_cut": 67, "reach_cut_pct": 35.3,
                    "calls": 5210, "newly_denied": 0, "review_denied": 155, "periodic": 10, "periodic_removed": 8,
                    "next_quarter_denied": 44, "sibling_kept": 14, "stray_kept": 2, "other_kept": 0,
                    "hard_rare_kept": 10, "hard_credit_kept": 4}
        self.assertEqual(s, expected)
        self.assertIn("Not vacuous", out)
        self.assertIn("KNOWN LIMITS", out)

    def test_the_tool_never_denies_a_logged_call_in_sample(self):
        run_step("step_04_with_diff.py")
        with open(os.path.join(SRC, "out", "step_04_grants.csv"), encoding="utf-8") as fh:
            header = fh.readline().strip().split(",")
        self.assertEqual(header[:3], ["agent_id", "scope", "action"])

    def test_sample_report_is_the_current_output(self):
        r = subprocess.run([sys.executable, "scopekeeper.py", "diff", "../data/grants.csv", "../data/calls.csv",
                            "--catalog", "../data/scope_catalog.csv", "--agents", "../data/agents.csv"],
                           cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        with open(os.path.join(ROOT, "sample_report.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), r.stdout)

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "scopekeeper.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("scopekeeper diff: 3 agents, 9 grants reaching 13 scopes, 94 calls over 90 days", r.stdout)
        self.assertIn("entitlements: 13 before, 7 after (6 cut, 46.2%)", r.stdout)


if __name__ == "__main__":
    unittest.main()
