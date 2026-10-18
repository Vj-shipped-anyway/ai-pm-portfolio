import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover


def fault(case_id, ftype, tool="", action="", attempts="1", step="S01", payload=""):
    return {"fault_id": "F", "case_id": case_id, "step": step, "tool": tool, "action": action, "attempts": attempts,
            "fault_type": ftype, "payload": payload}


class TestIdempotency(unittest.TestCase):
    def test_a_write_with_a_used_key_is_replayed_not_run_again(self):
        k, _ = support.kit(mode="live")
        a = k.registry.call("case_system", "append_note", {"case_id": "G01", "text": "a"}, case_id="G01", step="S11",
                            idempotency_key="note-1")
        b = k.registry.call("case_system", "append_note", {"case_id": "G01", "text": "a"}, case_id="G01", step="S11",
                            idempotency_key="note-1")
        self.assertEqual(a, b)
        self.assertEqual(len(k.env.cases["G01"]["notes"]), 1)
        outcomes = [e["detail"]["outcome"] for e in k.audit.events("G01")]
        self.assertEqual(outcomes, ["ok", "replay"])

    def test_the_gateway_dedupes_on_its_own_side_too(self):
        k, _ = support.kit(mode="live")
        a = k.env.resubmit("P-1", {}, idempotency_key="resubmit:EX-1")
        b = k.env.resubmit("P-1", {}, idempotency_key="resubmit:EX-1")
        self.assertEqual((a["status"], b["status"]), ("ACCEPTED", "DUPLICATE_IGNORED"))
        self.assertEqual(len(k.env.ledger), 1)

    def test_a_duplicate_delivery_of_a_resubmitted_exception_does_not_resubmit_again(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover())
        first = k.orchestrator.run_case("G01")
        second = k.orchestrator.run_case("G13")
        self.assertTrue(first.resubmitted)
        self.assertEqual((second.state, second.proposed_outcome, second.resubmitted),
                         ("CLOSED_DUPLICATE", "DUPLICATE_CLOSED", False))
        self.assertEqual(len(k.env.ledger), 1)
        self.assertEqual(k.env.cases["G13"]["disposition"], "DUPLICATE_CLOSED")
        self.assertIn("duplicate", k.audit.events("G13")[3]["detail"]["decision"])

    def test_the_same_case_delivered_twice_is_ignored(self):
        k, _ = support.kit(mode="live", approver=ScriptedApprover())
        first = k.orchestrator.run_case("G01")
        calls = k.registry.calls_by_case["G01"]
        second = k.orchestrator.run_case("G01")
        self.assertTrue(second.redelivery)
        self.assertEqual(k.registry.calls_by_case["G01"], calls)
        self.assertEqual(len(k.env.ledger), 1)
        self.assertEqual(first.state, "CLOSED")

    def test_a_lost_answer_after_the_resubmit_does_not_double_submit(self):
        rows = [fault("G01", "timeout_after_write", "payments_gateway", "resubmit", "1", "S10")]
        k, _ = support.kit(mode="live", approver=ScriptedApprover(), fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.state, res.resubmitted), ("CLOSED", True))
        self.assertEqual(len(k.env.ledger), 1)
        retries = [e for e in k.audit.events("G01") if e["kind"] == "retry"]
        self.assertEqual(len(retries), 1)
        calls = [e["detail"]["outcome"] for e in k.audit.events("G01") if e["kind"] == "tool_call"
                 and e["detail"]["action"] == "resubmit"]
        self.assertEqual(calls, ["timeout", "ok"])

    def test_without_a_key_the_same_loss_would_double_submit(self):
        k, _ = support.kit(mode="live")
        k.env.resubmit("P-1", {})
        k.env.resubmit("P-1", {})
        self.assertEqual(len(k.env.ledger), 2)     # the uncontrolled path: what the key prevents


if __name__ == "__main__":
    unittest.main()
