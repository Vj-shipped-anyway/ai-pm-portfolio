import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover
from agentkit.faults import FaultInjector


def fault(case_id, ftype, tool="", action="", attempts="1", step="S01", payload=""):
    return {"fault_id": "F", "case_id": case_id, "step": step, "tool": tool, "action": action, "attempts": attempts,
            "fault_type": ftype, "payload": payload}


def baseline(case_id):
    k, _ = support.kit()
    return k.orchestrator.run_case(case_id)


class TestToolTimeout(unittest.TestCase):
    def test_a_transient_timeout_is_retried_and_the_case_completes_as_before(self):
        rows = [fault("G01", "timeout", "payments_db", "get_payment", "1", "S03")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        base = baseline("G01")
        self.assertEqual((res.route, res.state, res.proposed_outcome), (base.route, base.state, base.proposed_outcome))
        self.assertEqual(res.correction, base.correction)
        kinds = [e["kind"] for e in k.audit.events("G01")]
        self.assertEqual(kinds.count("retry"), 1)
        outcomes = [e["detail"]["outcome"] for e in k.audit.events("G01") if e["kind"] == "tool_call"
                    and e["detail"]["tool"] == "payments_db"]
        self.assertEqual(outcomes, ["timeout", "ok"])

    def test_a_persistent_timeout_sends_the_case_to_the_human_queue_after_the_attempts(self):
        rows = [fault("G01", "timeout", "payments_db", "get_payment", "*", "S03")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.state, res.reason_kind), ("human_queue", "QUEUED_HUMAN", "tool_failure"))
        kinds = [e["kind"] for e in k.audit.events("G01")]
        self.assertEqual(kinds.count("retry"), 2)
        self.assertEqual(kinds.count("fallback"), 1)
        calls = [e for e in k.audit.events("G01") if e["kind"] == "tool_call" and e["detail"]["tool"] == "payments_db"]
        self.assertEqual(len(calls), 3)

    def test_the_attempt_limit_is_a_setting(self):
        rows = [fault("G01", "timeout", "payments_db", "get_payment", "1,2,3", "S03")]
        k, _ = support.kit(fault_rows=rows, max_attempts=5)
        self.assertEqual(k.orchestrator.run_case("G01").state, "WAITING_S09")
        k2, _ = support.kit(fault_rows=rows, max_attempts=3)
        self.assertEqual(k2.orchestrator.run_case("G01").route, "human_queue")

    def test_a_timeout_also_hits_a_write_call_in_dry_run(self):
        rows = [fault("G01", "timeout", "case_system", "open_case", "1", "S01")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertEqual(len([e for e in k.audit.events("G01") if e["kind"] == "retry"]), 1)

    def test_a_case_with_a_timeout_does_not_disturb_the_next_case(self):
        rows = [fault("G01", "timeout", "payments_db", "get_payment", "*", "S03")]
        k, _ = support.kit(fault_rows=rows)
        a, b = k.orchestrator.run_case("G01"), k.orchestrator.run_case("G02")
        self.assertEqual((a.route, b.state), ("human_queue", "WAITING_S09"))


class TestMalformedToolOutput(unittest.TestCase):
    def test_a_transient_malformed_answer_is_retried(self):
        rows = [fault("G01", "malformed_output", "reason_codes", "lookup", "1", "S02")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.state, "WAITING_S09")
        outcomes = [e["detail"]["outcome"] for e in k.audit.events("G01") if e["kind"] == "tool_call"
                    and e["detail"]["tool"] == "reason_codes"]
        self.assertEqual(outcomes, ["malformed", "ok"])

    def test_a_persistent_malformed_answer_from_the_watch_list_never_lets_the_case_through_unscreened(self):
        rows = [fault("G01", "malformed_output", "watchlist", "screen_party", "*", "S06")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.reason_kind), ("human_queue", "tool_failure"))
        self.assertNotIn("S08", res.steps_done)
        self.assertIsNone(res.correction)

    def test_a_malformed_answer_is_never_used(self):
        rows = [fault("G01", "malformed_output", "payments_db", "get_payment", "*", "S03")]
        k, _ = support.kit(fault_rows=rows)
        res = k.orchestrator.run_case("G01")
        self.assertEqual(res.route, "human_queue")
        self.assertNotIn("S03", res.steps_done)


class TestDuplicateDelivery(unittest.TestCase):
    def test_the_second_delivery_is_ignored_and_changes_nothing(self):
        rows = [fault("G01", "duplicate_delivery")]
        k, _ = support.kit(mode="live", approver=ScriptedApprover(), fault_rows=rows)
        res = k.orchestrator.run_all(["G01", "G02"])
        self.assertEqual(len(res), 3)
        self.assertTrue(res[1].redelivery)
        self.assertEqual(res[1].state, "REDELIVERY_IGNORED")
        self.assertEqual(len(k.env.ledger), 2)           # G01 and G02, once each

    def test_redelivery_costs_no_tool_calls(self):
        rows = [fault("G01", "duplicate_delivery")]
        k, _ = support.kit(fault_rows=rows)
        k.orchestrator.run_all(["G01"])
        calls = sum(1 for e in k.audit.events("G01") if e["kind"] == "tool_call")
        self.assertEqual(calls, k.registry.calls_by_case["G01"])
        self.assertEqual(len([e for e in k.audit.events("G01") if e["kind"] == "route"]), 2)


class TestInjectorParsing(unittest.TestCase):
    def test_attempt_specs(self):
        f = FaultInjector([fault("C", "timeout", "t", "a", "1,3")])
        hits = []
        for n in (1, 2, 3, 4):
            try:
                f.before_call("C", "t", "a", n)
                hits.append(False)
            except Exception:
                hits.append(True)
        self.assertEqual(hits, [True, False, True, False])

    def test_unknown_fault_type_is_refused(self):
        with self.assertRaises(ValueError):
            FaultInjector([fault("C", "meteor")])

    def test_counts(self):
        f = FaultInjector([fault("C", "timeout", "t", "a"), fault("D", "rogue_call", payload="x.y", step="S04")])
        self.assertEqual(f.counts(), {"timeout": 1, "rogue_call": 1})


if __name__ == "__main__":
    unittest.main()
