import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

import _bootstrap  # noqa: F401
import inventory_check as ic
from _fixtures import rec

AS_OF = "2026-09-30"
USAGE_HEAD = "system_id,model_id,first_seen,last_seen,calls\n"


def run(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ic.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, text):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def inventory(self, records, name="inv.json"):
        return self.write(name, json.dumps(records))

    def usage(self, body, name="use.csv"):
        return self.write(name, USAGE_HEAD + body)

    def usage_rows(self, rows, name="rows.csv"):
        p = os.path.join(self.dir.name, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["system_id", "model_id", "first_seen", "last_seen", "calls"])
            w.writerows(rows)
        return p

    def check(self, path, *extra):
        return run(["check", path, "--as-of", AS_OF] + list(extra))

    def assert_input_error(self, result):
        code, out, err = result
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertTrue(err.startswith("input error: "))
        self.assertNotIn("Traceback", err)

    # ------------------------------------------------------------ decisions and exit codes
    def test_fail_finding_exits_1(self):
        code, out, _ = self.check(self.inventory([rec(business_owner="TBD")]))
        self.assertEqual(code, 1)
        self.assertIn("decision: FAIL (1 fail, 0 review)", out)

    def test_clean_inventory_exits_0_and_says_there_is_nothing(self):
        code, out, _ = self.check(self.inventory([rec()]), "--usage", self.usage("AI-1,vendor-a-large-2026-03,2026-06-01,2026-09-29,10\n"))
        self.assertEqual(code, 0)
        self.assertIn("no findings", out)
        self.assertIn("decision: PASS", out)

    def test_review_only_exits_0_by_default_and_1_with_fail_on_review(self):
        path = self.inventory([rec(last_reviewed="2025-01-01")])
        self.assertEqual(self.check(path)[0], 0)
        code, out, _ = self.check(path, "--fail-on", "review")
        self.assertEqual(code, 1)
        self.assertIn("decision: REVIEW", out)

    def test_never_keeps_exit_0(self):
        self.assertEqual(self.check(self.inventory([rec(business_owner="TBD")]), "--fail-on", "never")[0], 0)

    def test_missing_usage_file_is_stated_in_the_output(self):
        _, out, _ = self.check(self.inventory([rec()]))
        self.assertIn("note: no usage file was given", out)
        self.assertIn("no usage file", out.splitlines()[0])

    def test_usage_that_matches_nothing_says_so(self):
        _, out, _ = self.check(self.inventory([rec()]), "--usage", self.usage("OTHER,m,2026-06-01,2026-09-29,10\n"))
        self.assertIn("no usage row matches an inventory system_id", out)

    def test_github_format_uses_annotations(self):
        path = self.inventory([rec(business_owner="TBD", last_reviewed="2025-01-01")])
        _, out, _ = self.check(path, "--format", "github")
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("::error title=inventory-check placeholder_value::"))
        self.assertTrue(any(ln.startswith("::warning title=inventory-check review_overdue::") for ln in lines))
        self.assertTrue(lines[-1].startswith("::notice title=inventory-check::decision FAIL"))

    def test_demo_runs_and_names_each_kind_of_finding(self):
        code, out, _ = run(["--demo"])
        self.assertEqual(code, 0)
        for kind in ("agent_field_missing", "review_overdue", "model_changed", "placeholder_value", "unregistered_system"):
            self.assertIn(kind, out)
        self.assertIn("decision: FAIL (3 fail, 2 review)", out)

    def test_demo_as_of_matches_the_data_files(self):
        with open(os.path.join(os.path.dirname(os.path.abspath(ic.__file__)), "..", "data", "as_of.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), ic.DEMO_AS_OF)

    # ------------------------------------------------------------ malformed input exits 2 with one line
    def test_missing_files_exit_2(self):
        self.assert_input_error(self.check(os.path.join(self.dir.name, "nope.json")))
        self.assert_input_error(self.check(self.inventory([rec()]), "--usage", os.path.join(self.dir.name, "nope.csv")))

    def test_empty_and_wrong_type_inventories_exit_2(self):
        for name, text in (("empty.json", ""), ("blank.json", "   "), ("none.json", "[]"), ("dict.json", "{}"), ("num.json", "7"),
                           ("str.json", '"abc"'), ("null.json", "null"), ("items.json", "[1, 2]"), ("mixed.json", '[{"system_id": "a"}, null]')):
            with self.subTest(name=name):
                self.assert_input_error(self.check(self.write(name, text)))

    def test_truncated_and_binary_inventories_exit_2(self):
        good = json.dumps([rec()])
        self.assert_input_error(self.check(self.write("cut.json", good[: len(good) // 2])))
        bin_path = os.path.join(self.dir.name, "bin.json")
        with open(bin_path, "wb") as fh:
            fh.write(b"\xff\xfe\x00\x01")
        self.assert_input_error(self.check(bin_path))

    def test_deeply_nested_inventory_exits_2(self):
        self.assert_input_error(self.check(self.write("deep.json", "[" * 200000)))

    def test_bad_usage_files_exit_2(self):
        inv = self.inventory([rec()])
        bad = {
            "empty.csv": "",
            "header_only.csv": USAGE_HEAD,
            "wrong_columns.csv": "system,model\nA,b\n",
            "short_row.csv": USAGE_HEAD + "AI-1,m,2026-01-01\n",
            "bad_date.csv": USAGE_HEAD + "AI-1,m,2026-01-01,yesterday,3\n",
            "reversed.csv": USAGE_HEAD + "AI-1,m,2026-09-01,2026-01-01,3\n",
            "future.csv": USAGE_HEAD + "AI-1,m,2026-09-01,2026-10-02,3\n",
            "negative.csv": USAGE_HEAD + "AI-1,m,2026-01-01,2026-02-01,-4\n",
            "words.csv": USAGE_HEAD + "AI-1,m,2026-01-01,2026-02-01,many\n",
            "blank_model.csv": USAGE_HEAD + "AI-1,,2026-01-01,2026-02-01,3\n",
        }
        for name, text in bad.items():
            with self.subTest(name=name):
                self.assert_input_error(self.check(inv, "--usage", self.write(name, text)))

    def test_bad_as_of_exits_2(self):
        inv = self.inventory([rec()])
        for v in ("yesterday", "2026-02-30", "2026-09-30\n", ""):
            with self.subTest(v=v):
                self.assert_input_error(run(["check", inv, "--as-of", v]))

    def test_wrong_typed_fields_are_findings_not_crashes(self):
        weird = {"system_id": "AI-1", "name": [1], "kind": {"a": 1}, "status": 7, "risk_tier": [3], "last_reviewed": 20260930,
                 "tools": "x", "model_id": 5, "business_owner": True, "purpose": None, "evaluation_ref": {}, "fallback_plan": 1.5}
        code, out, err = self.check(self.inventory([weird, {}, {"system_id": 12}]), "--usage", self.usage("AI-1,m,2026-01-01,2026-02-01,3\n"))
        self.assertEqual((code, err), (1, ""))
        self.assertIn("decision: FAIL", out)

    # ------------------------------------------------------------ hostile strings
    HOSTILE = "x\r\n::error title=forged::approved 100% safe"

    def test_hostile_system_id_cannot_forge_an_annotation(self):
        path = self.inventory([rec(system_id=self.HOSTILE, business_owner="TBD")])
        _, out, _ = self.check(path, "--format", "github")
        lines = out.splitlines()
        self.assertEqual(len([ln for ln in lines if ln.startswith("::error")]), 1)
        self.assertTrue(all(ln.startswith(("::error title=inventory-check ", "::notice title=inventory-check::")) for ln in lines))
        self.assertNotIn("title=forged", lines[0].split("::", 2)[1])
        self.assertIn("x\\r\\n::error", lines[0])
        self.assertIn("100%25 safe", lines[0])
        self.assertNotIn("\r", out)

    def test_hostile_values_cannot_forge_a_line_in_the_text_report(self):
        path = self.inventory([rec(system_id=self.HOSTILE, business_owner=self.HOSTILE, status=self.HOSTILE)])
        use = self.usage_rows([[self.HOSTILE, "m", "2026-01-01", "2026-02-01", 3]])
        _, out, _ = self.check(path, "--usage", use)
        self.assertNotIn("\r", out)
        self.assertTrue(out.strip())
        for ln in out.splitlines():
            self.assertFalse(ln.startswith("::"), ln)
        self.assertIn("\\r\\n::error", out)

    def test_hostile_usage_id_is_escaped_in_both_formats(self):
        inv = self.inventory([rec()])
        use = self.usage_rows([["AI-1", "vendor-a-large-2026-03", "2026-06-01", "2026-09-29", 10], [self.HOSTILE, "m", "2026-01-01", "2026-02-01", 3]])
        _, github, _ = self.check(inv, "--usage", use, "--format", "github")
        lines = github.splitlines()
        self.assertTrue(all(ln.startswith(("::error title=inventory-check ", "::notice title=inventory-check::")) for ln in lines))
        self.assertEqual(len([ln for ln in lines if ln.startswith("::error")]), 1)
        _, text, _ = self.check(inv, "--usage", use)
        self.assertFalse(any(ln.startswith("::") for ln in text.splitlines()))

    def test_lone_surrogates_do_not_crash_the_report(self):
        path = self.write("sur.json", '[{"system_id": "AI-\\ud800", "name": "x"}]')
        code, out, err = self.check(path)
        self.assertEqual((code, err), (1, ""))
        self.assertIn("\\ud800", out)

    def test_escape_annotation_follows_the_github_rules(self):
        self.assertEqual(ic.escape_annotation("a\r\nb%c"), "a%0D%0Ab%25c")

    def test_show_cuts_long_values(self):
        self.assertEqual(len(ic.show("a" * 500)), 60)
        self.assertEqual(ic.show("tab\there"), "tab\\there")


if __name__ == "__main__":
    unittest.main()
