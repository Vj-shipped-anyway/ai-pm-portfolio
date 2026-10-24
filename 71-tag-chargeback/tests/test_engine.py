import os
import unittest

import _bootstrap  # noqa: F401
import tag_chargeback as tc

MICROS = tc.MICROS
REG = {"cc-1": {"cost_center": "CC-1", "name": "One", "active": True},
       "cc-2": {"cost_center": "CC-2", "name": "Two", "active": True},
       "cc-9": {"cost_center": "CC-9", "name": "Closed", "active": False}}
POLICY = {"required_tags": [{"key": "cost-center", "aliases": ["CostCenter"], "values": "registry"},
                            {"key": "app", "aliases": [], "values": "any"},
                            {"key": "env", "aliases": [], "values": ["prod", "dev"]}],
          "shared_services": frozenset({"Support"}), "max_unallocated_pct": 10.0}
ACCOUNTS = {"A1": {"shared": False, "default": "CC-1"}, "S1": {"shared": True, "default": ""}}


def line(i, usd, tags, account="S1", service="Compute", rid="r1"):
    return {"line_id": "L%d" % i, "month": "2026-03", "account_id": account, "service": service, "resource_id": rid,
            "usage_type": "u", "usd": int(usd * MICROS), "tags": tags}


def run(bill, **kw):
    return tc.allocate(bill, POLICY, REG, ACCOUNTS, **kw)


class RuleTests(unittest.TestCase):
    def test_exact_tag(self):
        r = run([line(1, 10, {"cost-center": "CC-1"})])[0]
        self.assertEqual((r["rule"], r["cost_center"]), ("tag", "CC-1"))

    def test_alias_key_and_loose_value_are_repaired(self):
        a, b = run([line(1, 10, {"CostCenter": "CC-2"}), line(2, 10, {"cost-center": "  cc-2 "})])
        self.assertEqual((a["rule"], a["cost_center"]), ("tag_repaired", "CC-2"))
        self.assertEqual((b["rule"], b["cost_center"]), ("tag_repaired", "CC-2"))

    def test_unlisted_alias_is_not_guessed(self):
        r = run([line(1, 10, {"costcentre": "CC-1"})])[0]
        self.assertEqual((r["rule"], r["reason"]), ("unallocated", "no_owner_found"))

    def test_closed_and_unknown_are_refused_and_not_overridden_by_the_account_default(self):
        closed, unknown = run([line(1, 10, {"cost-center": "CC-9"}, account="A1"), line(2, 10, {"cost-center": "CC-77"}, account="A1")])
        self.assertEqual(closed["reason"], "closed_cost_center")
        self.assertEqual(unknown["reason"], "unknown_cost_center")
        self.assertEqual((closed["rule"], unknown["rule"]), ("unallocated", "unallocated"))

    def test_conflicting_keys_refused_but_agreeing_keys_accepted(self):
        bad, ok = run([line(1, 10, {"cost-center": "CC-1", "CostCenter": "CC-2"}), line(2, 10, {"cost-center": "CC-1", "CostCenter": " cc-1"})])
        self.assertEqual(bad["reason"], "conflicting_tags")
        self.assertEqual((ok["rule"], ok["cost_center"]), ("tag_repaired", "CC-1"))

    def test_empty_value_counts_as_absent(self):
        r = run([line(1, 10, {"cost-center": "   "}, account="A1")])[0]
        self.assertEqual((r["rule"], r["cost_center"]), ("account_default", "CC-1"))

    def test_inherit_from_tagged_sibling(self):
        a, b = run([line(1, 10, {"cost-center": "CC-2"}), line(2, 5, {})])
        self.assertEqual((b["rule"], b["cost_center"]), ("inherit", "CC-2"))
        self.assertEqual(a["rule"], "tag")

    def test_inherit_passes_on_a_failed_tag_and_on_disagreement(self):
        bill = [line(1, 10, {"cost-center": "CC-9"}, rid="x"), line(2, 5, {}, rid="x"),
                line(3, 10, {"cost-center": "CC-1"}, rid="y"), line(4, 10, {"cost-center": "CC-2"}, rid="y"), line(5, 5, {}, rid="y")]
        r = run(bill)
        self.assertEqual((r[1]["rule"], r[1]["reason"]), ("unallocated", "closed_cost_center"))
        self.assertEqual((r[4]["rule"], r[4]["reason"]), ("unallocated", "resource_conflict"))

    def test_resource_grouping_uses_the_field_not_the_name(self):
        r = run([line(1, 10, {"cost-center": "CC-1"}, rid="res-1"), line(2, 5, {}, rid="res-10")])
        self.assertEqual(r[1]["reason"], "no_owner_found")

    def test_account_default_only_for_dedicated_accounts(self):
        a, b, c = run([line(1, 10, {}, account="A1", rid="a"), line(2, 10, {}, account="S1", rid="b"), line(3, 10, {}, account="nope", rid="c")])
        self.assertEqual((a["rule"], a["cost_center"]), ("account_default", "CC-1"))
        self.assertEqual((b["reason"], c["reason"]), ("no_owner_found", "no_owner_found"))

    def test_zero_cost_line_is_not_reported_as_unallocated(self):
        r = run([line(1, 0, {}), line(2, 10, {"cost-center": "CC-1"}, rid="q")])[0]
        self.assertEqual(r["rule"], "zero_cost")

    def test_rule_switches(self):
        bill = [line(1, 10, {}, account="A1")]
        self.assertEqual(run(bill, extras=frozenset())[0]["reason"], "no_owner_found")
        self.assertEqual(run([line(1, 10, {"cost-center": "cc-1"})], repair=False)[0]["reason"], "unknown_cost_center")


