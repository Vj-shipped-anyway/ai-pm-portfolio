import datetime
import time
import unittest

import _bootstrap  # noqa: F401
from evidence_gate import clean, escape_annotation, parse_date, parse_record, parse_tier, visible_lines

PLAIN = """## AI change record
Use case: UC-014
Declared tier: 2
- [x] E01 Use-case card | ref: evidence/UC-014/E01.md | date: 2026-09-02
- [ ] E02 Data-source attestation | ref: evidence/UC-014/E02.md | date: 2026-09-03
"""


class ParseTests(unittest.TestCase):
    def test_plain_record(self):
        r = parse_record(PLAIN)
        self.assertEqual((r["use_case"], r["declared_tier"], r["conflicts"]), ("UC-014", 2, []))
        self.assertEqual([(e["id"], e["ticked"]) for e in r["entries"]], [("E01", True), ("E02", False)])
        self.assertEqual(r["entries"][0]["ref"], "evidence/UC-014/E01.md")
        self.assertEqual(r["entries"][0]["date"], "2026-09-02")

    def test_formatted_description_reads_the_same(self):
        body = ("**Use case:** UC-014\r\n**Declared tier:** 2\r\n"
                "* [X] e01 Use-case card  |  ref: `evidence/UC-014/E01.md`  |  date: 2026-9-2\r\n")
        r = parse_record(body)
        self.assertEqual((r["use_case"], r["declared_tier"]), ("UC-014", 2))
        self.assertEqual((r["entries"][0]["id"], r["entries"][0]["ticked"]), ("E01", True))
        self.assertEqual(r["entries"][0]["date"], "2026-9-2")

    def test_comments_and_fences_are_not_read(self):
        body = ("Use case: UC-1\nDeclared tier: 1\n<!-- hint\n- [x] E01 a | ref: x | date: 2026-01-01\n-->\n"
                "```\n- [x] E02 b | ref: y | date: 2026-01-01\n```\n"
                "inline <!-- Declared tier: 4 --> text\n")
        r = parse_record(body)
        self.assertEqual(r["entries"], [])
        self.assertEqual(r["declared_tier"], 1)
        self.assertEqual(r["conflicts"], [])

    def test_unterminated_comment_or_fence_hides_the_rest(self):
        def seen(text):
            return [ln for ln in visible_lines(text) if ln.strip()]
        self.assertEqual(seen("a\n<!-- never closed\nb\nc"), ["a"])
        self.assertEqual(seen("a\n" + "~" * 3 + "\nb\nc"), ["a"])
        self.assertEqual(seen("a <!-- x --> b\nc"), ["a  b", "c"])

    def test_conflicting_fields_are_reported(self):
        r = parse_record("Use case: UC-1\nUse case: UC-2\nDeclared tier: 1\n")
        self.assertEqual(r["conflicts"], ["use case"])
        self.assertEqual(r["use_case"], "UC-1")

    def test_evidence_id_must_be_explicit(self):
        body = "Use case: UC-1\n- [x] E1 a | ref: x | date: 2026-01-01\n- [x] E001 b | ref: x | date: 2026-01-01\n- [x] Card | ref: x\n"
        self.assertEqual(parse_record(body)["entries"], [])

    def test_free_text_is_no_record(self):
        for body in ("", "   \n\n", "Fixes the login bug.\n", "## AI change record\n\n(to be completed)\n"):
            self.assertFalse(parse_record(body)["has_record"], body)

    def test_blank_field_is_not_a_value(self):
        r = parse_record("Use case:\nDeclared tier:   \n")
        self.assertEqual((r["use_case"], r["declared_tier"], r["has_record"]), (None, None, False))

    def test_tier_forms(self):
        self.assertEqual([parse_tier(t) for t in ("3", "Tier 3", "tier3", " 2 (medium)")], [3, 3, 3, 2])
        for bad in ("", "0", "5", "12", "3x", "three", "\u0663", "\u00bd"):
            self.assertIsNone(parse_tier(bad), bad)

    def test_date_forms(self):
        self.assertEqual(parse_date("2026-10-16"), datetime.date(2026, 10, 16))
        self.assertEqual(parse_date(" 2026-9-2 "), datetime.date(2026, 9, 2))
        for bad in ("", "TBD", "03/09/2026", "2026-02-30", "2026-13-01", "0000-01-01", "20261016", "2026-10-16T00:00",
                    "\u0662\u0660\u0662\u0666-10-16"):
            self.assertIsNone(parse_date(bad), bad)

    def test_hostile_unicode_labels_do_not_crash(self):
        r = parse_record("u\u017fe ca\u017fe: UC-1\nDeclared tier: \u0663\n")
        self.assertIsNone(r["declared_tier"])

    def test_hostile_long_lines_are_read_in_linear_time(self):
        start = time.time()
        for line in ("Use case: x" + " " * 60000 + "y", "<!--" * 15000, "- [x] E01 " + "|" * 60000, "**" * 30000 + "Use case: a"):
            parse_record("Declared tier: 1\n" + line)
        self.assertLess(time.time() - start, 2.0)

    def test_untrusted_text_is_cleaned_and_escaped(self):
        self.assertNotIn("\n", clean("a\n::error::b\r\u2028c\x1b[31m"))
        self.assertEqual(clean("x" * 200, 20), "x" * 17 + "...")
        self.assertEqual(escape_annotation("100%\r\nnext"), "100%25%0D%0Anext")


if __name__ == "__main__":
    unittest.main()
