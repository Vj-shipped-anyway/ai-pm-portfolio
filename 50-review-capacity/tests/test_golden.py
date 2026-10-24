"""Pin the numbers the README prints, so a change to the model or the data that moves them fails here first."""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
import common

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(ROOT, "data")


def run_script(*args):
    r = subprocess.run([sys.executable, *args], cwd=SRC, capture_output=True, text=True)
    return r


class GoldenTests(unittest.TestCase):
    def lines(self, script):
        r = run_script(script)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        return r.stdout.splitlines()

    def test_step_01(self):
        out = self.lines("step_01_average_workload.py")
        for line in ("  queues: 13   cases replayed: 7049   days replayed: 11 to 20",
                     "  reviewers at the desk: 39 chosen, 61 needed (smallest count that meets both limits)",
                     "  queues that meet the wait target: 2 of 13",
                     "  queues within the utilization cap: 4 of 13",
                     "  queues that meet both: 0 of 13",
                     "  cases that waited past their target: 2300 of 7049 (32.6%)"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = self.lines("step_02_erlang_c.py")
        for line in ("  queues that meet both limits on the replay: 10 of 13",
                     "  matches the true number of reviewers: 8 of 13; within one: 11 of 13",
                     "  queues with too few reviewers: 3; with too many: 2",
                     "  reviewers at the desk: 54 chosen, 61 needed",
                     "  cases that waited past their target: 802 of 7049 (11.4%)"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = self.lines("step_03_deficiencies_exposed.py")
        self.assertIn("  batch_only        matches the true number: 10 of 13; too few: 1; too many: 2; meets both limits on the replay: 12", out)
        self.assertIn("  variability_only moves the answer on 2 queues: nearer the truth on 1 (model_override_audit), "
                      "farther on 1 (dispute_summary_check)", out)
        self.assertTrue(any(ln.startswith("    card_dispute_wave: spread of arrival gaps 1.64; hourly arrival counts, variance over mean 3.66") for ln in out))
        self.assertTrue(any(ln.startswith("    onboarding_review: spread of arrival gaps 0.96; hourly arrival counts, variance over mean 0.80") for ln in out))

    def test_step_04(self):
        out = self.lines("step_04_with_review_capacity.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["exact"], s["within_one"], s["queues"]), (10, 13, 13))
        self.assertEqual((s["short"], s["spare"]), (1, 2))
        self.assertEqual((s["meets"], s["erlang_meets"]), (12, 10))
        self.assertEqual((s["seats"], s["true_seats"], s["erlang_seats"]), (62, 61, 54))
        self.assertEqual((s["late_pct"], s["erlang_late_pct"]), (3.7, 11.4))
        self.assertEqual((s["forecast_exact"], s["forecast_short"]), (7, 3))
        self.assertIn("  hard negatives not over-staffed: 2 of 2 (adverse_media_review 4 against 4, policy_qa_escalations 2 against 2)", out)
        self.assertIn("  opening-batch queues: tool 7, 7 reviewers, Erlang C 3, 3, needed 7, 7", out)
        self.assertTrue(any("KNOWN LIMIT payment_limit_exceptions: 5.31 live cases an hour on days 1 to 10, 6.78 on days 11 to 20" in ln for ln in out))

    def test_demo_output(self):
        r = run_script("review_capacity.py", "--demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), [
            "queue                   load  seats  util  mean-only  roster  have  status",
            "morning_batch_review     1.9      7   28%          3      10     6  SHORT by 4",
            "onboarding_exceptions    3.0      5   60%          5       7     6  SHORT by 1",
            "complaint_escalations    2.7      5   53%          4       7     7  ok",
            "decision: SHORT on 2 of 3 queues with a current_headcount"])


class TruthTests(unittest.TestCase):
    """The truth is written by data/_generate.py with its own replay. The tool's replay must agree with it."""

    def test_true_seats_meet_the_limits_and_one_fewer_does_not(self):
        for q in common.load_world():
            self.assertTrue(common.judge(q, q["true_seats"])["meets"], q["queue_id"])
            if q["true_seats"] > 1:
                self.assertFalse(common.judge(q, q["true_seats"] - 1)["meets"], q["queue_id"])

    def test_every_planted_kind_is_present(self):
        kinds = {q["kind"] for q in common.load_world()}
        self.assertEqual(kinds, {"plain", "variable_handling", "opening_batch", "bursty_arrivals", "low_variance",
                                 "hard_negative", "drift", "heavy_tail"})

    def test_generator_reproduces_the_data_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            # the generator writes next to itself, so run a copy
            copy = os.path.join(tmp, "data")
            os.makedirs(copy)
            shutil.copy(os.path.join(DATA, "_generate.py"), copy)
            subprocess.run([sys.executable, "_generate.py"], cwd=copy, check=True, capture_output=True)
            for name in ("cases.csv", "queues.csv", "queue_truth.csv", "example_queues.csv"):
                self.assertTrue(filecmp.cmp(os.path.join(DATA, name), os.path.join(copy, name), shallow=False), name)


if __name__ == "__main__":
    unittest.main()
