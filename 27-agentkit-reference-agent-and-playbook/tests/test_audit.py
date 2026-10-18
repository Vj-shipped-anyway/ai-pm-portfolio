import copy
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover
from agentkit.audit import AuditLog, completeness, load_jsonl, verify_chain
from agentkit.errors import AuditError

IDS = [g["id"] for g in support.golden()]


def run_all(mode="shadow", **kw):
    k, _ = support.kit(mode=mode, **kw)
    k.orchestrator.run_all(IDS)
    return k


class TestChain(unittest.TestCase):
    def test_chain_verifies(self):
        k = run_all()
        self.assertEqual(verify_chain(k.audit.events()), (True, None))

    def test_editing_an_event_breaks_the_chain(self):
        k = run_all()
        ev = k.audit.events()
        ev[10]["detail"] = dict(ev[10]["detail"], outcome="ok-edited")
        ok, bad = verify_chain(ev)
        self.assertFalse(ok)
        self.assertEqual(bad, ev[10]["seq"])

    def test_deleting_an_event_breaks_the_chain(self):
        ev = run_all().audit.events()
        del ev[5]
        self.assertFalse(verify_chain(ev)[0])

    def test_reordering_events_breaks_the_chain(self):
        ev = run_all().audit.events()
        ev[3], ev[4] = ev[4], ev[3]
        self.assertFalse(verify_chain(ev)[0])

    def test_there_is_no_way_to_change_or_remove_an_event(self):
        log = AuditLog()
        log.append("case_start", "C1")
        for name in ("update", "delete", "remove", "pop", "clear", "edit", "insert"):
            self.assertFalse(hasattr(log, name), name)
        log.events()[0]["kind"] = "tampered"
        self.assertEqual(log.events()[0]["kind"], "case_start")

    def test_unknown_event_kind_is_refused(self):
        with self.assertRaises(AuditError):
            AuditLog().append("note", "C1")

    def test_jsonl_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audit.jsonl"
            k, _ = support.kit(audit_path=p)
            k.orchestrator.run_all(IDS)
            k.audit.close()
            loaded = load_jsonl(p)
            self.assertEqual(loaded, k.audit.events())
            self.assertEqual(verify_chain(loaded), (True, None))
            self.assertEqual(len(p.read_text().splitlines()), len(loaded))


class TestCompleteness(unittest.TestCase):
    def test_complete_on_a_clean_shadow_run(self):
        k = run_all()
        rep = completeness(k.audit.events(), k.orchestrator.expected_trace())
        self.assertTrue(rep["ok"])
        self.assertEqual(rep["fraction"], 1.0)
        self.assertEqual(rep["missing"], [])

    def test_complete_on_a_live_run_with_approvals(self):
        k = run_all("live", approver=ScriptedApprover())
        rep = completeness(k.audit.events(), k.orchestrator.expected_trace())
        self.assertTrue(rep["ok"])
        kinds = k.audit.kind_counts()
        self.assertGreater(kinds["approval"], 0)
        self.assertGreater(kinds["gate"], 0)

    def test_missing_events_are_found(self):
        k = run_all()
        ev = [e for e in k.audit.events() if not (e["case_id"] == "G01" and e["kind"] == "tool_call")]
        rep = completeness(ev, k.orchestrator.expected_trace())
        self.assertFalse(rep["ok"])
        self.assertLess(rep["fraction"], 1.0)
        self.assertTrue(any(m["case_id"] == "G01" and m["kind"] == "tool_call" for m in rep["missing"]))

    def test_a_lost_approval_event_is_found(self):
        k = run_all("live", approver=ScriptedApprover())
        ev = [e for e in k.audit.events() if not (e["case_id"] == "G01" and e["kind"] == "approval")]
        rep = completeness(ev, k.orchestrator.expected_trace())
        self.assertTrue(any(m["case_id"] == "G01" and m["kind"] == "approval" for m in rep["missing"]))

    def test_a_lost_route_event_is_found(self):
        k = run_all()
        ev = [e for e in k.audit.events() if not (e["case_id"] == "G05" and e["kind"] == "route")]
        rep = completeness(ev, k.orchestrator.expected_trace())
        self.assertTrue(any(m["case_id"] == "G05" and m["kind"] == "route" for m in rep["missing"]))

    def test_every_tool_call_and_every_gate_has_a_trace(self):
        k = run_all()
        expect = k.orchestrator.expected_trace()
        by_case = {}
        for e in k.audit.events():
            by_case.setdefault(e["case_id"], []).append(e["kind"])
        for cid, exp in expect.items():
            self.assertEqual(by_case[cid].count("tool_call"), exp["tool_calls"], cid)
            self.assertEqual(by_case[cid].count("gate"), exp["gates"], cid)
            self.assertEqual(by_case[cid].count("route"), exp["deliveries"], cid)

    def test_every_case_ends_with_a_route_event(self):
        k = run_all()
        for cid in IDS:
            self.assertEqual(k.audit.events(cid)[-1]["kind"], "route", cid)

    def test_a_tool_failure_leaves_a_fallback_event(self):
        rows = [{"fault_id": "F", "case_id": "G01", "step": "S03", "tool": "payments_db", "action": "get_payment",
                 "attempts": "*", "fault_type": "timeout", "payload": ""}]
        k, _ = support.kit(fault_rows=rows)
        k.orchestrator.run_case("G01")
        kinds = [e["kind"] for e in k.audit.events("G01")]
        self.assertIn("fallback", kinds)
        self.assertEqual(kinds.count("retry"), 2)

    def test_decisions_carry_their_reason(self):
        k = run_all()
        d = [e for e in k.audit.events("G04") if e["kind"] == "decision"]
        self.assertTrue(all(e["detail"]["rationale"] for e in d))


if __name__ == "__main__":
    unittest.main()
