import unittest

import _bootstrap  # noqa: F401
import payment_repair as pr
from support import CREDITOR_IBAN, DEBTOR_IBAN, GOOD, UETR_OK, approval, msg, refs


class RouteTests(unittest.TestCase):
    def test_complete_message_passes_untouched(self):
        m = msg()
        r = pr.repair_message(m, refs())
        self.assertEqual(r["route"], "PASS")
        self.assertIs(r["message"], m)
        self.assertEqual(r["edits"], [])

    def test_auto_tier_is_applied_without_a_person(self):
        r = pr.repair_message(msg(NB=None), refs())
        self.assertEqual(r["route"], "REPAIRED")
        self.assertIsNone(r["approver"])
        self.assertEqual(r["message"][pr.NB], "1")

    def test_debtor_bic_and_name_come_from_the_banks_own_tables(self):
        r = pr.repair_message(msg(DBTR_BIC=None, DBTR_NM=""), refs())
        self.assertEqual(r["route"], "REPAIRED")
        self.assertEqual(r["message"][pr.DBTR_BIC], "AAAADEFFXXX")
        self.assertEqual(r["message"][pr.DBTR_NM], "Debtor Co GmbH")

    def test_creditor_bic_waits_for_a_person_and_nothing_is_applied(self):
        m = msg(CDTR_BIC=None)
        r = pr.repair_message(m, refs())
        self.assertEqual(r["route"], "HOLD")
        self.assertEqual(r["edits"][0]["new"], "BBBBFR22XXX")
        self.assertIs(r["message"], m)
        self.assertNotIn(pr.CDTR_BIC, m)
        self.assertEqual(len(r["digest"]), 64)

    def test_malformed_bic_is_repaired_like_a_missing_one(self):
        r = pr.repair_message(msg(CDTR_BIC="bbbb"), refs())
        self.assertEqual(r["route"], "HOLD")
        self.assertEqual(r["edits"][0]["kind"], "malformed")
        self.assertEqual(r["edits"][0]["old"], "bbbb")

    def test_never_tier_fields_return_the_message_untouched(self):
        for change in ({"CDTR_NM": None}, {"CCY": None}, {"AMT": ""}, {"CDTR_IBAN": None}, {"DBTR_IBAN": None}, {"E2E": None}):
            m = msg(**change)
            r = pr.repair_message(m, refs())
            self.assertEqual(r["route"], "RETURN", change)
            self.assertIs(r["message"], m)
            self.assertEqual(r["edits"], [])

    def test_placeholder_creditor_name_is_returned_not_filled(self):
        r = pr.repair_message(msg(CDTR_NM="N/A"), refs())
        self.assertEqual(r["route"], "RETURN")
        self.assertIn("beneficiary name", r["refusals"][0]["reason"])

    def test_one_refusal_returns_the_whole_message_with_no_partial_repair(self):
        r = pr.repair_message(msg(NB=None, CCY=None), refs())
        self.assertEqual(r["route"], "RETURN")
        self.assertEqual(r["edits"], [])
        self.assertEqual([f["path"] for f in r["refusals"]], [pr.CCY])

    def test_bic_needs_exactly_one_active_row_in_the_same_country(self):
        two = [{"country": "FR", "bank_code": "90000002", "bic": "BBBBFR22XXX", "status": "active"},
               {"country": "FR", "bank_code": "90000002", "bic": "CCCCFR22XXX", "status": "active"}]
        retired = [{"country": "FR", "bank_code": "90000002", "bic": "BBBBFR22XXX", "status": "retired"}]
        other_country = [{"country": "DE", "bank_code": "90000002", "bic": "BBBBDE22XXX", "status": "active"}]
        for rows, word in ((two, "2 active"), (retired, "no active"), (other_country, "no active"), ([], "no active")):
            r = pr.repair_message(msg(CDTR_BIC=None), refs(directory=rows))
            self.assertEqual(r["route"], "RETURN", word)
            self.assertIn(word, r["refusals"][0]["reason"])

    def test_retired_row_next_to_an_active_one_is_ignored(self):
        rows = [{"country": "FR", "bank_code": "90000002", "bic": "OLDDFR22XXX", "status": "retired"},
                {"country": "FR", "bank_code": "90000002", "bic": "BBBBFR22XXX", "status": "active"}]
        r = pr.repair_message(msg(CDTR_BIC=None), refs(directory=rows))
        self.assertEqual(r["edits"][0]["new"], "BBBBFR22XXX")

    def test_debtor_name_refuses_joint_closed_and_unknown_accounts(self):
        joint = [{"iban": DEBTOR_IBAN, "customer_id": "CU-1", "name": "A", "account_ccy": "EUR", "status": "open"},
                 {"iban": DEBTOR_IBAN, "customer_id": "CU-2", "name": "B", "account_ccy": "EUR", "status": "open"}]
        closed = [{"iban": DEBTOR_IBAN, "customer_id": "CU-1", "name": "A", "account_ccy": "EUR", "status": "closed"}]
        for rows, word in ((joint, "2 holders"), (closed, "not open"), ([], "no customer master")):
            r = pr.repair_message(msg(DBTR_NM=None), refs(master=rows))
            self.assertEqual(r["route"], "RETURN", word)
            self.assertIn(word, r["refusals"][0]["reason"])

    def test_derivations_need_a_usable_source_field(self):
        r = pr.repair_message(msg(CDTR_IBAN=None, CDTR_BIC=None, CDTR_CTRY=None), refs())
        self.assertEqual(r["route"], "RETURN")
        self.assertEqual(len(r["refusals"]), 3)

    def test_table_value_that_is_itself_unusable_is_refused(self):
        rows = [{"country": "FR", "bank_code": "90000002", "bic": "bad", "status": "active"}]
        r = pr.repair_message(msg(CDTR_BIC=None), refs(directory=rows))
        self.assertEqual(r["route"], "RETURN")

    def test_uetr_and_charge_bearer_come_only_from_one_payment_order(self):
        r = pr.repair_message(msg(UETR=None, CHRG=None), refs())
        self.assertEqual(r["route"], "HOLD")
        self.assertEqual({e["path"]: e["new"] for e in r["edits"]}, {pr.UETR: UETR_OK, pr.CHRG: "SHAR"})
        order = {"end_to_end_id": "E2E-1", "uetr": UETR_OK, "charge_bearer": "SHAR", "initiator_id": "U-2001"}
        for rows in ([], [order, dict(order, uetr="22222222-2222-4333-8444-555555555555")]):
            r = pr.repair_message(msg(UETR=None), refs(orders=rows))
            self.assertEqual(r["route"], "RETURN")

    def test_creditor_country_is_taken_from_the_iban_prefix_and_needs_approval(self):
        r = pr.repair_message(msg(CDTR_CTRY=None), refs())
        self.assertEqual(r["route"], "HOLD")
        self.assertEqual(r["edits"][0]["new"], CREDITOR_IBAN[:2])

    def test_repair_is_idempotent(self):
        r = pr.repair_message(msg(DBTR_BIC=None), refs())
        again = pr.repair_message(r["message"], refs())
        self.assertEqual(again["route"], "PASS")

    def test_input_message_is_not_mutated(self):
        m = msg(NB=None)
        pr.repair_message(m, refs())
        self.assertNotIn(pr.NB, m)


