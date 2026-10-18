import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover
from agentkit.brief import derive_config
from agentkit.errors import BriefError, GateViolation
from agentkit.gates import Approval
from agentkit.kit import build_kit


class TestGatesInShadowMode(unittest.TestCase):
    def test_every_resubmit_proposal_parks_at_s09_and_every_ambiguous_match_at_s07(self):
        k, _ = support.kit()
        res = k.orchestrator.run_all([g["id"] for g in support.golden()])
        gates = {}
        for e in k.audit.events():
            if e["kind"] == "gate":
                gates.setdefault(e["case_id"], []).append(e["step"])
        for r in res:
            if r.proposed_outcome == "RESUBMIT":
                self.assertEqual(r.state, "WAITING_S09")
                self.assertIn("S09", gates[r.case_id])
            if r.proposed_outcome == "DEFER_TO_PERSON":
                self.assertEqual(r.state, "WAITING_S07")
                self.assertIn("S07", gates[r.case_id])

    def test_s07_is_routed_to_a_person_even_with_a_provider_that_does_not_answer(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(answer_judge=False))
        res = k.orchestrator.run_case("G04")
        self.assertEqual((res.route, res.state), ("to_person", "WAITING_S07"))
        self.assertEqual(k.env.ledger, [])

    def test_s09_parks_when_nobody_answers(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(answer_approve=False))
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.state), ("to_person", "WAITING_S09"))
        self.assertEqual(k.env.ledger, [])

    def test_no_provider_means_no_resubmit_in_live_mode(self):
        k, _ = support.kit(mode="live")
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertEqual(k.env.ledger, [])

    def test_shadow_mode_never_reaches_s10(self):
        k, _ = support.kit()
        res = k.orchestrator.run_all([g["id"] for g in support.golden()])
        self.assertTrue(all("S10" not in r.steps_done for r in res))
        self.assertEqual((k.env.ledger, k.env.cases, k.env.worksheet), ([], {}, {}))

    def test_a_parked_case_gets_a_handover_note_but_is_not_closed(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.run_case("G01")
        self.assertEqual(k.env.cases["G01"]["status"], "OPEN")
        self.assertIn("Waiting for a person at S09", k.env.cases["G01"]["notes"][0])


class TestResubmitNeedsApproval(unittest.TestCase):
    def test_s10_without_approval_is_refused_by_the_orchestrator(self):
        k, _ = support.kit(mode="live")
        ctx = k.orchestrator.new_context("G01")
        for s in ["S01", "S02", "S03", "S04", "S05", "S06", "S08"]:
            k.orchestrator.run_step(s, ctx)
        with self.assertRaises(GateViolation):
            k.orchestrator.run_step("S10", ctx)
        self.assertEqual(k.env.ledger, [])

    def test_the_tool_layer_refuses_too(self):
        k, _ = support.kit(mode="live")
        params = {"payment_id": "P-1", "payload": {}, "correction_digest": "abc"}
        for ap in (None, Approval(True, "agent:wire-repair", "payments_operations_reviewer", "abc"),
                   Approval(False, "person:r1", "payments_operations_reviewer", "abc"),
                   Approval(True, "person:r1", "payments_operations_reviewer", "different")):
            with self.assertRaises(GateViolation):
                k.registry.call("payments_gateway", "resubmit", params, case_id="X", step="S10", approval=ap)
        self.assertEqual(k.env.ledger, [])
        outcomes = [e["detail"]["outcome"] for e in k.audit.events("X")]
        self.assertEqual(outcomes, ["blocked_gate"] * 4)

    def test_the_tool_layer_accepts_a_valid_approval(self):
        k, _ = support.kit(mode="live")
        ap = Approval(True, "person:r1", "payments_operations_reviewer", "abc")
        r = k.registry.call("payments_gateway", "resubmit", {"payment_id": "P-1", "payload": {},
                                                             "correction_digest": "abc"},
                            case_id="X", step="S10", approval=ap, idempotency_key="k1")
        self.assertEqual(r["status"], "ACCEPTED")

    def test_valid_approval_resubmits_once_and_closes(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover())
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.state, res.resubmitted), ("to_person", "CLOSED", True))
        self.assertEqual(len(k.env.ledger), 1)
        self.assertEqual(k.env.cases["G01"]["status"], "CLOSED")
        kinds = [e["kind"] for e in k.audit.events("G01")]
        self.assertIn("approval", kinds)

    def test_the_s07_judge_cannot_also_approve(self):
        ap = ScriptedApprover(judge_id="person:same", approver_id="person:same")
        k, _ = support.kit(mode="live", approver=ap)
        res = k.orchestrator.run_case("G04")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertIn("four-eyes", res.reason)
        self.assertEqual(k.env.ledger, [])
        rejected = [e for e in k.audit.events("G04") if e["kind"] == "approval" and e["detail"]["result"] ==
                    "rejected_invalid"]
        self.assertEqual(len(rejected), 1)

    def test_the_agent_cannot_approve_its_own_work(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(approver_id="agent:wire-repair"))
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertEqual(k.env.ledger, [])

    def test_wrong_role_cannot_approve(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(approver_role="payments_operations_analyst"))
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertEqual(k.env.ledger, [])

    def test_approval_for_a_different_correction_is_rejected(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(digest_override="f" * 16))
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertIn("different correction", res.reason)
        self.assertEqual(k.env.ledger, [])

    def test_a_decline_sends_the_case_to_the_human_queue(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(approve=lambda r: False))
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.state, res.reason_kind), ("human_queue", "DECLINED", "declined"))
        self.assertEqual(k.env.ledger, [])

    def test_s07_same_party_continues_to_s09(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(same_party=lambda r: True))
        res = k.orchestrator.run_case("G04")
        self.assertEqual((res.state, res.proposed_outcome), ("CLOSED", "RESUBMIT"))
        self.assertEqual(len(k.env.ledger), 1)

    def test_s07_different_party_returns_to_originator_without_a_resubmit(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(same_party=lambda r: False))
        res = k.orchestrator.run_case("G04")
        self.assertEqual((res.state, res.proposed_outcome), ("CLOSED", "RETURN_TO_ORIGINATOR"))
        self.assertEqual(k.env.ledger, [])

    def test_a_judge_with_the_wrong_role_does_not_unpark_s07(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover(judge_role="somebody_else"))
        res = k.orchestrator.run_case("G04")
        self.assertEqual(res.state, "WAITING_S07")

    def test_watch_list_hit_never_reaches_a_resubmit_even_with_an_approver(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover())
        res = k.orchestrator.run_case("G08")
        self.assertEqual(res.state, "ESCALATED")
        self.assertEqual(k.env.ledger, [])


class TestBriefCannotRemoveTheGates(unittest.TestCase):
    def test_a_brief_without_the_s09_gate_cannot_build_a_kit(self):
        b = support.brief()
        b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S09"]
        with self.assertRaises(BriefError):
            derive_config(b)
        with self.assertRaises(BriefError):
            build_kit(support.tiny_world(), b)

    def test_a_brief_without_the_s07_gate_cannot_build_a_kit(self):
        b = support.brief()
        b["controls"]["hitl_gates"] = [g for g in b["controls"]["hitl_gates"] if g["step"] != "S07"]
        with self.assertRaises(BriefError):
            derive_config(b)


if __name__ == "__main__":
    unittest.main()
