from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import scam_friction_sim as sim

PAY_HEADER = "payment_id,amount,usual_amount,payee_age_days,hour,call_active,device_new\n"
TRU_HEADER = "payment_id,is_scam,scenario,u_abandon,u_evade\n"
# P1: a coached scam that a score policy holds; P2: an ordinary legitimate payment that passes.
PAY = PAY_HEADER + "P1,1000,100,0,10,1,0\nP2,50,50,100,12,0,0\n"
TRU = TRU_HEADER + "P1,1,coached_live,0.1000,0.9000\nP2,0,ordinary,0.9000,0.9000\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = sim.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def files(self, pay=PAY, tru=TRU):
        return self.write("p.csv", pay), self.write("t.csv", tru)

    def go(self, pay=PAY, tru=TRU, *extra):
        p, t = self.files(pay, tru)
        return run(["run", "--payments", p, "--truth", t, *extra])

    def assert_input_error(self, result, fragment=""):
        code, _, err = result
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith(("input error:", "usage error:")), err)
        self.assertEqual(err.count("\n"), 1, err)
        self.assertNotIn("Traceback", err)
        self.assertIn(fragment, err)

    # ---- good runs
    def test_run_prints_the_numbers(self):
        code, out, err = self.go(PAY, TRU, "--hold-score", "8")
        self.assertEqual((code, err), (0, ""))
        self.assertIn("payments: 2 (1 scam, 1 legitimate)", out)
        self.assertIn("scam value stopped: $1,000 of $1,000 (100.0%)", out)

    def test_max_held_pct_exits_1_when_broken(self):
        pay = PAY + "P3,600,100,0,12,0,0\n"
        tru = TRU + "P3,0,big_first_time,0.9000,0.9000\n"
        code, out, _ = self.go(pay, tru, "--hold-score", "5", "--max-held-pct", "10")
        self.assertEqual(code, 1)
        self.assertIn("budget broken: legitimate payments held 50.0% is above the limit 10%", out)
        self.assertEqual(self.go(pay, tru, "--hold-score", "5", "--max-held-pct", "60")[0], 0)

    def test_min_stopped_pct_exits_1_when_missed(self):
        code, out, _ = self.go(PAY, TRU, "--policy", "none", "--min-stopped-pct", "5")
        self.assertEqual(code, 1)
        self.assertIn("budget broken: scam value stopped 0.0% is below the target 5%", out)

    def test_policy_that_holds_nothing_says_so(self):
        _, out, _ = self.go(PAY, TRU, "--hold-score", "13")
        self.assertIn("note: this policy held and warned no payments in this file", out)

    def test_file_with_no_scams_says_so(self):
        code, out, _ = self.go(PAY, TRU.replace("P1,1,coached_live", "P1,0,ordinary"))
        self.assertEqual(code, 0)
        self.assertIn("note: the truth file has no scam payments", out)

    def test_custom_assumptions_change_the_result(self):
        a = self.write("a.json", json.dumps({"coach_rate": 1.0}))
        _, out, _ = self.go(PAY, TRU, "--hold-score", "8", "--assumptions", a)
        self.assertIn("scam value stopped: $0 of $1,000", out)

    # ---- malformed input exits 2 with one line
    def test_empty_files(self):
        self.assert_input_error(self.go("", TRU), "empty")
        self.assert_input_error(self.go(PAY, ""), "empty")

    def test_header_only_payments(self):
        self.assert_input_error(self.go(PAY_HEADER, TRU_HEADER), "no payments")

    def test_wrong_type(self):
        self.assert_input_error(self.go(PAY.replace("1000", "lots"), TRU), "amount is not a number")
        self.assert_input_error(self.go(PAY.replace("1000", "nan"), TRU), "finite")
        self.assert_input_error(self.go(PAY.replace(",10,1,0", ",10.5,1,0"), TRU), "whole number")
        self.assert_input_error(self.go(PAY, TRU.replace("0.1000", "1.0000")), "out of range")
        self.assert_input_error(self.go(PAY.replace(",10,1,0", ",25,1,0"), TRU), "out of range")

    def test_truncated_row(self):
        self.assert_input_error(self.go(PAY_HEADER + "P1,1000,100\n", TRU), "truncated")

    def test_extra_values(self):
        self.assert_input_error(self.go(PAY_HEADER + "P1,1000,100,0,10,1,0,9\n", TRU), "more values than columns")

    def test_missing_column(self):
        self.assert_input_error(self.go(PAY.replace("usual_amount", "usual"), TRU), "missing column")

    def test_duplicate_and_unmatched_ids(self):
        self.assert_input_error(self.go(PAY + "P1,5,5,5,5,0,0\n", TRU), "duplicate")
        self.assert_input_error(self.go(PAY, TRU + "P1,0,ordinary,0.5,0.5\n"), "duplicate")
        self.assert_input_error(self.go(PAY, TRU_HEADER + "P1,1,coached_live,0.1,0.9\n"), "no row in the truth file")
        self.assert_input_error(self.go(PAY, TRU + "P9,0,ordinary,0.5,0.5\n"), "no payment")

    def test_unknown_scam_scenario(self):
        self.assert_input_error(self.go(PAY, TRU.replace("coached_live", "mystery")), "no entry in scam_scenarios")

    def test_missing_file_and_binary_file(self):
        self.assert_input_error(run(["run", "--payments", "/no/such.csv", "--truth", "/no/such.csv"]), "cannot read")
        p = os.path.join(self.dir.name, "bin.csv")
        with open(p, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        t = self.write("t.csv", TRU)
        self.assert_input_error(run(["run", "--payments", p, "--truth", t]), "cannot read")

    def test_bad_assumptions_file(self):
        p, t = self.files()
        for name, text, frag in (("a1.json", "", "not valid JSON"), ("a2.json", "[1]", "expected a JSON object"),
                                 ("a3.json", '{"coach_rate": "high"}', "coach_rate"), ("a4.json", '{"typo": 1}', "unknown key")):
            a = self.write(name, text)
            self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--assumptions", a]), frag)

    def test_bad_options(self):
        p, t = self.files()
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--legit-weight", "0"]), "legit-weight")
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--min-amount", "-5"]), "min-amount")
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--hold-score", "x"]), "hold-score")
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--hold-score", "4", "--warn-score", "4"]), "warn-score")
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--policy", "other"]), "policy")
        self.assert_input_error(run(["run"]), "required")

    def test_no_command_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)

    # ---- hostile strings
    def test_hostile_payment_id_is_escaped_in_the_message(self):
        evil = "P1\n::error::boom%\r::set-output name=x::y"
        pay = PAY_HEADER + '"' + evil + '",lots,100,0,10,1,0\n'
        code, _, err = self.go(pay, TRU)
        self.assertEqual(code, 2)
        self.assertEqual(err.count("\n"), 1)
        self.assertNotIn("\r", err)
        self.assertIn("%0A", err)
        self.assertIn("%25", err)

    def test_hostile_scenario_and_path_are_escaped(self):
        tru = TRU_HEADER + 'P1,1,"x\r\n::error::y%",0.1000,0.9000\nP2,0,ordinary,0.9000,0.9000\n'
        code, _, err = self.go(PAY, tru)
        self.assertEqual((code, err.count("\n")), (2, 1))
        self.assertIn("x%0D%0A::error::y%25", err)
        p, t = self.files()
        code, _, err = run(["run", "--payments", "bad\n::error::path", "--truth", t])
        self.assertEqual((code, err.count("\n")), (2, 1))
        self.assertIn("bad%0A::error::path", err)

    def test_deeply_nested_assumptions_file(self):
        p, t = self.files()
        a = self.write("deep.json", "[" * 100000)
        self.assert_input_error(run(["run", "--payments", p, "--truth", t, "--assumptions", a]), "")

    def test_output_never_contains_untrusted_ids(self):
        _, out, _ = self.go(PAY.replace("P1", "P1::error::z"), TRU.replace("P1", "P1::error::z"))
        self.assertNotIn("::error::", out)


if __name__ == "__main__":
    unittest.main()
