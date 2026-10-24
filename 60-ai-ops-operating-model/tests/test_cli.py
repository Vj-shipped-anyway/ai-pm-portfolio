import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import ops_model_review as omr

CHECKLIST = ("item_id,stage,stage_name,item,min_tier,cycle_days,independent,day_window\n"
             "A,1,Find,Build brief,1,10,no,30\n"
             "B,2,Admit,Validation,1,100,yes,60\n")
PROGRAMS = "program_id,program_name,tier,builder,claimed_stage\nP1,Demo,1,u1,2\n"
EVIDENCE = ("program_id,item_id,artifact_ref,produced_by,date\n"
            "P1,A,DOC-1,u1,2026-09-29\n"
            "P1,B,DOC-2,u1,2026-09-28\n")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = omr.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({"encoding": "utf-8"} if mode == "w" else {})) as fh:
            fh.write(text)
        return p

    def review(self, checklist=CHECKLIST, programs=PROGRAMS, evidence=EVIDENCE, extra=()):
        c, p, e = self.write("c.csv", checklist), self.write("p.csv", programs), self.write("e.csv", evidence)
        return run(["review", "--checklist", c, "--programs", p, "--evidence", e, "--as-of", "2026-09-30", *extra])

    def assert_input_error(self, result):
        code, out, err = result
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(err.count("\n"), 1, err)
        self.assertNotIn("Traceback", err)

    def test_overclaim_exits_1(self):
        code, out, _ = self.review()
        self.assertEqual(code, 1)
        self.assertIn("B Validation: NOT_INDEPENDENT", out)
        self.assertIn("evidence reaches stage 1 of 2", out)
        self.assertIn("decision: OVERCLAIM (claimed 2)", out)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.review(extra=["--fail-on", "never"])[0], 0)

    def test_confirmed_exits_0(self):
        ev = EVIDENCE.replace("P1,B,DOC-2,u1", "P1,B,DOC-2,u2")
        code, out, _ = self.review(evidence=ev)
        self.assertEqual(code, 0)
        self.assertIn("decision: CONFIRMED (claimed 2)", out)

    def test_github_format(self):
        code, out, _ = self.review(extra=["--format", "github"])
        lines = out.splitlines()
        self.assertEqual(code, 1)
        self.assertTrue(lines[0].startswith("::warning title=ops-model-review::"))
        self.assertTrue(lines[-1].startswith("::error title=ops-model-review::"))

    def test_window_line(self):
        _, out, _ = self.review(extra=["--window", "60"])
        self.assertIn("first 60 days: 1 of 2 owed items evidenced; open: B", out)

    def test_program_filter_and_summary_line(self):
        progs = PROGRAMS + "P2,Other,1,u3,0\n"
        _, out, _ = self.review(programs=progs)
        self.assertIn("programs: 2   confirmed 1   overclaim 1   underclaim 0", out)
        _, out, _ = self.review(programs=progs, extra=["--program", "P2"])
        self.assertNotIn("program: P1", out)
        self.assertIn("no evidence rows for this program, so every owed item is MISSING", out)

    def test_unknown_program_filter_exits_2(self):
        self.assert_input_error(self.review(extra=["--program", "P9"]))

    def test_empty_files_exit_2(self):
        for which in range(3):
            args = [CHECKLIST, PROGRAMS, EVIDENCE]
            args[which] = ""
            self.assert_input_error(self.review(*args))

    def test_header_only_files(self):
        self.assert_input_error(self.review(checklist=CHECKLIST.splitlines()[0] + "\n"))
        self.assert_input_error(self.review(programs=PROGRAMS.splitlines()[0] + "\n"))
        code, out, _ = self.review(evidence=EVIDENCE.splitlines()[0] + "\n")
        self.assertEqual(code, 1)
        self.assertIn("no evidence rows for this program", out)

    def test_wrong_type_of_file_exits_2(self):
        self.assert_input_error(self.review(checklist='{"item_id": "A"}\n'))
        self.assert_input_error(self.review(evidence="[1, 2, 3]"))

    def test_truncated_rows_exit_2(self):
        self.assert_input_error(self.review(evidence=EVIDENCE + "P1,A,DOC-1,u1"))
        self.assert_input_error(self.review(checklist=CHECKLIST + "C,3,Run,Report"))
        self.assert_input_error(self.review(evidence=EVIDENCE + "P1,A,DOC-1,u1,2026-09-29,extra\n"))

    def test_bad_values_exit_2(self):
        self.assert_input_error(self.review(programs=PROGRAMS.replace(",1,u1,2", ",one,u1,2")))
        self.assert_input_error(self.review(programs=PROGRAMS.replace(",1,u1,2", ",0,u1,2")))
        self.assert_input_error(self.review(programs=PROGRAMS.replace(",u1,2", ",u1,9")))
        self.assert_input_error(self.review(programs=PROGRAMS.replace(",u1,2", ",,2")))
        self.assert_input_error(self.review(evidence=EVIDENCE.replace("2026-09-29", "29 Sep 2026")))
        self.assert_input_error(self.review(checklist=CHECKLIST.replace(",no,30", ",maybe,30")))
        self.assert_input_error(self.review(checklist=CHECKLIST.replace(",10,no", ",0,no")))
        self.assert_input_error(self.review(checklist=CHECKLIST.replace(",10,no", ",1" + "0" * 400 + ",no")))

    def test_unknown_or_repeated_keys_exit_2(self):
        self.assert_input_error(self.review(evidence=EVIDENCE + "P1,Z,DOC-3,u2,2026-09-29\n"))
        self.assert_input_error(self.review(evidence=EVIDENCE + "P9,A,DOC-3,u2,2026-09-29\n"))
        self.assert_input_error(self.review(evidence=EVIDENCE + "P1,A,DOC-3,u2,2026-09-29\n"))
        self.assert_input_error(self.review(programs=PROGRAMS + "P1,Again,1,u1,0\n"))
        self.assert_input_error(self.review(checklist=CHECKLIST + "A,3,Run,Again,1,10,no,0\n"))

    def test_bad_as_of_missing_file_directory_and_binary_exit_2(self):
        c, p, e = self.write("c.csv", CHECKLIST), self.write("p.csv", PROGRAMS), self.write("e.csv", EVIDENCE)
        base = ["review", "--checklist", c, "--programs", p, "--evidence", e]
        self.assert_input_error(run(base + ["--as-of", "yesterday"]))
        self.assert_input_error(run(["review", "--checklist", os.path.join(self.dir.name, "nope.csv"), "--programs", p,
                                     "--evidence", e, "--as-of", "2026-09-30"]))
        self.assert_input_error(run(["review", "--checklist", self.dir.name, "--programs", p, "--evidence", e,
                                     "--as-of", "2026-09-30"]))
        binary = self.write("b.csv", b"\xff\xfe\x00\x01 not text", mode="wb")
        self.assert_input_error(run(["review", "--checklist", binary, "--programs", p, "--evidence", e,
                                     "--as-of", "2026-09-30"]))

    def test_window_must_be_one_of_the_marks(self):
        self.assertEqual(self.review(extra=["--window", "45"])[0], 2)

    def test_hostile_strings_cannot_forge_a_workflow_command(self):
        forged = "x\n::error title=forged::approved"
        checklist = CHECKLIST.replace("Validation", '"' + forged + '"')
        programs = PROGRAMS.replace("Demo", '"' + forged + '"').replace(",u1,", ',"' + forged + '",')
        evidence = EVIDENCE.replace("P1,B,DOC-2,u1", 'P1,B,DOC-2,"' + forged + '"')
        for fmt in ("github", "text"):
            _, out, _ = self.review(checklist, programs, evidence, extra=["--format", fmt, "--fail-on", "never"])
            commands = [ln for ln in out.splitlines() if ln.startswith("::")]
            if fmt == "github":
                self.assertEqual(len(commands), 2, out)           # the finding and the decision, nothing forged
                self.assertTrue(all(c.startswith(("::warning title=ops-model-review::", "::error title=ops-model-review::"))
                                    for c in commands))
                self.assertIn("%0A", commands[0])
            else:
                self.assertEqual(commands, [], out)

    def test_percent_signs_are_escaped_in_annotations(self):
        evidence = EVIDENCE.replace("DOC-1", "100%").replace("P1,B,DOC-2,u1", "P1,B,DOC-2,u%0A")
        _, out, _ = self.review(programs=PROGRAMS.replace(",u1,", ",u%0A,"), evidence=evidence, extra=["--format", "github"])
        self.assertIn("u%250A", out)

    def test_byte_order_mark_is_accepted(self):
        code, _, _ = self.review(checklist="﻿" + CHECKLIST)
        self.assertEqual(code, 1)

    def test_demo_runs(self):
        code, out, err = run(["--demo"])
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("program: EX-01"))
        self.assertIn("decision: OVERCLAIM", out)
        self.assertIn("I04 Vendor rating: MISSING", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
