import hashlib
import json
import unittest

import _bootstrap  # noqa: F401
import audit_chain as ac
from support import chain, lines


class WriterTests(unittest.TestCase):
    def test_first_hash_follows_the_documented_formula(self):
        ev = ac.AuditLog().append("case_start", "C1", None, "agent", {"b": 2, "a": 1})
        core = '{"actor":"agent","case_id":"C1","detail":{"a":1,"b":2},"kind":"case_start","seq":1,"step":null}'
        self.assertEqual(ev["prev"], "0" * 64)
        self.assertEqual(ev["hash"], hashlib.sha256(("0" * 64 + core).encode("utf-8")).hexdigest())

    def test_each_event_carries_the_hash_of_the_one_before(self):
        log = ac.AuditLog()
        a = log.append("case_start", "C1")
        b = log.append("route", "C1", detail={"route": "auto"})
        self.assertEqual(b["prev"], a["hash"])
        self.assertEqual((a["seq"], b["seq"]), (1, 2))

    def test_a_fresh_log_verifies(self):
        log = ac.AuditLog()
        for kind in ("case_start", "decision", "route"):
            log.append(kind, "C1", "S01", "agent", {"k": "v"})
        report = ac.verify_lines([ac.dumps_event(e) for e in log.events()])
        self.assertTrue(report["ok"])
        self.assertEqual(report["events"], 3)

    def test_unknown_kind_is_refused(self):
        with self.assertRaises(ac.AuditError):
            ac.AuditLog().append("note", "C1")

    def test_bad_arguments_are_refused(self):
        log = ac.AuditLog()
        for kwargs in ({"case_id": ""}, {"case_id": 5}, {"actor": ""}, {"step": 3}, {"detail": [1]}, {"detail": {"x": float("nan")}},
                       {"detail": {"x": {1, 2}}}):
            args = dict(kind="decision", case_id="C1")
            args.update(kwargs)
            with self.assertRaises(ac.AuditError, msg=str(kwargs)):
                log.append(**args)
        self.assertEqual(len(log), 0)

    def test_a_deeply_nested_detail_is_refused_not_a_crash(self):
        deep = {}
        for _ in range(5000):
            deep = {"k": deep}
        with self.assertRaises(ac.AuditError):
            ac.AuditLog().append("decision", "C1", detail=deep)

    def test_detail_is_copied_on_the_way_in_and_out(self):
        log = ac.AuditLog()
        detail = {"list": [1, 2]}
        log.append("decision", "C1", detail=detail)
        detail["list"].append(3)
        log.events()[0]["detail"]["list"].append(4)
        self.assertEqual(log.events()[0]["detail"], {"list": [1, 2]})

    def test_there_is_no_way_to_change_or_remove_an_event(self):
        log = ac.AuditLog()
        log.append("case_start", "C1")
        for name in ("update", "delete", "remove", "pop", "clear", "edit", "insert"):
            self.assertFalse(hasattr(log, name), name)

    def test_a_log_can_continue_from_events_it_was_given(self):
        evs = chain(3)
        log = ac.AuditLog(evs)
        new = log.append("route", "C1")
        self.assertEqual((new["seq"], new["prev"]), (4, evs[-1]["hash"]))
        self.assertTrue(ac.verify_lines(lines(log.events()))["ok"])

    def test_dumps_event_is_one_ascii_line(self):
        ev = ac.AuditLog().append("decision", "C1", detail={"note": "señal\nZoë"})
        text = ac.dumps_event(ev)
        self.assertNotIn("\n", text)
        self.assertTrue(text.isascii())
        self.assertEqual(json.loads(text), ev)


class AnchorTests(unittest.TestCase):
    def test_make_anchor_defaults_to_the_last_event(self):
        evs = chain(4)
        self.assertEqual(ac.make_anchor(evs), {"version": 1, "seq": 4, "hash": evs[-1]["hash"]})
        self.assertEqual(ac.make_anchor(evs, 2)["hash"], evs[1]["hash"])

    def test_make_anchor_rejects_a_seq_outside_the_log(self):
        for n in (0, -1, 5):
            with self.assertRaises(ValueError):
                ac.make_anchor(chain(4), n)


if __name__ == "__main__":
    unittest.main()
