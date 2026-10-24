import unittest
from datetime import date

import _bootstrap  # noqa: F401
import call_notes_actions as cna

CALL = date(2026, 10, 14)  # a Wednesday
NOTES = {"N": {"call_date": CALL, "sentences": {
    1: "I will send Ms. Okafor the rate sheet by Friday.",
    2: "She will return the KYC form by 21 October.",
    3: "If the mortgage rate moves by more than 25 basis points, she wants me to call her.",
    4: "She does not want a follow-up call this quarter.",
    5: "I already sent the fee schedule last week.",
    6: "I might send the term sheet next month.",
    7: "She complained about the wire fee.",
    8: "She wants the overdraft limit increased to $25,000; I will submit the request by 16 October.",
    9: "Ms. Okafor will return the KYC form by 16 October, and I will send the rate sheet by 21 October.",
    10: "I will try to call her on Friday about the overdraft.",
    11: "Rates were discussed at length.",
    12: "She wants the overdraft limit increased to twenty-five thousand dollars; I will submit the request by 16 October.",
}}}


def cand(**kw):
    base = {"cand_id": "C", "note_id": "N", "action_type": "send_document", "owner": "rm", "due": "", "subject": "",
            "amount": "", "cite_sent_id": "1", "cite_quote": NOTES["N"]["sentences"][1]}
    base.update(kw)
    return base


def decide(**kw):
    sid = kw.get("cite_sent_id", "1")
    kw.setdefault("cite_quote", NOTES["N"]["sentences"].get(int(sid) if sid.isdigit() else -1, "x" * 20))
    return cna.check_candidate(NOTES, cand(**kw))


class QuoteTests(unittest.TestCase):
    S = "I'll email the rate sheet to Ms. Okafor by Friday."

    def test_tidied_quotes_still_match(self):
        for q in (self.S, self.S.replace("'", "’"), self.S.replace(" ", "  ", 1), self.S.lower(),
                  "I'll email the rate sheet…", "I'll email ... by Friday", self.S.rstrip(".")):
            self.assertTrue(cna.quote_in(self.S, q), q)

    def test_changed_or_trivial_quotes_do_not(self):
        for q in ("I'll personally email the rate sheet to Ms. Okafor by Friday.", "", "...", "I", "email", "by Monday"):
            self.assertFalse(cna.quote_in(self.S, q), q)

    def test_ellipsis_parts_must_keep_their_order(self):
        self.assertFalse(cna.quote_in(self.S, "by Friday ... I'll email the rate"))


class SlotTests(unittest.TestCase):
    def test_weekday_is_the_first_one_after_the_call(self):
        self.assertEqual(cna.resolve_dates("by Friday", CALL), {"2026-10-16"})
        self.assertEqual(cna.resolve_dates("on Wednesday", CALL), {"2026-10-21"})

    def test_tomorrow_day_month_and_iso(self):
        self.assertEqual(cna.resolve_dates("by tomorrow", CALL), {"2026-10-15"})
        self.assertEqual(cna.resolve_dates("on 21 October", CALL), {"2026-10-21"})
        self.assertEqual(cna.resolve_dates("on 3rd Nov", CALL), {"2026-11-03"})
        self.assertEqual(cna.resolve_dates("by 2026-11-02", CALL), {"2026-11-02"})

    def test_a_past_day_month_rolls_into_next_year_and_a_fake_date_is_ignored(self):
        self.assertEqual(cna.resolve_dates("on 5 January", date(2026, 12, 20)), {"2027-01-05"})
        self.assertEqual(cna.resolve_dates("on 31 February", CALL), set())

    def test_amounts_need_a_dollar_sign_or_a_suffix(self):
        self.assertEqual(cna.find_amounts("to $25,000 by 21 October"), {25000})
        self.assertEqual(cna.find_amounts("to $25k"), {25000})
        self.assertEqual(cna.find_amounts("to 25 thousand dollars"), {25000})
        self.assertEqual(cna.find_amounts("to $1.5m"), {1500000})
        self.assertEqual(cna.find_amounts("below 4.1% on 14 November, 12 months"), set())
        self.assertEqual(cna.find_amounts("to twenty-five thousand dollars"), set())

    def test_owner_markers(self):
        self.assertEqual(cna.owner_markers("I will send it."), (True, False))
        self.assertEqual(cna.owner_markers("She asked me to ring her."), (True, False))
        self.assertEqual(cna.owner_markers("Ms. Okafor will return it."), (False, True))
        self.assertEqual(cna.owner_markers("Rates were discussed."), (False, False))


