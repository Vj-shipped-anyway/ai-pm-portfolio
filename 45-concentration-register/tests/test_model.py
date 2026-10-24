from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401
from concentration_register import analyze, lost_set, make_register, over_limit, scenarios_for


def svc(sid, crit="critical", primary=("CP-1", "R1"), mode="single", second=None):
    return {"id": sid, "name": sid, "owner": "internal", "criticality": crit,
            "primary": primary, "resilience": mode if primary else "", "second": second}


def reg_of(services, edges=()):
    return make_register({s["id"]: s for s in services}, list(edges))


P1 = {"id": "P:CP-1", "kind": "provider", "provider": "CP-1", "region": ""}
R1 = {"id": "R:CP-1/R1", "kind": "region", "provider": "CP-1", "region": "R1"}
R2 = {"id": "R:CP-1/R2", "kind": "region", "provider": "CP-1", "region": "R2"}


class ModelTests(unittest.TestCase):
    def test_single_placement_is_lost_with_its_region_only(self):
        reg = reg_of([svc("a"), svc("b", primary=("CP-1", "R2"))])
        self.assertEqual(lost_set(reg, R1), {"a"})
        self.assertEqual(lost_set(reg, P1), {"a", "b"})

    def test_standby_outside_the_outage_carries_the_service(self):
        reg = reg_of([svc("a", mode="warm_standby", second=("CP-2", "R1"))])
        self.assertEqual(lost_set(reg, P1), set())
        self.assertEqual(lost_set(reg, P1, failover=False), {"a"})

    def test_standby_in_the_same_provider_does_not_survive_a_provider_outage(self):
        reg = reg_of([svc("a", mode="warm_standby", second=("CP-1", "R2"))])
        self.assertEqual(lost_set(reg, P1), {"a"})
        self.assertEqual(lost_set(reg, R1), set())

    def test_standby_on_the_same_placement_is_lost(self):
        reg = reg_of([svc("a", mode="warm_standby", second=("CP-1", "R1"))])
        self.assertEqual(lost_set(reg, R1), {"a"})

    def test_hard_dependency_propagates_through_a_chain_and_soft_does_not(self):
        reg = reg_of([svc("base"), svc("mid", primary=("CP-2", "R1")), svc("top", primary=("CP-3", "R1")),
                      svc("soft_only", primary=("CP-4", "R1"))],
                     [("mid", "base", "hard"), ("top", "mid", "hard"), ("soft_only", "base", "soft")])
        self.assertEqual(lost_set(reg, R1), {"base", "mid", "top"})
        self.assertEqual(lost_set(reg, R1, deps=False), {"base"})
        self.assertEqual(lost_set(reg, R1, soft_as_hard=True), {"base", "mid", "top", "soft_only"})

    def test_a_dependency_with_a_working_standby_stops_the_chain(self):
        reg = reg_of([svc("base", mode="active_active", second=("CP-2", "R1")), svc("top", primary=("CP-3", "R1"))],
                     [("top", "base", "hard")])
        self.assertEqual(lost_set(reg, P1), set())

    def test_unplaced_service_is_never_lost_by_placement(self):
        reg = reg_of([svc("a", primary=None)])
        self.assertEqual(lost_set(reg, P1), set())

    def test_scenarios_cover_primaries_and_standbys(self):
        reg = reg_of([svc("a", mode="warm_standby", second=("CP-2", "R1"))])
        self.assertEqual([s["id"] for s in scenarios_for(reg["services"])],
                         ["P:CP-1", "P:CP-2", "R:CP-1/R1", "R:CP-2/R1"])

    def test_limit_is_strict(self):
        self.assertFalse(over_limit(3, 10, 30.0))
        self.assertTrue(over_limit(4, 10, 30.0))

    def test_analyze_counts_only_critical_and_reports_unplaced(self):
        reg = reg_of([svc("a"), svc("b", crit="standard"), svc("c", primary=None)])
        res = analyze(reg, 30.0)
        self.assertEqual(res["critical"], 2)
        by = {r["scenario"]: r for r in res["scenarios"]}
        self.assertEqual((by["P:CP-1"]["effective_critical"], by["P:CP-1"]["critical_total"]), (1, 2))
        self.assertEqual(res["unplaced_critical"], ["c"])

    def test_no_critical_service_is_an_error_not_a_silent_zero(self):
        with self.assertRaises(ValueError):
            analyze(reg_of([svc("a", crit="standard")]), 30.0)

    def test_hard_cycle_is_rejected(self):
        with self.assertRaises(ValueError):
            reg_of([svc("a"), svc("b")], [("a", "b", "hard"), ("b", "a", "hard")])

    def test_soft_cycle_is_allowed(self):
        reg_of([svc("a"), svc("b")], [("a", "b", "soft"), ("b", "a", "soft")])

    def test_provider_names_are_compared_exactly(self):
        reg = reg_of([svc("a", primary=("CP-1", "R1")), svc("b", primary=("cp-1", "R1"))])
        self.assertEqual(lost_set(reg, P1), {"a"})


if __name__ == "__main__":
    unittest.main()
