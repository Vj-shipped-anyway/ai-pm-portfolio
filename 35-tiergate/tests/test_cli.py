"""Command line: exit codes, malformed input, hostile strings."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
from tiergate import INTAKE_COLUMNS

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")


def row(**overrides) -> dict:
    base = {"use_case_id": "T-1", "title": "Staff lookup", "description": "Looks up a policy for staff.",
            "dataset_name": "ds", "customer_facing": "no", "decision_autonomy": "advisory", "data_class": "internal",
            "vendor_model": "none", "regulatory_scope": "none", "financial_exposure_band": "lt_1m",
            "self_declared_tier": "1"}
    base.update(overrides)
    return base


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def write_rows(self, name: str, rows: list, columns=None) -> str:
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=columns or INTAKE_COLUMNS, lineterminator="\n", extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        return self.path(name)

    def write_text(self, name: str, text: str) -> str:
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def write_bytes(self, name: str, data: bytes) -> str:
        with open(self.path(name), "wb") as fh:
            fh.write(data)
        return self.path(name)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "tiergate.py"] + list(args), cwd=SRC, capture_output=True, text=True)

    def assert_exit_2(self, result, fragment: str = ""):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stderr.count("\n"), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("tiergate: "), result.stderr)
        self.assertIn(fragment, result.stderr)


class ExitCodeTests(CliCase):
    def test_demo_exits_0_and_prints_three_lines(self):
        r = self.run_cli("--demo")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.splitlines()), 3)

    def test_exit_1_when_a_form_is_under_declared(self):
        p = self.write_rows("a.csv", [row(decision_autonomy="automated", self_declared_tier="1")])
        r = self.run_cli("check", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("UNDER-DECLARED", r.stdout)

    def test_exit_0_when_every_tier_matches(self):
        r = self.run_cli("check", self.write_rows("a.csv", [row()]))
        self.assertEqual(r.returncode, 0)
        self.assertIn("checked 1 submissions: 0 under-declared, 0 over-declared, 1 unchanged", r.stdout)

    def test_extra_columns_and_a_byte_order_mark_are_accepted(self):
        p = self.write_rows("a.csv", [dict(row(), reference_tier="3")], INTAKE_COLUMNS + ["reference_tier"])
        with open(p, "rb") as fh:
            body = fh.read()
        with open(p, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + body)
        self.assertEqual(self.run_cli("check", p).returncode, 0)

    def test_hidden_columns_do_not_change_the_result(self):
        data = os.path.join(SRC, "..", "data")
        base = ["check", os.path.join(data, "intake_submissions.csv"), "--catalog", os.path.join(data, "data_catalog.csv"),
                "--registry", os.path.join(data, "vendor_registry.csv")]
        with open(os.path.join(data, "intake_submissions.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        visible = self.write_rows("visible.csv", rows)  # extrasaction=ignore drops every hidden column
        same = base[:1] + [visible] + base[2:]
        self.assertEqual(self.run_cli(*base).stdout, self.run_cli(*same).stdout)


class MalformedInputTests(CliCase):
    def test_empty_file(self):
        self.assert_exit_2(self.run_cli("check", self.write_text("e.csv", "")), "is empty")

    def test_header_only(self):
        p = self.write_rows("h.csv", [])
        self.assert_exit_2(self.run_cli("check", p), "no rows")

    def test_missing_file_and_directory(self):
        self.assert_exit_2(self.run_cli("check", self.path("nope.csv")), "cannot read")
        self.assert_exit_2(self.run_cli("check", self.dir), "cannot read")

    def test_wrong_type(self):
        self.assert_exit_2(self.run_cli("check", self.write_text("j.json", '{"use_case_id": "T-1"}')), "missing columns")
        self.assert_exit_2(self.run_cli("check", self.write_bytes("c.bin", b"\x89PNG\r\n\x1a\n\x00\xff\xfe")), "not UTF-8")
        self.assert_exit_2(self.run_cli("check", self.write_bytes("n.csv", b"use_case_id\x00,title\n")), "")

    def test_truncated_row(self):
        p = self.write_rows("t.csv", [row(), row(use_case_id="T-2")])
        with open(p, encoding="utf-8") as fh:
            text = fh.read()
        self.write_text("t.csv", text[: text.rindex(",") - 10])
        self.assert_exit_2(self.run_cli("check", p), "fields")

    def test_missing_column_is_named(self):
        cols = [c for c in INTAKE_COLUMNS if c != "data_class"]
        self.assert_exit_2(self.run_cli("check", self.write_rows("m.csv", [row()], cols)), "data_class")

    def test_bad_values(self):
        for bad, fragment in ((row(data_class="secret"), "data_class"), (row(self_declared_tier="5"), "self_declared_tier"),
                              (row(self_declared_tier="2.0"), "self_declared_tier"), (row(self_declared_tier=""), "self_declared_tier"),
                              (row(customer_facing="maybe"), "customer_facing"), (row(use_case_id=""), "blank")):
            with self.subTest(fragment=fragment):
                self.assert_exit_2(self.run_cli("check", self.write_rows("v.csv", [bad])), fragment)

    def test_duplicate_id(self):
        self.assert_exit_2(self.run_cli("check", self.write_rows("d.csv", [row(), row()])), "twice")

    def test_bad_catalog_and_registry(self):
        intake = self.write_rows("a.csv", [row()])
        cat = self.write_rows("c.csv", [{"dataset_name": "ds", "catalog_class": "top_secret"}], ["dataset_name", "catalog_class"])
        reg = self.write_rows("r.csv", [{"use_case_id": "T-1", "vendor_model": "none"}] * 2, ["use_case_id", "vendor_model"])
        self.assert_exit_2(self.run_cli("check", intake, "--catalog", cat), "catalog_class")
        self.assert_exit_2(self.run_cli("check", intake, "--registry", reg), "twice")

    def test_usage_errors_are_one_line(self):
        self.assert_exit_2(self.run_cli(), "give --demo")
        self.assert_exit_2(self.run_cli("check"), "usage error")
        self.assert_exit_2(self.run_cli("check", "x.csv", "--format", "xml"), "usage error")
        self.assert_exit_2(self.run_cli("check", "x.csv", "--bogus"), "usage error")

    def test_hostile_value_in_an_error_stays_on_one_line(self):
        p = self.write_rows("h.csv", [row(data_class="x\r\n::error::injected")])
        r = self.run_cli("check", p)
        self.assert_exit_2(r, "data_class")

    def test_unwritable_out_path(self):
        p = self.write_rows("a.csv", [row()])
        self.assert_exit_2(self.run_cli("check", p, "--out", self.path("no_such_dir/out.csv")), "cannot write")


class HostileStringTests(CliCase):
    HOSTILE = "Loan%0A::error::one\r\n::error::two"

    def hostile_files(self):
        intake = self.write_rows("h.csv", [row(use_case_id="::error::id", title=self.HOSTILE, description="Helps customers\n::warning::x",
                                               dataset_name="evil\n::warning::y", decision_autonomy="automated")])
        catalog = self.write_rows("c.csv", [{"dataset_name": "other", "catalog_class": "public"}], ["dataset_name", "catalog_class"])
        return intake, catalog

    def test_github_format_escapes_percent_cr_and_newline(self):
        intake, catalog = self.hostile_files()
        r = self.run_cli("check", intake, "--catalog", catalog, "--format", "github")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("\r", r.stdout)
        commands = [ln for ln in r.stdout.splitlines() if ln.startswith("::")]
        self.assertEqual(len(commands), 1, r.stdout)
        self.assertTrue(commands[0].startswith("::error title=tiergate::"))
        self.assertIn("%250A", commands[0])
        self.assertIn("%0A", commands[0])

    def test_text_format_has_no_line_that_starts_with_input_text(self):
        intake, catalog = self.hostile_files()
        r = self.run_cli("check", intake, "--catalog", catalog)
        lines = r.stdout.splitlines()
        self.assertNotIn("\r", r.stdout)
        self.assertFalse([ln for ln in lines if ln.lstrip().startswith("::")], r.stdout)
        self.assertEqual(sum(1 for ln in lines if ln.startswith("UNDER-DECLARED")), 1)

    def test_out_file_guards_formula_cells(self):
        p = self.write_rows("f.csv", [row(use_case_id="=1+1")])
        out = self.path("out.csv")
        self.assertEqual(self.run_cli("check", p, "--out", out).returncode, 0)
        with open(out, newline="", encoding="utf-8") as fh:
            self.assertEqual(list(csv.reader(fh))[1][0], "'=1+1")


class SilentNoOpTests(CliCase):
    def test_no_second_source_given_is_said(self):
        out = self.run_cli("check", self.write_rows("a.csv", [row()])).stdout
        self.assertIn("note: no catalog given", out)
        self.assertIn("note: no registry given", out)

    def test_second_source_that_matches_nothing_is_said(self):
        intake = self.write_rows("a.csv", [row()])
        cat = self.write_rows("c.csv", [{"dataset_name": "other", "catalog_class": "public"}], ["dataset_name", "catalog_class"])
        reg = self.write_rows("r.csv", [{"use_case_id": "Z-9", "vendor_model": "vendor_api"}], ["use_case_id", "vendor_model"])
        out = self.run_cli("check", intake, "--catalog", cat, "--registry", reg).stdout
        self.assertIn("note: no dataset in the intake file is in the catalog", out)
        self.assertIn("note: no use case in the intake file is in the registry", out)

    def test_demo_has_no_notes(self):
        self.assertNotIn("note:", self.run_cli("--demo").stdout)


if __name__ == "__main__":
    unittest.main()
