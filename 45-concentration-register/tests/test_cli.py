from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import concentration_register as cr

HEAD = "service_id,name,owner_type,criticality,provider,region,resilience,standby_provider,standby_region\n"
GOOD = HEAD + ("a,alpha api,internal,critical,CP-1,R1,single,,\n"
               "b,beta api,internal,critical,CP-2,R1,single,,\n"
               "c,gamma batch,saas,important,,,,,\n")
DEPS = "service_id,depends_on,kind\nb,a,hard\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cr.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text, binary=False):
        p = os.path.join(self.dir.name, name)
        with open(p, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def assert_input_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertTrue(err.startswith("input error: "), err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)

    def test_demo_prints_the_readme_output(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "register: 10 services (7 critical), 3 providers, 5 regions; 7 hard and 2 soft dependencies")
        self.assertIn("  P:CP-2       1 of 7 (14.3%)   6 of 7 (85.7%)  OVER", lines)
        self.assertIn("  P:CP-1       3 of 7 (42.9%)   2 of 7 (28.6%)", lines)
        self.assertEqual(lines[-1], "decision: OVER LIMIT (2 of 8 scenarios lose more than 30% of critical services)")

    def test_over_limit_exits_1_and_within_exits_0(self):
        s, d = self.write("s.csv", GOOD), self.write("d.csv", DEPS)
        code, out, _ = run(["check", s, "--deps", d, "--limit-pct", "40"])
        self.assertEqual(code, 1)
        self.assertIn("decision: OVER LIMIT", out)
        code, out, _ = run(["check", s, "--deps", d, "--limit-pct", "100"])
        self.assertEqual(code, 0)
        self.assertIn("decision: WITHIN LIMIT", out)

    def test_dependency_changes_the_answer(self):
        s, d = self.write("s.csv", GOOD), self.write("d.csv", DEPS)
        _, without, _ = run(["check", s, "--limit-pct", "60"])
        code, with_deps, _ = run(["check", s, "--deps", d, "--limit-pct", "60"])
        self.assertIn("decision: WITHIN LIMIT", without)
        self.assertEqual(code, 1)
        self.assertIn("P:CP-1       1 of 2 (50.0%)   2 of 2 (100.0%)", with_deps)

    def test_no_deps_file_and_empty_deps_file_say_so(self):
        s = self.write("s.csv", GOOD)
        self.assertIn("no file given, so no dependency was followed", run(["check", s])[1])
        empty = self.write("d.csv", "service_id,depends_on,kind\n")
        self.assertIn("the file has no rows", run(["check", s, "--deps", empty])[1])

    def test_unplaced_critical_service_is_reported(self):
        text = GOOD + "d,delta engine,saas,critical,,,,,\n"
        _, out, _ = run(["check", self.write("s.csv", text)])
        self.assertIn("unplaced: 1 critical service with no provider or region (d delta engine)", out)

    def test_json_format_parses(self):
        code, out, _ = run(["check", self.write("s.csv", GOOD), "--format", "json", "--limit-pct", "100"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["critical"], 2)

    def test_empty_and_header_only_and_no_critical_files_exit_2(self):
        self.assert_input_error(["check", self.write("e.csv", "")])
        self.assert_input_error(["check", self.write("h.csv", HEAD)])
        self.assert_input_error(["check", self.write("n.csv", HEAD + "a,alpha,internal,standard,CP-1,R1,single,,\n")])

    def test_wrong_type_and_truncated_input_exit_2(self):
        self.assert_input_error(["check", self.write("j.csv", '{"services": []}')])
        self.assert_input_error(["check", self.write("b.csv", b"\xff\xfe\x00\x01\x80", binary=True)])
        self.assert_input_error(["check", self.write("t.csv", GOOD[:-20])])
        self.assert_input_error(["check", self.write("c.csv", "service_id,name\na,b\n")])
        self.assert_input_error(["check", self.dir.name])
        self.assert_input_error(["check", os.path.join(self.dir.name, "missing.csv")])

    def test_bad_values_exit_2(self):
        for row in ("a,x,internal,urgent,CP-1,R1,single,,\n",              # criticality
                    "a,x,vendor,critical,CP-1,R1,single,,\n",              # owner
                    "a,x,internal,critical,CP-1,,single,,\n",              # region missing
                    "a,x,internal,critical,CP-1,R1,warm_standby,,\n",      # standby missing
                    "a,x,internal,critical,CP-1,R1,single,CP-2,R1\n",      # standby on a single
                    "a,x,internal,critical,CP-1,R1,hot,,\n",               # resilience
                    "a,x,internal,critical,,,single,,\n",                  # resilience without placement
                    "a,x,internal,critical,CP-1,R1,single,,\na,y,internal,critical,CP-1,R1,single,,\n"):  # duplicate id
            self.assert_input_error(["check", self.write("s.csv", HEAD + row)])

    def test_bad_dependencies_exit_2(self):
        s = self.write("s.csv", GOOD)
        for body in ("b,zzz,hard\n", "b,a,sometimes\n", "a,a,hard\n", "a,b,hard\nb,a,hard\n"):
            self.assert_input_error(["check", s, "--deps", self.write("d.csv", "service_id,depends_on,kind\n" + body)])

    def test_bad_options_exit_2(self):
        s = self.write("s.csv", GOOD)
        for args in (["check", s, "--limit-pct", "abc"], ["check", s, "--limit-pct", "101"],
                     ["check", s, "--limit-pct", "nan"], ["check", s, "--format", "xml"], [], ["check"]):
            self.assert_input_error(args)

    def csv_text(self, *rows):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(HEAD.strip().split(","))
        w.writerows(rows)
        return buf.getvalue()

    def test_hostile_strings_cannot_forge_a_line_or_a_command(self):
        hostile = "x\n::error title=forged::approved\x1b[31m\r%"
        text = self.csv_text((hostile, hostile, "saas", "critical", "", "", "", "", ""),
                             ("b", "beta api", "internal", "critical", "CP-1", "R1", "single", "", ""))
        _, out, err = run(["check", self.write("s.csv", text)])
        self.assertEqual(err, "")
        for ch in "\x1b\r":
            self.assertNotIn(ch, out)
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("::")])
        self.assertIn("x\\x0a::error title=forged::approved\\x1b[31m\\x0d%", out)
        bad = self.csv_text(("a", "x", "internal", hostile, "", "", "", "", ""))
        code, _, err = run(["check", self.write("bad.csv", bad)])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\x1b", err)
        d = self.write("d.csv", f'service_id,depends_on,kind\nb,"{hostile}",hard\n')
        code, _, err = run(["check", self.write("g.csv", GOOD), "--deps", d])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\r", err)

    def test_clean_escapes_and_truncates(self):
        self.assertEqual(cr.clean("a\nb\x1b"), "a\\x0ab\\x1b")
        self.assertEqual(len(cr.clean("z" * 500)), 60)


if __name__ == "__main__":
    unittest.main()
