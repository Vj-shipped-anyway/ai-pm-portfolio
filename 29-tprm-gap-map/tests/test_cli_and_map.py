import contextlib
import csv
import io
import os
import unittest

import _bootstrap  # noqa: F401
import tprm_gap_map as t

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def run(args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = t.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


class CliAndMapTests(unittest.TestCase):
    def test_demo(self):
        code, out = run(["--demo"])
        self.assertEqual(code, 0)
        self.assertIn("text examples catch 17 of 24; with AI characteristics 22 of 24", out)

    def test_map_has_one_row_per_stage_and_valid_prompts(self):
        with open(os.path.join(DATA, "guidance_map.csv"), newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 16)
        self.assertTrue({r["how_the_text_prompts_it"] for r in rows} <= {"named", "principle", "example", "not mentioned"})
        self.assertEqual([r["stage"] for r in rows if r["how_the_text_prompts_it"] == "not mentioned"],
                         ["High-risk characteristics: AI-specific", "Due diligence: AI evidence"])
        code, out = run(["map"])
        self.assertEqual(code, 0)
        self.assertIn("Subcontractors", out)

    def test_tier_reports_ai_vendors_with_no_upstream_on_file(self):
        import tempfile
        cols = ["vendor_id", "service_type", "activity_share_pct", "upstream_provider", "model_change_notice_days",
                "trains_on_bank_data", "bank_data_retained_days", "soc_report", "insurance", "financial_ok", "key_personnel"]
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerow(["V1", "ai_enabled_service", 10, "", 30, "no", 30, "yes", "yes", "yes", "yes"])
        self.addCleanup(os.unlink, f.name)
        code, out = run(["tier", f.name])
        self.assertEqual(code, 0)
        self.assertIn("no upstream provider on file: 1", out)

    def test_missing_file_exits_2(self):
        self.assertEqual(run(["tier", "nope.csv"])[0], 2)
        self.assertEqual(run(["terms", "nope.txt"])[0], 2)

    def test_terms_counts_a_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("a plain third-party text with no such wording")
        self.addCleanup(os.unlink, f.name)
        code, out = run(["terms", f.name])
        self.assertEqual(code, 0)
        self.assertIn("occurrences of AI wording: 0", out)


def run_all(args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = t.main(args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


COLS = ["vendor_id", "service_type", "activity_share_pct", "upstream_provider", "model_change_notice_days",
        "trains_on_bank_data", "bank_data_retained_days"]
AI_VENDOR = ["V1", "ai_enabled_service", 10, "P1", 30, "no", 30]


class InputHandlingTests(unittest.TestCase):
    def table(self, header, rows):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_incident_log_without_the_material_column_exits_2(self):
        v = self.table(COLS, [AI_VENDOR])
        log = self.table(["vendor_id", "month"], [["V1", "2026-01"]])
        code, out, err = run_all(["tier", v, "--incidents", log])
        self.assertEqual(code, 2)
        self.assertIn("missing column(s): material", err)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertEqual(out, "")

    def test_vendors_without_a_column_the_tiering_reads_exits_2(self):
        header = [c for c in COLS if c != "trains_on_bank_data"]
        v = self.table(header, [["V1", "ai_enabled_service", 10, "P1", 30, 30]])
        code, _, err = run_all(["tier", v])
        self.assertEqual(code, 2)
        self.assertIn("missing column(s): trains_on_bank_data", err)

    def test_vendors_file_with_only_a_header_exits_2(self):
        code, out, err = run_all(["tier", self.table(COLS, [])])
        self.assertEqual(code, 2)
        self.assertIn("no vendor rows", err)
        self.assertEqual(out, "")

    def test_a_short_row_exits_2_and_is_not_a_traceback(self):
        code, _, err = run_all(["tier", self.table(COLS, [["V1", "ai_enabled_service"]])])
        self.assertEqual(code, 2)
        self.assertTrue(err.startswith("input error:"))

    def test_incident_log_with_only_a_header_says_nothing_was_scored(self):
        v = self.table(COLS, [AI_VENDOR])
        log = self.table(["vendor_id", "month", "cause", "customer_impact_hours", "material"], [])
        code, out, _ = run_all(["tier", v, "--incidents", log])
        self.assertEqual(code, 0)
        self.assertIn("incident log has a header and no rows", out)
        self.assertNotIn("text examples catch", out)

    def test_an_unrecognized_service_type_is_named(self):
        v = self.table(COLS, [AI_VENDOR, ["V2", "core-processing", 5, "", "", "", ""]])
        _, out, _ = run_all(["tier", v])
        self.assertIn("service types the tool does not recognize: 'core-processing' (1)", out)
        self.assertNotIn("does not recognize", run_all(["--demo"])[1])

    def test_a_hostile_provider_name_stays_on_one_line(self):
        v = self.table(COLS, [["V1", "ai_enabled_service", 10, "P1\n::error::forged\r::notice::x", 30, "no", 30]])
        code, out, _ = run_all(["tier", v])
        self.assertEqual(code, 0)
        for ln in out.splitlines():
            self.assertFalse(ln.startswith("::"), ln)
        self.assertIn("P1\\n::error::forged\\r::notice::x (ai_enabled_service) 100%", out)

    def test_safe_escapes_control_characters_and_leaves_ordinary_text(self):
        self.assertEqual(t.safe("a\nb\r\tc\x1b\u2028"), "a\\nb\\r\\tc\\x1b\\u2028")
        self.assertEqual(t.safe("P1 (cloud) 50%"), "P1 (cloud) 50%")

    def test_a_hostile_service_type_stays_on_one_line(self):
        v = self.table(COLS, [AI_VENDOR, ["V2", "x\n::error::forged", 5, "", "", "", ""]])
        _, out, _ = run_all(["tier", v])
        for ln in out.splitlines():
            self.assertFalse(ln.startswith("::"), ln)
        self.assertIn("x\\n::error::forged", out)


if __name__ == "__main__":
    unittest.main()
