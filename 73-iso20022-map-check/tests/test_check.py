import os
import unittest
from decimal import Decimal

import _bootstrap  # noqa: F401
import iso20022_map_check as tool
from fixtures import LEGACY, ISO, MAPPING, GOOD_SOURCE, GOOD_TARGET, bundle, rows

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def kinds(source, target, b=None, schema=True):
    return sorted((f["kind"], f["subject"]) for f in tool.check_pair(source, target, b or bundle(), schema))


class PairTests(unittest.TestCase):
    def test_a_faithful_conversion_has_no_findings(self):
        self.assertEqual(kinds(GOOD_SOURCE, GOOD_TARGET), [])

    def test_truncation_is_reported_with_lengths_not_values(self):
        got = tool.check_pair(GOOD_SOURCE, dict(GOOD_TARGET, Nm="ACM"), bundle())
        self.assertEqual([(f["kind"], f["detail"]) for f in got], [("truncated", "kept 3 of 4 characters")])

    def test_a_changed_value_is_altered_and_a_missing_one_is_dropped(self):
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Nm="ACNE")), [("altered", "Nm")])
        no_name = {k: v for k, v in GOOD_TARGET.items() if k != "Nm"}
        self.assertEqual(kinds(GOOD_SOURCE, no_name), [("dropped", "Nm")])

    def test_padding_and_a_value_exactly_at_the_limit_are_not_defects(self):
        src = dict(GOOD_SOURCE, NM="0123456789")
        self.assertEqual(kinds(src, dict(GOOD_TARGET, Nm="0123456789   ")), [])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Nm="  ACME  ")), [])

    def test_amounts_are_compared_as_numbers(self):
        self.assertEqual(kinds(dict(GOOD_SOURCE, AMT="000000125000"), dict(GOOD_TARGET, Amt="1250")), [])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Amt="1250.5")), [])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Amt="1251")), [("altered", "Amt")])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Amt="not a number")), [("altered", "Amt"), ("schema_bad_value", "Amt")])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Amt="sNaN")), [("altered", "Amt"), ("schema_bad_value", "Amt")])

    def test_implied_decimals_scale_the_legacy_amount(self):
        expected, _issues, _ = tool.expected_target(GOOD_SOURCE, bundle())
        self.assertEqual(expected["Amt"], Decimal("1250.50"))

    def test_dates(self):
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Dt="2026-24-10")), [("altered", "Dt"), ("schema_bad_value", "Dt")])
        self.assertEqual(kinds(dict(GOOD_SOURCE, DT="20261340"), GOOD_TARGET), [("source_invalid", "DT")])
        self.assertEqual(kinds(dict(GOOD_SOURCE, AMT="12x"), GOOD_TARGET), [("source_invalid", "AMT")])
        self.assertEqual(kinds(dict(GOOD_SOURCE, DT="２０２６１０２４"), GOOD_TARGET), [("source_invalid", "DT")])

    def test_a_code_the_table_lacks_is_reported_once_and_its_fallback_is_not_untraced(self):
        src = dict(GOOD_SOURCE, CD="Z")
        self.assertEqual(kinds(src, dict(GOOD_TARGET, Code="AAAA")), [("code_unmapped", "CD=Z")])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Code="BBBB")), [("altered", "Code")])

    def test_joined_lines(self):
        src = dict(GOOD_SOURCE, L1="AB", L2="")
        self.assertEqual(kinds(src, dict(GOOD_TARGET, Text="AB")), [])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Text="AB C")), [("truncated", "Text")])
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Text="CD AB")), [("altered", "Text")])

    def test_unmapped_fields_and_the_explicit_drop(self):
        b = bundle(mapping=[r for r in MAPPING if r["row_id"] != "R1"])
        self.assertEqual(kinds(GOOD_SOURCE, GOOD_TARGET, b), [("unmapped_lost", "NM"), ("untraced", "Nm")])
        self.assertEqual(kinds(dict(GOOD_SOURCE, NOTE="secret"), GOOD_TARGET), [])
        self.assertEqual(kinds(dict(GOOD_SOURCE, ZZ="x"), GOOD_TARGET), [("unknown_source_field", "ZZ")])

    def test_untraced_values(self):
        self.assertEqual(kinds(GOOD_SOURCE, dict(GOOD_TARGET, Extra="v")), [("untraced", "Extra")])
        self.assertEqual(kinds(dict(GOOD_SOURCE, NM="          "), GOOD_TARGET), [("untraced", "Nm")])

    def test_schema_checks_can_be_skipped(self):
        no_ref = {k: v for k, v in GOOD_TARGET.items() if k != "Ref"}
        self.assertIn(("schema_missing_mandatory", "Ref"), kinds(GOOD_SOURCE, no_ref))
        self.assertNotIn("schema_missing_mandatory", [k for k, _ in kinds(GOOD_SOURCE, no_ref, schema=False)])
        self.assertIn(("schema_over_length", "Text"), kinds(dict(GOOD_SOURCE, L1="ABCDE", L2="FGHIJ"), dict(GOOD_TARGET, Text="ABCDE FGHIJK")))
        self.assertIn(("schema_bad_value", "Code"), kinds(GOOD_SOURCE, dict(GOOD_TARGET, Code="CCCC")))


