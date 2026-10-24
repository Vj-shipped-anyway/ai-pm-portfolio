import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import cost_gate

BUDGET = {"min_items": 30, "prices_usd_per_1k_tokens": {"m": {"input": 1.0, "output": 1.0}},
          "overall": {"max_cost_per_correct_usd": 100.0}, "slices": {"a": {"max_cost_per_correct_usd": 2.5}}}
HEADER = "item_id,slice,model,correct,input_tokens,output_tokens\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cost_gate.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.budget = self.write("budget.json", json.dumps(BUDGET))

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def results(self, right, n=40, name="r.csv", slice_name="a", header=HEADER):
        # each call bills 1000 + 1000 tokens at 1.0 per 1k, so 2.0 a call; `right` of n are correct
        rows = "".join(f'Q{i},{slice_name},m,{1 if i < right else 0},1000,1000\n' for i in range(n))
        return self.write(name, header + rows)

    def test_over_budget_exits_1(self):
        code, out, _ = run(["check", self.results(20), self.budget])     # about 4.0 per correct against 2.5
        self.assertEqual(code, 1)
        self.assertIn("decision: FAIL", out)

    def test_within_budget_exits_0(self):
        code, out, _ = run(["check", self.results(40), self.budget])     # 2.0 per correct
        self.assertEqual(code, 0)
        self.assertIn("decision: PASS", out)

    def test_warn_exits_0_by_default_and_1_with_fail_on_warn(self):
        # 2.0 per correct would pass; 28 right of 40 gives 2.86, over 2.5, with an interval that still reaches it
        r = self.results(28)
        code, out, _ = run(["check", r, self.budget])
        self.assertEqual((code, "decision: WARN" in out), (0, True))
        self.assertEqual(run(["check", r, self.budget, "--fail-on", "warn"])[0], 1)

    def test_never_keeps_exit_0(self):
        self.assertEqual(run(["check", self.results(20), self.budget, "--fail-on", "never"])[0], 0)

    def test_github_format_emits_error_annotation_and_notice(self):
        _, out, _ = run(["check", self.results(20), self.budget, "--format", "github"])
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("::error title=cost-gate FAIL::"))
        self.assertTrue(lines[-1].startswith("::notice title=cost-gate::decision FAIL"))

    def test_extra_columns_are_ignored(self):
        p = self.write("x.csv", "cr_id,item_id,slice,model,correct,input_tokens,output_tokens\n"
                       + "".join(f"CR-1,Q{i},a,m,1,1000,1000\n" for i in range(40)))
        self.assertEqual(run(["check", p, self.budget])[0], 0)

    def test_utf8_byte_order_mark_is_accepted(self):
        p = self.write("bom.csv", (b"\xef\xbb\xbf" + (HEADER + "".join(f"Q{i},a,m,1,1000,1000\n" for i in range(40))).encode()), mode="wb")
        self.assertEqual(run(["check", p, self.budget])[0], 0)

    def test_path_starting_with_a_dash_works_after_double_dash(self):
        before = os.getcwd()
        os.chdir(self.dir.name)
        self.addCleanup(os.chdir, before)
        self.results(40, name="-r.csv")
        self.assertEqual(run(["check", "--", "-r.csv", "budget.json"])[0], 0)

    def test_budget_without_slices_says_only_the_whole_run_was_checked(self):
        b = self.write("whole.json", json.dumps({k: v for k, v in BUDGET.items() if k != "slices"}))
        code, out, _ = run(["check", self.results(40), b])
        self.assertEqual(code, 0)
        self.assertIn("no slice ceilings", out)
        self.assertIn("NO_BUDGET", out)       # the slice in the results has no ceiling, and the run says so

    def test_slice_names_that_match_nothing_are_reported_both_ways(self):
        _, out, _ = run(["check", self.results(40, slice_name="renamed"), self.budget])
        self.assertIn("NO_ROWS", out)
        self.assertIn("NO_BUDGET", out)
        self.assertIn("decision: WARN", out)

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_missing_files_exit_2(self):
        self.assert_input_error(["check", "nope.csv", self.budget])
        self.assert_input_error(["check", self.results(40), "nope.json"])

    def test_empty_and_header_only_results_exit_2(self):
        self.assert_input_error(["check", self.write("empty.csv", ""), self.budget])
        self.assert_input_error(["check", self.write("head.csv", HEADER), self.budget])

    def test_wrong_type_values_exit_2(self):
        for bad in ("Q1,a,m,yes,1000,1000\n", "Q1,a,m,1,lots,1000\n", "Q1,a,m,1,1000,-3\n", "Q1,a,zz,1,1000,1000\n", "Q1,a,m,1,1e3,1000\n"):
            self.assert_input_error(["check", self.write("bad.csv", HEADER + bad), self.budget])

    def test_truncated_input_exits_2(self):
        self.assert_input_error(["check", self.write("cut.csv", HEADER + "Q1,a,m,1,1000,1000\nQ2,a,m,1,10"), self.budget])
        self.assert_input_error(["check", self.write("nohead.csv", "item_id,slice\nQ1,a\n"), self.budget])
        self.assert_input_error(["check", self.results(40), self.write("cut.json", '{"min_items": 30, "prices_usd_')])

    def test_binary_and_wrong_shape_files_exit_2(self):
        self.assert_input_error(["check", self.write("bin.csv", b"\xff\xfe\x00\x01", mode="wb"), self.budget])
        self.assert_input_error(["check", self.results(40), self.write("list.json", "[1, 2]")])
        self.assert_input_error(["check", self.results(40), self.write("deep.json", "[" * 100000)])
        self.assert_input_error(["check", self.results(40), self.write("nan.json", '{"prices_usd_per_1k_tokens": {"m": {"input": NaN, "output": 1}}}')])

    def test_two_runs_in_one_file_exit_2(self):
        p = self.write("two.csv", HEADER + "Q1,a,m,1,1000,1000\nQ1,a,m,1,1000,1000\n")
        self.assert_input_error(["check", p, self.budget])

    def test_hostile_slice_name_cannot_forge_a_line_in_text_output(self):
        evil = '"a\ndecision: PASS\n::error title=forged::approved"'
        _, out, _ = run(["check", self.results(40, slice_name=evil), self.budget, "--fail-on", "never"])
        lines = out.splitlines()
        self.assertEqual(sum(1 for ln in lines if ln.startswith("decision:")), 1)
        self.assertFalse(any(ln.startswith("::") for ln in lines))
        self.assertIn("\\u000a", out)

    def test_hostile_slice_name_cannot_forge_an_annotation(self):
        evil = '"a\n::error title=forged::approved"'
        _, out, _ = run(["check", self.results(40, slice_name=evil), self.budget, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertTrue(all(c.startswith(("::warning title=cost-gate", "::notice title=cost-gate")) for c in commands), commands)
        self.assertIn("%0A", out)

    def test_percent_and_carriage_return_are_escaped(self):
        self.assertEqual(cost_gate.escape_annotation("a%b\r\nc"), "a%25b%0D%0Ac")

    def test_hostile_model_name_stays_on_one_line_in_the_error(self):
        p = self.write("m.csv", HEADER + 'Q1,a,"x\nfake line",1,1000,1000\n')
        self.assert_input_error(["check", p, self.budget])

    def test_demo_runs_and_shows_a_slice_over_budget(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: FAIL", out)
        self.assertIn("card_services", out)

    def test_no_arguments_exit_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
