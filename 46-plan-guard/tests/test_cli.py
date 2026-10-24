import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import plan_guard as pg

BAD_VOLUME = {"address": "aws_ebs_volume.v", "mode": "managed", "type": "aws_ebs_volume", "name": "v",
              "change": {"actions": ["create"], "before": None, "after": {"encrypted": False}, "after_unknown": {}}}
LISTENER = {"address": "aws_lb_listener.l", "mode": "managed", "type": "aws_lb_listener", "name": "l",
            "change": {"actions": ["create"], "before": None, "after": {"protocol": "HTTP", "default_action": [{"type": "forward"}]},
                       "after_unknown": {}}}
GOOD_VOLUME = {"address": "aws_ebs_volume.g", "mode": "managed", "type": "aws_ebs_volume", "name": "g",
               "change": {"actions": ["create"], "before": None, "after": {"encrypted": True}, "after_unknown": {}}}


def plan(*rcs):
    return {"format_version": "1.2", "resource_changes": list(rcs)}


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = pg.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, obj, name="plan.json"):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return p

    def write_text(self, text, name="raw.json", mode="w"):
        p = os.path.join(self.dir.name, name)
        with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(text)
        return p

    def test_block_exits_1(self):
        code, out, _ = run(["check", self.write(plan(BAD_VOLUME))])
        self.assertEqual(code, 1)
        self.assertIn("decision: BLOCK", out)

    def test_clean_plan_exits_0(self):
        code, out, _ = run(["check", self.write(plan(GOOD_VOLUME))])
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)
        self.assertIn("no finding in 1 checked resource changes", out)

    def test_fail_on_levels(self):
        p = self.write(plan(LISTENER))
        self.assertEqual(run(["check", p])[0], 0)
        self.assertEqual(run(["check", p, "--fail-on", "review"])[0], 1)
        self.assertEqual(run(["check", self.write(plan(BAD_VOLUME)), "--fail-on", "never"])[0], 0)

    def test_github_format(self):
        _, out, _ = run(["check", self.write(plan(BAD_VOLUME, LISTENER)), "--format", "github"])
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("::error title=plan-guard PG06::"))
        self.assertTrue(lines[1].startswith("::warning title=plan-guard PG10::"))
        self.assertTrue(lines[2].startswith("::notice title=plan-guard::decision BLOCK; 2 of 2"))

    def test_malformed_input_exits_2_with_one_line(self):
        cases = {
            "empty": "", "truncated": '{"format_version": "1.2", "resource_changes": [{"address"',
            "list": "[1, 2]", "no_version": "{}", "major_2": '{"format_version": "2.0"}',
            "version_type": '{"format_version": 1.2}', "changes_type": '{"format_version": "1.2", "resource_changes": {}}',
            "entry_type": '{"format_version": "1.2", "resource_changes": [5]}',
            "no_change": '{"format_version": "1.2", "resource_changes": [{"address": "a", "type": "t"}]}',
            "actions_type": '{"format_version": "1.2", "resource_changes": [{"address": "a", "type": "t", "change": {"actions": "create"}}]}',
            "after_type": '{"format_version": "1.2", "resource_changes": [{"address": "a", "type": "t", "change": {"actions": ["create"], "after": "x"}}]}',
            "unknown_type": '{"format_version": "1.2", "resource_changes": [{"address": "a", "type": "t", "change": {"actions": [], "after_unknown": []}}]}',
            "address_type": '{"format_version": "1.2", "resource_changes": [{"address": 7, "type": "t", "change": {"actions": []}}]}',
            "deep": '{"format_version": "1.2", "resource_changes": [], "x": ' + "[" * 100000 + "]" * 100000 + "}",
        }
        for label, text in cases.items():
            code, out, err = run(["check", self.write_text(text)])
            self.assertEqual(code, 2, label)
            self.assertEqual(out, "", label)
            self.assertTrue(err.startswith("input error:") and err.count("\n") == 1, f"{label}: {err!r}")

    def test_deeply_nested_after_unknown_never_shows_a_traceback(self):
        for depth in (3000, 900):
            nested = '{"a": ' * depth + "true" + "}" * depth
            text = ('{"format_version": "1.2", "resource_changes": [{"address": "a", "type": "aws_ebs_volume", "change": '
                    '{"actions": ["create"], "after": {}, "after_unknown": {"encrypted": ' + nested + "}}}]}")
            code, _, err = run(["check", self.write_text(text)])
            self.assertNotIn("Traceback", err)
            self.assertIn(code, (0, 1, 2))
            if depth == 3000:
                self.assertEqual(code, 2)

    def test_missing_file_directory_and_bad_bytes_exit_2(self):
        self.assertEqual(run(["check", os.path.join(self.dir.name, "nope.json")])[0], 2)
        self.assertEqual(run(["check", self.dir.name])[0], 2)
        self.assertEqual(run(["check", self.write_text(b"\xff\xfe\x00\x80", mode="wb")])[0], 2)

    def test_no_resource_changes_says_nothing_was_checked(self):
        code, out, _ = run(["check", self.write({"format_version": "1.2"})])
        self.assertEqual(code, 0)
        self.assertIn("the plan has no resource changes; nothing was checked", out)

    def test_nothing_matches_says_so(self):
        vpc = dict(GOOD_VOLUME, type="aws_vpc", address="aws_vpc.v")
        deleted = dict(BAD_VOLUME, change=dict(BAD_VOLUME["change"], actions=["delete"]))
        code, out, _ = run(["check", self.write(plan(vpc, deleted))])
        self.assertEqual(code, 0)                     # REVIEW does not fail the step unless --fail-on review
        self.assertIn("1 of the 2 resource changes create or update a type that has no rule; nothing was checked", out)
        self.assertIn("PG00 nothing_checked", out)
        self.assertTrue(out.rstrip().endswith("decision: REVIEW"))
        self.assertEqual(run(["check", self.write(plan(vpc, deleted)), "--fail-on", "review"])[0], 1)
        _, gh, _ = run(["check", self.write(plan(vpc)), "--format", "github"])
        self.assertIn("nothing was checked", gh)
        self.assertIn("::warning title=plan-guard PG00::", gh)

    def test_only_deletes_and_no_ops_need_no_check_and_are_allowed(self):
        deleted = dict(BAD_VOLUME, change=dict(BAD_VOLUME["change"], actions=["delete"]))
        noop = dict(GOOD_VOLUME, change=dict(GOOD_VOLUME["change"], actions=["no-op"]))
        code, out, _ = run(["check", self.write(plan(deleted, noop)), "--fail-on", "review"])
        self.assertEqual(code, 0)
        self.assertIn("nothing was checked and nothing needed checking", out)
        self.assertTrue(out.rstrip().endswith("decision: ALLOW"))

    def test_a_plan_with_one_read_resource_and_one_unruled_is_not_pg00(self):
        vpc = dict(GOOD_VOLUME, type="aws_vpc", address="aws_vpc.v")
        _, out, _ = run(["check", self.write(plan(vpc, GOOD_VOLUME))])
        self.assertNotIn("PG00", out)
        self.assertTrue(out.rstrip().endswith("decision: ALLOW"))

    def test_hostile_address_cannot_forge_a_line_or_command(self):
        evil = dict(BAD_VOLUME, address="aws_ebs_volume.v\n::error title=forged::approved\r::notice::ok")
        p = self.write(plan(evil))
        _, text, _ = run(["check", p, "--fail-on", "never"])
        for line in text.splitlines():
            self.assertTrue(line.startswith(("plan:", "  [", "decision:")), line)
        self.assertIn("\\n::error title=forged", text)
        _, gh, _ = run(["check", p, "--format", "github", "--fail-on", "never"])
        commands = [ln for ln in gh.splitlines() if ln.startswith("::")]
        self.assertEqual(len(gh.splitlines()), 2)
        self.assertEqual(len(commands), 2)
        self.assertIn("%0A", commands[0])
        self.assertIn("%0D", commands[0])

    def test_hostile_attribute_value_is_not_echoed_raw(self):
        evil = dict(BAD_VOLUME, change=dict(BAD_VOLUME["change"], after={"encrypted": "no\n::error::x\x1b[31m"}))
        _, text, _ = run(["check", self.write(plan(evil)), "--fail-on", "never"])
        self.assertNotIn("\x1b", text)
        self.assertEqual([ln for ln in text.splitlines() if ln.startswith("::")], [])

    def test_hostile_file_name_is_not_echoed_raw(self):
        p = self.write(plan(GOOD_VOLUME), name="a\nb::error::c.json")
        _, text, _ = run(["check", p])
        self.assertEqual([ln for ln in text.splitlines() if ln.startswith("::")], [])

    def test_escape_helpers(self):
        self.assertEqual(pg.escape_annotation("a%b\r\nc"), "a%25b%0D%0Ac")
        self.assertEqual(pg.visible("a\x1b[0m b"), "a\\x1b[0m\\u2028b")

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)
        self.assertIn("7 resource changes, 5 checked", out)

    def test_no_arguments_prints_help_and_exits_2(self):
        self.assertEqual(run([])[0], 2)


if __name__ == "__main__":
    unittest.main()
