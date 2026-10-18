import unittest

import _bootstrap  # noqa: F401
import support
from agentkit.approvers import ScriptedApprover
from agentkit.errors import KillSwitchEngaged
from agentkit.orchestrator import KillSwitch

IDS = [g["id"] for g in support.golden()]


class KillingApprover(ScriptedApprover):
    def __init__(self, ks):
        super().__init__()
        self.ks = ks

    def approve(self, request):
        self.ks.engage("test: stop after the approval is given")
        return super().approve(request)


class TestKillSwitch(unittest.TestCase):
    def test_engaged_before_a_run_sends_every_case_to_the_human_queue(self):
        k, _ = support.kit()
        k.killswitch.engage("drill", by="operator-1")
        res = k.orchestrator.run_all(IDS)
        self.assertTrue(all((r.route, r.state, r.reason_kind) == ("human_queue", "KILLED", "kill_switch")
                            for r in res))
        self.assertEqual(sum(k.registry.calls_by_case.values()), 0)
        self.assertEqual(k.env.call_log, [])
        events = [e for e in k.audit.events() if e["kind"] == "kill_switch"]
        self.assertEqual(len(events), len(IDS))
        self.assertEqual(events[0]["detail"]["by"], "operator-1")

    def test_engaged_midway_stops_the_remaining_cases(self):
        k, _ = support.kit()
        first = [k.orchestrator.run_case(c) for c in IDS[:3]]
        calls_before = sum(k.registry.calls_by_case.values())
        k.killswitch.engage("midway")
        rest = [k.orchestrator.run_case(c) for c in IDS[3:]]
        self.assertTrue(all(r.state == "KILLED" for r in rest))
        self.assertTrue(all(r.state != "KILLED" for r in first))
        self.assertEqual(sum(k.registry.calls_by_case.values()), calls_before)

    def test_the_switch_beats_a_valid_approval(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.approver = KillingApprover(k.killswitch)
        res = k.orchestrator.run_case("G01")
        self.assertEqual((res.route, res.state), ("human_queue", "KILLED"))
        self.assertEqual(k.env.ledger, [])
        self.assertNotIn("S10", res.steps_done)

    def test_a_killed_case_keeps_its_trace_and_a_route_event(self):
        k, _ = support.kit()
        k.killswitch.engage("drill")
        k.orchestrator.run_case("G01")
        kinds = [e["kind"] for e in k.audit.events("G01")]
        self.assertEqual(kinds, ["case_start", "kill_switch", "route"])

    def test_release_lets_new_cases_run_again(self):
        k, _ = support.kit()
        k.killswitch.engage("drill")
        k.orchestrator.run_case("G01")
        k.killswitch.release(by="operator-2")
        res = k.orchestrator.run_case("G02")
        self.assertEqual(res.state, "WAITING_S09")
        self.assertEqual([h[0] for h in k.killswitch.history], ["engage", "release"])

    def test_the_registry_refuses_calls_while_engaged(self):
        k, _ = support.kit()
        k.killswitch.engage("drill")
        with self.assertRaises(KillSwitchEngaged):
            k.registry.call("payments_db", "get_payment", {"payment_id": "P-1"}, case_id="X", step="S03")
        self.assertEqual(k.audit.events("X")[0]["detail"]["outcome"], "blocked_killswitch")
        self.assertEqual(k.env.call_log, [])

    def test_a_fresh_switch_is_released(self):
        ks = KillSwitch()
        self.assertFalse(ks.engaged)
        ks.engage("x")
        self.assertTrue(ks.engaged)

    def test_open_cases_stay_open_not_closed_when_killed(self):
        k, _ = support.kit(mode="live")
        k.orchestrator.run_case("G01")            # parked at S09, case open
        k.killswitch.engage("drill")
        k.orchestrator.run_case("G06")            # would have been closed
        self.assertEqual(k.env.cases["G01"]["status"], "OPEN")
        self.assertNotIn("G06", k.env.cases)


if __name__ == "__main__":
    unittest.main()
