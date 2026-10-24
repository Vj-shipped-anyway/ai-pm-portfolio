import datetime
import unittest

import _bootstrap  # noqa: F401
import ops_model_review as omr

D = datetime.date
AS_OF = D(2026, 9, 30)


def item(item_id, stage, min_tier=1, cycle=10, independent=False, window=0):
    return {"item_id": item_id, "stage": stage, "stage_name": f"S{stage}", "item": f"item {item_id}", "min_tier": min_tier,
            "cycle_days": cycle, "independent": independent, "day_window": window}


CHECKLIST = [item("A", 1, window=30), item("B", 1, min_tier=3), item("C", 2, cycle=100, independent=True, window=60),
             item("D", 3)]
PROGRAM = {"program_id": "P1", "program_name": "demo", "tier": 3, "builder": "u1", "claimed_stage": 3}


def row(days_old=1, ref="DOC-1", who="u2", on=None):
    return {"artifact_ref": ref, "produced_by": who, "date": on or AS_OF - datetime.timedelta(days=days_old)}


def register(**rows):
    return {("P1", k): v for k, v in rows.items()}


FULL = register(A=row(), B=row(), C=row(), D=row())


class JudgeTests(unittest.TestCase):
    def test_fresh_row_is_ok(self):
        self.assertEqual(omr.judge(CHECKLIST[0], row(), "u1", AS_OF)[0], "OK")

    def test_no_row_is_missing(self):
        self.assertEqual(omr.judge(CHECKLIST[0], None, "u1", AS_OF)[0], "MISSING")

    def test_age_limit_is_one_and_a_half_cycles_inclusive(self):
        self.assertEqual(omr.judge(CHECKLIST[0], row(days_old=15), "u1", AS_OF)[0], "OK")
        status, detail = omr.judge(CHECKLIST[0], row(days_old=16), "u1", AS_OF)
        self.assertEqual(status, "STALE")
        self.assertIn("limit 15 days", detail)

    def test_date_after_review_is_future_and_same_day_is_not(self):
        self.assertEqual(omr.judge(CHECKLIST[0], row(on=AS_OF + datetime.timedelta(days=1)), "u1", AS_OF)[0], "FUTURE")
        self.assertEqual(omr.judge(CHECKLIST[0], row(on=AS_OF), "u1", AS_OF)[0], "OK")

    def test_placeholder_references(self):
        for ref in ("", "   ", "TBD", "n/a", "N/A", "Todo", "-", "?"):
            self.assertEqual(omr.judge(CHECKLIST[0], row(ref=ref), "u1", AS_OF)[0], "BLANK_REF", ref)
        self.assertEqual(omr.judge(CHECKLIST[0], row(ref="DOC-TBD-7"), "u1", AS_OF)[0], "OK")

    def test_builder_cannot_produce_an_independent_item(self):
        self.assertEqual(omr.judge(CHECKLIST[2], row(who="u1"), "u1", AS_OF)[0], "NOT_INDEPENDENT")
        self.assertEqual(omr.judge(CHECKLIST[2], row(who=""), "u1", AS_OF)[0], "NOT_INDEPENDENT")
        self.assertEqual(omr.judge(CHECKLIST[2], row(who="u2"), "u1", AS_OF)[0], "OK")

    def test_builder_may_produce_an_item_that_needs_no_independence(self):
        # a hard negative: a rule that rejected every builder-made row would raise a false alarm here
        self.assertEqual(omr.judge(CHECKLIST[0], row(who="u1"), "u1", AS_OF)[0], "OK")

    def test_switched_off_checks_do_not_run(self):
        stale = row(days_old=99)
        self.assertEqual(omr.judge(CHECKLIST[0], stale, "u1", AS_OF, rules=())[0], "OK")
        self.assertEqual(omr.judge(CHECKLIST[0], stale, "u1", AS_OF, rules=("ref", "future", "indep"))[0], "OK")
        self.assertEqual(omr.judge(CHECKLIST[0], stale, "u1", AS_OF)[0], "STALE")
        self.assertEqual(omr.judge(CHECKLIST[0], None, "u1", AS_OF, rules=())[0], "MISSING")


