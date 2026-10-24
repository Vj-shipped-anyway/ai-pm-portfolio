import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import mcp_scope_lint as ml

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
READ = {"readOnlyHint": True}


def sample(tool_name="t", scope_id="a:read", extra_grant=None):
    catalog = [{"id": "a:read", "resource": "a", "access": "read"}, {"id": "a:write", "resource": "a", "access": "write"},
               {"id": "a:*", "resource": "a", "access": "any"}]
    if scope_id not in ("a:read", "a:write", "a:*"):
        catalog.append({"id": scope_id, "resource": "a", "access": "read"})
    return {"server": {"name": "s"}, "scope_catalog": catalog,
            "granted_scopes": ["a:read"] + ([extra_grant] if extra_grant else []),
            "tools": [{"name": tool_name, "requires_scopes": ["a:read"], "annotations": READ}]}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ml.main(args)
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
            fh.write(obj if isinstance(obj, str) else json.dumps(obj))
        return p

    def test_clean_manifest_exits_0(self):
        code, out, _ = run(["lint", os.path.join(DATA, "example_clean.json")])
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)

    def test_error_exits_1_and_warning_alone_does_not(self):
        example = os.path.join(DATA, "example_manifest.json")
        self.assertEqual(run(["lint", example])[0], 1)
        warn_only = sample(extra_grant="a:*")        # a wildcard granted next to the tool's read scope: narrowable, not unused
        path = self.write("w.json", warn_only)
        code, out, _ = run(["lint", path])
        self.assertIn("wildcard_narrowable", out)
        self.assertEqual(code, 0)
        self.assertEqual(run(["lint", path, "--fail-on", "warn"])[0], 1)
        self.assertEqual(run(["lint", example, "--fail-on", "never"])[0], 0)

    def test_propose_prints_the_proposal(self):
        _, out, _ = run(["lint", os.path.join(DATA, "example_manifest.json"), "--propose", "--fail-on", "never"])
        self.assertIn("proposal (least privilege", out)
        self.assertIn("reachable scopes: 9 -> 6", out)

    def test_github_format(self):
        _, out, _ = run(["lint", os.path.join(DATA, "example_manifest.json"), "--format", "github"])
        self.assertTrue(out.startswith("::error title=mcp-scope-lint tool_scope_above_hint::"))
        self.assertIn("::notice title=mcp-scope-lint::", out)

    def test_missing_file_exits_2(self):
        code, out, err = run(["lint", os.path.join(self.dir.name, "nope.json")])
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(err.startswith("input error:"))
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_empty_truncated_and_wrong_type_input_exit_2_with_one_line(self):
        cases = {"empty.json": "", "cut.json": '{"server": {"name": "s"}, "tools": [', "list.json": "[1, 2]",
                 "string.json": '"text"', "object.json": "{}", "tools.json": json.dumps(dict(sample(), tools="x")),
                 "binary.json": "\x00\x01"}
        for name, content in cases.items():
            code, out, err = run(["lint", self.write(name, content)])
            self.assertEqual((code, out), (2, ""), name)
            self.assertEqual(len(err.strip().splitlines()), 1, name)
            self.assertNotIn("Traceback", err)

    def test_deeply_nested_input_exits_2(self):
        path = self.write("deep.json", "[" * 100000)
        self.assertEqual(run(["lint", path])[0], 2)

    def test_non_utf8_file_exits_2(self):
        path = os.path.join(self.dir.name, "latin.json")
        with open(path, "wb") as fh:
            fh.write(b'{"server": {"name": "caf\xe9"}}')
        self.assertEqual(run(["lint", path])[0], 2)

    def test_hostile_tool_name_cannot_forge_a_workflow_command(self):
        hostile = "x\n::error title=forged::approved%0A\r::warning::again"
        obj = sample(tool_name=hostile, extra_grant="a:write")
        obj["tools"][0]["requires_scopes"] = ["a:read", "a:write"]
        path = self.write("h.json", obj)
        _, out, _ = run(["lint", path, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), len(out.splitlines()))            # no line was started by the hostile text
        self.assertEqual(len(commands), 2)                                # the one finding and the notice
        self.assertIn("%0A", commands[0])
        self.assertIn("%250A", commands[0])                               # a literal percent sequence is escaped, not decoded
        self.assertIn("%0D", commands[0])

    def test_hostile_names_cannot_forge_lines_in_text_output_or_errors(self):
        hostile = "x\nresult: 0 errors, 0 warnings\x1b[31m"
        obj = sample(tool_name=hostile, extra_grant="a:write")
        obj["tools"][0]["requires_scopes"] = ["a:read", "a:write"]
        path = self.write("h.json", obj)
        _, out, _ = run(["lint", path, "--propose", "--fail-on", "never"])
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("result:")), 1)
        self.assertNotIn("\x1b", out)
        bad = sample()
        bad["granted_scopes"] = ["no\nsuch\x1b"]
        code, _, err = run(["lint", self.write("b.json", bad)])
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn("\x1b", err)

    def test_demo_runs_and_prints_the_findings(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("result: 2 errors, 2 warnings", out)

    def test_no_arguments_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
