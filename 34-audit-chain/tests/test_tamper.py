"""Each planted edit, run against the four checks, on a log built from the bundled actions. The tuple is
(no check, record check, bare chain, strict chain with anchor): True means the check flagged the log."""
import unittest

import _bootstrap  # noqa: F401
import common
from audit_chain import make_anchor


class PlantedEditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        events = common.build_log()
        cls.last = len(events)
        cls.base = [common.dumps_event(e) for e in events]
        cls.anchor = make_anchor(events, common.load_params()["anchor_seq"])

    def flags(self, op, seq=0, count=0):
        lines = common.OPS[op](self.base, seq, count)
        return tuple(common.CHECKS[name](lines, self.anchor) for name in common.DETECTORS)

    def test_the_untouched_log_passes_every_check(self):
        self.assertEqual(tuple(common.CHECKS[n](self.base, self.anchor) for n in common.DETECTORS), (False,) * 4)

    def test_edit_value(self):
        self.assertEqual(self.flags("edit_value", 50), (False, True, True, True))

    def test_edit_rehash_in_the_middle_and_at_the_last_event(self):
        self.assertEqual(self.flags("edit_rehash", 50), (False, False, True, True))
        self.assertEqual(self.flags("edit_rehash", self.last), (False, False, False, False))

    def test_delete_event_and_delete_fix(self):
        self.assertEqual(self.flags("delete_event", 50), (False, True, True, True))
        self.assertEqual(self.flags("delete_fix", 50), (False, False, True, True))

    def test_swap_and_insert_are_found_by_the_links(self):
        self.assertEqual(self.flags("swap_fix", 50), (False, False, True, True))
        self.assertEqual(self.flags("insert_fix", 50), (False, False, True, True))

    def test_a_duplicate_key_and_an_extra_field_pass_everything_but_the_strict_check(self):
        self.assertEqual(self.flags("dup_key", 50), (False, False, False, True))
        self.assertEqual(self.flags("add_field", 50), (False, False, False, True))

    def test_a_full_rewrite_is_found_only_when_it_touches_the_anchored_events(self):
        self.assertEqual(self.flags("rewrite_all", 50), (False, False, False, True))
        self.assertEqual(self.flags("rewrite_all", 250), (False, False, False, False))

    def test_a_cut_is_found_only_when_it_goes_below_the_anchor(self):
        self.assertEqual(self.flags("truncate", 0, 100), (False, False, False, True))
        self.assertEqual(self.flags("truncate", 0, 10), (False, False, False, False))
        self.assertEqual(self.flags("truncate", 0, self.last - 200), (False, False, False, False))

    def test_forged_appends_pass_every_check_and_so_do_legitimate_ones(self):
        self.assertEqual(self.flags("append_forged", 0, 3), (False,) * 4)
        self.assertEqual(self.flags("append_legit", 0, 5), (False,) * 4)

    def test_harmless_rewrites_of_the_file_are_not_flagged(self):
        for op in ("reformat_keys", "reformat_unicode", "reformat_crlf", "reformat_blank_lines"):
            self.assertEqual(self.flags(op), (False,) * 4, op)

    def test_the_reformatted_files_really_differ_from_the_original(self):
        for op in ("reformat_keys", "reformat_unicode", "reformat_crlf", "reformat_blank_lines"):
            self.assertNotEqual(common.OPS[op](self.base, 0, 0), self.base, op)

    def test_every_op_in_the_plan_exists_and_every_row_is_labelled(self):
        plan = common.load_plan()
        self.assertTrue({r["op"] for r in plan} <= set(common.OPS))
        self.assertTrue({r["truth"] for r in plan} <= {"tampered", "benign"})


if __name__ == "__main__":
    unittest.main()
