import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import smb_faq_abstain as g

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
KB = os.path.join(DATA, "kb.csv")
GOOD_Q = "What is the monthly fee on Business Checking Basic?"
GOOD_D = "Business Checking Basic has a monthly maintenance fee of $15."
HEADER = "fact_id,product,excluded_states,text\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = g.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(text)
        return p

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)

    def test_grounded_draft_exits_0(self):
        code, out, _ = run(["check", "--kb", KB, "--question", GOOD_Q, "--draft", GOOD_D])
        self.assertEqual(code, 0)
        self.assertIn("decision: SERVE (grounded)", out)

    def test_ungrounded_draft_exits_1(self):
        code, out, _ = run(["check", "--kb", KB, "--question", GOOD_Q, "--draft", "The fee is $99."])
        self.assertEqual(code, 1)
        self.assertIn("decision: ABSTAIN (ungrounded)", out)

    def test_no_matching_passage_says_so(self):
        code, out, _ = run(["check", "--kb", KB, "--question", "Do you offer payroll services?", "--draft", "Yes, for $20."])
        self.assertEqual(code, 1)
        self.assertIn("no passage covers the question", out)

    def test_missing_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", os.path.join(self.dir.name, "nope.csv"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_directory_as_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.dir.name, "--question", GOOD_Q, "--draft", GOOD_D])

    def test_empty_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("empty.csv", ""), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_header_only_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("h.csv", HEADER), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_wrong_type_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("kb.json", '{"fact_id": "F01"}'), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_missing_column_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("c.csv", "fact_id,product,text\nF01,P,t\n"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_truncated_row_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("t.csv", HEADER + "F01,Business Savings\n"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_truncated_inside_a_quote_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("q.csv", HEADER + 'F01,Business Savings,,"Pays 1.20% APY'), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_binary_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("b.csv", b"\xff\xfe\x00\x01", "wb"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_unknown_state_in_kb_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("s.csv", HEADER + "F01,P,narnia,Some text here.\n"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_duplicate_fact_id_exits_2(self):
        self.assert_input_error(["check", "--kb", self.write("d.csv", HEADER + "F01,P,,one\nF01,Q,,two\n"), "--question", GOOD_Q, "--draft", GOOD_D])

    def test_empty_question_or_draft_exits_2(self):
        self.assert_input_error(["check", "--kb", KB, "--question", "  ", "--draft", GOOD_D])
        self.assert_input_error(["check", "--kb", KB, "--question", GOOD_Q, "--draft", ""])

    def test_min_grounded_out_of_range_exits_2(self):
        self.assertEqual(run(["check", "--kb", KB, "--question", GOOD_Q, "--draft", GOOD_D, "--min-grounded", "0"])[0], 2)
        self.assertEqual(run(["check", "--kb", KB, "--question", GOOD_Q, "--draft", GOOD_D, "--min-grounded", "1.5"])[0], 2)

    def test_hostile_strings_stay_on_one_line(self):
        hostile = "ok\n::error title=forged::approved\r\n%0A\x1b[31m"
        _, out, _ = run(["check", "--kb", KB, "--question", GOOD_Q + hostile, "--draft", hostile])
        lines = out.splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual([ln.split(":")[0] for ln in lines], ["question", "draft", "decision"])
        self.assertNotIn("\x1b", out)

    def test_hostile_kb_text_cannot_forge_a_line(self):
        kb = self.write("h.csv", HEADER + 'F01,"Alpha\n::error::forged",,"Fee is $1."\nF02,"Beta\n::error::forged",,"Fee is $1."\n')
        _, out, _ = run(["check", "--kb", kb, "--question", "What is the fee?", "--draft", "The fee is $1."])
        self.assertEqual(len(out.splitlines()), 3)
        self.assertFalse(any(ln.startswith("::") for ln in out.splitlines()))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def pairs(self, text):
        p = os.path.join(self.dir.name, "pairs.csv")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def test_batch_prints_one_line_per_row_and_a_summary(self):
        p = self.pairs("query_id,question,draft\n1," + f'"{GOOD_Q}","{GOOD_D}"\n2,"{GOOD_Q}","The fee is $99."\n')
        code, out, _ = run(["batch", "--kb", KB, "--pairs", p])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn("served 1 of 2, held back 1", out)

    def test_batch_with_no_rows_exits_2(self):
        code, _, err = run(["batch", "--kb", KB, "--pairs", self.pairs("query_id,question,draft\n")])
        self.assertEqual(code, 2)
        self.assertIn("no rows", err)

    def test_batch_with_wrong_columns_exits_2(self):
        code, _, err = run(["batch", "--kb", KB, "--pairs", self.pairs("id,q\n1,x\n")])
        self.assertEqual(code, 2)
        self.assertIn("missing column", err)

    def test_batch_hostile_row_stays_on_one_line(self):
        p = self.pairs('query_id,question,draft\n"a\n::error::x","What is the rate?","line1\nline2"\n')
        _, out, _ = run(["batch", "--kb", KB, "--pairs", p])
        self.assertEqual(len(out.splitlines()), 2)


class DemoTests(unittest.TestCase):
    def test_demo_prints_three_lines_and_a_decision(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertEqual(len(out.splitlines()), 3)
        self.assertIn("decision: ABSTAIN", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage", out)


if __name__ == "__main__":
    unittest.main()
