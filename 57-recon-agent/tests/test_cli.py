import contextlib
import io
import os
import unittest

import _bootstrap  # noqa: F401
from _ledgers import Workspace, a_line, b_line, write_csv, A_HEAD
import recon_agent as ra

GOOD_A = [a_line("A1", "2026-03-02", "100.00", ref="INV-1")]
GOOD_B = [b_line("B1", "2026-03-02", "100.00", ref="INV-1")]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ra.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliBase(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.close)

    def raw(self, name, text, mode="w"):
        p = self.ws.path(name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def good(self):
        return self.ws.ledgers(GOOD_A, GOOD_B)

    def assert_input_error(self, code, out, err):
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)


class RunTests(CliBase):
    def test_demo_runs_and_shows_every_outcome(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        for text in ("posted_auto", "posted_approved", "rejected", "pending", "ambiguous_candidates", "reference_conflict",
                     "possible_duplicate", "refused:", "self-approval", "stale", "posted 5 (3 on their own, 2 on approval)"):
            self.assertIn(text, out)

    def test_reconcile_prints_and_exits_0_even_with_open_items(self):
        pa, pb = self.ws.ledgers(GOOD_A + [a_line("A2", "2026-03-09", "5.00", name="Other Co")], GOOD_B)
        code, out, _ = run(["reconcile", pa, pb])
        self.assertEqual(code, 0)
        self.assertIn("open items: 1", out)

    def test_fail_on_open_exits_1_only_when_something_is_open(self):
        pa, pb = self.good()
        self.assertEqual(run(["reconcile", pa, pb, "--fail-on-open"])[0], 0)
        pa, pb = self.ws.ledgers(GOOD_A + [a_line("A2", "2026-03-09", "5.00", name="Other Co")], GOOD_B)
        self.assertEqual(run(["reconcile", pa, pb, "--fail-on-open"])[0], 1)

    def test_out_writes_both_files_and_verify_accepts_them(self):
        pa, pb = self.good()
        out_dir = self.ws.path("o")
        self.assertEqual(run(["reconcile", pa, pb, "--out", out_dir])[0], 0)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "unmatched.csv")))
        code, out, _ = run(["verify", pa, pb, os.path.join(out_dir, "matches.csv")])
        self.assertEqual((code, out.strip()), (0, "checked 1 posted matches: 0 problem(s)"))

    def test_verify_exits_1_on_a_tampered_file(self):
        pa, pb = self.good()
        out_dir = self.ws.path("o")
        run(["reconcile", pa, pb, "--out", out_dir])
        path = os.path.join(out_dir, "matches.csv")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.raw("tampered.csv", text.replace("B1", "B9"))
        code, out, _ = run(["verify", pa, pb, self.ws.path("tampered.csv")])
        self.assertEqual(code, 1)
        self.assertIn("not in the ledgers", out)

    def test_verify_of_a_file_with_nothing_posted_says_so(self):
        pa, pb = self.good()
        self.raw("m.csv", "match_id,rule,status,a_ids,b_ids,evidence,approver\n")
        code, out, _ = run(["verify", pa, pb, self.ws.path("m.csv")])
        self.assertEqual(code, 0)
        self.assertIn("none to check", out)

    def test_approvals_file_is_applied(self):
        pa, pb = self.ws.ledgers([a_line("A1", "2026-03-02", "100.00")], GOOD_B)
        key = "name_amount:A1:B1:10000"
        self.raw("ap.csv", f"key,decision,approver,note\n{key},approve,reviewer-1,ok\n")
        code, out, _ = run(["reconcile", pa, pb, "--approvals", self.ws.path("ap.csv")])
        self.assertEqual(code, 0)
        self.assertIn("posted_approved", out)


