"""Pin the numbers the README prints, so a change to the rules or the data that moves them fails here first."""
import os
import subprocess
import sys
import unittest

import _bootstrap  # noqa: F401

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def run_script(*args):
    r = subprocess.run([sys.executable] + list(args), cwd=SRC, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    return r.stdout


class GoldenTests(unittest.TestCase):
    def test_step_01(self):
        out = run_script("step_01_no_allocation.py")
        for want in ("billing lines: 1284   accounts: 12   net spend: $781,113.30",
                     "charged to the planted owner: $435,971.77 (55.8% of net spend)",
                     "charged to another team's cost center: $56,251.32 (7.2%)",
                     "parked in the central pool: $288,890.21 (37.0%)",
                     "630 of 1244 (63.1% of their dollars)"):
            self.assertIn(want, out)

    def test_step_02(self):
        out = run_script("step_02_exact_tag_report.py")
        for want in ("distinct values in the report: 34 (the registry has 14 cost centers)", "values that are not a registry id: 20",
                     "charged to the planted owner: $499,835.82 (64.0% of net spend)",
                     "sitting in buckets that are not cost centers: $71,586.46 (9.2%)",
                     "$180,467.03 (23.1%)"):
            self.assertIn(want, out)

    def test_step_03(self):
        out = run_script("step_03_deficiencies_exposed.py")
        for want in ("$499,835.82 64.0%", "$589,357.94 75.5%", "$610,719.98 78.2%", "$653,362.84 83.6%", "$702,526.86 89.9%",
                     "account default placed $59,311.25; $16,668.39 (28.1%) of it belongs to another team",
                     "KNOWN LIMIT: 24 lines ($20,618.63)", "20 of 24 pass the tag compliance check"):
            self.assertIn(want, out)

    def test_step_04(self):
        out = run_script("step_04_with_tool.py")
        for want in ("net spend: $781,113.30   allocated: $740,232.55 (94.8%)   unallocated: $40,880.75 (5.2%)",
                     "equals the bill to the cent: yes",
                     "correct $702,526.86 (89.9%), wrong $37,705.69 (4.8%), left for a person $40,880.75 (5.2%)",
                     "630 of 1244 lines strict (63.1% of dollars); 694 of 1244 after repair (74.3%)",
                     "flags 450; 40 of them need no tag", "asks for a fix on 410",
                     "zero-cost untagged lines: 24 of 24", "shared-service lines, split by proportion: 16 of 16",
                     "credit lines allocated to the planted owner: 10 of 10", "tags in another case or with spaces: 56 of 56",
                     "valid tag, wrong cost center: 24 lines, correct $0.00, wrong $20,618.63",
                     "untagged resource of another team in a dedicated account: 36 lines, correct $0.00, wrong $16,460.42"):
            self.assertIn(want, out)

    def test_demo_output(self):
        out = run_script("tag_chargeback.py", "--demo")
        self.assertIn("bill: example_bill.csv   14 lines   period 2026-03   net spend $11,490.00", out)
        self.assertIn("5       $3,250.00    28.3%", out)
        self.assertIn("result: unallocated 28.3% of net spend, limit 10.0%: OVER", out)


if __name__ == "__main__":
    unittest.main()
