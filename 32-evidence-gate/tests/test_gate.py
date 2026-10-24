import datetime
import unittest

import _bootstrap  # noqa: F401
from evidence_gate import evaluate, parse_record, required_ids

TIERS = [{"id": "E01", "item": "card", "first_tier": 1, "max_age_days": 365},
         {"id": "E02", "item": "eval", "first_tier": 2, "max_age_days": 90},
         {"id": "E03", "item": "sign-off", "first_tier": 3, "max_age_days": 30}]
AS_OF = datetime.date(2026, 10, 16)
FILES = {"ev/a.md", "ev/b.md", "ev/c.md"}
REGISTRY = {"UC-1": 2, "UC-3": 3}


def body(uc="UC-1", tier=2, lines=None):
    lines = lines if lines is not None else ["- [x] E01 card | ref: ev/a.md | date: 2026-09-01",
                                             "- [x] E02 eval | ref: ev/b.md | date: 2026-09-01"]
    head = ([f"Use case: {uc}"] if uc else []) + ([f"Declared tier: {tier}"] if tier else [])
    return "\n".join(head + lines)


def check(text, registry=REGISTRY, files=FILES, as_of=AS_OF):
    return evaluate(parse_record(text), TIERS, registry, files, as_of)


def kinds(res):
    return [f["kind"] for f in res["findings"]]


