import copy
import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.audit import AuditLog
from agentkit.brief import derive_config
from agentkit.environment import SimEnvironment
from agentkit.errors import ScopeError
from agentkit.kit import build_kit
from agentkit.tools import Tool, ToolRegistry, build_tools

ROGUE = {"fault_id": "F1", "case_id": "G01", "step": "S04", "tool": "", "action": "", "attempts": "1",
         "fault_type": "rogue_call", "payload": "payments_db.update_payment"}


class TestScopeEnforcement(unittest.TestCase):
    def test_in_scope_read_runs(self):
        k, _ = support.kit()
        r = k.registry.call("payments_db", "get_payment", {"payment_id": "P-1"}, case_id="X", step="S03")
        self.assertEqual(r["payment_id"], "P-1")

    def test_tool_not_in_the_brief_is_blocked_and_never_runs(self):
        k, _ = support.kit()
        with self.assertRaises(ScopeError):
            k.registry.call("mailer", "send", {}, case_id="X", step="S03")
        self.assertEqual(k.env.call_log, [])
        ev = k.audit.events("X")[0]
        self.assertEqual((ev["kind"], ev["detail"]["outcome"]), ("tool_call", "blocked_scope"))
        self.assertIn("not in the brief", ev["detail"]["reason"])

    def test_action_not_allowed_is_blocked_and_never_runs(self):
        k, _ = support.kit(mode="live")
        before = dict(k.env.payments["P-1"])
        with self.assertRaises(ScopeError):
            k.registry.call("payments_db", "update_payment", {"payment_id": "P-1", "field": "beneficiary_account",
                                                              "value": "0000000000"}, case_id="X", step="S04")
        self.assertEqual(k.env.payments["P-1"], before)
        self.assertEqual([c for c in k.env.call_log if c[1] == "update_payment"], [])
        self.assertEqual(k.registry.blocked, 1)

    def test_a_tool_that_declares_more_than_the_brief_is_still_limited(self):
        k, _ = support.kit(mode="live")
        env = k.env
        tools = build_tools(env)
        tools["payments_db"] = Tool("payments_db", "read", frozenset({"get_payment", "update_payment"}),
                                    {"get_payment": env.get_payment, "update_payment": env.update_payment})
        reg = ToolRegistry(tools, k.config.tool_scope, AuditLog(), mode="live")
        with self.assertRaises(ScopeError):
            reg.call("payments_db", "update_payment", {"payment_id": "P-1", "field": "x", "value": "y"},
                     case_id="X", step="S04")
        self.assertEqual([c for c in env.call_log if c[1] == "update_payment"], [])

    def test_access_mismatch_between_code_and_brief_fails_at_build_time(self):
        k, _ = support.kit()
        tools = build_tools(k.env)
        tools["payments_db"].access = "write"
        with self.assertRaises(ScopeError):
            ToolRegistry(tools, k.config.tool_scope, AuditLog())

    def test_tool_declaring_a_handlerless_action_is_refused(self):
        with self.assertRaises(ValueError):
            Tool("t", "read", frozenset({"a"}), {})

    def test_tool_access_must_be_read_or_write(self):
        with self.assertRaises(ValueError):
            Tool("t", "admin", frozenset(), {})

    def test_exactly_one_audit_event_per_call(self):
        k, _ = support.kit()
        k.orchestrator.run_all([g["id"] for g in support.golden()])
        n_events = sum(1 for e in k.audit.events() if e["kind"] == "tool_call")
        self.assertEqual(n_events, sum(k.registry.calls_by_case.values()))

    def test_rogue_call_is_blocked_and_the_case_goes_back_to_the_human_queue(self):
        k, _ = support.kit(mode="live", fault_rows=[ROGUE])
        before = dict(k.env.payments["P-1"])
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.reason_kind), ("human_queue", "scope_violation"))
        self.assertEqual(k.env.payments["P-1"], before)
        self.assertEqual([c for c in k.env.call_log if c[1] == "update_payment"], [])
        blocked = [e for e in k.audit.events("G01") if e["detail"].get("outcome") == "blocked_scope"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(k.env.cases["G01"]["queue"], "human_queue")

    def test_scope_comes_from_the_brief_not_from_the_code(self):
        b = support.brief()
        for t in b["tools"]:
            if t["name"] == "case_system":
                t["allowed_actions"] = ["open_case", "append_note", "close_case"]   # no escalate_case
        k = build_kit(support.tiny_world(), b, mode="live")
        res = k.orchestrator.run_case("G08")      # needs escalate_case at S12
        self.assertEqual((res.route, res.reason_kind), ("human_queue", "scope_violation"))
        self.assertEqual(k.env.cases["G08"]["status"], "OPEN")

    def test_the_environment_has_actions_the_kit_cannot_reach(self):
        k, _ = support.kit(mode="live")
        for tool, action in [("payments_gateway", "cancel_payment"), ("watchlist", "remove_party"),
                             ("watchlist", "export_list"), ("exception_queue", "delete_exception")]:
            with self.assertRaises(ScopeError):
                k.registry.call(tool, action, {}, case_id="X", step="S01")
        self.assertEqual(k.env.call_log, [])


if __name__ == "__main__":
    unittest.main()
