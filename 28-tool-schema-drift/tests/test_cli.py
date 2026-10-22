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

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)


if __name__ == "__main__":
    unittest.main()
