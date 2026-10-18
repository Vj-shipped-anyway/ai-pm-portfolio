import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover
from agentkit.errors import GateViolation, NotFoundError, RecordInvalid
from agentkit.gates import Approval
from agentkit.matching import AMBIGUOUS, CLOSE, EXACT, MISMATCH
from agentkit.reasoning_stub import StubReasoner
from agentkit.skills import SKILLS
from agentkit.skills.draft_correction import check_draft
from agentkit.skills.open_exception import validate_exception


def upto(k, case_id, last, mode_steps=None):
    """Run S01..last on a fresh context through the orchestrator's guarded runner."""
    ctx = k.orchestrator.new_context(case_id)
    for s in ["S01", "S02", "S03", "S04", "S05", "S06", "S08"]:
        k.orchestrator.run_step(s, ctx)
        if s == last:
            break
    return ctx


class TestSkillRegistry(unittest.TestCase):
    def test_skills_exist_for_every_agent_step_and_none_for_person_steps(self):
        self.assertEqual(sorted(SKILLS), ["S01", "S02", "S03", "S04", "S05", "S06", "S08", "S10", "S11", "S12"])
        self.assertNotIn("S07", SKILLS)
        self.assertNotIn("S09", SKILLS)


class TestS01(unittest.TestCase):
    def test_opens_a_valid_exception(self):
        k, _ = support.kit()
        ctx = k.orchestrator.new_context("G01")
        res = k.orchestrator.run_step("S01", ctx)
        self.assertEqual(res.decision, "opened")
        self.assertEqual(ctx.exception["exception_ref"], "EX-1")

    def test_blank_field_is_rejected(self):
        self.assertTrue(validate_exception({"case_id": "C", "exception_ref": "E", "payment_id": "",
                                            "reason_code": "RX01", "returned_name": "N", "amount": "5"}))

    def test_bad_amount_is_rejected(self):
        p = validate_exception({"case_id": "C", "exception_ref": "E", "payment_id": "P", "reason_code": "RX01",
                                "returned_name": "N", "amount": "12,5O"})
        self.assertIn("amount is not a number", p)

    def test_malformed_record_raises(self):
        k, _ = support.kit()
        ctx = k.orchestrator.new_context("G09")
        with self.assertRaises(RecordInvalid):
            k.orchestrator.run_step("S01", ctx)

    def test_second_delivery_of_the_same_exception_is_a_duplicate(self):
        k, _ = support.kit()
        k.orchestrator.run_case("G01")
        ctx = k.orchestrator.new_context("G13")
        res = k.orchestrator.run_step("S01", ctx)
        self.assertEqual(res.decision, "duplicate_delivery")
        self.assertEqual(ctx.disposition, "DUPLICATE_CLOSED")
        self.assertEqual(ctx.facts["duplicate_of"], "G01")

    def test_shadow_mode_does_not_open_a_case_in_the_system(self):
        k, _ = support.kit()
        k.orchestrator.run_step("S01", k.orchestrator.new_context("G01"))
        self.assertEqual(k.env.cases, {})

    def test_live_mode_opens_the_case(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.run_step("S01", k.orchestrator.new_context("G01"))
        self.assertIn("G01", k.env.cases)


class TestS02(unittest.TestCase):
    def test_repairable_code(self):
        k, _ = support.kit()
        ctx = upto(k, "G01", "S02")
        self.assertEqual(ctx.rule["repair_rule"], "FIX_ACCOUNT")
        self.assertIsNone(ctx.disposition)

    def test_not_repairable_code_returns_to_originator(self):
        k, _ = support.kit()
        ctx = upto(k, "G06", "S02")
        self.assertEqual(ctx.disposition, "RETURN_TO_ORIGINATOR")
        self.assertTrue(ctx.early_return)

    def test_unknown_code_is_a_malformed_record(self):
        k, _ = support.kit()
        with self.assertRaises(RecordInvalid):
            upto(k, "G10", "S02")


class TestS03(unittest.TestCase):
    def test_finds_the_payment(self):
        k, _ = support.kit()
        ctx = upto(k, "G01", "S03")
        self.assertEqual(ctx.payment["payment_id"], "P-1")

    def test_orphan_payment_is_a_malformed_record(self):
        k, _ = support.kit()
        with self.assertRaises(RecordInvalid):
            upto(k, "G11", "S03")


class TestS04(unittest.TestCase):
    def test_copies_the_five_fields(self):
        k, _ = support.kit()
        ctx = upto(k, "G01", "S04")
        self.assertEqual(sorted(ctx.worksheet), ["amount", "beneficiary_account", "beneficiary_bank_code",
                                                 "beneficiary_name", "currency"])

    def test_leading_zero_account_survives_the_copy(self):
        k, _ = support.kit()
        ctx = upto(k, "G14", "S04")
        self.assertEqual(ctx.worksheet["beneficiary_account"], support.ZERO_ACCT)
        self.assertTrue(ctx.worksheet["beneficiary_account"].startswith("0"))

    def test_a_copy_that_differs_from_the_source_is_caught(self):
        k, _ = support.kit(mode="live")
        tool = k.registry.tools["worksheet"]
        original = tool.handlers["write_fields"]
        # a worksheet that stores numbers as numbers: it drops the leading zero whatever the caller asked for
        tool.handlers["write_fields"] = lambda case_id, fields, as_text=False: original(case_id, fields, False)
        with self.assertRaises(RecordInvalid) as cm:
            upto(k, "G14", "S04")
        self.assertIn("beneficiary_account", str(cm.exception))


class TestS05(unittest.TestCase):
    def test_exact_and_close_continue(self):
        k, _ = support.kit()
        self.assertEqual(upto(k, "G02", "S05").name_class, EXACT)
        self.assertEqual(upto(k, "G03", "S05").name_class, CLOSE)

    def test_ambiguous_needs_a_judgment(self):
        k, _ = support.kit()
        ctx = upto(k, "G04", "S05")
        self.assertEqual(ctx.name_class, AMBIGUOUS)
        self.assertTrue(ctx.needs_judgment)
        self.assertIsNone(ctx.disposition)

    def test_mismatch_on_a_name_reason_returns_to_originator(self):
        k, _ = support.kit()
        ctx = upto(k, "G05", "S05")
        self.assertEqual(ctx.name_class, MISMATCH)
        self.assertEqual(ctx.disposition, "RETURN_TO_ORIGINATOR")

    def test_payment_account_check_digit_is_recorded(self):
        k, _ = support.kit()
        self.assertFalse(upto(k, "G01", "S05").facts["payment_account_check_digit_ok"])


class TestS06(unittest.TestCase):
    def test_no_hit_for_a_clean_party(self):
        k, _ = support.kit()
        ctx = upto(k, "G01", "S06")
        self.assertEqual(ctx.hits, [])
        self.assertIsNone(ctx.disposition)

    def test_hit_escalates_and_is_logged(self):
        k, _ = support.kit()
        ctx = upto(k, "G08", "S06")
        self.assertEqual(ctx.disposition, "ESCALATE_COMPLIANCE")
        self.assertEqual(ctx.hits[0]["party_id"], "W-001")
        logged = [e for e in k.audit.events("G08") if e["kind"] == "decision" and e["step"] == "S06"]
        self.assertEqual(logged[0]["detail"]["decision"], "watchlist_hit")
        self.assertEqual(logged[0]["detail"]["hits"][0]["party_id"], "W-001")

    def test_both_names_are_screened(self):
        k, _ = support.kit()
        upto(k, "G02", "S06")
        calls = [e for e in k.audit.events("G02") if e["kind"] == "tool_call" and e["detail"]["tool"] == "watchlist"]
        self.assertEqual(len(calls), 2)


class TestS08(unittest.TestCase):
    def test_stub_drafts_a_correction_with_a_digest(self):
        k, _ = support.kit()
        ctx = upto(k, "G01", "S08")
        self.assertEqual((ctx.draft.field, ctx.draft.new_value), ("beneficiary_account", support.RIGHT))
        self.assertTrue(ctx.draft.stub)
        self.assertIn("[STUB]", ctx.draft.message)
        self.assertEqual(len(ctx.draft.digest), 16)

    def test_bank_code_correction(self):
        k, _ = support.kit()
        ctx = upto(k, "G07", "S08")
        self.assertEqual((ctx.draft.field, ctx.draft.new_value), ("beneficiary_bank_code", "SYNB4242"))

    def test_a_draft_that_fails_the_rule_check_is_not_shown(self):
        k, _ = support.kit()
        with self.assertRaises(RecordInvalid):
            upto(k, "G12", "S08")

    def test_check_draft_rules(self):
        stub = StubReasoner()
        pay = support.payment("P-1", account=support.WRONG)
        rule = support.REASON_CODES["RX01"]
        good = stub.draft_correction(case_id="C", reason_code="RX01", rule=rule, payment=pay,
                                     advised_value=support.RIGHT, name_class="EXACT", name_score=1.0)
        self.assertEqual(check_draft(good, rule, pay), [])
        same = stub.draft_correction(case_id="C", reason_code="RX01", rule=rule, payment=pay,
                                     advised_value=support.WRONG, name_class="EXACT", name_score=1.0)
        self.assertTrue(check_draft(same, rule, pay))
        wrong_field = stub.draft_correction(case_id="C", reason_code="RX02",
                                            rule=support.REASON_CODES["RX02"], payment=pay,
                                            advised_value="Quillax Marine", name_class="MISMATCH", name_score=0.1)
        self.assertTrue(check_draft(wrong_field, rule, pay))
        name_rule = support.REASON_CODES["RX02"]
        bad_name = stub.draft_correction(case_id="C", reason_code="RX02", rule=name_rule, payment=pay,
                                         advised_value="Quillax Marine Systems", name_class="MISMATCH",
                                         name_score=0.1)
        self.assertTrue(check_draft(bad_name, name_rule, pay))


class TestS10(unittest.TestCase):
    def _ready(self):
        k, _ = support.kit(mode="live")
        ctx = upto(k, "G01", "S08")
        return k, ctx

    def test_refuses_without_an_approval(self):
        k, ctx = self._ready()
        with self.assertRaises(GateViolation):
            k.orchestrator.run_step("S10", ctx)
        self.assertEqual(k.env.ledger, [])
        self.assertIn("gate_violation", [e["kind"] for e in k.audit.events("G01")])

    def test_refuses_an_approval_for_another_correction(self):
        k, ctx = self._ready()
        ctx.approval = Approval(True, "person:r1", "payments_operations_reviewer", "0" * 16)
        with self.assertRaises(GateViolation):
            k.orchestrator.run_step("S10", ctx)
        self.assertEqual(k.env.ledger, [])

    def test_refuses_a_declined_approval(self):
        k, ctx = self._ready()
        ctx.approval = Approval(False, "person:r1", "payments_operations_reviewer", ctx.draft.digest)
        with self.assertRaises(GateViolation):
            k.orchestrator.run_step("S10", ctx)

    def test_runs_once_with_a_valid_approval(self):
        k, ctx = self._ready()
        ctx.approval = Approval(True, "person:r1", "payments_operations_reviewer", ctx.draft.digest)
        res = k.orchestrator.run_step("S10", ctx)
        self.assertEqual(res.decision, "resubmitted")
        self.assertEqual(len(k.env.ledger), 1)
        self.assertEqual(k.env.ledger[0]["payload"]["beneficiary_account"], support.RIGHT)
        self.assertEqual(k.env.ledger[0]["key"], "resubmit:EX-1")


class TestS11S12(unittest.TestCase):
    def test_note_is_labelled_stub(self):
        k, _ = support.kit(mode="live")
        ctx = upto(k, "G01", "S08")
        k.orchestrator.run_step("S11", ctx)
        self.assertIn("[STUB]", k.env.cases["G01"]["notes"][0])
        self.assertIn("no language model wrote this", k.env.cases["G01"]["notes"][0])

    def test_close_case_in_live_mode(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.run_case("G06")
        self.assertEqual(k.env.cases["G06"]["status"], "CLOSED")
        self.assertEqual(k.env.cases["G06"]["disposition"], "RETURN_TO_ORIGINATOR")

    def test_watch_list_hit_is_escalated_not_closed(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.run_case("G08")
        self.assertEqual(k.env.cases["G08"]["status"], "ESCALATED")
        self.assertEqual(k.env.cases["G08"]["queue"], "compliance")
        self.assertEqual(k.env.ledger, [])


if __name__ == "__main__":
    unittest.main()
