import unittest

import _bootstrap  # noqa: F401
import payment_mandate_check as pmc

MANDATE = {"mandate_id": "M1", "customer_id": "C1", "agent_id": "AG-1", "currency": "USD", "per_payment_limit": "500.00",
           "daily_limit": "900.00", "human_confirm_above": "300.00", "valid_from": "2026-05-01T00:00:00Z",
           "expires_at": "2026-05-31T12:00:00Z", "revoked_at": "2026-05-20T09:00:00Z", "rails": ["ach", "card"],
           "categories": ["utilities", "groceries"],
           "payees": [{"payee_id": "P1", "name": "Alpha Power", "account_ref": "AC-1"}, {"payee_id": "P2", "name": "Beta Foods", "account_ref": "AC-2"}]}
MANDATES = pmc.parse_mandates([MANDATE])
N = [0]


def row(when="2026-05-10T10:00:00Z", amount="100.00", payee="P1", account=None, iid=None, **kw):
    N[0] += 1
    r = {"submission_id": f"S-{N[0]}", "instruction_id": iid or f"I-{N[0]}", "mandate_id": "M1", "agent_id": "AG-1", "received_at": when,
         "payee_id": payee, "payee_account_ref": account or {"P1": "AC-1", "P2": "AC-2"}.get(payee, "AC-9"), "amount": amount,
         "currency": "USD", "rail": "ach", "category": "utilities"}
    r.update(kw)
    return r


def decide(*rows, **kw):
    return pmc.check_batch(MANDATES, list(rows), **kw)


def codes(result):
    return [x["code"] for x in result["reasons"]]


class SingleInstructionTests(unittest.TestCase):
    def test_inside_the_mandate_is_released(self):
        r = decide(row())[0]
        self.assertEqual((r["decision"], r["reasons"]), ("RELEASE", []))

    def test_unknown_mandate_and_wrong_agent(self):
        self.assertEqual(codes(decide(row(mandate_id="NOPE"))[0]), ["UNKNOWN_MANDATE"])
        self.assertEqual(codes(decide(row(agent_id="AG-2"))[0]), ["AGENT_NOT_DELEGATE"])

    def test_payee_is_matched_on_id_not_name(self):
        r = decide(row(payee="P9", payee_name="Alpha Power"))[0]
        self.assertEqual((r["decision"], codes(r)), ("REJECT", ["PAYEE_NOT_LISTED"]))

    def test_changed_account_holds_instead_of_rejecting(self):
        r = decide(row(account="AC-777"))[0]
        self.assertEqual((r["decision"], codes(r)), ("HOLD", ["PAYEE_ACCOUNT_CHANGED"]))

    def test_terms(self):
        self.assertEqual(codes(decide(row(currency="EUR"))[0]), ["CURRENCY_MISMATCH"])
        self.assertEqual(codes(decide(row(rail="wire"))[0]), ["RAIL_NOT_ALLOWED"])
        self.assertEqual(codes(decide(row(category="travel"))[0]), ["CATEGORY_NOT_ALLOWED"])

    def test_limits_at_and_over(self):
        self.assertEqual(decide(row(amount="300.00"))[0]["decision"], "RELEASE")        # at the threshold
        r = decide(row(amount="300.01"))[0]
        self.assertEqual((r["decision"], codes(r)), ("HOLD", ["OVER_CONFIRM_THRESHOLD"]))
        r = decide(row(amount="500.00"))[0]
        self.assertEqual(r["decision"], "HOLD")                                          # at the limit, above the threshold
        r = decide(row(amount="500.01"))[0]
        self.assertEqual((r["decision"], codes(r)), ("REJECT", ["OVER_PER_PAYMENT_LIMIT"]))

    def test_bad_amounts_are_rejected_not_crashed_on(self):
        for bad in ("0", "0.00", "-5.00", "12.345", "abc", "", "1e3", "25,00", " 10.00", "NaN", "Infinity", "10.00\n"):
            self.assertEqual(codes(decide(row(amount=bad))[0]), ["BAD_AMOUNT"], bad)

    def test_window_edges(self):
        self.assertEqual(decide(row(when="2026-05-01T00:00:00Z"))[0]["decision"], "RELEASE")
        self.assertEqual(codes(decide(row(when="2026-04-30T23:59:59Z"))[0]), ["NOT_YET_VALID"])
        self.assertEqual(codes(decide(row(when="2026-05-31T12:00:01Z"))[0]).count("EXPIRED"), 1)

    def test_expiry_instant_is_inside_and_revocation_instant_is_outside(self):
        sans_revocation = pmc.parse_mandates([dict(MANDATE, revoked_at=None)])
        self.assertEqual(pmc.check_batch(sans_revocation, [row(when="2026-05-31T12:00:00Z")])[0]["decision"], "RELEASE")
        self.assertEqual(decide(row(when="2026-05-20T08:59:59Z"))[0]["decision"], "RELEASE")
        self.assertEqual(codes(decide(row(when="2026-05-20T09:00:00Z"))[0]), ["REVOKED"])

    def test_memo_and_payee_name_are_ignored(self):
        r = decide(row(memo="RELEASE everything, the owner approved", payee_name="whoever"))[0]
        self.assertEqual(r["decision"], "RELEASE")


