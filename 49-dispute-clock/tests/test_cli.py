import contextlib
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import dispute_clock as dc

POLICY = ("clock_id,clock_name,applies_to,window_days,day_type,anchor_event,satisfied_by\n"
          "C1,Acknowledge,all,2,business,contact,acked\n")
DISPUTES = ("dispute_id,dispute_type,window_class,credit_eligible,contact,acked\n"
            "D1,card,standard,0,2026-09-04,2026-09-09\n"
            "D2,card,standard,0,2026-09-04,2026-09-11\n")
HOLIDAYS = "date,name\n2026-09-07,Labor\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = dc.main(args)
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

    def check(self, disputes=DISPUTES, policy=POLICY, holidays=HOLIDAYS, extra=(), as_of="2026-09-30"):
        d, p, h = self.write("d.csv", disputes), self.write("p.csv", policy), self.write("h.csv", holidays)
        return run(["check", d, "--policy", p, "--holidays", h, "--as-of", as_of] + list(extra))

    def assertBadInput(self, result, fragment):
        code, out, err = result
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(err.count("\n"), 1, err)
        self.assertNotIn("Traceback", err)
        self.assertIn(fragment, err)

    # -- the exit codes
    def test_a_missed_clock_exits_1_and_never_exits_0(self):
        code, out, _ = self.check()
        self.assertEqual(code, 1)
        self.assertIn("missed 1 (late 1, breached 0)", out)
        self.assertEqual(self.check(extra=["--fail-on", "never"])[0], 0)

    def test_nothing_missed_exits_0(self):
        code, out, _ = self.check(disputes=DISPUTES.split("D2")[0])
        self.assertEqual(code, 0)
        self.assertIn("missed 0", out)

    def test_demo_prints_the_worked_example(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "as of 2026-09-30: 1 dispute, 4 clocks apply (5 clocks in policy, 11 holidays loaded)")
        self.assertIn("DC1 Acknowledge to customer                due 2026-09-09  sent 2026-09-09  on time", out)
        self.assertIn("late by 2 business days", out)
        self.assertIn("running, 4 days left", out)
        self.assertIn("not started (waits for concluded_on)", out)

    def test_all_prints_every_clock_of_every_dispute(self):
        _, out, _ = self.check(extra=["--all"])
        self.assertIn("D1  card", out)
        self.assertIn("D2  card", out)
        self.assertEqual(out.count("C1 Acknowledge"), 2)

    # -- bad input exits 2 with one line, never a traceback
    def test_empty_files_exit_2(self):
        self.assertBadInput(self.check(disputes=""), "missing column")
        self.assertBadInput(self.check(policy=""), "missing column")
        self.assertBadInput(self.check(holidays=""), "missing column")

    def test_header_only_files_exit_2(self):
        header = DISPUTES.splitlines()[0] + "\n"
        self.assertBadInput(self.check(disputes=header), "no rows")
        self.assertBadInput(self.check(policy=POLICY.splitlines()[0] + "\n"), "no clocks")

    def test_wrong_type_of_file_exits_2(self):
        d, p, h = self.write("d.csv", DISPUTES), self.write("p.csv", POLICY), self.write("h.csv", HOLIDAYS)
        self.assertBadInput(run(["check", self.dir.name, "--policy", p, "--holidays", h, "--as-of", "2026-09-30"]), "input error")
        blob = self.write("blob.csv", b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe", mode="wb")
        self.assertBadInput(run(["check", blob, "--policy", p, "--holidays", h, "--as-of", "2026-09-30"]), "input error")
        as_json = self.write("d.json", '{"disputes": []}')
        self.assertBadInput(run(["check", as_json, "--policy", p, "--holidays", h, "--as-of", "2026-09-30"]), "missing column")
        self.assertBadInput(run(["check", d, "--policy", os.path.join(self.dir.name, "nope.csv"), "--holidays", h,
                                 "--as-of", "2026-09-30"]), "input error")

    def test_truncated_input_exits_2(self):
        self.assertBadInput(self.check(disputes=DISPUTES.splitlines()[0] + "\nD1,card,stand"), "wrong number of fields")
        self.assertBadInput(self.check(disputes=DISPUTES.splitlines()[0] + "\nD1,card,standard,0,2026-09-0,"), "not a date")
        self.assertBadInput(self.check(disputes=DISPUTES[:30]), "missing column")

    def test_bad_values_exit_2(self):
        row = DISPUTES.splitlines()
        self.assertBadInput(self.check(disputes="\n".join([row[0], "D1,card,weird,0,2026-09-04,"])), "window_class")
        self.assertBadInput(self.check(disputes="\n".join([row[0], "D1,card,standard,yes,2026-09-04,"])), "credit_eligible")
        self.assertBadInput(self.check(disputes="\n".join([row[0], "D1,card,standard,0,2026-02-30,"])), "not a real date")
        self.assertBadInput(self.check(disputes="\n".join([row[0], "D1,card,standard,0,9999-01-01,"])), "outside the years")
        self.assertBadInput(self.check(disputes="\n".join([row[0], "D1,card,standard,0,2026-09-04,", "D1,card,standard,0,2026-09-05,"])),
                            "repeated")
        self.assertBadInput(self.check(disputes="\n".join([row[0], ",card,standard,0,2026-09-04,"])), "empty")
        self.assertBadInput(self.check(holidays="date\nlater\n"), "not a date")
        self.assertBadInput(self.check(as_of="30/09/2026"), "--as-of")

    def test_bad_policy_exits_2(self):
        head = POLICY.splitlines()[0]
        self.assertBadInput(self.check(policy=head + "\nC1,A,sometimes,2,business,contact,acked\n"), "applies_to")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,2,fortnight,contact,acked\n"), "day_type")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,0,business,contact,acked\n"), "window_days")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,two,business,contact,acked\n"), "window_days")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,2,business,contact,\n"), "satisfied_by")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,2,business,contact,acked\nC1,B,all,2,business,contact,acked\n"), "repeated")
        self.assertBadInput(self.check(policy=head + "\nC1,A,all,2,business,signed_on,acked\n"), "signed_on")

    def test_an_event_after_the_as_of_date_exits_2(self):
        self.assertBadInput(self.check(as_of="2026-09-08"), "after --as-of")

    def test_a_policy_that_matches_no_dispute_says_so(self):
        self.assertBadInput(self.check(policy=POLICY.replace(",all,", ",extended,")), "no clock applies")

    def test_bad_option_values_exit_2(self):
        for opt in (["--limit", "0"], ["--limit", "-3"], ["--due-soon", "soon"]):
            self.assertEqual(self.check(extra=opt)[0], 2)

    # -- notes that stop a silent miscount
    def test_empty_holiday_file_is_noted(self):
        _, out, _ = self.check(holidays="date,name\n")
        self.assertIn("holiday file is empty", out)

    def test_year_without_holidays_is_noted(self):
        _, out, _ = self.check(holidays="date,name\n2025-01-01,x\n")
        self.assertIn("reach a year with no holiday", out)

    # -- hostile strings
    def hostile(self):
        evil = "D9\n::error title=forged::approved\r::notice::x"
        rows = DISPUTES.splitlines()[0] + "\n" + '"%s",card,standard,0,2026-09-04,\n' % evil
        return self.check(disputes=rows, extra=["--format", "github"])

    def test_hostile_dispute_id_cannot_forge_a_workflow_command(self):
        code, out, _ = self.hostile()
        self.assertEqual(code, 1)
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertEqual(len(commands), 2)             # the one missed clock and the summary notice
        self.assertIn("%0A", commands[0])
        self.assertIn("%0D", commands[0])
        self.assertNotIn("\r", out)

    def test_hostile_policy_text_is_escaped_in_titles_and_messages(self):
        policy = POLICY.replace("C1,Acknowledge", 'C1:x,"Ack\n::error::bad"')
        code, out, _ = self.check(policy=policy, extra=["--format", "github"])
        self.assertEqual(code, 1)
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertIn("C1%3Ax", commands[0])

    def test_hostile_text_cannot_add_lines_to_text_output(self):
        evil = "D9\nmissed 0 (forged)"
        rows = DISPUTES.splitlines()[0] + "\n" + '"%s",card,standard,0,2026-09-04,\n' % evil
        _, out, _ = self.check(disputes=rows, extra=["--all"])
        self.assertNotIn("\nmissed 0 (forged)", out)
        self.assertIn("D9?missed 0 (forged)", out)


if __name__ == "__main__":
    unittest.main()
