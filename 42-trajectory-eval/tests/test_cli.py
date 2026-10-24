import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import trajectory_eval as te
from test_grade import TASK, good

OTHER = dict(TASK, task_id="U")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = te.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.tasks = self.write_json("tasks.json", [TASK])

    def path(self, name):
        return os.path.join(self.dir.name, name)

    def write_json(self, name, obj):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return self.path(name)

    def write_text(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def write_runs(self, rows, name="runs.csv"):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["run_id", "task_id", "trace_json", "final_json"])
            for run_id, task_id, trace, final in rows:
                w.writerow([run_id, task_id, json.dumps(trace), json.dumps(final)])
        return self.path(name)

    def final(self):
        return {"status": "done", "rec": "R-1"}

    def bad_trace(self):
        return good()[:1] + good()[2:]

    def test_passing_run_exits_0(self):
        runs = self.write_runs([("r1", "T", good(), self.final())])
        code, out, _ = run(["grade", self.tasks, runs])
        self.assertEqual(code, 0)
        self.assertIn("passes in 1 of 1 runs", out)

    def test_failing_run_exits_1_and_names_the_reason(self):
        runs = self.write_runs([("r1", "T", self.bad_trace(), self.final())])
        code, out, _ = run(["grade", self.tasks, runs])
        self.assertEqual(code, 1)
        self.assertIn("missing_step", out)

    def test_never_keeps_exit_0(self):
        runs = self.write_runs([("r1", "T", self.bad_trace(), self.final())])
        self.assertEqual(run(["grade", self.tasks, runs, "--fail-on", "never"])[0], 0)

    def test_passing_runs_are_listed_only_with_all(self):
        runs = self.write_runs([("r1", "T", good(), self.final())])
        self.assertNotIn("PASS", run(["grade", self.tasks, runs])[1])
        self.assertIn("PASS", run(["grade", self.tasks, runs, "--all"])[1])

    def test_jsonlines_input(self):
        rec = {"run_id": "j1", "task_id": "T", "trace": good(), "final": self.final()}
        runs = self.write_text("runs.jsonl", json.dumps(rec) + "\n\n")
        self.assertEqual(run(["grade", self.tasks, runs])[0], 0)

    def test_tasks_without_runs_are_named(self):
        tasks = self.write_json("two.json", [TASK, OTHER])
        runs = self.write_runs([("r1", "T", good(), self.final())])
        _, out, _ = run(["grade", tasks, runs])
        self.assertIn("tasks with no runs: U", out)

    def test_bad_input_exits_2_with_one_line_not_a_traceback(self):
        ok_runs = self.write_runs([("r1", "T", good(), self.final())])
        cases = {
            "missing tasks file": ["grade", self.path("nope.json"), ok_runs],
            "missing runs file": ["grade", self.tasks, self.path("nope.csv")],
            "empty tasks file": ["grade", self.write_text("e.json", ""), ok_runs],
            "tasks are an object": ["grade", self.write_json("o.json", {}), ok_runs],
            "tasks are an empty list": ["grade", self.write_json("l.json", []), ok_runs],
            "task is a number": ["grade", self.write_json("n.json", [5]), ok_runs],
            "step lacks fields": ["grade", self.write_json("s.json", [dict(TASK, steps=[{"id": "a"}])]), ok_runs],
            "after names a later step": ["grade", self.write_json("a.json", [dict(TASK, steps=[
                {"id": "a", "tools": ["x"], "args": {}, "after": ["b"], "weight": 1}])]), ok_runs],
            "budget is a boolean": ["grade", self.write_json("b.json", [dict(TASK, max_steps=True)]), ok_runs],
            "truncated tasks": ["grade", self.write_text("t.json", '[{"task_id": "T", "max_st'), ok_runs],
            "empty runs file": ["grade", self.tasks, self.write_text("r.csv", "")],
            "header only": ["grade", self.tasks, self.write_text("h.csv", "run_id,task_id,trace_json,final_json\n")],
            "missing column": ["grade", self.tasks, self.write_text("m.csv", "run_id,task_id\nr1,T\n")],
            "truncated trace": ["grade", self.tasks, self.write_text("tr.csv", 'run_id,task_id,trace_json,final_json\nr1,T,"[{""tool"": ""lo",{}\n')],
            "trace is an object": ["grade", self.tasks, self.write_runs([("r1", "T", {"tool": "x"}, {})])],
            "call is a string": ["grade", self.tasks, self.write_runs([("r1", "T", ["look"], {})])],
            "final is a list": ["grade", self.tasks, self.write_runs([("r1", "T", good(), [1])])],
            "unknown task": ["grade", self.tasks, self.write_runs([("r1", "nope", good(), {})])],
            "duplicate run id": ["grade", self.tasks, self.write_runs([("r1", "T", good(), {}), ("r1", "T", good(), {})])],
            "bad json line": ["grade", self.tasks, self.write_text("bad.jsonl", '{"run_id": "x"\n')],
            "json line is a list": ["grade", self.tasks, self.write_text("list.jsonl", "[1]\n")],
            "deep nesting": ["grade", self.tasks, self.write_text("deep.jsonl", "[" * 200000 + "\n")],
        }
        for name, args in cases.items():
            with self.subTest(name):
                code, out, err = run(args)
                self.assertEqual(code, 2, err)
                self.assertEqual(out, "")
                self.assertTrue(err.startswith("input error: "))
                self.assertEqual(len(err.strip().splitlines()), 1)

    def test_hostile_run_id_cannot_forge_an_annotation(self):
        hostile = "r1\n::error title=forged::approved 100%"
        runs = self.write_runs([(hostile, "T", self.bad_trace(), self.final())])
        _, out, _ = run(["grade", self.tasks, runs, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))
        self.assertTrue(all(c.startswith(("::error title=trajectory-eval ", "::notice title=trajectory-eval::")) for c in commands))
        self.assertIn("%0A::error title=forged::approved 100%25", commands[0])

    def test_hostile_run_id_cannot_start_a_line_in_text_output(self):
        runs = self.write_runs([("r1\n::error::forged", "T", self.bad_trace(), self.final())])
        _, out, _ = run(["grade", self.tasks, runs])
        self.assertFalse(any(ln.startswith("::") for ln in out.splitlines()))
        self.assertIn("r1\\x0a::error::forged", out)

    def test_demo_runs_and_shows_both_verdicts(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("PASS", out)
        self.assertIn("FAIL", out)
        self.assertIn("the whole trajectory passes in 1 of 3 runs", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