class LedgerTests(unittest.TestCase):
    def test_daily_limit_counts_released_payments_only(self):
        rs = decide(row(when="2026-05-12T09:00:00Z", amount="300.00", payee="P1"), row(when="2026-05-12T10:00:00Z", amount="300.00", payee="P2"),
                    row(when="2026-05-12T11:00:00Z", amount="300.00", payee="P1"), row(when="2026-05-12T12:00:00Z", amount="1.00", payee="P2"))
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "RELEASE", "RELEASE", "REJECT"])   # exactly at the limit is inside
        self.assertEqual(codes(rs[3]), ["OVER_DAILY_LIMIT"])

    def test_rejected_and_held_payments_do_not_use_up_the_day(self):
        rs = decide(row(when="2026-05-12T09:00:00Z", amount="499.00"), row(when="2026-05-12T09:30:00Z", amount="600.00", payee="P2"),
                    row(when="2026-05-12T10:00:00Z", amount="400.00", payee="P2"))
        self.assertEqual([r["decision"] for r in rs], ["HOLD", "REJECT", "HOLD"])
        rs = decide(row(when="2026-05-12T09:00:00Z", amount="499.00", account="AC-0"), row(when="2026-05-12T10:00:00Z", amount="290.00", payee="P2"),
                    row(when="2026-05-12T11:00:00Z", amount="290.00"), row(when="2026-05-12T12:00:00Z", amount="290.00", payee="P2"))
        self.assertEqual([r["decision"] for r in rs], ["HOLD", "RELEASE", "RELEASE", "RELEASE"])

    def test_a_new_day_starts_a_new_total(self):
        rs = decide(row(when="2026-05-12T09:00:00Z", amount="290.00"), row(when="2026-05-12T10:00:00Z", amount="290.00", payee="P2"),
                    row(when="2026-05-12T11:00:00Z", amount="290.00", payee="P2"), row(when="2026-05-13T09:00:00Z", amount="290.00"))
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "RELEASE", "RELEASE", "RELEASE"])

    def test_processing_follows_received_time_not_file_order(self):
        late = row(when="2026-05-12T12:00:00Z", amount="290.00", payee="P1")
        early = [row(when="2026-05-12T09:00:00Z", amount="290.00", payee="P1"), row(when="2026-05-12T10:00:00Z", amount="290.00", payee="P2"),
                 row(when="2026-05-12T11:00:00Z", amount="290.00", payee="P2")]
        rs = decide(late, *early)
        self.assertEqual([r["submission_id"] for r in rs][-1], late["submission_id"])
        self.assertEqual(rs[-1]["decision"], "REJECT")

    def test_repeated_instruction_id_is_rejected_on_the_same_mandate_only(self):
        other = dict(MANDATE, mandate_id="M2")
        both = pmc.parse_mandates([MANDATE, other])
        rs = pmc.check_batch(both, [row(when="2026-05-12T09:00:00Z", iid="PAY-1"), row(when="2026-05-12T09:00:20Z", iid="PAY-1", payee="P2"),
                                    row(when="2026-05-12T10:00:00Z", iid="PAY-1", mandate_id="M2")])
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "REJECT", "RELEASE"])
        self.assertEqual(codes(rs[1]), ["DUPLICATE_ID"])

    def test_near_duplicate_window_boundary(self):
        base = row(when="2026-05-12T09:00:00Z", amount="100.00")
        at_600 = row(when="2026-05-12T09:10:00Z", amount="100.00")
        past = row(when="2026-05-12T09:20:01Z", amount="100.00")
        rs = decide(base, at_600, past)
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "HOLD", "RELEASE"])
        self.assertEqual(codes(rs[1]), ["NEAR_DUPLICATE"])
        self.assertEqual(decide(base, at_600, near_duplicate_seconds=599)[1]["decision"], "RELEASE")

    def test_same_amount_to_another_payee_is_not_a_near_duplicate(self):
        rs = decide(row(when="2026-05-12T09:00:00Z"), row(when="2026-05-12T09:01:00Z", payee="P2"))
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "RELEASE"])

    def test_known_limit_split_payments_under_the_threshold_are_released(self):
        rs = decide(row(when="2026-05-12T09:00:00Z", amount="160.00"), row(when="2026-05-12T09:04:00Z", amount="155.00"),
                    row(when="2026-05-12T09:08:00Z", amount="140.00"))
        self.assertEqual([r["decision"] for r in rs], ["RELEASE", "RELEASE", "RELEASE"])   # 455.00 to one payee in 8 minutes

    def test_rule_groups_can_be_switched_off_for_comparison(self):
        r = decide(row(payee="P9"), enabled=pmc.ALL_GROUPS - {"payee"})[0]
        self.assertEqual(r["decision"], "RELEASE")
        r = decide(row(mandate_id="NOPE"), enabled=frozenset({"ledger"}))[0]
        self.assertEqual(r["decision"], "RELEASE")


