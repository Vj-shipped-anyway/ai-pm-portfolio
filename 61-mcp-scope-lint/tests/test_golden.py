"""Pin the numbers the README prints, so a change to a rule that moves them fails here first."""
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
    def test_step_01(self):
        out = run_step("step_01_no_lint.py")
        self.assertIn("manifests: 30   tools: 218   granted scopes: 234 (27 are wildcards)", out)
        self.assertIn("scopes the grants reach, wildcards expanded: 260", out)
        self.assertIn("scopes the generator marks as not needed: 83 of 260 (31.9%)", out)
        self.assertIn("tools whose hints would let a check compare them with their scopes: 150 of 218", out)
        self.assertIn("manifests that grant a scope no tool asks for: 17 of 30", out)

    def test_step_02(self):
        out = run_step("step_02_blocklist.py")
        self.assertIn("grants flagged and removed: 45 of 234", out)
        self.assertIn("unneeded scopes cut: 53 of 83", out)
        self.assertIn("needed scopes cut: 18 (legit_admin 4, read_tool_wildcard 5, wildcard_fully_used 5, wildcard_nohint 4)", out)
        self.assertIn("unneeded scopes still reachable: 30 of 83", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        self.assertIn("unneeded scopes cut: 27 of 83; needed scopes cut: 0", out)
        self.assertIn("unneeded scopes cut: 38 of 83; needed scopes cut: 0", out)
        self.assertIn("unneeded scopes the full rules leave reachable: 22 of 83 (dead_tool 4, overscoped_nohint 6, overscoped_wrong_hint 4, wildcard_nohint 8)", out)
        self.assertIn("needed scopes the full rules cut: 3 (hint_wrong_scope_right 3)", out)
        self.assertEqual(out.count(" declares "), 6)

    def test_step_04_summary(self):
        run_step("step_04_with_lint.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["errors"], s["warnings"]), (38, 12))
        self.assertEqual((s["reach_before"], s["reach_after"]), (260, 196))
        self.assertEqual(s["manifest_unneeded"], 38)
        self.assertEqual((s["unneeded_cut"], s["truth_unneeded"], s["unneeded_kept"]), (61, 83, 22))
        self.assertEqual(s["needed_cut"], 3)
        self.assertEqual((s["declared_unneeded_cut"], s["declared_unneeded"], s["declared_needed_cut"]), (18, 36, 3))
        self.assertEqual(s["tools_emptied"], 0)
        self.assertEqual(s["hard_negative_findings"], {"wildcard_fully_used": 0, "multi_resource_reader": 0, "legit_admin": 0})

    def test_the_proposal_never_adds_a_scope_on_any_manifest(self):
        import common
        from mcp_scope_lint import propose, reach
        for m in common.load_servers():
            p = propose(m)
            self.assertLessEqual(set(p["cut"]), reach(m, m["granted"]))
            self.assertEqual(p["reach_before"] - len(p["cut"]), p["reach_after"])


if __name__ == "__main__":
    unittest.main()