class GateTests(unittest.TestCase):
    def test_required_ids_are_cumulative(self):
        self.assertEqual(required_ids(TIERS, 1), ["E01"])
        self.assertEqual(required_ids(TIERS, 3), ["E01", "E02", "E03"])

    def test_complete_record_is_allowed(self):
        res = check(body())
        self.assertEqual((res["decision"], res["findings"], res["required_tier"]), ("ALLOW", [], 2))

    def test_missing_item_blocks_and_names_it(self):
        res = check(body(lines=["- [x] E01 card | ref: ev/a.md | date: 2026-09-01"]))
        self.assertEqual((res["decision"], kinds(res), res["findings"][0]["items"]), ("BLOCK", ["evidence_missing"], ["E02"]))

    def test_unticked_box_blocks(self):
        res = check(body(lines=["- [ ] E01 card | ref: ev/a.md | date: 2026-09-01", "- [x] E02 e | ref: ev/b.md | date: 2026-09-01"]))
        self.assertEqual(kinds(res), ["not_ticked"])

    def test_ticked_box_without_a_reference_blocks(self):
        for line in ("- [x] E01 card | date: 2026-09-01", "- [x] E01 card | ref: | date: 2026-09-01", "- [x] E01 card | ref: `` | date: 2026-09-01"):
            res = check(body(lines=[line, "- [x] E02 e | ref: ev/b.md | date: 2026-09-01"]))
            self.assertEqual(kinds(res), ["no_reference"], line)

    def test_reference_must_be_a_listed_file(self):
        res = check(body(lines=["- [x] E01 card | ref: ev/nope.md | date: 2026-09-01", "- [x] E02 e | ref: ./ev/../ev/b.md | date: 2026-09-01"]))
        self.assertEqual(kinds(res), ["reference_not_found"])
        self.assertEqual(res["findings"][0]["items"], ["E01"])

    def test_reference_leaving_the_repository_blocks(self):
        for ref in ("../secret.md", "/etc/passwd", "file:///etc/passwd", "..", "C:\\x.md"):
            res = check(body(lines=[f"- [x] E01 card | ref: {ref} | date: 2026-09-01", "- [x] E02 e | ref: ev/b.md | date: 2026-09-01"]))
            self.assertEqual(kinds(res), ["reference_outside_repo"], ref)

    def test_external_link_goes_to_review_not_block(self):
        res = check(body(lines=["- [x] E01 card | ref: https://wiki.example.invalid/x | date: 2026-09-01",
                                "- [x] E02 e | ref: [plan](ev/b.md) | date: 2026-09-01"]))
        self.assertEqual((res["decision"], kinds(res)), ("REVIEW", ["reference_external"]))

    def test_dates(self):
        def one(date):
            return check(body(lines=["- [x] E01 card | ref: ev/a.md | " + date, "- [x] E02 e | ref: ev/b.md | date: 2026-09-01"]))
        self.assertEqual(kinds(one("date: TBD")), ["date_invalid"])
        self.assertEqual(kinds(one("date: 03/09/2026")), ["date_invalid"])
        self.assertEqual(kinds(one("")), ["date_invalid"])
        self.assertEqual(kinds(one("date: 2026-10-17")), ["date_future"])
        self.assertEqual(one("date: 2026-10-16")["decision"], "ALLOW")

    def test_age_limit_is_inclusive(self):
        last_valid = (AS_OF - datetime.timedelta(days=90)).isoformat()
        too_old = (AS_OF - datetime.timedelta(days=91)).isoformat()
        ok = check(body(lines=["- [x] E01 c | ref: ev/a.md | date: 2026-09-01", f"- [x] E02 e | ref: ev/b.md | date: {last_valid}"]))
        old = check(body(lines=["- [x] E01 c | ref: ev/a.md | date: 2026-09-01", f"- [x] E02 e | ref: ev/b.md | date: {too_old}"]))
        self.assertEqual(ok["decision"], "ALLOW")
        self.assertEqual((kinds(old), old["findings"][0]["reason"]), (["stale"], "E02 is 91 days old; the limit is 90"))

    def test_registry_tier_sets_the_bar_over_the_declared_tier(self):
        res = check(body(uc="UC-3", tier=1, lines=["- [x] E01 card | ref: ev/a.md | date: 2026-09-01"]))
        self.assertEqual(res["required_tier"], 3)
        self.assertEqual(kinds(res), ["tier_mismatch", "evidence_missing"])
        self.assertEqual(res["findings"][1]["items"], ["E02", "E03"])

    def test_wrong_label_with_complete_evidence_goes_to_review(self):
        for tier in (1, 3, None):
            res = check(body(tier=tier))
            self.assertEqual((res["decision"], kinds(res)), ("REVIEW", ["tier_mismatch"]), tier)

    def test_unregistered_use_case_takes_the_declared_tier_and_is_reviewed(self):
        res = check(body(uc="UC-99", tier=1, lines=["- [x] E01 card | ref: ev/a.md | date: 2026-09-01"]))
        self.assertEqual((res["decision"], kinds(res), res["required_tier"]), ("REVIEW", ["tier_unverified"], 1))

    def test_no_tier_from_anywhere_blocks(self):
        res = check(body(uc="UC-99", tier=None))
        self.assertEqual((res["decision"], kinds(res)), ("BLOCK", ["tier_unknown"]))
        self.assertEqual(check(body(uc=None, tier=None, lines=["- [x] E01 c | ref: ev/a.md | date: 2026-09-01"]))["decision"], "BLOCK")

    def test_missing_use_case_blocks(self):
        self.assertIn("use_case_missing", kinds(check(body(uc=None))))

    def test_conflicting_fields_block(self):
        self.assertIn("conflicting_fields", kinds(check("Use case: UC-1\nUse case: UC-3\n" + body(uc=None))))

    def test_no_record_blocks_and_says_so(self):
        res = check("Fixes a typo.")
        self.assertEqual((res["decision"], kinds(res)), ("BLOCK", ["no_record"]))
        self.assertIn("no AI change record", res["findings"][0]["reason"])

    def test_skipped_inputs_are_said_aloud(self):
        res = check(body(), registry=None, files=None, as_of=None)
        self.assertEqual(res["notes"], ["reference files were not checked (no file listing given)", "dates were not checked (no as-of date)"])
        self.assertEqual(kinds(res), ["tier_unverified"])

    def test_without_dates_a_future_date_passes(self):
        text = body(lines=["- [x] E01 c | ref: ev/a.md | date: 2099-01-01", "- [x] E02 e | ref: ev/b.md | date: soon"])
        self.assertEqual(check(text, as_of=None)["decision"], "ALLOW")

    def test_item_not_required_at_the_tier_is_ignored(self):
        text = body(uc="UC-99", tier=1, lines=["- [x] E01 c | ref: ev/a.md | date: 2026-09-01", "- [ ] E03 sign | ref: | date: x"])
        self.assertEqual(kinds(check(text)), ["tier_unverified"])

    def test_duplicate_lines_one_good_one_bad_passes_but_two_bad_do_not(self):
        good = "- [x] E01 card | ref: ev/a.md | date: 2026-09-01"
        e2 = "- [x] E02 e | ref: ev/b.md | date: 2026-09-01"
        self.assertEqual(check(body(lines=["- [ ] E01 card | ref: ev/a.md | date: 2026-09-01", good, e2]))["decision"], "ALLOW")
        self.assertEqual(check(body(lines=["- [ ] E01 card", "- [x] E01 card", e2]))["decision"], "BLOCK")

    def test_evidence_only_in_a_comment_does_not_count(self):
        res = check(body(lines=["- [x] E01 card | ref: ev/a.md | date: 2026-09-01", "<!--", "- [x] E02 e | ref: ev/b.md | date: 2026-09-01", "-->"]))
        self.assertEqual((kinds(res), res["findings"][0]["items"]), (["evidence_missing"], ["E02"]))


if __name__ == "__main__":
    unittest.main()