class ReviewTests(unittest.TestCase):
    def review(self, program=PROGRAM, reg=FULL, **kw):
        return omr.review_program(program, CHECKLIST, reg, AS_OF, **kw)

    def test_clean_register_reaches_the_last_stage(self):
        r = self.review()
        self.assertEqual((r["reached"], r["decision"], r["gaps"]), (3, "CONFIRMED", []))

    def test_a_gap_stops_later_stages_even_when_their_evidence_is_fine(self):
        reg = dict(FULL)
        del reg[("P1", "C")]
        r = self.review(reg=reg)
        self.assertEqual(r["reached"], 1)
        self.assertEqual(r["decision"], "OVERCLAIM")
        self.assertEqual([g["item_id"] for g in r["gaps"]], ["C"])

    def test_gaps_are_listed_only_up_to_the_claimed_stage(self):
        reg = dict(FULL)
        del reg[("P1", "D")]
        r = self.review(program=dict(PROGRAM, claimed_stage=2), reg=reg)
        self.assertEqual((r["gaps"], r["reached"], r["decision"]), ([], 2, "CONFIRMED"))
        r2 = self.review(reg=reg)
        self.assertEqual([g["item_id"] for g in r2["gaps"]], ["D"])

    def test_items_the_tier_does_not_owe_are_left_alone(self):
        low = dict(PROGRAM, tier=1, claimed_stage=3)
        reg = register(A=row(), C=row(), D=row())
        r = self.review(program=low, reg=reg)
        self.assertEqual((r["reached"], r["not_owed"], r["decision"]), (3, 1, "CONFIRMED"))
        self.assertNotIn("B", [i["item_id"] for i in r["items"]])
        self.assertEqual(self.review(program=dict(PROGRAM, tier=3), reg=reg)["reached"], 0)

    def test_tier_check_off_asks_everyone_for_everything(self):
        low = dict(PROGRAM, tier=1)
        r = self.review(program=low, reg=register(A=row(), C=row(), D=row()), rules=())
        self.assertEqual((r["not_owed"], r["reached"]), (0, 0))

    def test_underclaim_and_zero_claim(self):
        self.assertEqual(self.review(program=dict(PROGRAM, claimed_stage=1))["decision"], "UNDERCLAIM")
        r = self.review(program=dict(PROGRAM, claimed_stage=0), reg={})
        self.assertEqual((r["reached"], r["decision"]), (0, "CONFIRMED"))

    def test_empty_register_marks_every_owed_item_missing(self):
        r = self.review(reg={})
        self.assertEqual({i["status"] for i in r["items"]}, {"MISSING"})
        self.assertEqual(len(r["items"]), 4)

    def test_window_counts_only_items_due_by_the_window(self):
        reg = dict(FULL)
        reg[("P1", "C")] = row(who="u1")
        w30, w60 = self.review(window=30)["window"], self.review(window=60)["window"]
        self.assertEqual((w30["owed"], w30["ok"], w30["open"]), (1, 1, []))
        self.assertEqual((w60["owed"], w60["ok"]), (2, 2))
        w = self.review(reg=reg, window=60)["window"]
        self.assertEqual((w["ok"], w["open"]), (1, ["C"]))
        self.assertNotIn("window", self.review())

    def test_rules_constant_is_not_changed_by_a_run(self):
        before = omr.RULES
        self.review(rules=())
        self.assertEqual(omr.RULES, before)


class OutputTests(unittest.TestCase):
    def test_one_line_removes_control_characters(self):
        self.assertEqual(omr.one_line("a\nb\r::c\x1bd"), "a b ::c d")

    def test_escape_annotation(self):
        self.assertEqual(omr.escape_annotation("100%\r\n::x"), "100%25%0D%0A::x")

    def test_dates_must_be_iso(self):
        for bad in ("30/09/2026", "2026-9-30", "20260930", "2026-02-30", "", "2026-09-30T10:00"):
            with self.assertRaises(ValueError, msg=bad):
                omr.parse_date(bad, "x")
        self.assertEqual(omr.parse_date(" 2026-09-30 ", "x"), AS_OF)


if __name__ == "__main__":
    unittest.main()
