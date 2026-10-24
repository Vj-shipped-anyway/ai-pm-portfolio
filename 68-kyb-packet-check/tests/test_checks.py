import unittest

import _bootstrap  # noqa: F401
from fixtures import ENTITY_EXTRACTION, ENTITY_SOURCE, SOURCE, fresh
from kyb_packet_check import (DEFAULT_TOLERANCE, beneficial_owners, check_packet, decide, name_key, ownership,
                              parse_extraction)


def kinds(findings):
    return sorted(f["kind"] for f in findings)


class CleanPackets(unittest.TestCase):
    def test_clean_packet_passes(self):
        self.assertEqual(check_packet(SOURCE, fresh()), [])
        self.assertEqual(decide([]), "PASS")

    def test_entity_with_lookthrough_passes(self):
        self.assertEqual(check_packet(ENTITY_SOURCE, fresh(ENTITY_EXTRACTION)), [])

    def test_name_written_another_way_is_not_flagged(self):
        ex = fresh()
        ex["holders"][0]["name"] = "Whitfield, Dana"          # order changed, initial dropped
        ex["people"][0]["name"] = "Dana Whitfield"
        ex["control_person"]["name"] = "Whitfield, Dana A."
        self.assertEqual(check_packet(SOURCE, ex), [])

    def test_thirds_within_tolerance(self):
        src = SOURCE.replace("60%", "33.33%").replace("25%", "33.33%").replace("15%", "33.33%")
        ex = fresh()
        for h in ex["holders"]:
            h["pct"] = 33.33
        ex["people"].append({"name": "Priya Nair", "address": "1 A St", "dob": "1990-01-01", "id_last4": "1111"})
        src = src.replace("\n\nControl person", "\nPerson: Priya Nair | DOB 1990-01-01 | 1 A St | ID ending 1111\n\nControl person")
        self.assertEqual(check_packet(src, ex), [])
        self.assertEqual(kinds(check_packet(src, ex, tolerance=0, families=("arithmetic",))), ["direct_sum"])


class OwnershipRule(unittest.TestCase):
    def test_exactly_25_percent_is_a_beneficial_owner(self):
        names = [n for n, _ in beneficial_owners(parse_extraction(fresh()))]
        self.assertEqual(names, ["Dana A. Whitfield", "Tomas Reyes"])

    def test_just_under_25_is_not(self):
        ex = fresh()
        ex["holders"][0]["pct"], ex["holders"][1]["pct"], ex["holders"][2]["pct"] = 60.01, 24.99, 15
        names = [n for n, _ in beneficial_owners(parse_extraction(ex))]
        self.assertEqual(names, ["Dana A. Whitfield"])

    def test_direct_and_indirect_holdings_add_up(self):
        eff = dict(ownership(parse_extraction(fresh(ENTITY_EXTRACTION))))
        self.assertEqual(eff["Dana A. Whitfield"], 35.0)       # 15 direct + 50% of 40
        self.assertEqual(eff["Priya Nair"], 20.0)
        names = [n for n, _ in beneficial_owners(parse_extraction(fresh(ENTITY_EXTRACTION)))]
        self.assertEqual(names, ["Tomas Reyes", "Dana A. Whitfield"])

    def test_structure_comes_from_the_kind_field_not_the_name(self):
        ex = fresh()
        ex["holders"][2] = {"name": "Nair Holdings Ltd", "kind": "individual", "pct": 15}   # looks like a company, is marked individual
        ex["holders"][1] = {"name": "Reyes", "kind": "entity", "pct": 25}                    # looks like a person, is marked entity
        f = check_packet(SOURCE, ex, families=("arithmetic",))
        self.assertEqual([x["subject"] for x in f if x["kind"] == "lookthrough_missing"], ["Reyes"])

    def test_entity_below_25_needs_no_lookthrough_and_at_25_does(self):
        ex = fresh()
        ex["holders"] = [{"name": "Dana A. Whitfield", "kind": "individual", "pct": 80},
                         {"name": "Hollis Park Holdings Ltd", "kind": "entity", "pct": 20}]
        self.assertEqual(check_packet(SOURCE, ex, families=("arithmetic",)), [])
        ex["holders"] = [{"name": "Dana A. Whitfield", "kind": "individual", "pct": 75},
                         {"name": "Hollis Park Holdings Ltd", "kind": "entity", "pct": 25}]
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("arithmetic",))), ["lookthrough_missing"])


class Arithmetic(unittest.TestCase):
    def test_total_above_and_below_100(self):
        for pct in (70, 50):
            ex = fresh()
            ex["holders"][0]["pct"] = pct
            self.assertEqual(kinds(check_packet(SOURCE, ex, families=("arithmetic",))), ["direct_sum"])

    def test_tolerance_is_a_parameter(self):
        ex = fresh()
        ex["holders"][2]["pct"] = 14.95
        self.assertEqual(check_packet(SOURCE, ex, tolerance=0.1, families=("arithmetic",)), [])
        self.assertEqual(kinds(check_packet(SOURCE, ex, tolerance=0.01, families=("arithmetic",))), ["direct_sum"])
        self.assertEqual(DEFAULT_TOLERANCE, 0.1)

    def test_out_of_range_percent(self):
        ex = fresh()
        ex["holders"][2]["pct"] = 0
        ex["holders"][0]["pct"] = 130
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("arithmetic",))).count("pct_out_of_range"), 2)

    def test_lookthrough_sum_and_orphan(self):
        ex = fresh(ENTITY_EXTRACTION)
        ex["lookthrough"][1]["pct"] = 30
        self.assertEqual(kinds(check_packet(ENTITY_SOURCE, ex, families=("arithmetic",))), ["lookthrough_sum"])
        ex = fresh(ENTITY_EXTRACTION)
        ex["lookthrough"][0]["entity"] = "Other Holdings Ltd"
        ex["lookthrough"][1]["entity"] = "Other Holdings Ltd"
        self.assertEqual(kinds(check_packet(ENTITY_SOURCE, ex, families=("arithmetic",))), ["lookthrough_missing", "lookthrough_orphan"])

    def test_no_holders(self):
        ex = fresh()
        ex["holders"] = []
        self.assertIn("no_holders", kinds(check_packet(SOURCE, ex)))


