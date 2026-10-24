"""Pin the numbers the README prints, so a change to a rule that moves them fails here first."""
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
        out = run("step_01_no_mandate_check.py")
        for line in ("instructions received: 475 on 14 mandates",
                     "planted truth: 249 inside the mandate, 62 for a person to look at, 164 outside it",
                     "released although the mandate forbids them: 164 of 475",
                     "USD value of the forbidden ones that parse as an amount: 37,521.25"):
            self.assertIn(line, out)

    def test_step_02(self):
        out = run("step_02_flat_cap_and_name_list.py")
        for line in ("forbidden instructions released: 136 of 164", "instructions that needed a person, released: 60 of 62",
                     "legitimate instructions stopped: 6 of 249", "decisions that match the planted truth: 271 of 475",
                     "look-alike payees (same name, other payee_id) released: 12 of 12"):
            self.assertIn(line, out)

    def test_step_03(self):
        out = run("step_03_deficiencies_exposed.py")
        self.assertIn("forbidden instructions released: 28; needed a person but released: 30; legitimate stopped: 0", out)
        self.assertIn("forbidden instructions released: 133; needed a person but released: 46; legitimate stopped: 0", out)
        self.assertIn("daily_cap_breach 10, duplicate_id 10, near_duplicate 14", out)
        self.assertIn("split_below_confirm: 16 of 16", out)
        self.assertIn("memo_contradicts_category: 8 of 8", out)

    def test_step_04_summary(self):
        out = run("step_04_with_mandate_check.py")
        with open(os.path.join(SRC, "out", "step_04_summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
        self.assertEqual((s["released"], s["inside"]), (249, 249))
        self.assertEqual((s["held"], s["for_person"]), (46, 62))
        self.assertEqual((s["rejected"], s["outside"]), (156, 164))
        self.assertEqual(s["legit_stopped"], 0)
        self.assertEqual((s["hard_negatives_released"], s["hard_negatives"]), (49, 49))
        self.assertEqual((s["exact_match"], s["instructions"]), (451, 475))
        self.assertEqual(s["still_released"], 24)
        self.assertIn("audit: 475 records, chain ok", out)

    def test_audit_file_verifies_from_the_command_line(self):
        run("step_04_with_mandate_check.py")
        r = subprocess.run([sys.executable, "payment_mandate_check.py", "verify", os.path.join("out", "step_04_audit.jsonl")],
                           cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("475 records, chain ok", r.stdout)

    def test_demo_output(self):
        r = subprocess.run([sys.executable, "payment_mandate_check.py", "--demo"], cwd=SRC, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        self.assertIn("7 instructions: 4 RELEASE, 1 HOLD, 2 REJECT", r.stdout)
        self.assertIn("OVER_DAILY_LIMIT: 900.00 already released today, limit 900.00", r.stdout)


if __name__ == "__main__":
    unittest.main()