class MappingTests(unittest.TestCase):
    def found(self, b):
        return sorted((f["kind"], f["subject"]) for f in tool.check_mapping(b))

    def test_the_small_mapping_is_clean_apart_from_the_reverse_warning(self):
        self.assertEqual([k for k in self.found(bundle()) if k[0] != "reverse_exposure"], [])

    def test_unmapped_legacy_field_and_explicit_drop(self):
        b = bundle(mapping=[r for r in MAPPING if r["row_id"] not in ("R1", "R7")])
        self.assertEqual([k for k in self.found(b) if k[0] == "legacy_unmapped"], [("legacy_unmapped", "NM"), ("legacy_unmapped", "NOTE")])
        self.assertEqual([k for k in self.found(bundle()) if k[0] == "legacy_unmapped"], [])

    def test_mandatory_element_needs_a_row_or_a_constant(self):
        b = bundle(mapping=[r for r in MAPPING if r["row_id"] != "R6"])
        self.assertIn(("iso_mandatory_unsourced", "Ref"), self.found(b))
        self.assertNotIn("iso_mandatory_unsourced", [k for k, _ in self.found(bundle())])

    def test_code_without_a_table_entry(self):
        self.assertIn(("code_not_covered", "CD=B"), self.found(bundle(tables={"cd": {"A": "AAAA"}})))

    def test_capacity_overflow_and_exact_fit(self):
        b = bundle(iso=rows(ISO, Nm={"max_len": "9"}))
        self.assertIn(("capacity_overflow", "Nm"), self.found(b))
        exact = bundle(iso=rows(ISO, Nm={"max_len": "10"}))
        self.assertNotIn("capacity_overflow", [k for k, _ in self.found(exact)])

    def test_joined_capacity_counts_the_separator(self):
        # 5 + 5 characters of text plus one separator is 11
        self.assertNotIn(("capacity_overflow", "Text"), self.found(bundle()))
        self.assertIn(("capacity_overflow", "Text"), self.found(bundle(iso=rows(ISO, Text={"max_len": "10"}))))

    def test_reverse_exposure_is_a_warning(self):
        got = [f for f in tool.check_mapping(bundle(iso=rows(ISO, Nm={"max_len": "40"}))) if f["subject"] == "Nm"]
        self.assertEqual([(f["kind"], f["severity"]) for f in got], [("reverse_exposure", "warning")])


