import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import call_notes_actions as cna

NOTES = ("note_id,call_date,sent_id,text\n"
         "N1,2026-10-14,1,I will send Ms. Okafor the rate sheet by Friday.\n"
         "N1,2026-10-14,2,She does not want a follow-up call this quarter.\n"
         "N2,2026-10-15,1,Rates were discussed at length.\n")
HEAD = "cand_id,note_id,action_type,owner,due,subject,amount,cite_sent_id,cite_quote\n"
GOOD = 'C1,N1,send_document,rm,2026-10-16,rate sheet,,1,I will send Ms. Okafor the rate sheet by Friday.\n'
HELD = 'C2,N1,callback,rm,,,,2,She does not want a follow-up call this quarter.\n'
BAD = 'C3,N1,send_document,rm,,rate sheet,,9,I will send the rate sheet.\n'


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cna.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def check(self, notes, cands, *extra):
        return run(["check", self.write("n.csv", notes), self.write("c.csv", cands)] + list(extra))

    def assert_exit_2(self, notes, cands):
        code, out, err = self.check(notes, cands)
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)      # one line, no traceback
        self.assertTrue(err.startswith("error: "))

    def test_demo_runs_and_prints_the_three_decisions(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("checked 7: 3 accepted, 3 held for review, 1 rejected", out)

    def test_exit_status_follows_fail_on(self):
        self.assertEqual(self.check(NOTES, HEAD + GOOD)[0], 0)
        self.assertEqual(self.check(NOTES, HEAD + GOOD + BAD)[0], 1)
        self.assertEqual(self.check(NOTES, HEAD + GOOD + HELD)[0], 0)
        self.assertEqual(self.check(NOTES, HEAD + GOOD + HELD, "--fail-on", "hold")[0], 1)
        self.assertEqual(self.check(NOTES, HEAD + GOOD + BAD, "--fail-on", "never")[0], 0)

    def test_json_format_parses(self):
        code, out, _ = self.check(NOTES, HEAD + GOOD + HELD, "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual([r["decision"] for r in json.loads(out)["results"]], ["ACCEPT", "REVIEW"])

    def test_empty_input_exits_2(self):
        self.assert_exit_2("", HEAD + GOOD)
        self.assert_exit_2(NOTES, "")
        self.assert_exit_2(NOTES.split("\n")[0] + "\n", HEAD + GOOD)       # header and no sentences

    def test_missing_column_and_missing_file_exit_2(self):
        self.assert_exit_2(NOTES.replace("call_date", "when"), HEAD + GOOD)
        self.assert_exit_2(NOTES, HEAD.replace("cite_quote", "quote") + GOOD)
        self.assertEqual(run(["check", "nope.csv", "nope2.csv"])[0], 2)
        self.assertEqual(run(["check", self.dir.name, self.dir.name])[0], 2)

    def test_wrong_type_exits_2(self):
        self.assert_exit_2(NOTES.replace("2026-10-14,1", "14/10/2026,1"), HEAD + GOOD)
        self.assert_exit_2(NOTES.replace("2026-10-15", "2026-02-31"), HEAD + GOOD)
        self.assert_exit_2(NOTES.replace("N1,2026-10-14,1", "N1,2026-10-14,first"), HEAD + GOOD)

    def test_truncated_input_exits_2(self):
        self.assert_exit_2(NOTES + "N3,2026-10-16\n", HEAD + GOOD)
        self.assert_exit_2(NOTES, HEAD + GOOD + "C9,N1,callback\n")
        self.assert_exit_2(NOTES, HEAD + GOOD.rstrip("\n") + ",extra\n")

    def test_binary_file_and_duplicates_exit_2(self):
        n = self.write("bin.csv", b"\xff\xfe\x00\x01", "wb")
        c = self.write("c.csv", HEAD + GOOD)
        self.assertEqual(run(["check", n, c])[0], 2)
        self.assert_exit_2(NOTES, HEAD + GOOD + GOOD)
        self.assert_exit_2(NOTES + NOTES.split("\n")[1] + "\n", HEAD + GOOD)

    def test_wrong_type_citation_is_a_finding_not_a_crash(self):
        bad = 'C4,N1,send_document,rm,,,,abc,I will send the rate sheet.\n'
        code, out, _ = self.check(NOTES, HEAD + bad)
        self.assertEqual(code, 1)
        self.assertIn("cite_not_found", out)

    def test_hostile_strings_cannot_forge_a_log_line(self):
        evil = "x\n::error title=forged::approved\r%0A"
        hostile = HEAD + 'C5,N1,"' + evil + '",rm,,,,1,"' + evil + '"\n' + f'"{evil}",N1,callback,rm,,,,1,"{evil}"\n'
        code, out, err = self.check(NOTES, hostile, "--fail-on", "never")
        self.assertEqual(code, 0, err)
        for line in out.splitlines():
            self.assertFalse(line.startswith("::"), line)
        self.assertIn("%0A", out)
        self.assertIn("%0D", out)
        self.assertIn("%250A", out)                              # a literal %0A in the input is not decoded
        self.assertNotIn("\r", out)

    def test_error_message_escapes_the_path(self):
        code, _, err = run(["check", "bad\n::error::x.csv", "y.csv"])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_candidates_with_no_rows_say_so(self):
        code, out, _ = self.check(NOTES, HEAD)
        self.assertEqual(code, 0)
        self.assertIn("no candidates: nothing was checked", out)
        self.assertIn("notes with no proposed action: 2 of 2", out)

    def test_candidates_for_unknown_notes_say_so(self):
        code, out, _ = self.check(NOTES, HEAD + GOOD.replace(",N1,", ",ZZ,"))
        self.assertEqual(code, 1)
        self.assertIn("note_not_found", out)
        self.assertIn("none of the candidates names a note", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)

    def test_esc_escapes_percent_cr_lf_and_control_characters(self):
        self.assertEqual(cna.esc("a%b\r\nc\x07"), "a%25b%0D%0Ac%07")
        self.assertEqual(len(cna.esc("x" * 500)), 120)


if __name__ == "__main__":
    unittest.main()