class SplitTests(unittest.TestCase):
    def test_split_adds_up_exactly(self):
        parts = tc.split_amount(100 * MICROS, [("A", 1), ("B", 1), ("C", 1)])
        self.assertEqual(sum(v for _, v in parts), 100 * MICROS)
        neg = tc.split_amount(-7, [("A", 2), ("B", 1)])
        self.assertEqual(sum(v for _, v in neg), -7)
        self.assertTrue(all(v <= 0 for _, v in neg))

    def test_shared_service_follows_the_other_allocations(self):
        bill = [line(1, 30, {"cost-center": "CC-1"}, rid="a"), line(2, 10, {"cost-center": "CC-2"}, rid="b"),
                line(3, 40, {}, service="Support", rid="")]
        r = run(bill)
        self.assertEqual(dict(r[2]["shares"]), {"CC-1": 30 * MICROS, "CC-2": 10 * MICROS})

    def test_no_basis_is_said_not_hidden(self):
        r = run([line(1, 40, {}, service="Support", rid="")])[0]
        self.assertEqual(r["reason"], "no_basis_for_split")

    def test_allocated_plus_unallocated_equals_the_bill(self):
        bill = [line(1, 33.33, {"cost-center": "CC-1"}, rid="a"), line(2, 33.34, {"cost-center": "CC-2"}, rid="b"),
                line(3, 10.01, {}, service="Support", rid=""), line(4, -3.1, {"cost-center": "CC-9"}, rid="c"),
                line(5, 2.5, {}, rid="d")]
        r = run(bill)
        placed = sum(v for x in r for _, v in x["shares"])
        self.assertEqual(placed + sum(x["usd"] for x in r if x["rule"] == "unallocated"), sum(b["usd"] for b in bill))


class ComplianceTests(unittest.TestCase):
    def test_exempt_strict_and_repaired(self):
        full = {"cost-center": "CC-1", "app": "x", "env": "prod"}
        loose = {"CostCenter": "cc-1", "app": "x", "env": "prod"}
        self.assertIsNone(tc.line_compliance(line(1, 0, full), POLICY, REG, False))
        self.assertIsNone(tc.line_compliance(line(2, 5, {}, service="Support"), POLICY, REG, False))
        self.assertTrue(tc.line_compliance(line(3, 5, full), POLICY, REG, False))
        self.assertFalse(tc.line_compliance(line(4, 5, loose), POLICY, REG, False))
        self.assertTrue(tc.line_compliance(line(5, 5, loose), POLICY, REG, True))
        self.assertFalse(tc.line_compliance(line(6, 5, dict(full, env="production")), POLICY, REG, True))

    def test_hostile_text_is_escaped_for_one_line_output(self):
        self.assertEqual(tc.clean("a\nb\r::error::x\x1b"), "a\\nb\\r::error::x\\x1b")
        self.assertEqual(tc.escape_annotation("a%\r\nb"), "a%25%0D%0Ab")

    def test_hostile_tag_values_do_not_crash_the_engine(self):
        tags = {"cost-center": "CC-1\n::error title=forged::x", "app": "\x00", "env": "%s%n"}
        r = run([line(1, 10, tags)])[0]
        self.assertEqual(r["reason"], "unknown_cost_center")


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        cls.reg = tc.load_cost_centers(os.path.join(d, "cost_centers.csv"))
        cls.policy = tc.load_policy(os.path.join(d, "policy.json"))
        cls.accounts = tc.load_accounts(os.path.join(d, "accounts.csv"), cls.reg)
        cls.bill = tc.load_bill(os.path.join(d, "billing_export.csv"))
        import csv
        with open(os.path.join(d, "billing_truth.csv"), newline="", encoding="utf-8") as fh:
            cls.truth = {r["line_id"]: r for r in csv.DictReader(fh)}

    def test_strict_compliance_agrees_with_the_planted_label_on_every_line(self):
        for b in self.bill:
            got = tc.line_compliance(b, self.policy, self.reg, False)
            want = {"yes": True, "no": False, "exempt": None}[self.truth[b["line_id"]]["compliant"]]
            self.assertEqual(got, want, b["line_id"])

    def test_full_bill_reconciles_and_the_input_is_not_changed(self):
        before = [dict(b) for b in self.bill]
        r1 = tc.allocate(self.bill, self.policy, self.reg, self.accounts)
        r2 = tc.allocate(self.bill, self.policy, self.reg, self.accounts)
        self.assertEqual(r1, r2)
        self.assertEqual(before, self.bill)
        placed = sum(v for x in r1 for _, v in x["shares"])
        self.assertEqual(placed + sum(x["usd"] for x in r1 if x["rule"] == "unallocated"), sum(b["usd"] for b in self.bill))


if __name__ == "__main__":
    unittest.main()
