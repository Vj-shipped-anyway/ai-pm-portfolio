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
        out = run("step_01_no_repair.py")
        for line in ("with at least one planted defect: 356", "rejected by the presence check (a required field is absent or empty): 319 of 500",
                     "planted defective fields: 374", "caught by the presence check (missing or blank): 340 of 374",
                     "let through as if complete (placeholder, malformed, or well-formed and wrong): 34 of 374",
                     "a bank table or the message itself holds it: 249 of 374; only the originator can say: 125"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run("step_02_fill_script.py")
        for line in ("Done. 500 messages released.", "messages it changed: 322 of 500", "required fields filled: 310   optional fields filled: 40",
                     "messages released with a required field still absent or empty: 27 of 500"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run("step_03_deficiencies_exposed.py")
        for line in ("ended correct: 248   written wrong: 62   left unusable: 52   present and wrong, untouched: 12",
                     "currency: filled on 32 messages, right on 22, wrong on 10", "creditor name: filled on 18 messages, right on 13, wrong on 5",
                     "UETR with no payment order: invented on 6 messages, right on 0",
                     "released as if complete: 25 messages", "changes to fields the policy puts behind a person: 204 of 310; the script has no approval step",
                     "fields changed: 350; the script keeps no record of source or approver",
                     "messages released with a wrong or unusable required value: 126 of 500", "KNOWN LIMIT: 12 messages"):
            self.assertIn(line, out)

    def test_step_04(self):
        out = run("step_04_with_repair_tool.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["pass_a"], s["repaired_a"], s["hold_a"], s["return_a"]), (156, 90, 125, 129))
        self.assertEqual((s["route_match"], s["messages"]), (488, 500))
        self.assertEqual((s["auto_correct"], s["auto_fields"]), (90, 90))
        self.assertEqual((s["probes_blocked"], s["probes_attempted"]), (766, 766))
        self.assertEqual((s["approved_correct"], s["approved_fields"]), (126, 135))
        self.assertEqual(s["wrong_applied"], 9)
        self.assertEqual((s["bad_released"], s["basic_bad"]), (21, 126))
        self.assertEqual((s["false_alarm"], s["audit_rows"]), (0, 225))
        self.assertRegex(out, r"approver entered the payment order +blocked 16 of 16")
        for line in ("hard negatives left alone: bic8_valid 6 of 6, lookalike_name 8 of 8, optional_absent 30 of 30",
                     "returned: 129 messages, 129 of 129 left untouched (no value written)",
                     "approver entered the payment order",
                     "applied 125 of 125",
                     "AUDIT: 225 rows for 225 fields changed; rows without a source: 0; approval-tier rows without an approver: 0"):
            self.assertIn(line, out)

    def test_demo_html_is_built_from_the_same_run(self):
        run("step_04_with_repair_tool.py")
        run("_build_demo.py")
        with open(os.path.join(SRC, "..", "demo.html"), encoding="utf-8") as fh:
            page = fh.read()
        self.assertIn('"route_match": 488', page)


if __name__ == "__main__":
    unittest.main()
