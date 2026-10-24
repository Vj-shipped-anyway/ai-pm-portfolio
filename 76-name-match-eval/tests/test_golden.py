"""Pin the numbers the README prints, so a change to a matcher that moves them fails here first."""
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
        out = run_step("step_01_exact_match.py")
        self.assertIn("caught: 24 of 150 (16.0%)", out)
        self.assertIn("false alerts: 8 of 250 (3.2%)", out)
        self.assertIn("order_swap 3 of 24", out)

    def test_step_02(self):
        out = run_step("step_02_edit_similarity.py")
        self.assertIn("false alerts <= 10.0% of clear names: lowest threshold 0.93, recall 36.0%", out)
        self.assertIn("recall >= 85.0%: not reachable at any threshold from 0.30 to 1.00", out)
        self.assertIn("best recall at the lowest threshold tried (0.30): 81.3%, with false alerts on 99.2% of clear names", out)
        self.assertIn("about 2,778 false alerts for each true hit", out)

    def test_step_03(self):
        out = run_step("step_03_deficiencies_exposed.py")
        flat = " ".join(out.split())
        self.assertIn("order_swap 4 of 24 3 of 24 3 of 24", flat)
        self.assertIn("shared_given 47 of 56 14 of 56 0 of 56", flat)
        self.assertIn("more than 4 of 24 order swaps or 5 of 14 initials", out)
        for kind in ("exact", "edit", "tokens"):
            self.assertIn("namesake alerts at 1.00: 8 of 8", [ln for ln in out.splitlines() if ln.strip().startswith(kind)][0])

    def test_step_04(self):
        out = run_step("step_04_token_matcher.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        a, b = s["tokens_at_false_alert_target"], s["tokens_at_recall_target"]
        self.assertEqual((a["threshold"], a["caught"], a["false_alerts"]), (0.93, 86, 24))
        self.assertEqual((b["threshold"], b["caught"], b["false_alerts"]), (0.73, 128, 46))
        self.assertFalse(s["both_targets_met"])
        self.assertIn("tokens-flat  false alerts <= 10.0%: threshold 0.94, recall 50.0%", out)
        self.assertIn("particle_joined caught at 0.75: tokens 2 of 8, edit 8 of 8", out)
        self.assertIn("alias_unlisted caught at 0.50: 0 of 10", out)

    def test_demo_numbers(self):
        r = subprocess.run([sys.executable, "name_match_eval.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines[1], "edit   at 0.80: caught 1 of 5, false alerts 1 of 7")
        self.assertEqual(lines[2], "tokens at 0.80: caught 4 of 5, false alerts 1 of 7")


if __name__ == "__main__":
    unittest.main()