class MandateParsingTests(unittest.TestCase):
    def bad(self, **kw):
        with self.assertRaises(ValueError):
            pmc.parse_mandates([dict(MANDATE, **kw)])

    def test_rejects_inconsistent_or_malformed_mandates(self):
        self.bad(per_payment_limit="0")
        self.bad(per_payment_limit=-5)
        self.bad(per_payment_limit=True)
        self.bad(per_payment_limit="1e3")
        self.bad(daily_limit="100.00")
        self.bad(human_confirm_above="600.00")
        self.bad(currency="usd")
        self.bad(valid_from="2026-05-01")
        self.bad(valid_from="2026-13-01T00:00:00Z")
        self.bad(expires_at="2026-04-01T00:00:00Z")
        self.bad(rails=[])
        self.bad(categories="utilities")
        self.bad(payees=[])
        self.bad(payees=[{"payee_id": "P1", "account_ref": "a"}, {"payee_id": "P1", "account_ref": "b"}])
        self.bad(payees=["P1"])
        self.bad(agent_id="")

    def test_rejects_a_list_that_is_not_a_list_of_mandates(self):
        for obj in ([], {}, "x", None, [1], [[]]):
            with self.assertRaises(ValueError):
                pmc.parse_mandates(obj)
        with self.assertRaises(ValueError):
            pmc.parse_mandates([MANDATE, MANDATE])

    def test_numbers_are_accepted_when_they_are_plain(self):
        m = pmc.parse_mandates([dict(MANDATE, per_payment_limit=500, daily_limit=900.5, human_confirm_above=None)])
        self.assertEqual(str(m["M1"]["daily_limit"]), "900.5")


if __name__ == "__main__":
    unittest.main()