class DigestAndApprovalTests(unittest.TestCase):
    def hold(self, **changes):
        return pr.repair_message(msg(**(changes or {"CDTR_BIC": None})), refs())

    def test_digest_is_stable_and_binds_the_message(self):
        a, b = self.hold(), self.hold()
        self.assertEqual(a["digest"], b["digest"])
        c = pr.repair_message(msg(CDTR_BIC=None, RMT="changed"), refs())
        self.assertNotEqual(a["digest"], c["digest"])

    def test_valid_approval_applies_every_change(self):
        h = self.hold(CDTR_BIC=None, NB=None)
        r = pr.repair_message(msg(CDTR_BIC=None, NB=None), refs(), [approval(h)])
        self.assertEqual(r["route"], "REPAIRED")
        self.assertEqual(r["approver"], "U-1041")
        self.assertEqual(r["message"][pr.NB], "1")
        self.assertEqual(r["message"][pr.CDTR_BIC], "BBBBFR22XXX")

    def test_each_bad_approval_leaves_the_message_on_hold_with_a_reason(self):
        h = self.hold()
        cases = [
            (approval(h, digest="0" * 64), "different plan"),
            (approval(h, approver="nobody"), "not in the registry"),
            (approval(h, approver="A-7001"), "agent"),
            (approval(h, approver="U-1044"), "not active"),
            (approval(h, approver="U-2001"), "reviewer role"),
        ]
        for a, word in cases:
            r = pr.repair_message(msg(CDTR_BIC=None), refs(), [a])
            self.assertEqual(r["route"], "HOLD", word)
            self.assertIn(word, r["hold_reason"])
            self.assertNotIn(pr.CDTR_BIC, r["message"])

    def test_the_person_who_entered_the_order_cannot_approve(self):
        orders = [{"end_to_end_id": "E2E-1", "uetr": UETR_OK, "charge_bearer": "SHAR", "initiator_id": "U-1041"}]
        h = pr.repair_message(msg(CDTR_BIC=None), refs(orders=orders))
        r = pr.repair_message(msg(CDTR_BIC=None), refs(orders=orders), [approval(h, "U-1041")])
        self.assertEqual(r["route"], "HOLD")
        self.assertIn("entered the payment order", r["hold_reason"])
        ok = pr.repair_message(msg(CDTR_BIC=None), refs(orders=orders), [approval(h, "U-1042")])
        self.assertEqual(ok["route"], "REPAIRED")

    def test_unknown_initiator_blocks_approval(self):
        for orders in ([], [{"end_to_end_id": "E2E-1", "uetr": UETR_OK, "charge_bearer": "SHAR", "initiator_id": " "}]):
            h = pr.repair_message(msg(CDTR_BIC=None), refs(orders=orders))
            r = pr.repair_message(msg(CDTR_BIC=None), refs(orders=orders), [approval(h)])
            self.assertEqual(r["route"], "HOLD")
            self.assertIn("four-eyes cannot be checked", r["hold_reason"])

    def test_approval_does_not_survive_a_change_to_the_message(self):
        h = self.hold()
        r = pr.repair_message(msg(CDTR_BIC=None, RMT="edited later"), refs(), [approval(h)])
        self.assertEqual(r["route"], "HOLD")

    def test_a_reviewer_can_reject_and_the_message_goes_back(self):
        h = self.hold()
        r = pr.repair_message(msg(CDTR_BIC=None), refs(), [approval(h, decision="reject")])
        self.assertEqual(r["route"], "RETURN")
        self.assertEqual(r["edits"], [])

    def test_a_later_valid_approval_counts_after_an_invalid_one(self):
        h = self.hold()
        r = pr.repair_message(msg(CDTR_BIC=None), refs(), [approval(h, "A-7001"), approval(h, "U-1042")])
        self.assertEqual(r["route"], "REPAIRED")
        self.assertEqual(r["approver"], "U-1042")

    def test_approval_for_an_auto_only_plan_is_not_needed(self):
        results, unused = pr.repair_all([msg(NB=None)], refs(), [{"msg_id": "M-1", "plan_digest": "x", "approver_id": "U-1041", "decision": "approve"}])
        self.assertEqual(results[0]["route"], "REPAIRED")
        self.assertEqual(unused, {"no_message": 0, "not_needed": 1})

    def test_approval_naming_no_message_is_counted(self):
        _, unused = pr.repair_all([msg()], refs(), [{"msg_id": "M-404", "plan_digest": "x", "approver_id": "U-1041", "decision": "approve"}])
        self.assertEqual(unused["no_message"], 1)


