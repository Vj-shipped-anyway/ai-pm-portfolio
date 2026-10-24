import json
import unittest

import _bootstrap  # noqa: F401
from _util import feed, policy
import agent_breaker as ab


def build():
    f = ab.Fleet(policy())
    feed(f, "a", ["ok"] * 3 + ["fail"] * 5)
    feed(f, "a", ["ok"] * 4, start=40)
    f.control(60, "b", "engage", "oncall", "maintenance")
    feed(f, "b", ["ok"] * 2, start=61)
    return f


def rewrite(lines, i, **changes):
    ev = json.loads(lines[i])
    ev["data"] = dict(ev["data"], **changes)
    return lines[:i] + [json.dumps(ev, sort_keys=True, ensure_ascii=True)] + lines[i + 1:]


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.fleet = build()
        self.lines = self.fleet.log.lines()

    def test_a_clean_log_verifies(self):
        self.assertEqual(ab.verify_log(self.lines), [])
        self.assertEqual(ab.verify_log(self.lines, policy(), self.fleet.log.head), [])

    def test_same_input_gives_the_same_head_hash(self):
        self.assertEqual(build().log.head, self.fleet.log.head)

    def test_an_edited_line_is_found_at_that_line(self):
        bad = rewrite(self.lines, 2, case="forged")
        self.assertTrue(ab.verify_log(bad)[0].startswith("line 3:"))

    def test_a_removed_line_breaks_the_chain(self):
        bad = self.lines[:4] + self.lines[5:]
        self.assertIn("chain broken", ab.verify_log(bad)[0])

    def test_reordered_lines_break_the_chain(self):
        bad = self.lines[:3] + [self.lines[4], self.lines[3]] + self.lines[5:]
        self.assertTrue(ab.verify_log(bad))

    def test_a_rehashed_forgery_is_caught_by_the_replay(self):
        events = self.fleet.log.events
        trip = next(i for i, e in enumerate(events) if e["kind"] == "transition" and e["data"]["to"] == "OPEN")
        forged = ab.AuditLog()
        for i, e in enumerate(events):
            if i != trip:
                forged.append(e["t"], e["agent"], e["kind"], e["data"])
        problems = ab.verify_log(forged.lines())
        self.assertTrue(problems)
        self.assertNotIn("chain", problems[0])

    def test_a_call_that_reached_the_agent_while_open_is_named(self):
        forged = ab.AuditLog()
        for e in self.fleet.log.events:
            data = dict(e["data"])
            if e["kind"] == "call" and data["route"] == "human_queue":
                data.update(route="agent", outcome="ok")
            forged.append(e["t"], e["agent"], e["kind"], data)
        self.assertTrue(any("reached the agent while the breaker was" in p for p in ab.verify_log(forged.lines())))

    def test_a_cut_tail_is_only_found_with_the_stored_head(self):
        cut = self.lines[:-2]            # cut between two complete events; a cut inside one is a replay mismatch
        self.assertEqual(ab.verify_log(cut), [])
        self.assertIn("head hash differs", ab.verify_log(cut, head=self.fleet.log.head)[0])

    def test_a_different_policy_is_reported(self):
        self.assertIn("policy in the log differs", ab.verify_log(self.lines, policy(hold_min=10))[0])

    def test_a_held_call_carries_no_outcome(self):
        held = [json.loads(x)["data"] for x in self.lines if json.loads(x)["kind"] == "call" and json.loads(x)["data"]["route"] == "human_queue"]
        self.assertTrue(held)
        self.assertTrue(all(h["outcome"] is None for h in held))

    def test_a_nonsense_policy_inside_the_log_is_a_problem_not_a_crash(self):
        bad = ab.AuditLog()
        bad.append(None, "", "policy", {"window_min": "soon"})
        self.assertIn("policy", ab.verify_log(bad.lines())[0])

    def test_a_log_that_does_not_start_with_the_policy(self):
        log = ab.AuditLog()
        log.append(1, "a", "warn", {"window_calls": 1, "window_fails": 1, "rate": 1.0})
        self.assertIn("policy", ab.verify_log(log.lines())[-1])

    def test_malformed_lines_raise_value_error(self):
        for bad in ([], ["{not json"], ["[1, 2]"], ['{"seq": 1}'], ['{"seq": 1, "t": 0, "agent": "", "kind": "other", "data": {}, "prev": "", "hash": ""}']):
            with self.assertRaises(ValueError, msg=str(bad)):
                ab.verify_log(bad)

    def test_hostile_strings_stay_on_one_line_each(self):
        f = ab.Fleet(policy())
        hostile = "a\n::error::forged\r "
        f.handle(0, hostile, "c\n1", "fail", "x\ny")
        f.control(1, hostile, "engage", "who\nelse", "why\r\nnot")
        lines = f.log.lines()
        self.assertEqual(len(lines), len(f.log.events))
        self.assertTrue(all("\n" not in x and "\r" not in x for x in lines))
        self.assertEqual(ab.verify_log(lines), [])


class SafeTests(unittest.TestCase):
    def test_control_characters_are_escaped(self):
        s = ab.safe("a\nb\rc\td\x1b[31m e\x85")
        self.assertEqual(s, "a\\nb\\rc\\td\\x1b[31m\\u2028e\\x85")
        self.assertTrue(s.isprintable())


if __name__ == "__main__":
    unittest.main()
