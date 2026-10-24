import contextlib
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import evidence_gate as eg

TIERS = "evidence_id,evidence_item,first_tier,max_age_days\nE01,card,1,365\nE02,eval,2,90\n"
REGISTRY = "use_case_id,tier\nUC-1,2\n"
GOOD = ("Use case: UC-1\nDeclared tier: 2\n- [x] E01 card | ref: ev/a.md | date: 2026-09-01\n"
        "- [x] E02 eval | ref: ev/b.md | date: 2026-09-01\n")


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = eg.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.tiers = self.write("tiers.csv", TIERS)
        self.registry = self.write("registry.csv", REGISTRY)
        self.files = self.write("files.txt", "ev/a.md\nev/b.md\n")

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return p

    def check(self, body, *extra, tiers=None):
        p = self.write("body.md", body)
        return run(["check", "--body", p, "--tiers", tiers or self.tiers, "--as-of", "2026-10-16", *extra])

    def test_complete_description_exits_0(self):
        code, out, _ = self.check(GOOD, "--registry", self.registry, "--files", self.files)
        self.assertEqual(code, 0)
        self.assertIn("decision: ALLOW", out)

    def test_missing_evidence_exits_1(self):
        code, out, _ = self.check("Use case: UC-1\nDeclared tier: 2\n", "--registry", self.registry)
        self.assertEqual(code, 1)
        self.assertIn("E01, E02 are required at tier 2 and not in the record", out)

    def test_fail_on_levels(self):
        body = GOOD.replace("Declared tier: 2", "Declared tier: 1")
        args = ("--registry", self.registry, "--files", self.files)
        self.assertEqual(self.check(body, *args)[0], 0)
        self.assertEqual(self.check(body, *args, "--fail-on", "review")[0], 1)
        self.assertEqual(self.check("nothing", *args, "--fail-on", "never")[0], 0)

    def test_empty_description_is_a_finding_not_a_crash(self):
        code, out, err = self.check("")
        self.assertEqual((code, err), (1, ""))
        self.assertIn("no_record", out)

    def test_omitted_inputs_are_said_aloud(self):
        _, out, _ = self.check(GOOD)
        self.assertIn("note: reference files were not checked", out)
        self.assertIn("tier_unverified", out)

    def test_default_as_of_is_today(self):
        old = GOOD.replace("2026-09-01", "2000-01-01")
        code, out, _ = run(["check", "--body", self.write("b.md", old), "--tiers", self.tiers])
        self.assertEqual(code, 1)
        self.assertIn("stale", out)

    def test_event_file(self):
        def event(pr):
            return self.write("event.json", json.dumps(pr))
        code, out, _ = run(["check", "--event", event({"pull_request": {"body": GOOD}}), "--tiers", self.tiers, "--as-of", "2026-10-16"])
        self.assertEqual(code, 0, out)
        code, out, _ = run(["check", "--event", event({"pull_request": {"body": None}}), "--tiers", self.tiers])
        self.assertEqual(code, 1)
        self.assertIn("no_record", out)

    def test_bad_event_files_exit_2(self):
        for name, text in (("empty", ""), ("truncated", '{"pull_request": {"bo'), ("list", "[1, 2]"), ("no_pr", "{}"),
                           ("no_body", '{"pull_request": {}}'), ("body_number", '{"pull_request": {"body": 5}}'),
                           ("deep", "[" * 100000)):
            code, _, err = run(["check", "--event", self.write(name + ".json", text), "--tiers", self.tiers])
            self.assertEqual(code, 2, name)
            self.assertTrue(err.startswith("input error: ") and err.count("\n") == 1, (name, err))

    def test_bad_tier_tables_exit_2(self):
        bad = {"empty": "", "header_only": "evidence_id,evidence_item,first_tier,max_age_days\n",
               "wrong_columns": "id,name\nE01,card\n", "tier_text": TIERS.replace("E01,card,1,365", "E01,card,one,365"),
               "tier_5": TIERS.replace("E01,card,1,365", "E01,card,5,365"), "zero_age": TIERS.replace("365", "0"),
               "bad_id": TIERS.replace("E01", "X1"), "dup_id": TIERS + "E01,again,1,30\n",
               "truncated_row": TIERS + "E03,sign\n", "nul": TIERS + "E03,si\x00gn,3,30\n", "no_name": TIERS.replace("card", "")}
        for name, text in bad.items():
            code, _, err = self.check(GOOD, tiers=self.write(name + ".csv", text))
            self.assertEqual(code, 2, name)
            self.assertTrue(err.startswith("input error: ") and err.count("\n") == 1, (name, err))

    def test_bad_registry_and_files_exit_2(self):
        for name, text in (("empty", ""), ("no_tier", "use_case_id,tier\nUC-1,\n"), ("conflict", REGISTRY + "UC-1,3\n"),
                           ("truncated", "use_case_id,tier\nUC-1")):
            self.assertEqual(self.check(GOOD, "--registry", self.write(name + ".csv", text))[0], 2, name)
        self.assertEqual(self.check(GOOD, "--files", self.write("blank.txt", "\n  \n"))[0], 2)
        self.assertEqual(self.check(GOOD, "--files", os.path.join(self.dir.name, "missing.txt"))[0], 2)

    def test_bad_arguments_exit_2(self):
        self.assertEqual(self.check(GOOD, "--as-of", "yesterday")[0], 2)
        self.assertEqual(run(["check", "--body", "nope.md", "--tiers", self.tiers])[0], 2)
        self.assertEqual(run(["check", "--tiers", self.tiers])[0], 2)
        self.assertEqual(run(["check", "--body", "a", "--event", "b", "--tiers", self.tiers])[0], 2)
        self.assertEqual(run([])[0], 2)

    def test_non_utf8_description_exits_2(self):
        p = os.path.join(self.dir.name, "latin.md")
        with open(p, "wb") as fh:
            fh.write(b"Use case: UC-1\n\xff\xfe")
        self.assertEqual(run(["check", "--body", p, "--tiers", self.tiers])[0], 2)

    def test_hostile_text_cannot_forge_a_workflow_command(self):
        body = ("Use case: UC-1 %0A::error title=forged::approved ::error title=forged2::ok\nDeclared tier: 2\r\n"
                "- [x] E01 card | ref: ev/%0D\x1b[31m::error::x | date: \u0000\n::error title=forged3::at line start\n")
        for fmt in ("github", "text"):
            _, out, _ = self.check(body, "--format", fmt)
            for line in out.splitlines():
                if fmt == "github":
                    self.assertTrue(line.startswith(("::error title=evidence-gate ", "::warning title=evidence-gate ", "::notice title=evidence-gate::")), line)
                else:
                    self.assertTrue(line.startswith(("use case ", "  [", "  note: ", "decision: ")), line)
                self.assertNotIn("\r", line)
        _, out, _ = self.check(body, "--format", "github")
        self.assertIn("%250A", out)

    def test_demo_runs(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("decision: BLOCK", out)
        self.assertIn("tier_mismatch", out)


if __name__ == "__main__":
    unittest.main()