class AuditTests(unittest.TestCase):
    def test_one_row_per_applied_change_with_the_approver_only_on_approval_tier(self):
        h = pr.repair_message(msg(CDTR_BIC=None, NB=None), refs())
        r = pr.repair_message(msg(CDTR_BIC=None, NB=None), refs(), [approval(h)])
        rows = pr.audit_rows([r])
        self.assertEqual(len(rows), 2)
        who = {row[1]: row[7] for row in rows}
        self.assertEqual(who, {pr.NB: "(rule)", pr.CDTR_BIC: "U-1041"})

    def test_nothing_applied_means_no_rows(self):
        self.assertEqual(pr.audit_rows([pr.repair_message(msg(CDTR_BIC=None), refs())]), [])

    def test_formula_cells_are_neutralised(self):
        self.assertEqual(pr.csv_safe("=1+1"), "'=1+1")
        self.assertEqual(pr.csv_safe("-5"), "'-5")
        self.assertEqual(pr.csv_safe("-"), "-")
        self.assertEqual(pr.csv_safe(None), "")

    def test_clean_escapes_control_and_non_ascii_characters(self):
        self.assertEqual(pr.clean("a\nb\x1b​é"), "a\\x0ab\\x1b\\u200b\\xe9")
        self.assertEqual(pr.clean("x" * 200, 10), "xxxxxxx...")


class SanityTests(unittest.TestCase):
    def test_fixture_is_a_complete_message(self):
        self.assertEqual(set(GOOD) - {pr.MSG_ID}, set(pr.REQUIRED) | set(pr.OPTIONAL))


if __name__ == "__main__":
    unittest.main()
