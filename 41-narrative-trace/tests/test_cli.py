import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import narrative_trace as nt

HEADER = "txn_id,case_id,date,amount,direction,channel,counterparty\n"
GOOD_TXNS = (HEADER + "T-1,C1,2026-03-03,9800.00,in,cash,\n" + "T-2,C1,2026-03-05,12000.00,out,wire,Tessel Trading Ltd.\n"
             + "T-3,C2,2026-03-06,100.00,in,ach,Brindle Foods Inc.\n")
GOOD_TEXT = "The customer deposited $9,800.00 in cash on 2026-03-03 [txn: T-1].\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = nt.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, content, mode="w"):
        path = os.path.join(self.dir.name, name)
        with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8", "newline": ""})) as fh:
            fh.write(content)
        return path

    def check(self, narrative, txns=GOOD_TXNS, *extra):
        return run(["check", self.write("n.txt", narrative), self.write("t.csv", txns), "--case", "C1"] + list(extra))

    def test_clean_narrative_exits_0(self):
        code, out, _ = self.check(GOOD_TEXT)
        self.assertEqual(code, 0)
        self.assertIn("result: PASS", out)

    def test_untraced_sentence_exits_1(self):
        code, out, _ = self.check(GOOD_TEXT + "The customer then left. ")
        self.assertEqual(code, 1)
        self.assertIn("uncited", out)
        self.assertIn("result: FAIL", out)

    def test_fail_on_never_and_unchecked(self):
        text = GOOD_TEXT + "The funds were moved onward [txn: T-1].\n"
        self.assertEqual(self.check(text)[0], 0)
        self.assertEqual(self.check(text, GOOD_TXNS, "--fail-on", "unchecked")[0], 1)
        self.assertEqual(self.check("Nothing cited.", GOOD_TXNS, "--fail-on", "never")[0], 0)

    def test_truncated_citation_is_a_finding_not_a_crash(self):
        code, out, _ = self.check("The customer deposited $9,800.00 in cash [txn: T-")
        self.assertEqual(code, 1)
        self.assertIn("uncited", out)

    def test_demo(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)  # the demo prints FAIL and still exits 0
        self.assertTrue(out.startswith("narrative-trace: example_narrative.txt against 7 records (case EX-1)"))
        for word in ("channel mismatch", "amount mismatch", "uncited", "other case", "dangling citation", "unchecked"):
            self.assertIn(word, out)
        self.assertIn("result: FAIL", out)

    def test_github_format(self):
        code, out, _ = self.check("Nothing cited here.", GOOD_TXNS, "--format", "github")
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("::error file=n.txt,line=1,title=narrative-trace::"))
        self.assertTrue(lines[-1].startswith("::notice "))

    def test_narrative_that_cites_nothing_says_so(self):
        _, out, _ = self.check("One thing happened. Another thing happened.")
        self.assertIn("note: no sentence has a citation", out)

    def test_narrative_for_another_export_says_so(self):
        _, out, _ = self.check("It happened [txn: X-1].")
        self.assertIn("note: none of the 1 cited IDs", out)

    # ---- input that cannot be read exits 2 with one line on stderr
    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_missing_and_unreadable_files(self):
        t = self.write("t.csv", GOOD_TXNS)
        n = self.write("n.txt", GOOD_TEXT)
        self.assert_input_error(["check", os.path.join(self.dir.name, "none.txt"), t])
        self.assert_input_error(["check", n, os.path.join(self.dir.name, "none.csv")])
        self.assert_input_error(["check", self.dir.name, t])
        self.assert_input_error(["check", n, self.dir.name])

    def test_bad_narratives(self):
        t = self.write("t.csv", GOOD_TXNS)
        for name, content, mode in (("empty", "", "w"), ("blank", "  \n\n ", "w"), ("punct", "... ?! .", "w"),
                                    ("nul", b"abc\x00def", "wb"), ("latin1", b"caf\xe9 [txn: T-1].", "wb")):
            with self.subTest(name=name):
                self.assert_input_error(["check", self.write(name + ".txt", content, mode), t])

    def test_bad_transaction_files(self):
        n = self.write("n.txt", GOOD_TEXT)
        base = "T-1,C1,2026-03-03,9800.00,in,cash,\n"
        cases = {"empty": "", "header only": HEADER, "missing column": "txn_id,date\nT-1,2026-03-03\n",
                 "short row": HEADER + "T-1,C1,2026-03-03,98\n", "extra field": HEADER + base.rstrip("\n") + ",x\n",
                 "text amount": HEADER + "T-1,C1,2026-03-03,12abc,in,cash,\n",
                 "nan amount": HEADER + "T-1,C1,2026-03-03,NaN,in,cash,\n",
                 "negative amount": HEADER + "T-1,C1,2026-03-03,-5,in,cash,\n",
                 "exponent amount": HEADER + "T-1,C1,2026-03-03,1e3,in,cash,\n",
                 "slash date": HEADER + "T-1,C1,2026/03/03,5,in,cash,\n",
                 "compact date": HEADER + "T-1,C1,20260303,5,in,cash,\n",
                 "no such day": HEADER + "T-1,C1,2026-02-30,5,in,cash,\n",
                 "bad direction": HEADER + "T-1,C1,2026-03-03,5,sideways,cash,\n",
                 "no channel": HEADER + "T-1,C1,2026-03-03,5,in,,\n",
                 "empty id": HEADER + ",C1,2026-03-03,5,in,cash,\n",
                 "duplicate id": HEADER + base + base,
                 "binary": b"\x00\x01\x02"}
        for name, content in cases.items():
            with self.subTest(name=name):
                mode = "wb" if isinstance(content, bytes) else "w"
                self.assert_input_error(["check", n, self.write("bad.csv", content, mode)])

    def test_case_option_errors(self):
        n = self.write("n.txt", GOOD_TEXT)
        self.assert_input_error(["check", n, self.write("a.csv", GOOD_TXNS), "--case", "C9"])
        no_case = "txn_id,date,amount,direction,channel,counterparty\nT-1,2026-03-03,5,in,cash,\n"
        self.assert_input_error(["check", n, self.write("b.csv", no_case), "--case", "C1"])
        code, out, _ = run(["check", n, self.write("b.csv", no_case)])
        self.assertEqual(code, 1)  # no --case: records resolve across the whole file
        self.assertIn("amount mismatch", out)

    def test_bad_command_line(self):
        for args in ([], ["frobnicate"], ["check"], ["check", "a", "b", "--format", "xml"], ["--nope"]):
            with self.subTest(args=args):
                code, _, err = run(args)
                self.assertEqual(code, 2)
                self.assertNotIn("Traceback", err)

    # ---- text from the input must not forge workflow commands or terminal lines
    def test_hostile_citation_cannot_forge_an_annotation(self):
        hostile = "Paid it [txn: T-9%\n::error title=forged::approved]\r::warning::x and again.\n"
        _, out, _ = self.check(hostile, GOOD_TXNS, "--format", "github")
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(out.splitlines()), len(commands))
        self.assertTrue(all(c.startswith(("::error file=n.txt", "::warning file=n.txt", "::notice title=")) for c in commands), commands)
        self.assertIn("T-9%25%0A::error title=forged::approved", out)
        self.assertNotIn("\r", out)
        _, text, _ = self.check(hostile)
        self.assertFalse([ln for ln in text.splitlines() if ln.lstrip().startswith("::")], text)

    def test_hostile_counterparty_name_from_the_file(self):
        txns = HEADER + 'T-1,C1,2026-03-03,5.00,in,wire,"Evil Co\n::error title=forged::x"\n'
        narrative = "It went to Tessel Trading Ltd. [txn: T-1].\n"
        # the name appears in a mismatch detail, not only in the quote
        txns += "T-2,C1,2026-03-04,5.00,in,wire,Tessel Trading Ltd.\n"
        for fmt in ("text", "github"):
            _, out, _ = run(["check", self.write("n.txt", narrative), self.write("t.csv", txns), "--case", "C1", "--format", fmt])
            self.assertFalse([ln for ln in out.splitlines() if ln.lstrip().startswith("::error title=forged")], out)
            self.assertIn("party mismatch" if fmt == "text" else "party", out)

    def test_hostile_file_name_is_escaped_in_the_annotation_property(self):
        n = self.write("a,b:c.txt", "Nothing cited.")
        _, out, _ = run(["check", n, self.write("t.csv", GOOD_TXNS), "--case", "C1", "--format", "github"])
        self.assertIn("file=a%2Cb%3Ac.txt", out)

    def test_control_characters_are_flattened_in_text_output(self):
        _, out, _ = self.check("Paid it\x1b[31m red\x07 now.\n")
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\x07", out)


if __name__ == "__main__":
    unittest.main()
