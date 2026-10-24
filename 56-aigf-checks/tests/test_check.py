import unittest

import _bootstrap  # noqa: F401
import aigf_checks as ac


def risk(rid, *aspects):
    return {"risk_id": rid, "title": "t", "aspects": frozenset(aspects)}


def check(cid, *aspects):
    return {"check_id": cid, "project": "p", "command": "c", "exercises": frozenset(aspects)}


def row(rid="ROW-1", risk_id="R-1", check_id="C-1", covers="full", label="caught", value="25 of 25", note=""):
    return {"row_id": rid, "risk_id": risk_id, "check_id": check_id, "covers": covers,
            "claim_label": label, "claim_value": value, "note": note}


RISKS = {"R-1": risk("R-1", "a", "b"), "R-2": risk("R-2", "a"), "R-3": risk("R-3", "z")}
CHECKS = {"C-1": check("C-1", "a", "b"), "C-2": check("C-2", "a")}
OUTPUTS = {"C-1": "CHECK C-1\n  caught: 25 of 25\n  Big Count  :   1,200 of 1,500\n  time: 10:30\n", "C-2": "  caught: 3 of 4\n"}


def kinds(rows):
    result = ac.analyze(RISKS, CHECKS, rows, OUTPUTS)
    return [f["kind"] for f in result["findings"]], result


class NormalizeTests(unittest.TestCase):
    def test_label_and_value_set_aside_case_spacing_and_separators(self):
        self.assertEqual(ac.norm_label("  Big   Count "), "big count")
        self.assertEqual(ac.norm_value("1,200 of 1,500."), "1200 of 1500")
        self.assertEqual(ac.norm_value("94.2%"), "94.2%")

    def test_printed_lines_split_on_the_first_colon_only(self):
        lines = ac.printed_lines(OUTPUTS["C-1"])
        self.assertIn(("time", "10:30"), lines)
        self.assertNotIn("check c-1", [lab for lab, _ in lines])

    def test_lines_without_a_value_are_ignored(self):
        self.assertEqual(ac.printed_lines("heading:\n: orphan\nno colon here\n"), [])


class FindingTests(unittest.TestCase):
    def test_a_row_that_holds_has_no_finding_and_the_risk_is_checked(self):
        k, result = kinds([row()])
        self.assertEqual(k, [])
        self.assertEqual(result["risk_status"]["R-1"], "CHECKED")

    def test_stale_value(self):
        k, _ = kinds([row(value="24 of 25")])
        self.assertEqual(k, ["stale_value"])

    def test_a_short_number_is_not_found_inside_a_longer_one(self):
        k, _ = kinds([row(value="5 of 25")])
        self.assertEqual(k, ["stale_value"])

    def test_format_differences_are_not_findings(self):
        k, _ = kinds([row(label="BIG count", value="1200 of 1500")])
        self.assertEqual(k, [])

    def test_label_missing_even_when_the_number_is_printed_elsewhere(self):
        k, _ = kinds([row(label="renamed line", value="25 of 25")])
        self.assertEqual(k, ["label_missing"])

    def test_no_output_is_reported_not_skipped(self):
        outputs = {"C-2": OUTPUTS["C-2"]}
        result = ac.analyze(RISKS, CHECKS, [row()], outputs)
        self.assertEqual([f["kind"] for f in result["findings"]], ["no_output"])

    def test_unknown_risk_and_unknown_check(self):
        k, _ = kinds([row(rid="ROW-1", risk_id="R-9"), row(rid="ROW-2", check_id="C-9", label="other")])
        self.assertEqual(k, ["unknown_risk", "unknown_check"])

    def test_duplicate_ignores_case_and_spacing_of_the_label(self):
        k, _ = kinds([row(rid="ROW-1"), row(rid="ROW-2", label=" CAUGHT ")])
        self.assertEqual(k, ["duplicate_row"])

    def test_two_labels_on_the_same_pair_are_not_duplicates(self):
        k, _ = kinds([row(rid="ROW-1"), row(rid="ROW-2", label="big count", value="1200 of 1500")])
        self.assertEqual(k, [])

    def test_aspect_gap_for_full_and_for_partial_without_overlap(self):
        k, _ = kinds([row(rid="ROW-1", check_id="C-2", value="3 of 4"),
                      row(rid="ROW-2", risk_id="R-3", covers="partial", check_id="C-2", value="3 of 4")])
        self.assertEqual(k, ["aspect_gap", "aspect_gap"])

    def test_an_honest_partial_row_is_not_a_finding(self):
        k, result = kinds([row(check_id="C-2", covers="partial", value="3 of 4")])
        self.assertEqual(k, [])
        self.assertEqual(result["risk_status"]["R-1"], "PARTIAL")


class WordingTests(unittest.TestCase):
    def test_overclaim_words_are_found(self):
        for note in ("Compliant with the rule.", "Certified coverage.", "The check guarantees it.", "Certification done."):
            self.assertEqual(kinds([row(note=note)])[0], ["overclaim_wording"], note)

    def test_non_compliant_is_not_an_overclaim(self):
        self.assertEqual(kinds([row(note="Lists non-compliant rows. Non-Compliant ones too.")])[0], [])

    def test_known_limit_other_words_pass(self):
        self.assertEqual(kinds([row(note="Fully satisfies the requirement.")])[0], [])

    def test_known_limit_declared_aspects_are_taken_as_written(self):
        declared_all = {"C-3": check("C-3", "a", "b")}
        result = ac.analyze(RISKS, declared_all, [row(check_id="C-3")], {"C-3": OUTPUTS["C-1"]})
        self.assertEqual(result["findings"], [])


class StatusTests(unittest.TestCase):
    def test_gap_unverified_partial(self):
        rows = [row(rid="ROW-1", risk_id="R-2", value="2 of 25"), row(rid="ROW-2", risk_id="R-1", check_id="C-2", covers="partial", value="3 of 4")]
        _, result = kinds(rows)
        self.assertEqual(result["risk_status"], {"R-1": "PARTIAL", "R-2": "UNVERIFIED", "R-3": "GAP"})

    def test_a_row_with_a_stale_claim_does_not_count_as_checked(self):
        _, result = kinds([row(value="24 of 25")])
        self.assertEqual(result["risk_status"]["R-1"], "UNVERIFIED")

    def test_claims_compared_counts_rows_whose_label_was_found(self):
        _, result = kinds([row(rid="ROW-1"), row(rid="ROW-2", label="nothing")])
        self.assertEqual(result["compared"], 1)


if __name__ == "__main__":
    unittest.main()
