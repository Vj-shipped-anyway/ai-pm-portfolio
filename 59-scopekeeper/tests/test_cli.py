import contextlib
import csv
import io
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import scopekeeper as sk

GRANTS = [["A", "x:read"], ["A", "x:write"]]
CALLS = [["A", "x:read", 1]]


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = sk.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, header, rows):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
        return p

    def files(self, grants=GRANTS, calls=CALLS):
        return (self.write("g.csv", ["agent_id", "scope"], grants), self.write("c.csv", ["agent_id", "scope_used", "day"], calls))

    def test_proposals_exit_1(self):
        code, out, _ = run(["diff", *self.files()])
        self.assertEqual(code, 1)
        self.assertIn("remove  A       x:write", out)
        self.assertIn("decision: 1 grants to remove or narrow", out)

    def test_nothing_to_change_exits_0_and_says_so(self):
        code, out, _ = run(["diff", *self.files(calls=[["A", "x:read", 1], ["A", "x:write", 2]])])
        self.assertEqual(code, 0)
        self.assertIn("none: every grant was called", out)
        self.assertIn("decision: no change proposed", out)

    def test_never_keeps_exit_0(self):
        self.assertEqual(run(["diff", *self.files(), "--fail-on", "never"])[0], 0)

    def test_github_format_emits_one_warning_per_proposal(self):
        _, out, _ = run(["diff", *self.files(), "--format", "github", "--fail-on", "never"])
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("::warning title=scopekeeper remove::A x:write"))
        self.assertTrue(lines[1].startswith("::notice"))

    def test_bad_input_exits_2_with_one_line_and_no_traceback(self):
        empty = self.write("e.csv", ["agent_id", "scope"], [])
        wrong = os.path.join(self.dir.name, "w.csv")
        with open(wrong, "w", encoding="utf-8") as fh:
            fh.write('{"not": "a table"}')
        cut = os.path.join(self.dir.name, "t.csv")
        with open(cut, "w", encoding="utf-8") as fh:
            fh.write("agent_id,scope_used,day\nA,x:read,1\nA,x:wri")
        g, c = self.files()
        for args in (["diff", empty, c], ["diff", wrong, c], ["diff", g, wrong], ["diff", g, cut], ["diff", "nope.csv", c],
                     ["diff", g, c, "--catalog", wrong], ["diff", g, c, "--agents", empty],
                     ["diff", g, c, "--min-calls", "0"], ["diff", g, c, "--window-days", "0"]):
            code, out, err = run(args)
            self.assertEqual(code, 2, args)
            self.assertEqual(out, "")
            self.assertTrue(err.startswith("input error: "), err)
            self.assertEqual(len(err.strip().splitlines()), 1, err)
            self.assertNotIn("Traceback", err)

    def test_unknown_option_exits_2(self):
        self.assertEqual(run(["diff", *self.files(), "--no-such-flag"])[0], 2)

    def test_hostile_values_cannot_forge_output_lines(self):
        evil = "A\n::error title=forged::approved\r%0A"
        g, c = self.files(grants=[[evil, "x:read"], [evil, "x:\nwrite"], ["B", "x:read"]], calls=[["B", "x:read", 1]])
        code, out, _ = run(["diff", g, c, "--fail-on", "never"])
        self.assertEqual(code, 0)
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::")])
        self.assertIn("A\\n::error title=forged::approved\\r%0A", out)
        code, out, _ = run(["diff", g, c, "--format", "github", "--fail-on", "never"])
        commands = out.splitlines()
        self.assertEqual(len(commands), 3)                        # two removals and the notice, nothing forged
        self.assertTrue(all(ln.startswith(("::warning title=scopekeeper remove::", "::notice title=scopekeeper::")) for ln in commands))
        self.assertIn("%0A::error title=forged::approved%0D%250A", commands[0])

    def test_hostile_scope_in_a_narrowed_group(self):
        cat = self.write("k.csv", ["scope", "reaches"], [["g", "a;b\nc"]])
        g = self.write("g.csv", ["agent_id", "scope"], [["A", "g"]])
        c = self.write("c.csv", ["agent_id", "scope_used"], [["A", "a"]])
        _, out, _ = run(["diff", g, c, "--catalog", cat, "--format", "github", "--fail-on", "never"])
        self.assertEqual(len(out.splitlines()), 2)

    def test_demo_runs_and_shows_the_three_kinds_of_line(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("narrow  EX-01   accounts:*", out)
        self.assertIn("remove  EX-03   cases:close_case", out)
        self.assertIn("kept on untagged calls alone (1)", out)
        self.assertIn("replay: 0 of 94 calls newly denied", out)

    def test_catalog_and_agents_flags_work_together(self):
        cat = self.write("k.csv", ["scope", "reaches"], [["g", "a;b"]])
        ag = self.write("a.csv", ["agent_id", "service_account"], [["A", "S"], ["B", "S"]])
        g = self.write("g.csv", ["agent_id", "scope"], [["A", "g"], ["B", "b"]])
        c = self.write("c.csv", ["agent_id", "scope_used", "service_account"], [["A", "a", "S"], ["", "b", "S"]])
        code, out, _ = run(["diff", g, c, "--catalog", cat, "--agents", ag])
        self.assertEqual(code, 0)           # A's group is called on a and b (b by credit), B's b is credited: nothing to cut
        self.assertIn("kept on untagged calls alone (1)", out)
        self.assertIn("B       b", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        code, out, _ = run([])
        self.assertEqual(code, 2)
        self.assertIn("usage: scopekeeper", out)


if __name__ == "__main__":
    unittest.main()
