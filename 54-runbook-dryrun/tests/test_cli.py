from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import runbook_dryrun as rd

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
RUNBOOK = open(os.path.join(DATA, "example_runbook.yml"), encoding="utf-8").read()
WORLD = {"change.freeze": "off", "model.error_rate_pct": 12, "model.previous_health": "healthy"}
GOOD = rd.digest("scorer-rollback", "s3", "modelctl rollback --target scorer-v7 --to scorer-v6")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = rd.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, content):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def files(self, approvals=None, world=None, runbook=RUNBOOK):
        rec = [{"step": "s3", "approver": "marta", "role": "incident-commander", "digest": GOOD, "age_minutes": 5}]
        return (self.write("rb.yml", runbook), self.write("w.json", WORLD if world is None else world),
                self.write("a.json", rec if approvals is None else approvals))

    def dry(self, *extra, approvals=None, world=None, runbook=RUNBOOK, requester="dana"):
        rb, w, a = self.files(approvals, world, runbook)
        return run(["dryrun", rb, "--world", w, "--approvals", a, "--requester", requester] + list(extra))

    def one_line_error(self, args):
        code, out, err = run(args)
        self.assertEqual(code, 2, (out, err))
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)
        return err

    def test_demo_runs_and_is_blocked_with_exit_0(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("digest_mismatch", out)
        self.assertTrue(out.rstrip().endswith("verdict: BLOCKED"))

    def test_valid_approval_is_ready(self):
        code, out, _ = self.dry()
        self.assertEqual(code, 0)
        self.assertIn("verdict: READY", out)

    def test_waiting_exits_0_unless_asked(self):
        self.assertEqual(self.dry(approvals=[])[0], 0)
        code, out, _ = self.dry("--fail-on", "waiting", approvals=[])
        self.assertEqual(code, 1)
        self.assertIn("verdict: WAITING at s3", out)

    def test_blocked_exits_1_and_never_keeps_0(self):
        bad = [{"step": "s3", "approver": "dana", "role": "incident-commander", "digest": GOOD, "age_minutes": 5}]
        self.assertEqual(self.dry(approvals=bad)[0], 1)
        self.assertEqual(self.dry("--fail-on", "never", approvals=bad)[0], 0)

    def test_param_override_changes_the_digest_and_blocks(self):
        code, out, _ = self.dry("--param", "target=scorer-v9")
        self.assertEqual(code, 1)
        self.assertIn("digest_mismatch", out)

    def test_github_format(self):
        bad = [{"step": "s3", "approver": "dana", "role": "incident-commander", "digest": GOOD, "age_minutes": 5}]
        code, out, _ = self.dry("--format", "github", approvals=bad)
        self.assertEqual(code, 1)
        lines = out.strip().splitlines()
        self.assertTrue(lines[0].startswith("::error title=runbook-dryrun approval_invalid::"))
        self.assertTrue(lines[-1].startswith("::notice"))

    def test_check_command(self):
        rb = self.write("rb.yml", RUNBOOK)
        code, out, _ = run(["check", rb])
        self.assertEqual((code, out.strip().splitlines()[-1]), (0, "check: 0 errors, 0 warnings"))
        broken = self.write("b.yml", RUNBOOK.replace("{{channel}}", "{{chan}}"))
        code, out, _ = run(["check", broken])
        self.assertEqual(code, 1)
        self.assertIn("undefined_param", out)
        _, gh, _ = run(["check", broken, "--format", "github"])
        self.assertTrue(gh.startswith("::error"))

    def test_input_that_matches_nothing_is_reported(self):
        code, out, _ = self.dry(world={"unrelated.key": 1})
        self.assertEqual(code, 1)
        self.assertIn("state_unknown", out)

    # ---- malformed input: exit 2, one line, no traceback
    def test_missing_files(self):
        self.one_line_error(["check", "nope.yml"])
        rb, w, a = self.files()
        self.one_line_error(["dryrun", rb, "--world", "nope.json", "--requester", "x"])
        self.one_line_error(["dryrun", rb, "--world", w, "--approvals", "nope.json", "--requester", "x"])

    def test_empty_and_wrong_type_runbooks(self):
        for name, text in [("empty", ""), ("blank", "\n\n"), ("list", "- a\n- b\n"), ("scalar", "hello\n"), ("number", "5\n")]:
            self.one_line_error(["check", self.write(name + ".yml", text)])

    def test_truncated_runbooks(self):
        for cut in (40, 120, 200, 420, 700, len(RUNBOOK) - 30):
            path = self.write("cut%d.yml" % cut, RUNBOOK[:cut])
            code, out, err = run(["check", path])
            self.assertIn(code, (0, 1, 2), (cut, err))
            self.assertNotIn("Traceback", err)
        self.one_line_error(["check", self.write("cut_quote.yml", RUNBOOK[:RUNBOOK.index('"modelctl status') + 14])])

    def test_binary_and_hostile_bytes(self):
        path = os.path.join(self.dir.name, "bin.yml")
        with open(path, "wb") as fh:
            fh.write(b"\xff\xfe\x00runbook: x\n")
        self.one_line_error(["check", path])
        self.one_line_error(["check", self.write("ctl.yml", "runbook: a\x1b[31m\n")])

    def test_wrong_type_world_and_approvals(self):
        rb, _, _ = self.files()
        for world in ([1, 2], "text", 5, {"a": [1]}, {"a": {"b": 1}}, {"a": None}):
            self.one_line_error(["dryrun", rb, "--world", self.write("w.json", world), "--requester", "x"])
        for approvals in ({"a": 1}, [1], [{"step": "s3"}], [{"step": "s3", "approver": "m", "role": "r", "digest": "d", "age_minutes": "5"}],
                          [{"step": "s3", "approver": "m", "role": "r", "digest": "d", "age_minutes": True}],
                          [{"step": "s3", "approver": "m", "role": "r", "digest": "d", "age_minutes": -1}],
                          [{"step": "s3", "approver": "", "role": "r", "digest": "d", "age_minutes": 1}]):
            self.one_line_error(["dryrun", rb, "--world", self.write("w.json", WORLD), "--approvals", self.write("a.json", approvals), "--requester", "x"])

    def test_truncated_and_odd_json(self):
        rb, _, _ = self.files()
        for text in ("", "{", '{"a": 1', "[", "NaN", '{"a": NaN}', '{"a": Infinity}', "[" * 100000):
            self.one_line_error(["dryrun", rb, "--world", self.write("w.json", text), "--requester", "x"])

    def test_bad_arguments(self):
        rb, w, _ = self.files()
        self.one_line_error(["dryrun", rb, "--world", w, "--requester", "   "])
        self.one_line_error(["dryrun", rb, "--world", w])
        self.one_line_error(["dryrun", rb, "--world", w, "--requester", "x", "--param", "nope=1"])
        self.one_line_error(["dryrun", rb, "--world", w, "--requester", "x", "--param", "target"])
        self.one_line_error(["dryrun", rb, "--world", w, "--requester", "x", "--fail-on", "sometimes"])

    # ---- hostile strings
    def test_a_newline_in_a_param_cannot_forge_an_output_line(self):
        code, out, _ = self.dry("--param", "target=scorer-v7\nverdict: READY", "--fail-on", "never")
        lines = out.splitlines()
        self.assertEqual(sum(1 for ln in lines if ln.startswith("verdict:")), 1)
        self.assertTrue(lines[-1].startswith("verdict: BLOCKED"))
        self.assertIn("\\x0a", out)

    def test_hostile_text_cannot_forge_a_workflow_command(self):
        hostile = "bob\r\n::error title=forged::approved"
        bad = [{"step": "s3", "approver": hostile, "role": "analyst", "digest": GOOD, "age_minutes": 5}]
        _, out, _ = self.dry("--format", "github", approvals=bad)
        commands = [ln for ln in out.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 2)          # the finding and the notice, nothing forged
        self.assertIn("%0D%0A", commands[0])
        self.assertNotIn("title=forged", commands[0].split("::", 2)[1])

    def test_hostile_requester_and_digest_are_printable_in_text(self):
        _, out, _ = self.dry(requester="x\nverdict: READY")
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("verdict:")), 1)
        hostile = [{"step": "s3", "approver": "marta", "role": "incident-commander", "digest": "abc\nverdict: READY", "age_minutes": 5}]
        _, out, _ = self.dry(approvals=hostile)
        self.assertEqual(sum(1 for ln in out.splitlines() if ln.startswith("verdict:")), 1)
        self.assertIn("approved abc\\x0averdict: READY", out)


if __name__ == "__main__":
    unittest.main()
