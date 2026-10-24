import json
import unittest

import _bootstrap  # noqa: F401
import audit_chain as ac
from support import chain, event, lines


def codes(report):
    return [p["code"] for p in report["problems"]]


class DetectionTests(unittest.TestCase):
    def test_an_intact_log_passes(self):
        r = ac.verify_lines(lines(chain(6)))
        self.assertTrue(r["ok"])
        self.assertEqual((r["events"], r["problems"]), (6, []))

    def test_an_edited_event_is_found_at_that_event(self):
        evs = chain(6)
        evs[2]["detail"] = {"decided": "hold"}
        r = ac.verify_lines(lines(evs))
        self.assertEqual(codes(r), ["hash_mismatch"])
        self.assertEqual((r["problems"][0]["line"], r["problems"][0]["seq"]), (3, 3))

    def test_an_edit_with_its_own_hash_recomputed_is_found_at_the_next_event(self):
        evs = chain(6)
        evs[2]["detail"] = {"decided": "hold"}
        evs[2]["hash"] = ac.digest(evs[2]["prev"], {k: evs[2][k] for k in ac.CORE_KEYS})
        r = ac.verify_lines(lines(evs))
        self.assertEqual((codes(r), r["problems"][0]["seq"]), (["link_broken"], 4))

    def test_a_removed_event_is_found(self):
        evs = chain(6)
        del evs[2]
        self.assertIn("seq_gap", codes(ac.verify_lines(lines(evs))))

    def test_reordered_events_are_found(self):
        evs = chain(6)
        evs[2], evs[3] = evs[3], evs[2]
        self.assertFalse(ac.verify_lines(lines(evs))["ok"])

    def test_a_line_cut_off_in_the_middle_is_a_problem_not_a_crash(self):
        ls = lines(chain(4))
        ls[-1] = ls[-1][:40]
        r = ac.verify_lines(ls)
        self.assertEqual(codes(r), ["not_json"])
        self.assertEqual(r["problems"][0]["line"], 4)

    def test_lines_that_are_not_events_are_problems(self):
        for bad in ("not json at all", "[1, 2]", "5", "null", '"text"', "{}"):
            ls = lines(chain(3)) + [bad]
            self.assertFalse(ac.verify_lines(ls)["ok"], bad)

    def test_invalid_utf8_is_a_problem(self):
        ls = [x.encode("ascii") for x in lines(chain(2))] + [b'{"seq": "\xff"}']
        self.assertEqual(codes(ac.verify_lines(ls))[0], "not_json")

    def test_wrong_field_types_are_problems(self):
        base = chain(2)
        for over in ({"seq": True}, {"seq": "2"}, {"detail": [1]}, {"actor": 7}, {"step": 3}, {"case_id": None}):
            ev = event(3, base[-1]["hash"])
            ev.update(over)
            self.assertIn("bad_field", codes(ac.verify_lines(lines(base + [ev]))), over)

    def test_a_bad_prev_or_hash_shape_is_a_problem(self):
        ev = dict(chain(1)[0], hash="abc")
        self.assertEqual(codes(ac.verify_lines(lines([ev]))), ["bad_field"])


class StrictnessTests(unittest.TestCase):
    """Each of these parses to a valid chain under plain json.loads, and is still a problem here."""

    def test_a_duplicate_key_is_a_problem(self):
        ls = lines(chain(3))
        ls[1] = '{"kind": "route", ' + ls[1][1:]
        self.assertEqual(codes(ac.verify_lines(ls)), ["duplicate_key"])

    def test_a_field_outside_the_hash_is_a_problem(self):
        evs = chain(3)
        evs[1]["verified"] = True
        self.assertEqual(codes(ac.verify_lines(lines(evs))), ["extra_field"])

    def test_an_unknown_kind_is_a_problem_even_with_a_correct_hash(self):
        evs = chain(2) + [event(3, chain(2)[-1]["hash"], kind="note")]
        self.assertEqual(codes(ac.verify_lines(lines(evs))), ["unknown_kind"])

    def test_nan_and_out_of_range_numbers_are_problems(self):
        for text in ('{"seq": NaN}', '{"seq": Infinity}', '{"seq": 1e999}', '{"seq": -Infinity}'):
            self.assertEqual(codes(ac.verify_lines([text])), ["not_json"], text)

    def test_deep_nesting_is_a_problem_not_a_crash(self):
        deep = "[" * 100000 + "]" * 100000
        self.assertEqual(codes(ac.verify_lines([deep])), ["not_json"])
        self.assertEqual(codes(ac.verify_lines(["[" * 200000])), ["not_json"])


class HarmlessChangeTests(unittest.TestCase):
    def test_key_order_spacing_and_blank_lines_do_not_matter(self):
        ls = []
        for i, e in enumerate(chain(5), start=1):
            ls.append(json.dumps(dict(reversed(list(e.items()))), indent=1 if i % 2 else None).replace("\n", " "))
            ls.append("")
        self.assertTrue(ac.verify_lines(ls)["ok"])

    def test_carriage_returns_and_a_byte_order_mark_are_tolerated(self):
        data = ("﻿" + "\r\n".join(lines(chain(4))) + "\r\n").encode("utf-8")
        self.assertTrue(ac.verify_lines(data.split(b"\n"))["ok"])
        self.assertTrue(ac.verify_lines([x + "\r" for x in lines(chain(4))])["ok"])

    def test_text_written_raw_or_escaped_hashes_the_same(self):
        evs = [event(1, ac.GENESIS, detail={"note": "señal Zoë €"})]
        self.assertTrue(ac.verify_lines([json.dumps(evs[0], ensure_ascii=False)])["ok"])
        self.assertTrue(ac.verify_lines([json.dumps(evs[0], ensure_ascii=True)])["ok"])

    def test_events_added_after_the_anchor_are_accepted(self):
        evs = chain(8)
        anchor = ac.make_anchor(evs, 5)
        self.assertTrue(ac.verify_lines(lines(evs), anchor)["ok"])


class AnchorDetectionTests(unittest.TestCase):
    def setUp(self):
        self.evs = chain(8)
        self.anchor = ac.make_anchor(self.evs, 5)

    def test_a_log_cut_below_the_anchor_is_found(self):
        r = ac.verify_lines(lines(self.evs[:4]), self.anchor)
        self.assertEqual(codes(r), ["shorter_than_anchor"])

    def test_a_cut_that_keeps_the_anchored_events_is_not_found(self):
        self.assertTrue(ac.verify_lines(lines(self.evs[:5]), self.anchor)["ok"])

    def test_a_rewrite_that_recomputes_every_hash_is_found_only_by_the_anchor(self):
        evs = chain(8)
        evs[1]["detail"] = {"decided": "hold"}
        prev = evs[0]["hash"]
        for e in evs[1:]:
            e["prev"] = prev
            e["hash"] = ac.digest(prev, {k: e[k] for k in ac.CORE_KEYS})
            prev = e["hash"]
        self.assertTrue(ac.verify_lines(lines(evs))["ok"])
        self.assertEqual(codes(ac.verify_lines(lines(evs), self.anchor)), ["anchor_mismatch"])

    def test_an_empty_log_is_a_problem_with_or_without_an_anchor(self):
        self.assertEqual(codes(ac.verify_lines([])), ["empty"])
        self.assertEqual(codes(ac.verify_lines(["", "\r"], self.anchor)), ["shorter_than_anchor"])


if __name__ == "__main__":
    unittest.main()
