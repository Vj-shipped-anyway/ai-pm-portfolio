import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import tool_schema_drift as tsd

OLD = {"name": "t", "version": "1.0.0", "description": "d", "parameters": {"required": ["a"], "properties": {
    "a": {"type": "string", "description": "x", "enum": ["p", "q"]}}}}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = tsd.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, obj):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return p

    def pair(self, enum):
        new = json.loads(json.dumps(OLD))
        new["parameters"]["properties"]["a"]["enum"] = enum
        return self.write("old.json", OLD), self.write("new.json", new)

    def test_breaking_change_exits_1(self):
        o, n = self.pair(["p"])
        code, out, _ = run(["check", o, n])
        self.assertEqual(code, 1)
        self.assertIn("decision: BLOCK", out)

    def test_harmless_change_exits_0(self):
        o, n = self.pair(["p", "q", "r"])
        code, out, _ = run(["check", o, n])
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)

    def test_never_keeps_exit_0(self):
        o, n = self.pair(["p"])
        self.assertEqual(run(["check", o, n, "--fail-on", "never"])[0], 0)

    def test_github_format_emits_error_annotation(self):
        o, n = self.pair(["p"])
        _, out, _ = run(["check", o, n, "--format", "github"])
        self.assertTrue(out.startswith("::error"))

    def test_replay_failures_force_block(self):
        o, n = self.pair(["p", "q", "r"])
        calls = os.path.join(self.dir.name, "c.csv")
        with open(calls, "w", encoding="utf-8") as fh:
            fh.write('call_id,tool,args_json\n1,t,"{""a"": ""zzz""}"\n')
        code, out, _ = run(["check", o, n, "--calls", calls])
        self.assertEqual(code, 1)
        self.assertIn("1 of 1 recorded calls fail", out)

    def test_missing_file_exits_2(self):
        self.assertEqual(run(["check", "nope.json", "nope2.json"])[0], 2)

    def test_malformed_schema_exits_2_not_1(self):
        # exit 1 means BLOCK; a crash on bad input must not look like one
        empty = self.write("empty.json", {})
        as_list = self.write("list.json", [1, 2])
        self.assertEqual(run(["check", empty, empty])[0], 2)
        self.assertEqual(run(["check", as_list, as_list])[0], 2)
        bad_spec = self.write("bad.json", {"parameters": {"properties": {"a": 5}}})
        self.assertEqual(run(["check", bad_spec, bad_spec])[0], 2)

    def test_hostile_parameter_name_cannot_forge_an_annotation(self):
        new = json.loads(json.dumps(OLD))
        new["parameters"]["properties"] = {"b\n::error title=forged::approved": {"type": "string", "description": "x"}}
        o, n = self.write("old.json", OLD), self.write("new.json", new)
        _, out, _ = run(["check", o, n, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 2)          # the finding and the notice, nothing forged
        self.assertNotIn("title=forged", "\n".join(commands[:1]).split("::", 2)[1])
        self.assertIn("%0A", commands[0])

    def test_calls_file_with_no_rows_for_the_tool_says_so(self):
        o, n = self.pair(["p", "q", "r"])
        calls = os.path.join(self.dir.name, "other.csv")
        with open(calls, "w", encoding="utf-8") as fh:
            fh.write('call_id,tool,args_json\n1,other_tool,"{}"\n')
        _, out, _ = run(["check", o, n, "--calls", calls])
        self.assertIn("nothing was replayed", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)


if __name__ == "__main__":
    unittest.main()
