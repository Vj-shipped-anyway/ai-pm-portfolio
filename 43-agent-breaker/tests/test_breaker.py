import os
import unittest

import _bootstrap  # noqa: F401
from _util import feed, policy
import agent_breaker as ab

ALLOWED = {("CLOSED", "OPEN"), ("OPEN", "HALF_OPEN"), ("HALF_OPEN", "OPEN"), ("HALF_OPEN", "CLOSED"),
           ("CLOSED", "FORCED_OPEN"), ("OPEN", "FORCED_OPEN"), ("HALF_OPEN", "FORCED_OPEN"), ("FORCED_OPEN", "HALF_OPEN")}


def moves(fleet, agent=None):
    return [(e["data"]["from"], e["data"]["to"], e["data"]["rule"]) for e in fleet.log.events
            if e["kind"] == "transition" and (agent is None or e["agent"] == agent)]


class TripTests(unittest.TestCase):
    def test_trips_on_five_failures_in_a_row_and_holds_the_next_call(self):
        f = ab.Fleet(policy())
        r = feed(f, "a", ["fail"] * 5 + ["ok"])
        self.assertEqual(moves(f), [("CLOSED", "OPEN", "consecutive")])
        self.assertEqual([x["route"] for x in r], ["agent"] * 5 + ["human_queue"])

    def test_four_failures_then_ok_does_not_trip(self):
        f = ab.Fleet(policy())
        feed(f, "a", ["fail"] * 4 + ["ok"] + ["fail"] * 4)
        self.assertEqual(moves(f), [])

    def test_rate_is_not_scored_below_the_minimum_window(self):
        f = ab.Fleet(policy(consecutive_trip=99))
        feed(f, "a", ["fail", "ok"] * 4 + ["fail"])            # 9 calls, 5 failed: too few to score
        self.assertEqual(moves(f), [])
        feed(f, "a", ["fail"], start=9)                        # the 10th call: 6 of 10
        self.assertEqual(moves(f), [("CLOSED", "OPEN", "rate")])

    def test_rate_reads_a_time_window_not_the_whole_history(self):
        f = ab.Fleet(policy(consecutive_trip=99, min_window_calls=4, window_min=10))
        feed(f, "a", ["fail"] * 3)                              # t 0-2
        feed(f, "a", ["ok", "ok", "fail", "ok"], start=100)     # t 100-103: the old failures have left the window
        self.assertEqual(moves(f), [])

    def test_critical_kind_trips_on_the_first_failure(self):
        f = ab.Fleet(policy())
        f.handle(0, "a", "c1", "fail", "scope_violation")
        self.assertEqual(moves(f), [("CLOSED", "OPEN", "critical")])
        g = ab.Fleet(policy())
        g.handle(0, "a", "c1", "fail", "timeout")
        self.assertEqual(moves(g), [])

    def test_warn_fires_once_switches_nothing_and_rearms(self):
        f = ab.Fleet(policy(consecutive_trip=99, min_window_calls=8, window_min=20))
        r = feed(f, "a", ["ok"] * 5 + ["fail"] * 3)            # 3 of 8 = 0.375 = warn level (0.75 x 0.5)
        warns = [e for e in f.log.events if e["kind"] == "warn"]
        self.assertEqual(len(warns), 1)
        self.assertEqual(moves(f), [])
        self.assertTrue(all(x["route"] == "agent" for x in r))
        feed(f, "a", ["ok"] * 30, start=8)                      # rate falls under the clear level, so it re-arms
        feed(f, "a", ["fail"] * 8, start=40)
        self.assertGreaterEqual(len([e for e in f.log.events if e["kind"] == "warn"]), 2)


class HoldAndRecoverTests(unittest.TestCase):
    def tripped(self, **kw):
        f = ab.Fleet(policy(**kw))
        feed(f, "a", ["fail"] * 5)                              # trips at t=4
        return f

    def test_calls_are_held_until_the_hold_has_elapsed_then_probes_start(self):
        f = self.tripped()
        self.assertEqual(f.handle(33, "a", "x", "ok")["route"], "human_queue")
        r = f.handle(34, "a", "y", "ok")
        self.assertEqual((r["route"], r["state"]), ("agent", "HALF_OPEN"))

    def test_three_good_probes_close_and_reset(self):
        f = self.tripped()
        feed(f, "a", ["ok"] * 3, start=34)
        self.assertEqual(moves(f)[-2:], [("OPEN", "HALF_OPEN", "hold_elapsed"), ("HALF_OPEN", "CLOSED", "probes_passed")])
        self.assertEqual(f.breakers["a"].hold, 30)
        self.assertEqual(f.handle(40, "a", "z", "ok")["state"], "CLOSED")

    def test_failed_probe_reopens_with_a_doubled_hold_and_a_cap(self):
        f = self.tripped(max_hold_min=100)
        t, holds = 34, []
        for _ in range(4):
            f.handle(t, "a", f"p{t}", "fail", "tool_error")
            holds.append(f.breakers["a"].hold)
            t += f.breakers["a"].hold
        self.assertEqual(holds, [60, 100, 100, 100])

    def test_probe_failure_after_good_probes_still_reopens(self):
        f = self.tripped()
        feed(f, "a", ["ok", "ok", "fail"], start=34)
        self.assertEqual(moves(f)[-1], ("HALF_OPEN", "OPEN", "probe_failed"))

    def test_a_fresh_trip_after_a_close_starts_from_the_base_hold(self):
        f = self.tripped()
        feed(f, "a", ["fail"], start=34)                         # hold becomes 60
        feed(f, "a", ["ok"] * 3, start=94)
        self.assertEqual(f.breakers["a"].state, "CLOSED")
        feed(f, "a", ["fail"] * 5, start=100)
        self.assertEqual(f.breakers["a"].hold, 30)


