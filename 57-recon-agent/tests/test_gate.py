import unittest

import _bootstrap  # noqa: F401
from _ledgers import Workspace, a_line, b_line
import recon_agent as ra


def ap(key, decision="approve", approver="reviewer-1"):
    return {"key": key, "decision": decision, "approver": approver, "note": ""}


class GateTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.close)
        # one match that needs a person: no reference on the bank line
        self.a, self.b = self.ws.rows([a_line("A1", "2026-03-02", "100.00")], [b_line("B1", "2026-03-02", "100.00", ref="INV-1001")])
        self.key = ra.reconcile(self.a, self.b, [])["proposals"][0]["key"]

    def status(self, approvals):
        res = ra.reconcile(self.a, self.b, approvals)
        return res["proposals"][0]["status"], res["refused"], res

    def test_without_an_approval_the_match_waits(self):
        self.assertEqual(self.status([])[0], "pending")

    def test_an_approval_from_someone_else_posts_it_with_their_name(self):
        status, refused, res = self.status([ap(self.key)])
        self.assertEqual((status, refused, res["proposals"][0]["approver"]), ("posted_approved", [], "reviewer-1"))

    def test_a_rejection_keeps_it_out_and_lists_both_lines(self):
        status, _, res = self.status([ap(self.key, "reject")])
        self.assertEqual(status, "rejected")
        self.assertEqual({o["reason"] for o in res["open"]}, {"rejected_by_reviewer"})

    def test_the_agent_cannot_approve_its_own_match_in_any_spelling(self):
        for who in ("recon-agent", "Recon-Agent", "  RECON-AGENT  "):
            status, refused, _ = self.status([ap(self.key, approver=who)])
            self.assertEqual(status, "pending", who)
            self.assertTrue(refused[0]["why"].startswith("self-approval"))

    def test_an_approval_for_a_different_proposal_is_refused_as_stale(self):
        status, refused, _ = self.status([ap(self.key.replace("B1", "B2"))])
        self.assertEqual(status, "pending")
        self.assertTrue(refused[0]["why"].startswith("stale"))

    def test_an_approval_for_the_same_lines_but_another_amount_is_stale(self):
        status, refused, _ = self.status([ap(self.key[:-1] + "1")])
        self.assertEqual((status, len(refused)), ("pending", 1))

    def test_conflicting_decisions_leave_it_pending(self):
        status, refused, _ = self.status([ap(self.key), ap(self.key, "reject", "reviewer-2")])
        self.assertEqual(status, "pending")
        self.assertTrue(refused[0]["why"].startswith("conflicting"))

    def test_a_valid_approval_next_to_a_self_approval_still_posts(self):
        status, refused, _ = self.status([ap(self.key, approver="recon-agent"), ap(self.key)])
        self.assertEqual((status, len(refused)), ("posted_approved", 1))

    def test_a_proposal_that_fails_its_check_is_blocked_even_with_an_approval(self):
        res = ra.reconcile(self.a, self.b, [])
        q = res["proposals"][0]
        q["problems"] = ["forced for the test"]
        ra.apply_gate(res["proposals"], [ap(q["key"])])
        self.assertEqual(q["status"], "blocked")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.close)

    def only(self, a, b, params=ra.DEFAULT_PARAMS):
        ar, br = self.ws.rows([a], [b])
        res = ra.reconcile(ar, br, [], params)
        return res["proposals"][0], res

    def test_a_clean_exact_match_below_the_limit_posts_on_its_own(self):
        q, _ = self.only(a_line("A1", "2026-03-02", "9999.99", ref="INV-1"), b_line("B1", "2026-03-02", "9999.99", ref="INV-1"))
        self.assertEqual((q["gate"], q["status"]), ("auto", "posted_auto"))

    def test_the_limit_is_inclusive_and_above_it_a_person_is_needed(self):
        q, _ = self.only(a_line("A1", "2026-03-02", "10000.00", ref="INV-1"), b_line("B1", "2026-03-02", "10000.00", ref="INV-1"))
        self.assertEqual(q["gate"], "auto")
        q, _ = self.only(a_line("A1", "2026-03-02", "10000.01", ref="INV-1"), b_line("B1", "2026-03-02", "10000.01", ref="INV-1"))
        self.assertEqual((q["gate"], q["status"]), ("approval", "pending"))
        self.assertIn("above 10000.00", q["gate_why"])

    def test_the_limit_is_a_parameter_and_applies_to_debits(self):
        q, _ = self.only(a_line("A1", "2026-03-02", "-500.00", ref="INV-1"), b_line("B1", "2026-03-02", "-500.00", ref="INV-1"), ra.Params(limit_cents=10000))
        self.assertEqual(q["gate"], "approval")

    def test_a_reference_match_with_a_different_payer_name_needs_a_person(self):
        q, _ = self.only(a_line("A1", "2026-03-02", "100.00", ref="INV-1", name="Quillon Group Treasury"), b_line("B1", "2026-03-02", "100.00", ref="INV-1"))
        self.assertEqual((q["gate"], q["gate_why"]), ("approval", "the counterparty text differs"))

    def test_an_approval_for_an_auto_proposal_changes_nothing(self):
        ar, br = self.ws.rows([a_line("A1", "2026-03-02", "100.00", ref="INV-1")], [b_line("B1", "2026-03-02", "100.00", ref="INV-1")])
        key = ra.reconcile(ar, br, [])["proposals"][0]["key"]
        res = ra.reconcile(ar, br, [ap(key, "reject")])
        self.assertEqual((res["proposals"][0]["status"], res["refused"]), ("posted_auto", []))

    def test_every_rule_but_ref_exact_needs_a_person(self):
        self.assertEqual({r for r, g in ra.GATE_POLICY.items() if g == "auto"}, {"ref_exact"})
        self.assertEqual(set(ra.GATE_POLICY), set(ra.RULES))


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        self.addCleanup(self.ws.close)
        a = [a_line("A1", "2026-03-02", "100.00", ref="INV-1"), a_line("A2", "2026-03-04", "3000.00", ref="BT-0304")]
        b = [b_line("B1", "2026-03-02", "100.00", ref="INV-1"), b_line("B2", "2026-03-04", "1000.00", ref="INV-2", batch="BT-0304"),
             b_line("B3", "2026-03-04", "2000.00", ref="INV-3", batch="BT-0304")]
        self.a, self.b = self.ws.rows(a, b)
        res = ra.reconcile(self.a, self.b, [])
        keyed = [ap(q["key"]) for q in res["proposals"] if q["gate"] == "approval"]
        self.res = ra.reconcile(self.a, self.b, keyed)
        ra.write_outputs(self.res, self.ws.path("out"))
        self.rows = ra.load_matches(self.ws.path("out/matches.csv"))

    def check(self, rows):
        return ra.verify_matches(self.a, self.b, rows)

    def test_a_clean_run_re_checks(self):
        self.assertEqual(self.check(self.rows), [])

    def test_a_swapped_book_line_is_caught(self):
        rows = [dict(m, b_ids="B3") if m["rule"] == "ref_exact" else m for m in self.rows]
        self.assertTrue(self.check(rows))

    def test_a_missing_line_is_caught(self):
        rows = [dict(m, b_ids="B9") if m["rule"] == "ref_exact" else m for m in self.rows]
        self.assertIn("not in the ledgers", self.check(rows)[0])

    def test_a_batch_that_leaves_out_a_member_is_caught(self):
        rows = [dict(m, b_ids="B2") if m["rule"] == "batch_sum" else m for m in self.rows]
        self.assertTrue(self.check(rows))

    def test_a_batch_match_that_skips_one_member_is_caught_even_when_the_sum_fits(self):
        a, b = self.ws.rows([a_line("A1", "2026-03-04", "3000.00", ref="BT-0304")],
                            [b_line("B1", "2026-03-04", "1000.00", ref="INV-2", batch="BT-0304"), b_line("B2", "2026-03-04", "2000.00", ref="INV-3", batch="BT-0304"),
                             b_line("B3", "2026-03-04", "500.00", ref="INV-4", batch="BT-0304")])
        claim = {"match_id": "M-1", "rule": "batch_sum", "status": "posted_approved", "a_ids": "A1", "b_ids": "B1+B2", "approver": "reviewer-1",
                 "evidence": " | ".join(ra.evidence_lines("batch_sum", a[0], [b[0], b[1]]))}
        self.assertEqual(ra.verify_matches(a, b, [claim]), ["M-1: the match leaves out a book line of the same batch"])

    def test_a_line_used_twice_is_caught(self):
        self.assertTrue(any("already used" in p for p in self.check(self.rows + [dict(self.rows[0], match_id="M-9")])))

    def test_approved_relabelled_as_auto_is_caught(self):
        rows = [dict(m, status="posted_auto") if m["status"] == "posted_approved" else m for m in self.rows]
        self.assertTrue(any("policy requires" in p for p in self.check(rows)))

    def test_approval_with_no_approver_or_the_agent_as_approver_is_caught(self):
        for who in ("", "recon-agent"):
            rows = [dict(m, approver=who) if m["status"] == "posted_approved" else m for m in self.rows]
            self.assertTrue(any("no approver" in p for p in self.check(rows)), who)

    def test_edited_evidence_is_caught(self):
        rows = [dict(m, evidence=m["evidence"].replace("names agree", "names differ")) if m["rule"] == "ref_exact" else m for m in self.rows]
        self.assertTrue(any("stored evidence" in p for p in self.check(rows)))

    def test_an_unknown_rule_is_caught_without_a_crash(self):
        rows = [dict(m, rule="made_up") if m["rule"] == "ref_exact" else m for m in self.rows]
        self.assertTrue(any("unknown rule" in p for p in self.check(rows)))

    def test_matches_that_are_not_posted_are_not_checked(self):
        self.assertEqual(self.check([dict(m, status="pending", b_ids="B9") for m in self.rows]), [])


if __name__ == "__main__":
    unittest.main()