class Completeness(unittest.TestCase):
    def test_missing_fields_of_an_owner(self):
        ex = fresh()
        ex["people"][1]["dob"] = ""
        del ex["people"][1]["id_last4"]
        f = check_packet(SOURCE, ex, families=("completeness",))
        self.assertEqual(kinds(f), ["person_field_missing", "person_field_missing"])
        self.assertEqual({x["subject"] for x in f}, {"Tomas Reyes"})

    def test_owner_without_a_details_record(self):
        ex = fresh()
        ex["people"] = ex["people"][:1]
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("completeness",))), ["person_record_missing"])

    def test_minority_owner_needs_no_details(self):
        self.assertEqual(check_packet(SOURCE, fresh(), families=("completeness",)), [])      # Priya Nair has 15 percent, no record

    def test_control_person_missing_and_needs_details(self):
        ex = fresh()
        ex["control_person"] = None
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("completeness",))), ["control_person_missing"])
        ex["control_person"] = {"name": "Priya Nair", "title": "Manager"}
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("completeness",))), ["person_record_missing"])

    def test_certification_gaps(self):
        for cert in (None, {"signed_by": "", "date": "2026-03-02"}, {"signed_by": "Dana A. Whitfield"}):
            ex = fresh()
            ex["certification"] = cert
            self.assertEqual(kinds(check_packet(SOURCE, ex, families=("completeness",))), ["certification_incomplete"])

    def test_legal_name_and_blank_holder_name(self):
        ex = fresh()
        ex["legal_name"] = ""
        ex["holders"][2]["name"] = " "
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("completeness",))), ["legal_name_missing", "name_missing"])


class Grounding(unittest.TestCase):
    def test_swapped_percents_add_up_but_are_not_in_the_source(self):
        ex = fresh()
        ex["holders"][0]["pct"], ex["holders"][1]["pct"] = 25, 60
        self.assertEqual(check_packet(SOURCE, ex, families=("arithmetic",)), [])
        f = check_packet(SOURCE, ex, families=("grounding",))
        self.assertEqual(kinds(f), ["pct_not_in_source", "pct_not_in_source"])
        self.assertIn("source line shows 60%", f[0]["detail"])

    def test_decimal_slip(self):
        ex = fresh()
        ex["holders"][1]["pct"] = 2.5
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("grounding",))), ["pct_not_in_source"])

    def test_misread_name_is_reported_once(self):
        ex = fresh()
        ex["holders"][1]["name"] = "Tomas Reyez"
        ex["people"][1]["name"] = "Tomas Reyez"
        f = check_packet(SOURCE, ex, families=("grounding",))
        self.assertEqual(kinds(f), ["name_not_in_source"])

    def test_detail_checks_do_not_echo_personal_values(self):
        ex = fresh()
        ex["people"][0]["dob"] = "1981-14-05"
        ex["people"][1]["address"] = "10 Elm Road, Lakeside TX 75001"
        ex["people"][1]["id_last4"] = "9999"
        f = check_packet(SOURCE, ex, families=("grounding",))
        self.assertEqual(kinds(f), ["detail_not_in_source"] * 3)
        text = " ".join(x["subject"] + x["detail"] for x in f)
        for secret in ("1981-14-05", "10 Elm", "9999"):
            self.assertNotIn(secret, text)

    def test_percent_of_another_holder_does_not_ground(self):
        ex = fresh()
        ex["holders"][1]["pct"] = 15        # 15 is on Priya Nair's line, not on Tomas Reyes's
        self.assertEqual(kinds(check_packet(SOURCE, ex, families=("grounding",))), ["pct_not_in_source"])

    def test_direct_percent_is_not_grounded_on_a_lookthrough_line(self):
        ex = fresh(ENTITY_EXTRACTION)
        ex["holders"][1]["pct"] = 50        # the entity line says 40; 50 appears only on look-through lines naming it
        f = check_packet(ENTITY_SOURCE, ex, families=("grounding",))
        self.assertEqual([x["subject"] for x in f], ["Hollis Park Holdings Ltd"])

    def test_lookthrough_percent(self):
        ex = fresh(ENTITY_EXTRACTION)
        ex["lookthrough"][0]["pct"] = 60
        f = check_packet(ENTITY_SOURCE, ex, families=("grounding",))
        self.assertEqual([x["subject"] for x in f], ["Dana A. Whitfield (look-through)"])

    def test_source_without_any_percent_says_so(self):
        src = SOURCE.replace("%", " percent")
        f = check_packet(src, fresh(), families=("grounding",))
        self.assertEqual(kinds(f), ["pct_not_in_source"] * 3)
        self.assertTrue(all("no percent figure" in x["detail"] for x in f))

    def test_name_key_ignores_initials_and_order(self):
        self.assertEqual(name_key("Dana A. Whitfield"), name_key("Whitfield, Dana"))
        self.assertNotEqual(name_key("Dana Whitfield"), name_key("Dana Whitfeld"))


if __name__ == "__main__":
    unittest.main()
