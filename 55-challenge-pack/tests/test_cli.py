"""Command line: exit codes, malformed input, hostile strings, memos."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest

import _bootstrap  # noqa: F401
from challenge_pack import EVIDENCE_COLUMNS, USE_CASE_COLUMNS

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
DATA = os.path.join(SRC, "..", "data")
AS_OF = "2026-10-01"


def uc(**o):
    base = {"use_case_id": "T-1", "title": "Staff lookup", "model_type": "ml", "vendor_model": "none",
            "customer_facing": "no", "decision_autonomy": "advisory", "data_class": "internal",
            "regulatory_scope": "none", "financial_exposure_band": "lt_1m", "developer_unit": "Cards",
            "deployed_version": "1.0", "declared_tier": "1"}
    base.update(o)
    return base


def ev(item, **o):
    base = {"use_case_id": "T-1", "item_id": item, "ref": "DOC-1", "prepared_by_unit": "Cards", "covers_version": "1.0",
            "evidence_date": "2026-09-01", "reaffirmed_date": ""}
    base.update(o)
    return base


COMPLETE = [ev("CH01"), ev("CH02"), ev("CH03")]


class CliCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def path(self, name):
        return os.path.join(self.dir, name)

    def write_rows(self, name, rows, columns):
        with open(self.path(name), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        return self.path(name)

    def write_text(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return self.path(name)

    def write_bytes(self, name, data):
        with open(self.path(name), "wb") as fh:
            fh.write(data)
        return self.path(name)

    def files(self, ucs=None, evs=None):
        return (self.write_rows("uc.csv", ucs if ucs is not None else [uc()], USE_CASE_COLUMNS),
                self.write_rows("ev.csv", evs if evs is not None else COMPLETE, EVIDENCE_COLUMNS))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "challenge_pack.py"] + list(args), cwd=SRC, capture_output=True, text=True)

    def pack(self, ucs=None, evs=None, *extra, as_of=AS_OF):
        u, e = self.files(ucs, evs)
        return self.run_cli("pack", u, e, "--as-of", as_of, *extra)

    def assert_exit_2(self, result, fragment=""):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stderr.count("\n"), 1, result.stderr)
        self.assertTrue(result.stderr.startswith("challenge_pack: "), result.stderr)
        self.assertIn(fragment, result.stderr)


class ExitCodeTests(CliCase):
    def test_demo_exits_0_and_prints_three_lines(self):
        r = self.run_cli("--demo")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(r.stdout.splitlines()), 3)
        self.assertIn("GAP  CH08", r.stdout)

    def test_exit_0_when_complete_and_the_summary_says_so(self):
        r = self.pack()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "checked 1 use cases: 0 with gaps, 1 complete; 3 plan items, 3 on file and current")

    def test_exit_1_on_a_gap(self):
        r = self.pack(evs=[ev("CH01"), ev("CH02")])
        self.assertEqual(r.returncode, 1)
        self.assertIn("GAP  CH03", r.stdout)
        self.assertIn("missing", r.stdout)

    def test_all_prints_complete_use_cases(self):
        r = self.pack(None, None, "--all")
        self.assertIn("complete: 3 plan items on file and current", r.stdout)

    def test_extra_columns_and_a_byte_order_mark_are_accepted(self):
        u = self.write_rows("uc.csv", [dict(uc(), note="x")], USE_CASE_COLUMNS + ["note"])
        with open(u, "rb") as fh:
            body = fh.read()
        with open(u, "wb") as fh:
            fh.write(b"\xef\xbb\xbf" + body)
        e = self.write_rows("ev.csv", COMPLETE, EVIDENCE_COLUMNS)
        self.assertEqual(self.run_cli("pack", u, e, "--as-of", AS_OF).returncode, 0)

    def test_the_bundled_data_gives_the_numbers_the_readme_prints(self):
        r = self.run_cli("pack", os.path.join(DATA, "use_cases.csv"), os.path.join(DATA, "evidence.csv"), "--as-of", AS_OF)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.splitlines()[-1], "checked 150 use cases: 130 with gaps, 20 complete; 1410 plan items, 1044 on file and current")

    def test_same_files_and_date_give_the_same_bytes(self):
        a = self.pack(None, None, "--out-dir", self.path("o1"))
        b = self.pack(None, None, "--out-dir", self.path("o2"))
        self.assertEqual(a.stdout, b.stdout)
        with open(self.path("o1/T-1.md"), "rb") as f1, open(self.path("o2/T-1.md"), "rb") as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_id_selects_one_use_case(self):
        u, e = self.files([uc(), uc(use_case_id="T-2")], COMPLETE)
        r = self.run_cli("pack", u, e, "--as-of", AS_OF, "--id", "T-2")
        self.assertIn("checked 1 use cases: 1 with gaps", r.stdout)

    def test_table_command(self):
        r = self.run_cli("table")
        self.assertEqual(r.returncode, 0)
        self.assertIn("| 4 | Independent validation, benchmark and senior sign-off | 13 | 12 months |", r.stdout)


class NotesTests(CliCase):
    def test_a_header_only_evidence_file_is_reported_not_swallowed(self):
        r = self.pack(evs=[])
        self.assertEqual(r.returncode, 1)
        self.assertIn("note: the evidence file has no rows", r.stdout)
        self.assertIn("3 plan items, 0 on file", r.stdout)

    def test_evidence_for_unknown_use_cases_and_items_is_named(self):
        r = self.pack(evs=COMPLETE + [ev("CH01", use_case_id="OTHER"), ev("ZZ9")])
        self.assertIn("1 evidence rows name a use case that is not in the use-case file", r.stdout)
        self.assertIn("1 evidence rows name an item that is not in the plan and were ignored (first: ZZ9)", r.stdout)

    def test_files_that_do_not_belong_together(self):
        r = self.pack(evs=[ev("CH01", use_case_id="OTHER")])
        self.assertIn("check that the two files belong together", r.stdout)


class MalformedInputTests(CliCase):
    def test_empty_and_header_only_use_case_files(self):
        e = self.write_rows("ev.csv", COMPLETE, EVIDENCE_COLUMNS)
        self.assert_exit_2(self.run_cli("pack", self.write_text("u.csv", ""), e, "--as-of", AS_OF), "is empty")
        self.assert_exit_2(self.run_cli("pack", self.write_rows("h.csv", [], USE_CASE_COLUMNS), e, "--as-of", AS_OF), "no rows")

    def test_empty_evidence_file(self):
        u = self.write_rows("uc.csv", [uc()], USE_CASE_COLUMNS)
        self.assert_exit_2(self.run_cli("pack", u, self.write_text("e.csv", ""), "--as-of", AS_OF), "is empty")

    def test_missing_file_and_directory(self):
        e = self.write_rows("ev.csv", COMPLETE, EVIDENCE_COLUMNS)
        self.assert_exit_2(self.run_cli("pack", self.path("nope.csv"), e, "--as-of", AS_OF), "cannot read")
        self.assert_exit_2(self.run_cli("pack", self.dir, e, "--as-of", AS_OF), "cannot read")

    def test_wrong_type(self):
        e = self.write_rows("ev.csv", COMPLETE, EVIDENCE_COLUMNS)
        self.assert_exit_2(self.run_cli("pack", self.write_text("j.json", '{"use_case_id": "T-1"}'), e, "--as-of", AS_OF), "missing columns")
        self.assert_exit_2(self.run_cli("pack", self.write_bytes("c.bin", b"\x89PNG\r\n\x1a\n\x00\xff\xfe"), e, "--as-of", AS_OF), "not UTF-8")
        self.assert_exit_2(self.run_cli("pack", self.write_bytes("n.csv", b"use_case_id\x00,title\n"), e, "--as-of", AS_OF), "NUL")

    def test_truncated_row(self):
        u, e = self.files()
        with open(u, encoding="utf-8") as fh:
            text = fh.read()
        self.write_text("uc.csv", text[: text.rindex(",") - 6])
        self.assert_exit_2(self.run_cli("pack", u, e, "--as-of", AS_OF), "fields")

    def test_missing_column_is_named(self):
        u = self.write_rows("uc.csv", [uc()], [c for c in USE_CASE_COLUMNS if c != "developer_unit"])
        e = self.write_rows("ev.csv", COMPLETE, EVIDENCE_COLUMNS)
        self.assert_exit_2(self.run_cli("pack", u, e, "--as-of", AS_OF), "developer_unit")

    def test_bad_use_case_values(self):
        for bad, fragment in ((uc(model_type="llm"), "model_type"), (uc(declared_tier="5"), "declared_tier"),
                              (uc(declared_tier="2.0"), "declared_tier"), (uc(customer_facing="maybe"), "customer_facing"),
                              (uc(developer_unit=""), "developer_unit"), (uc(use_case_id=""), "use_case_id"),
                              (uc(title=""), "title")):
            with self.subTest(fragment=fragment):
                self.assert_exit_2(self.pack([bad]), fragment)

    def test_unsafe_ids_cannot_name_a_file(self):
        for bad in ("../x", "a/b", ".hidden", "a" * 41, "x\ny"):
            with self.subTest(bad=bad):
                self.assert_exit_2(self.pack([uc(use_case_id=bad)], None, "--out-dir", self.path("o")), "use_case_id")
        self.assertFalse(os.path.exists(self.path("x.md")))

    def test_duplicates(self):
        self.assert_exit_2(self.pack([uc(), uc()]), "twice")
        self.assert_exit_2(self.pack(None, COMPLETE + [ev("CH01")]), "twice")

    def test_bad_dates(self):
        for bad, fragment in ((ev("CH01", evidence_date="01/09/2026"), "evidence_date"),
                              (ev("CH01", evidence_date="2026-02-30"), "not a real date"),
                              (ev("CH01", evidence_date=""), "evidence_date"),
                              (ev("CH01", evidence_date="2026-10-02"), "after --as-of"),
                              (ev("CH01", reaffirmed_date="2026-10-02"), "after --as-of"),
                              (ev("CH01", reaffirmed_date="2026-08-01"), "before evidence_date"),
                              (ev("CH01", ref=""), "ref")):
            with self.subTest(fragment=fragment):
                self.assert_exit_2(self.pack(None, [bad]), fragment)

    def test_as_of_and_usage_errors_are_one_line(self):
        u, e = self.files()
        self.assert_exit_2(self.run_cli("pack", u, e, "--as-of", "yesterday"), "--as-of")
        self.assert_exit_2(self.run_cli("pack", u, e), "usage error")
        self.assert_exit_2(self.run_cli("pack", u, e, "--as-of", AS_OF, "--format", "xml"), "usage error")
        self.assert_exit_2(self.run_cli("pack", u, e, "--as-of", AS_OF, "--id", "NOPE"), "--id")
        self.assert_exit_2(self.run_cli("pack", u), "usage error")


class HostileStringTests(CliCase):
    EVIL = "Evil\n::error::boom\r%0A | <script>alert(1)</script> [x](http://e) `z`"

    def test_text_output_is_one_clean_line_per_finding(self):
        r = self.pack([uc(title=self.EVIL)], [ev("CH01")])
        self.assertEqual(r.returncode, 1)
        for line in r.stdout.splitlines():
            self.assertFalse(line.startswith("::"), line)
            self.assertNotIn("\r", line)
        self.assertEqual(len(r.stdout.splitlines()), 4)

    def test_github_output_escapes_and_keeps_to_known_commands(self):
        r = self.pack([uc(title=self.EVIL, use_case_id="T-9")], [ev("CH01", use_case_id="T-9", prepared_by_unit="x\n::error::y")],
                      "--format", "github")
        for line in r.stdout.splitlines():
            self.assertTrue(line.startswith(("::error title=challenge-pack::", "::notice title=challenge-pack::", "checked ")), line)
        self.assertNotIn("\r", r.stdout)

    def test_a_hostile_unit_name_in_a_gap_detail_stays_on_one_line(self):
        r = self.pack([uc(declared_tier="3", developer_unit="Cards")], [ev("CH07", prepared_by_unit="Cards"),
                                                                        ev("CH08", covers_version="9\n::error::z")])
        for line in r.stdout.splitlines():
            self.assertFalse(line.startswith("::"), line)

    def test_memo_cells_cannot_break_the_table_or_add_html(self):
        r = self.pack([uc(title=self.EVIL)], COMPLETE, "--out-dir", self.path("o"))
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(self.path("o/T-1.md"), encoding="utf-8") as fh:
            memo = fh.read()
        self.assertNotIn("<script>", memo)
        self.assertEqual(len([ln for ln in memo.splitlines() if ln.startswith("# ")]), 1)
        self.assertNotIn("\r", memo)

    def test_summary_csv_neutralises_formulas(self):
        self.pack([uc(title="=HYPERLINK(\"http://e\")")], COMPLETE, "--out-dir", self.path("o"))
        with open(self.path("o/summary.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows[0]["title"].startswith("'="))


class OutputTests(CliCase):
    def test_out_dir_holds_one_memo_per_use_case_and_a_summary(self):
        r = self.pack([uc(), uc(use_case_id="T-2")], COMPLETE, "--out-dir", self.path("o"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(sorted(os.listdir(self.path("o"))), ["T-1.md", "T-2.md", "summary.csv"])
        with open(self.path("o/T-2.md"), encoding="utf-8") as fh:
            memo = fh.read()
        for heading in ("## 1. Use case", "## 3. Test plan and evidence checklist", "## 4. Findings", "## 6. Sign-off"):
            self.assertIn(heading, memo)
        self.assertIn("| CH01 Inventory record and named owner |", memo)
        self.assertIn("gap", memo)

    def test_out_dir_that_cannot_be_written_exits_2(self):
        blocker = self.write_text("file.txt", "x")
        self.assert_exit_2(self.pack(None, None, "--out-dir", os.path.join(blocker, "sub")), "cannot write")

    def test_scope_note_and_raised_tier_appear_in_the_memo(self):
        hot = uc(model_type="generative", decision_autonomy="automated", data_class="restricted", regulatory_scope="fair_lending")
        self.pack([hot], None, "--out-dir", self.path("o"))
        with open(self.path("o/T-1.md"), encoding="utf-8") as fh:
            memo = fh.read()
        self.assertIn("applied by analogy", memo)
        self.assertIn("raised from 1", memo)


if __name__ == "__main__":
    unittest.main()