class BundleErrorTests(unittest.TestCase):
    def fails(self, **kw):
        with self.assertRaises(tool.InputError):
            bundle(**kw)

    def test_bad_mapping_rows(self):
        self.fails(mapping=rows(MAPPING, R1={"legacy_fields": "NOPE"}))
        self.fails(mapping=rows(MAPPING, R1={"iso_path": "NoSuch"}))
        self.fails(mapping=rows(MAPPING, R1={"transform": "magic"}))
        self.fails(mapping=rows(MAPPING, R5={"legacy_fields": "L1"}))
        self.fails(mapping=rows(MAPPING, R1={"legacy_fields": "NM|L1"}))
        self.fails(mapping=rows(MAPPING, R4={"param": "nope"}))
        self.fails(mapping=rows(MAPPING, R6={"param": ""}))
        self.fails(mapping=rows(MAPPING, R7={"iso_path": "Nm"}))
        self.fails(mapping=rows(MAPPING, R2={"iso_path": "Nm"}))
        self.fails(mapping=rows(MAPPING, R2={"row_id": "R1"}))
        self.fails(mapping=[])

    def test_bad_catalogues_and_tables(self):
        self.fails(legacy=rows(LEGACY, NM={"max_len": "ten"}))
        self.fails(legacy=rows(LEGACY, NM={"max_len": "0"}))
        self.fails(legacy=rows(LEGACY, CD={"codes": ""}))
        self.fails(legacy=rows(LEGACY, NM={"kind": "blob"}))
        self.fails(iso=rows(ISO, Nm={"mandatory": "maybe"}))
        self.fails(iso=rows(ISO, Code={"codes": ""}))
        self.fails(tables=["not", "a", "table"])
        self.fails(tables={"cd": {"A": 1}})


class CoverageAndProbeTests(unittest.TestCase):
    def test_coverage_reports_unseen_codes_combinations_and_blank_rows(self):
        legacy = LEGACY + [{"field": "C2", "max_len": "1", "kind": "code", "codes": "X|Y"}]
        b = bundle(legacy=legacy)
        cov = tool.coverage([dict(GOOD_SOURCE, C2="X"), dict(GOOD_SOURCE, CD="B", C2="Y", L1="", L2="")], b)
        self.assertEqual(cov["codes_unseen"], [])
        self.assertEqual((cov["combos"]["missing"], cov["combos"]["total"], cov["combos"]["examples"]), (2, 4, "A/Y, B/X"))
        self.assertEqual(cov["blank_rows"], [])
        only_a = tool.coverage([dict(GOOD_SOURCE, L1="", L2="")], b)
        self.assertEqual(only_a["blank_rows"], ["R5"])
        self.assertEqual(only_a["codes_unseen"], ["CD=B", "C2=X", "C2=Y"])

    def test_probes_fill_every_field_and_cycle_the_codes(self):
        probes = tool.probe_messages(bundle())
        self.assertEqual([p["pair_id"] for p in probes], ["P1", "P2"])
        for p in probes:
            self.assertEqual({k: len(v) for k, v in p["source"].items()}, {s["field"]: int(s["max_len"]) for s in LEGACY})
        self.assertEqual([p["source"]["CD"] for p in probes], ["A", "B"])
        self.assertEqual(probes, tool.probe_messages(bundle()))

    def test_probes_match_the_boundary_messages_in_the_data(self):
        import json
        probes = tool.probe_messages(tool.load_bundle(DATA))
        with open(os.path.join(DATA, "legacy_messages.json"), encoding="utf-8") as fh:
            messages = json.load(fh)
        self.assertEqual({p["pair_id"]: p["source"] for p in probes}, {k: v for k, v in messages.items() if k.startswith("P")})


class SafeTests(unittest.TestCase):
    def test_control_characters_become_visible(self):
        self.assertEqual(tool.safe("a\nb\x1b[31mc\r"), "a\\u000ab\\u001b[31mc\\u000d")
        self.assertEqual(tool.safe("plain 100%"), "plain 100%")


if __name__ == "__main__":
    unittest.main()