class BadInputTests(CliBase):
    def test_missing_files(self):
        self.assert_input_error(*run(["reconcile", "nope_a.csv", "nope_b.csv"]))

    def test_a_directory_instead_of_a_file(self):
        self.assert_input_error(*run(["reconcile", self.ws.dir, self.ws.dir]))

    def test_empty_file(self):
        pa, pb = self.good()
        self.raw("empty.csv", "")
        self.assert_input_error(*run(["reconcile", self.ws.path("empty.csv"), pb]))

    def test_header_only(self):
        pa, pb = self.good()
        self.raw("h.csv", ",".join(A_HEAD) + "\n")
        code, out, err = run(["reconcile", self.ws.path("h.csv"), pb])
        self.assert_input_error(code, out, err)
        self.assertIn("no rows", err)

    def test_missing_column(self):
        pa, pb = self.good()
        self.raw("c.csv", "a_id,value_date,amount\nA1,2026-03-02,1.00\n")
        self.assert_input_error(*run(["reconcile", self.ws.path("c.csv"), pb]))

    def test_truncated_last_line(self):
        pa, pb = self.good()
        self.raw("t.csv", ",".join(A_HEAD) + "\nA1,2026-03-02,100.00,USD,Brindle Foods Ltd,CREDIT,INV-1\nA2,2026-03-03,5")
        code, out, err = run(["reconcile", self.ws.path("t.csv"), pb])
        self.assert_input_error(code, out, err)
        self.assertIn("truncated", err)

    def test_too_many_fields(self):
        pa, pb = self.good()
        self.raw("x.csv", ",".join(A_HEAD) + "\nA1,2026-03-02,100.00,USD,N,T,R,extra\n")
        self.assert_input_error(*run(["reconcile", self.ws.path("x.csv"), pb]))

    def test_wrong_type_amounts(self):
        pa, pb = self.good()
        for bad in ("abc", "1e5", "NaN", "Infinity", "1.234", "", "1,000.00", "9999999999999.00"):
            write_csv(self.ws.path("w.csv"), A_HEAD, [a_line("A1", "2026-03-02", bad)])
            self.assert_input_error(*run(["reconcile", self.ws.path("w.csv"), pb]))

    def test_bad_dates_and_currency(self):
        pa, pb = self.good()
        for row in (a_line("A1", "2026-02-30", "1.00"), a_line("A1", "02/03/2026", "1.00"), a_line("A1", "2026-03-02", "1.00", ccy="usd")):
            write_csv(self.ws.path("w.csv"), A_HEAD, [row])
            self.assert_input_error(*run(["reconcile", self.ws.path("w.csv"), pb]))

    def test_ids_must_be_unique_and_plain(self):
        pa, pb = self.good()
        for rows in ([a_line("A1", "2026-03-02", "1.00"), a_line("A1", "2026-03-03", "2.00")], [a_line("A:1", "2026-03-02", "1.00")], [a_line("A+1", "2026-03-02", "1.00")]):
            write_csv(self.ws.path("w.csv"), A_HEAD, rows)
            self.assert_input_error(*run(["reconcile", self.ws.path("w.csv"), pb]))

    def test_a_file_that_is_not_utf8(self):
        pa, pb = self.good()
        self.raw("bin.csv", b"a_id,value_date\n\xff\xfe\x00\x00", "wb")
        self.assert_input_error(*run(["reconcile", self.ws.path("bin.csv"), pb]))

    def test_approvals_with_a_bad_decision_or_missing_column(self):
        pa, pb = self.good()
        self.raw("ap1.csv", "key,decision,approver\nk,maybe,reviewer-1\n")
        self.raw("ap2.csv", "key,decision\nk,approve\n")
        self.raw("ap3.csv", "key,decision,approver\nk,approve,\n")
        for name in ("ap1.csv", "ap2.csv", "ap3.csv"):
            self.assert_input_error(*run(["reconcile", pa, pb, "--approvals", self.ws.path(name)]))

    def test_matches_file_missing_columns(self):
        pa, pb = self.good()
        self.raw("m.csv", "match_id,rule\nM-1,ref_exact\n")
        self.assert_input_error(*run(["verify", pa, pb, self.ws.path("m.csv")]))

    def test_usage_errors_are_one_line_with_exit_2(self):
        for args in (["reconcile"], ["bogus"], ["--nope"]):
            code, out, err = run(args)
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage", out)

    def test_unwritable_output_folder_exits_2(self):
        pa, pb = self.good()
        blocker = self.raw("file.txt", "x")
        code, _, err = run(["reconcile", pa, pb, "--out", os.path.join(blocker, "sub")])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("output error: "))


class HostileStringTests(CliBase):
    FORGE = "x\n::error title=forged::approved\r\n::set-output name=a::b"

    def test_a_hostile_name_or_reference_cannot_start_a_new_output_line(self):
        a = [a_line("A1", "2026-03-02", "100.00", name=self.FORGE, ref=self.FORGE)]
        b = [b_line("B1", "2026-03-02", "100.00", name=self.FORGE, ref="INV-77"), b_line("B2", "2026-03-02", "5.00", name=self.FORGE, ref=self.FORGE)]
        pa, pb = self.ws.ledgers(a, b)
        code, out, _ = run(["reconcile", pa, pb])
        self.assertEqual(code, 0)
        for line in out.splitlines():
            self.assertFalse(line.lstrip().startswith("::"), line)
        self.assertIn("\\n::error", out)

    def test_a_hostile_approver_name_is_escaped_in_the_report(self):
        pa, pb = self.ws.ledgers([a_line("A1", "2026-03-02", "100.00")], GOOD_B)
        self.raw("ap.csv", 'key,decision,approver\nname_amount:A1:B1:10000,approve,"ok\n::error::x"\n')
        _, out, _ = run(["reconcile", pa, pb, "--approvals", self.ws.path("ap.csv")])
        for line in out.splitlines():
            self.assertFalse(line.startswith("::"), line)

    def test_spreadsheet_formulas_are_neutralised_in_the_csv_output(self):
        a = [a_line("A1", "2026-03-02", "100.00", name='=HYPERLINK("http://x","y")'), a_line("A2", "2026-03-02", "7.00", name="@SUM(1+1)")]
        pa, pb = self.ws.ledgers(a, GOOD_B)
        out_dir = self.ws.path("o")
        run(["reconcile", pa, pb, "--out", out_dir])
        with open(os.path.join(out_dir, "unmatched.csv"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("'=HYPERLINK", text)
        self.assertIn("'@SUM", text)
        self.assertNotIn(",=HYPERLINK", text)

    def test_a_very_long_string_is_cut_in_the_report(self):
        a = [a_line("A1", "2026-03-02", "100.00", name="N" * 5000)]
        pa, pb = self.ws.ledgers(a, GOOD_B)
        _, out, _ = run(["reconcile", pa, pb])
        self.assertLess(max(len(line) for line in out.splitlines()), 400)


if __name__ == "__main__":
    unittest.main()