class FleetTests(unittest.TestCase):
    def test_breakers_are_per_agent_and_grouped_by_the_field_not_the_name(self):
        f = ab.Fleet(policy())
        feed(f, "pay-1", ["fail"] * 5)
        r = feed(f, "pay-2", ["ok"] * 3, start=10)
        self.assertEqual([x["route"] for x in r], ["agent"] * 3)
        self.assertEqual(moves(f, "pay-1"), [("CLOSED", "OPEN", "consecutive")])
        self.assertEqual(moves(f, "pay-2"), [])

    def test_operator_engage_holds_and_release_goes_through_probes(self):
        f = ab.Fleet(policy())
        feed(f, "a", ["ok"] * 3)
        self.assertTrue(f.control(5, "a", "engage", "oncall", "maintenance"))
        self.assertEqual(f.handle(6, "a", "x", "ok")["route"], "human_queue")
        self.assertEqual(f.handle(500, "a", "y", "ok")["route"], "human_queue")      # no timer releases it
        self.assertTrue(f.control(501, "a", "release", "oncall", "done"))
        self.assertEqual(f.breakers["a"].state, "HALF_OPEN")
        feed(f, "a", ["ok"] * 3, start=502)
        self.assertEqual(f.breakers["a"].state, "CLOSED")

    def test_repeated_control_is_logged_with_no_effect(self):
        f = ab.Fleet(policy())
        self.assertFalse(f.control(1, "a", "release", "x", "nothing to release"))
        self.assertTrue(f.control(2, "a", "engage", "x", "r"))
        self.assertFalse(f.control(3, "a", "engage", "x", "r"))
        effects = [e["data"]["effect"] for e in f.log.events if e["kind"] == "control"]
        self.assertEqual(effects, ["none", "engaged", "none"])

    def test_engage_during_open_takes_over_the_hold(self):
        f = ab.Fleet(policy())
        feed(f, "a", ["fail"] * 5)
        f.control(10, "a", "engage", "x", "r")
        self.assertEqual(f.handle(500, "a", "y", "ok")["route"], "human_queue")

    def test_admit_and_record_give_the_same_log_as_handle(self):
        outcomes = ["ok", "fail", "ok"] + ["fail"] * 5 + ["ok"] * 4
        a, b = ab.Fleet(policy()), ab.Fleet(policy())
        for i, o in enumerate(outcomes):
            a.handle(i * 10, "x", f"c{i}", o, "tool_error" if o == "fail" else None)
            rec = b.admit(i * 10, "x", f"c{i}")
            if rec["route"] == "agent":
                b.record(rec, o, "tool_error" if o == "fail" else None)
        self.assertEqual(a.log.head, b.log.head)

    def test_one_call_in_flight_per_agent(self):
        f = ab.Fleet(policy())
        rec = f.admit(1, "a", "c1")
        with self.assertRaises(ValueError):
            f.admit(2, "a", "c2")
        self.assertEqual(f.admit(2, "b", "c3")["route"], "agent")         # another agent is independent
        f.record(rec, "ok")
        with self.assertRaises(ValueError):
            f.record(rec, "ok")                                           # already recorded
        self.assertEqual(f.admit(3, "a", "c4")["route"], "agent")

    def test_a_held_call_cannot_be_recorded(self):
        f = ab.Fleet(policy())
        f.control(0, "a", "engage", "x", "r")
        rec = f.admit(1, "a", "c1")
        self.assertEqual(rec["route"], "human_queue")
        with self.assertRaises(ValueError):
            f.record(rec, "ok")

    def test_bad_calls_are_refused(self):
        f = ab.Fleet(policy())
        f.handle(5, "a", "c", "ok")
        with self.assertRaises(ValueError):
            f.handle(4, "a", "c", "ok")                          # time went backwards
        with self.assertRaises(ValueError):
            f.handle(6, "a", "c", "maybe")
        with self.assertRaises(ValueError):
            f.handle(6, "a", "c", None)                          # routed to the agent with no outcome
        with self.assertRaises(ValueError):
            f.control(6, "a", "pause", "x", "y")

    def test_only_legal_transitions_happen_on_the_full_stream(self):
        data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        fleet, _ = ab.run_stream(ab.load_events(os.path.join(data, "events.csv")), ab.load_controls(os.path.join(data, "controls.csv")),
                                 ab.load_policy(os.path.join(data, "policy.csv")))
        pairs = {(a, b) for a, b, _ in moves(fleet)}
        self.assertTrue(pairs <= ALLOWED, pairs - ALLOWED)
        self.assertGreater(len(pairs), 4)


class PolicyTests(unittest.TestCase):
    def test_bad_values_are_refused(self):
        for bad in ({"trip_failure_rate": 0}, {"trip_failure_rate": 1.5}, {"window_min": 0}, {"clear_fraction": 0.9},
                    {"max_hold_min": 5}, {"hold_backoff": 0}, {"probe_calls": True}, {"critical_kinds": 5}):
            with self.assertRaises(ValueError, msg=str(bad)):
                ab.check_policy(policy(**bad))

    def test_unknown_or_missing_parameter_is_refused(self):
        with self.assertRaises(ValueError):
            ab.check_policy(dict(policy(), surprise=1))
        p = policy()
        del p["probe_calls"]
        with self.assertRaises(ValueError):
            ab.check_policy(p)

    def test_defaults_match_the_shipped_policy_file(self):
        shipped = ab.load_policy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "policy.csv"))
        self.assertEqual(shipped, ab.default_policy())


if __name__ == "__main__":
    unittest.main()
