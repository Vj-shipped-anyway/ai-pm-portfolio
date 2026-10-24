import contextlib
import csv
import io
from decimal import Decimal
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import tag_chargeback as tc

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
HEADER = ["line_id", "usage_date", "account_id", "service", "resource_id", "usage_type", "cost_usd", "tags_json"]
GOOD = '{"cost-center":"CC-1001","app":"a","env":"prod"}'


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = tc.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def bill(self, rows, name="bill.csv"):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(HEADER)
            w.writerows(rows)
        return self.path(name)

    def text(self, name, content):
        with open(self.path(name), "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        return self.path(name)

    def report(self, bill, *extra, policy=None, cc=None, accounts=None):
        return run(["report", bill, "--policy", policy or os.path.join(DATA, "policy.json"),
                    "--cost-centers", cc or os.path.join(DATA, "cost_centers.csv"),
                    "--accounts", accounts or os.path.join(DATA, "accounts.csv")] + list(extra))

    def assert_exit_2(self, result):
        code, out, err = result
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "))
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("Traceback", err)

    def clean_row(self, i=1, cost="100.00", tags=GOOD, rid="r1", date="2026-03-05", account="410000000001", service="Compute"):
        return ["L%d" % i, date, account, service, rid, "u", cost, tags]

    # ---- exit codes
    def test_demo_exits_0_and_prints_the_result(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("result: unallocated 28.3% of net spend, limit 10.0%: OVER", out)

    def test_within_limit_exits_0_and_over_limit_exits_1(self):
        b = self.bill([self.clean_row(1), self.clean_row(2, tags="{}", rid="r2", account="410000000009")])
        self.assertEqual(self.report(b)[0], 1)
        self.assertEqual(self.report(b, "--max-unallocated-pct", "60")[0], 0)
        self.assertEqual(self.report(self.bill([self.clean_row(1)], "ok.csv"))[0], 0)

    def test_bad_limit_exits_2(self):
        b = self.bill([self.clean_row(1)])
        for bad in ("abc", "101", "-1", "nan"):
            self.assertEqual(self.report(b, "--max-unallocated-pct", bad)[0], 2, bad)

    # ---- malformed bill: empty, wrong type, truncated
    def test_empty_and_header_only_bill(self):
        self.assert_exit_2(self.report(self.text("empty.csv", "")))
        self.assert_exit_2(self.report(self.bill([], "header.csv")))
        self.assert_exit_2(self.report(self.path("missing.csv")))

    def test_wrong_types_in_the_bill(self):
        for cost in ("abc", "NaN", "Infinity", "1e999", "0.0000001", ""):
            self.assert_exit_2(self.report(self.bill([self.clean_row(1, cost=cost)])))
        for tags in ("[]", "5", '"x"', '{"cost-center": 5}', ""):
            self.assert_exit_2(self.report(self.bill([self.clean_row(1, tags=tags)])))
        self.assert_exit_2(self.report(self.bill([self.clean_row(1, date="03/05/2026")])))
        self.assert_exit_2(self.report(self.bill([self.clean_row(1, date="2026-02-30")])))

    def test_truncated_bill(self):
        self.assert_exit_2(self.report(self.text("short.csv", ",".join(HEADER) + "\nL1,2026-03-05,410000000001,Compute\n")))
        self.assert_exit_2(self.report(self.text("cut.csv", ",".join(HEADER) + '\nL1,2026-03-05,a,Compute,r1,u,10.00,"{""cost-cen')))
        self.assert_exit_2(self.report(self.text("long.csv", ",".join(HEADER) + "\nL1,d,a,s,r,u,1,{},extra\n")))

    def test_other_bill_problems(self):
        self.assert_exit_2(self.report(self.bill([self.clean_row(1), self.clean_row(1)])))
        self.assert_exit_2(self.report(self.bill([self.clean_row(1), self.clean_row(2, date="2026-04-01")])))
        self.assert_exit_2(self.report(self.bill([self.clean_row(1, cost="-5.00")])))
        self.assert_exit_2(self.report(self.bill([self.clean_row(1, cost="0")])))
        self.assert_exit_2(self.report(self.text("wrongcols.csv", "a,b\n1,2\n")))
        with open(self.path("bin.csv"), "wb") as fh:
            fh.write(b"\xff\xfe\x00\x00garbage")
        self.assert_exit_2(self.report(self.path("bin.csv")))

    # ---- malformed side files
    def test_malformed_policy(self):
        b = self.bill([self.clean_row(1)])
        for name, content in (("empty", ""), ("list", "[1, 2]"), ("cut", '{"required_tags": [{"key": "cost'), ("none", "{}"),
                              ("noreg", '{"required_tags": [{"key": "app", "values": "any"}]}'),
                              ("badlimit", '{"required_tags": [{"key": "c", "values": "registry"}], "max_unallocated_pct": "x"}'),
                              ("dupkey", '{"required_tags": [{"key": "c", "values": "registry"}, {"key": "c"}]}')):
            self.assert_exit_2(self.report(b, policy=self.text(name + ".json", content)))

    def test_malformed_registry_and_accounts(self):
        b = self.bill([self.clean_row(1)])
        head = "cost_center,name,business_line,owner_team,active\n"
        for name, content in (("empty", ""), ("noactive", head + "CC-1,n,b,t,maybe\n"), ("dup", head + "CC-1,n,b,t,true\nCC-1 ,n,b,t,true\n"),
                              ("norows", head)):
            self.assert_exit_2(self.report(b, cc=self.text(name + ".csv", content)))
        cc = self.text("cc.csv", head + "CC-1,n,b,t,true\nCC-2,n,b,t,false\n")
        ah = "account_id,account_name,default_cost_center,shared\n"
        for name, content in (("closed", ah + "a,n,CC-2,no\n"), ("unknown", ah + "a,n,CC-7,no\n"), ("badflag", ah + "a,n,CC-1,maybe\n"),
                              ("sharedwithdefault", ah + "a,n,CC-1,yes\n")):
            self.assert_exit_2(self.report(b, cc=cc, accounts=self.text(name + ".csv", content)))

    def test_unwritable_output_exits_2(self):
        b = self.bill([self.clean_row(1)])
        self.assert_exit_2(self.report(b, "--chargeback-csv", os.path.join(self.dir.name, "no", "such", "dir.csv")))

    # ---- hostile strings
    HOSTILE = "r1\n::error title=forged::approved\r%0A"

    def test_hostile_resource_id_cannot_forge_a_workflow_command(self):
        b = self.bill([self.clean_row(1), self.clean_row(2, tags="{}", rid=self.HOSTILE, account="410000000009", cost="50.00")])
        _, out, _ = self.report(b, "--format", "github")
        lines = out.splitlines()
        self.assertTrue(all(ln.startswith(("::warning ", "::notice ", "::error ")) for ln in lines), out)
        self.assertEqual(sum(1 for ln in lines if "title=forged" in ln.split("::", 2)[1]), 0)
        self.assertIn("%0A", out)
        self.assertIn("%25", out)

    def test_hostile_resource_id_stays_on_one_line_in_text(self):
        b = self.bill([self.clean_row(1), self.clean_row(2, tags="{}", rid=self.HOSTILE, account="410000000009", cost="50.00")])
        _, out, _ = self.report(b)
        self.assertFalse(any(ln.startswith("::") for ln in out.splitlines()))
        self.assertIn("\\n::error title=forged", out)

    def test_hostile_value_in_an_error_message_stays_on_one_line(self):
        self.assert_exit_2(self.report(self.bill([self.clean_row(1, cost="9\n::error::x")])))

    # ---- silent no-ops
    def test_nothing_matching_any_rule_is_said_out_loud(self):
        b = self.bill([self.clean_row(1, tags='{"team":"x"}', account="410000000009")])
        code, out, _ = self.report(b)
        self.assertEqual(code, 1)
        self.assertIn("no line matched an allocation rule", out)

    def test_accounts_missing_from_the_map_are_named(self):
        b = self.bill([self.clean_row(1), self.clean_row(2, tags="{}", rid="r9", account="999")])
        _, out, _ = self.report(b)
        self.assertIn("not in the account map", out)
        self.assertIn("999", out)

    # ---- output files
    def test_output_files_reconcile_to_the_bill(self):
        b = os.path.join(DATA, "billing_export.csv")
        cb, lc = self.path("cb.csv"), self.path("lines.csv")
        code, _, _ = self.report(b, "--chargeback-csv", cb, "--lines-csv", lc)
        self.assertEqual(code, 0)
        total = sum(x["usd"] for x in tc.load_bill(b))
        with open(lc, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(sum(Decimal(r["usd"]) for r in rows), Decimal(total) / tc.MICROS)
        with open(cb, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(rows[-1]["cost_center"], "UNALLOCATED")
        self.assertEqual(tc.exact_usd(1234500000), "1234.50")
        self.assertEqual(tc.exact_usd(-1234567891), "-1234.567891")
        self.assertEqual(sum(Decimal(r["total"]) for r in rows), Decimal(total) / tc.MICROS)


if __name__ == "__main__":
    unittest.main()
