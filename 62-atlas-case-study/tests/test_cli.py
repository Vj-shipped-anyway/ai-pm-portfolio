import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
from test_build import bundle, storm

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
HOSTILE = 'x\n---\nprocedure: []\r::error::bad %0A "quoted" \\ #hash   end'
LINE = re.compile(r'^ *(- )?[a-z_-]+:( ".*"| true| false| \d+)?$')


def cli(*args):
    return subprocess.run([sys.executable, "atlas_case_study.py"] + list(args), cwd=SRC, capture_output=True, text=True)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def write_bundle(self, name, b):
        return self.write(name, json.dumps(b))

    def assert_input_error(self, r):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(len(r.stderr.strip().splitlines()), 1, r.stderr)
        self.assertTrue(r.stderr.startswith("input error:"), r.stderr)

    def test_demo_prints_three_lines(self):
        r = cli("--demo")
        self.assertEqual((r.returncode, len(r.stdout.splitlines())), (0, 3))

    def test_no_arguments_exits_2(self):
        self.assertEqual(cli().returncode, 2)

    def test_missing_empty_wrong_type_and_truncated_input_exit_2(self):
        good = json.dumps(bundle(storm(20)))
        for name, text in (("empty.json", ""), ("list.json", "[]"), ("str.json", '"x"'), ("trunc.json", good[:len(good) // 2]),
                           ("nan.json", good.replace('"cost_usd": 0.01', '"cost_usd": NaN')), ("deep.json", "[" * 5000)):
            self.assert_input_error(cli("build", self.write(name, text)))
        self.assert_input_error(cli("build", self.path("missing.json")))

    def test_bad_fields_exit_2(self):
        for n, mutate in enumerate((lambda b: b.update(calls="x"), lambda b: b["run"].update(cost_cap_usd="big"),
                                    lambda b: b["calls"][0].update(args=5), lambda b: b.pop("identifier_keys"))):
            b = bundle(storm(20))
            mutate(b)
            self.assert_input_error(cli("build", self.write_bundle("b%d.json" % n, b)))

    def test_no_loop_says_so_and_exits_1(self):
        r = cli("build", self.write_bundle("short.json", bundle(storm(5))))
        self.assertEqual(r.returncode, 1)
        self.assertIn("no draft: no loop in 5 calls", r.stdout)

    def test_build_writes_yaml_and_json_and_lint_reads_them_back(self):
        b = self.write_bundle("b.json", bundle(storm(20)))
        y, j = self.path("d.yaml"), self.path("d.json")
        r = cli("build", b, "--yaml", y, "--json", j, "--reporter", "Team A")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(y, encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("study:\n"))
        r = cli("lint", j, "--bundle", b)
        self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]),
                         (0, "lint: 0 problems; todo fields: actor, references; identifier leaks: 0"))
        self.assertEqual(cli("lint", j, "--strict").returncode, 1)

    def test_lint_exits_1_on_a_schema_problem_and_on_a_leak(self):
        doc = {"study": {"name": "n", "summary": "Customer CUST_123456", "incident-date": "2026-03-01",
                         "incident-date-granularity": "DATE", "procedure": [], "reporter": "r"}}
        j = self.write("bad.json", json.dumps(doc))
        r = cli("lint", j)
        self.assertEqual(r.returncode, 1)
        self.assertIn("problem: study.procedure: no steps", r.stdout)
        doc["study"]["procedure"] = [{"tactic": "AML.TA0011", "technique": "AML.T0029", "description": "d"}]
        j = self.write("leak.json", json.dumps(doc))
        r = cli("lint", j, "--bundle", self.write_bundle("b.json", bundle(storm(20))))
        self.assertEqual(r.returncode, 1)
        self.assertIn("leak: declared identifier values appear in the study, under keys: customer_id", r.stdout)

    def test_lint_input_errors_exit_2(self):
        self.assert_input_error(cli("lint", self.write("l.json", "[]")))
        self.assert_input_error(cli("lint", self.write("e.json", "")))
        ok = self.write("ok.json", json.dumps({"study": {}}))
        self.assert_input_error(cli("lint", ok, "--bundle", self.write("nb.json", "{}")))

    def test_unwritable_output_exits_2(self):
        b = self.write_bundle("b.json", bundle(storm(20)))
        self.assert_input_error(cli("build", b, "--yaml", os.path.join(self.tmp.name, "no", "such", "dir", "d.yaml")))

    def test_hostile_path_is_escaped_on_one_line(self):
        r = cli("build", self.path("a\nb\rc::error::x%0A.json"))
        self.assert_input_error(r)
        self.assertNotIn("\r", r.stderr)

    def test_hostile_strings_stay_inside_one_quoted_value(self):
        clean = bundle(storm(20))
        hostile = bundle([dict(c, tool_name=HOSTILE) for c in storm(20)], role=HOSTILE)
        hostile["run"]["agent_id"] = HOSTILE
        outs = []
        for name, b in (("clean", clean), ("hostile", hostile)):
            y = self.path(name + ".yaml")
            r = cli("build", self.write_bundle(name + ".json", b), "--yaml", y)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(r.stdout.splitlines()), 3)
            with open(y, encoding="utf-8") as fh:
                outs.append(fh.read().splitlines())
        self.assertEqual(len(outs[0]), len(outs[1]))
        for line in outs[1]:
            self.assertRegex(line, LINE)
        self.assertNotIn("\r", "\n".join(outs[1]))

    def test_hostile_strings_in_lint_output_are_escaped(self):
        doc = {"study": {HOSTILE: 1}}
        r = cli("lint", self.write("h.json", json.dumps(doc)))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("\r", r.stdout)
        for line in r.stdout.splitlines():
            self.assertTrue(line.startswith(("problem:", "lint:")), line)


class DataTests(unittest.TestCase):
    def test_generator_reproduces_every_file(self):
        data = os.path.join(SRC, "..", "data")
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, os.path.join(data, "_generate.py")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            for name in ("runs.csv", "tool_calls.csv", "truth.csv", "identifier_keys.json", "example_bundle.json"):
                with open(os.path.join(data, name), "rb") as a, open(os.path.join(tmp, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)

    def test_run_totals_match_the_calls(self):
        data = os.path.join(SRC, "..", "data")
        with open(os.path.join(data, "runs.csv"), newline="", encoding="utf-8") as fh:
            runs = {r["run_id"]: r for r in csv.DictReader(fh)}
        totals, counts = {}, {}
        with open(os.path.join(data, "tool_calls.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                totals[r["run_id"]] = round(totals.get(r["run_id"], 0.0) + float(r["cost_usd"]), 4)
                counts[r["run_id"]] = counts.get(r["run_id"], 0) + 1
        for rid, r in runs.items():
            self.assertEqual((counts[rid], totals[rid]), (int(r["n_calls"]), float(r["total_cost_usd"])), rid)


if __name__ == "__main__":
    unittest.main()