class DecisionTests(unittest.TestCase):
    def test_grounded_action_is_accepted(self):
        self.assertEqual(decide(due="2026-10-16", subject="rate sheet"), ("ACCEPT", []))
        self.assertEqual(decide(action_type="await_document", owner="client", due="2026-10-21", subject="KYC form", cite_sent_id="2")[0], "ACCEPT")

    def test_statement_types_skip_owner_and_tense(self):
        self.assertEqual(decide(action_type="log_complaint", subject="wire fee", cite_sent_id="7"), ("ACCEPT", []))

    def test_missing_citation_is_rejected(self):
        self.assertEqual(decide(cite_sent_id="99"), ("REJECT", ["cite_not_found"]))
        self.assertEqual(decide(cite_sent_id="abc"), ("REJECT", ["cite_not_found"]))
        self.assertEqual(decide(cite_quote="I will personally send the rate sheet by Friday."), ("REJECT", ["cite_not_found"]))
        self.assertEqual(cna.check_candidate({}, cand())[0], "REJECT")

    def test_unknown_type_is_rejected(self):
        self.assertEqual(decide(action_type="wire_money"), ("REJECT", ["unknown_action_type"]))

    def test_sentence_that_does_not_carry_the_action_is_rejected(self):
        self.assertEqual(decide(cite_sent_id="11"), ("REJECT", ["no_support:trigger"]))
        self.assertEqual(decide(subject="term sheet"), ("REJECT", ["no_support:subject"]))

    def test_slots_owner_and_modality_send_it_to_a_person(self):
        self.assertEqual(decide(due="2026-10-17", subject="rate sheet"), ("REVIEW", ["due_not_in_sentence"]))
        self.assertEqual(decide(action_type="limit_request", subject="overdraft limit", due="2026-10-16", amount="30000", cite_sent_id="8"),
                         ("REVIEW", ["amount_not_in_sentence"]))
        self.assertEqual(decide(owner="client")[1], ["owner_mismatch"])
        self.assertEqual(decide(owner="")[1], ["owner_missing"])
        self.assertEqual(decide(action_type="callback", cite_sent_id="3")[1], ["conditional:if"])
        self.assertEqual(decide(action_type="callback", cite_sent_id="4")[1], ["owner_unclear", "negated:not"])
        self.assertEqual(decide(cite_sent_id="5")[1], ["owner_unclear", "past:already"])
        self.assertEqual(decide(cite_sent_id="6")[1], ["owner_unclear", "hedged:might"])

    def test_spelled_out_amount_is_held_not_read(self):
        self.assertEqual(decide(action_type="limit_request", subject="overdraft limit", due="2026-10-16", amount="25000", cite_sent_id="12"),
                         ("REVIEW", ["amount_not_in_sentence"]))

    def test_checks_can_be_chosen(self):
        c = cand(action_type="callback", cite_sent_id="3", cite_quote=NOTES["N"]["sentences"][3])
        self.assertEqual(cna.check_candidate(NOTES, c, ("cite",)), ("ACCEPT", []))
        self.assertEqual(cna.check_candidate(NOTES, c)[0], "REVIEW")

    def test_known_limit_clause_swap_passes(self):
        # the date 16 October belongs to the client's clause; the sentence-level rules cannot tell
        self.assertEqual(decide(due="2026-10-16", subject="rate sheet", cite_sent_id="9"), ("ACCEPT", []))

    def test_known_limit_soft_hedge_passes(self):
        self.assertEqual(decide(action_type="callback", due="2026-10-16", subject="overdraft", cite_sent_id="10"), ("ACCEPT", []))


if __name__ == "__main__":
    unittest.main()
