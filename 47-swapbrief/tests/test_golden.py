"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
import json
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run(script):
    r = subprocess.run([sys.executable, script], cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run("step_01_headline_average.py")
        for line in ("accuracy 81.8% -> 85.3% (+3.5 pp), rule says GO",
                     "simulated migrations: 80, of which 45 carry a real problem",
                     "false GO (a migration with a real problem gets GO): 41 of 45 (91.1%)",
                     "good migrations stopped: 0 of 35 (0.0%)"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run("step_02_average_plus_vendor_sheet.py")
        for line in ("accuracy +3.5 pp, list price per token 0.85x, median latency 0.96x -> GO",
                     "false GO: 36 of 45 (80.0%)", "good migrations stopped: 0 of 35 (0.0%)"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run("step_03_deficiencies_exposed.py")
        for line in ("list price per output token 0.85x, cost per correct answer 1.36x",
                     "median latency 0.96x, p95 latency 1.81x (true p95 ratio 2.02x)",
                     "slice account_closure (40 items) has a planted change of -8.0 pp and shows +5.0 pp in this sample",
                     "p95 ratio from 1.57x to 2.80x, cost per correct answer from 1.30x to 1.42x",
                     "says GO to 36 of 45 (80.0%)"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run("step_04_with_swapbrief.py")
        for line in ("decision: NO-GO",
                     "cost per correct  $0.00572 -> $0.00780   1.36x   interval 1.31x to 1.42x   BLOCK",
                     "p95 latency       4889 ms -> 8853 ms   1.81x   interval 1.50x to 2.57x   BLOCK   (p50 0.96x)",
                     "account_closure (40 items): +5.0 pp, interval -7.6 to +17.6 pp   INCONCLUSIVE",
                     "swapbrief                2 of 45 (4.4%)     0 of 35 (0.0%)       19 of 35 (54.3%)",
                     "GO 2, GO WITH GUARDRAILS 32, NO-GO 11",
                     "with an inconclusive critical slice 14, a watch or regressed slice 6, a cost flag 6, a p95 flag 0",
                     "cost problems with no cost flag: 0 of 26 (0.0%)",
                     "p95 problems with no p95 flag: 1 of 11 (9.1%)",
                     "KNOWN LIMIT: 4 of 26 true slice regressions pass unflagged",
                     "scenario 15, account_closure (30 items): planted -9.2 pp, observed +20.0 pp, interval +6.7 to +33.3 pp, status IMPROVED",
                     "migrations with a real problem that still get GO: 5, 74",
                     "8 scenarios (a real 7 to 10 pp fall in the 30-item account_closure slice, everything else clean): GO 1, GO WITH GUARDRAILS 7, NO-GO 0",
                     "8 scenarios (a good migration whose true cost per correct answer is 1.06x to 1.09x): GO 1, GO WITH GUARDRAILS 7, NO-GO 0"):
            self.assertIn(line, out)
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["bad"], s["good"]), (45, 35))
        self.assertEqual(s["false_go"], {"basic": 36, "headline": 41, "swapbrief": 2})
        self.assertEqual((s["slice_regressions"], s["slice_regressions_missed"]), (26, 4))

    def test_demo_run_matches_the_step_4_brief(self):
        r = subprocess.run([sys.executable, "swapbrief.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("accuracy          81.8% -> 85.3%   +3.5 pp   interval +0.3 to +7.0 pp   the average says GO", r.stdout)
        self.assertIn("decision: NO-GO", r.stdout)


if __name__ == "__main__":
    unittest.main()
