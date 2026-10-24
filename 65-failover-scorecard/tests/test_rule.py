"""The readiness rule, one branch at a time, on small in-memory services and drills."""
import unittest
from datetime import date, timedelta

import _bootstrap  # noqa: F401
import failover_scorecard as fs

AS_OF = date(2026, 10, 24)


def svc(sid="S1", tier=1, mode="warm_standby", rto=30, version=2, deps=(), accepted=False, secondary="region-b", **kw):
    d = {"service_id": sid, "name": "svc-" + sid, "domain": "payments", "tier": tier, "primary_region": "region-a",
         "secondary_region": secondary, "failover_mode": mode, "rto_target_min": rto, "config_version": version,
         "depends_on": list(deps), "accepted_risk": accepted}
    d.update(kw)
    return d


def drill(did="D1", sid="S1", age=30, kind="live", scenario="region_failover", region="region-b", version=2,
          minutes=20, outcome="pass", reason=""):
    return {"drill_id": did, "service_id": sid, "date": AS_OF - timedelta(days=age), "type": kind, "scenario": scenario,
            "target_region": region, "config_version": version, "minutes": minutes, "outcome": outcome, "reason": reason}


def status_of(services, drills, sid="S1", policy=None):
    return {r["service_id"]: r for r in fs.score(services, drills, AS_OF, policy)}[sid]


class OwnEvidenceTests(unittest.TestCase):
    def test_clean_service_is_ready(self):
        self.assertEqual(status_of([svc()], [drill()])["status"], "READY")

    def test_no_secondary_region_is_no_path(self):
        self.assertEqual(status_of([svc(secondary="", mode="none")], [])["status"], "NO_PATH")

    def test_secondary_equal_to_primary_is_no_path(self):
        self.assertEqual(status_of([svc(secondary="region-a")], [drill(region="region-a")])["status"], "NO_PATH")

    def test_accepted_risk_on_tier_3_is_not_required(self):
        s = svc(tier=3, mode="none", secondary="", accepted=True)
        self.assertEqual(status_of([s], [])["status"], "NOT_REQUIRED")

    def test_accepted_risk_on_tier_1_is_not_honoured(self):
        r = status_of([svc(tier=1, mode="none", secondary="", accepted=True)], [])
        self.assertEqual(r["status"], "NO_PATH")
        self.assertIn("not honoured", r["reason"])

    def test_no_drill_is_untested(self):
        self.assertEqual(status_of([svc()], [])["status"], "UNTESTED")

    def test_tabletop_does_not_count_and_is_named(self):
        r = status_of([svc()], [drill(kind="tabletop", minutes=None)])
        self.assertEqual(r["status"], "UNTESTED")
        self.assertIn("1 tabletop", r["reason"])

    def test_availability_zone_drill_does_not_count(self):
        r = status_of([svc()], [drill(scenario="az_failover", region="region-a")])
        self.assertEqual(r["status"], "UNTESTED")
        self.assertIn("another scenario", r["reason"])

    def test_cold_restore_needs_a_backup_restore_drill(self):
        s = svc(mode="cold_restore")
        self.assertEqual(status_of([s], [drill()])["status"], "UNTESTED")
        self.assertEqual(status_of([s], [drill(scenario="backup_restore")])["status"], "READY")

    def test_latest_failed_drill_is_failed(self):
        r = status_of([svc()], [drill("D1", age=90), drill("D2", age=10, outcome="fail", minutes=None, reason="x")])
        self.assertEqual(r["status"], "FAILED")

    def test_failed_then_passed_is_ready(self):
        r = status_of([svc()], [drill("D1", age=90, outcome="partial", minutes=None), drill("D2", age=10)])
        self.assertEqual(r["status"], "READY")

    def test_same_day_tie_is_broken_by_drill_id(self):
        a, b = drill("D1", age=10, outcome="fail", minutes=None), drill("D2", age=10)
        self.assertEqual(status_of([svc()], [a, b])["status"], "READY")
        self.assertEqual(status_of([svc()], [b, a])["status"], "READY")

    def test_recovery_time_boundary(self):
        self.assertEqual(status_of([svc(rto=30)], [drill(minutes=30)])["status"], "READY")
        self.assertEqual(status_of([svc(rto=30)], [drill(minutes=31)])["status"], "SLOW")

    def test_wrong_region_and_old_config_are_changed(self):
        self.assertEqual(status_of([svc()], [drill(region="region-c")])["status"], "CHANGED")
        self.assertEqual(status_of([svc(version=3)], [drill(version=2)])["status"], "CHANGED")

    def test_window_boundary_by_tier(self):
        self.assertEqual(status_of([svc(tier=1)], [drill(age=180)])["status"], "READY")
        self.assertEqual(status_of([svc(tier=1)], [drill(age=181)])["status"], "STALE")
        self.assertEqual(status_of([svc(tier=2)], [drill(age=365)])["status"], "READY")
        self.assertEqual(status_of([svc(tier=2)], [drill(age=366)])["status"], "STALE")

    def test_drill_after_as_of_is_rejected(self):
        with self.assertRaises(fs.InputError):
            fs.score([svc()], [drill(age=-1)], AS_OF)

    def test_drill_for_unknown_service_is_rejected(self):
        with self.assertRaises(fs.InputError):
            fs.score([svc()], [drill(sid="S9")], AS_OF)


class DependencyTests(unittest.TestCase):
    def test_unready_dependency_blocks_a_clean_service(self):
        services = [svc("S1", deps=["S2"]), svc("S2")]
        r = {x["service_id"]: x for x in fs.score(services, [drill("D1", "S1")], AS_OF)}
        self.assertEqual(r["S1"]["status"], "DEPENDENCY")
        self.assertEqual(r["S1"]["blocked_by"], "S2")
        self.assertIn("UNTESTED", r["S1"]["reason"])

    def test_chain_names_where_it_ends(self):
        services = [svc("S1", deps=["S2"]), svc("S2", deps=["S3"]), svc("S3")]
        drills = [drill("D1", "S1"), drill("D2", "S2")]
        r = {x["service_id"]: x for x in fs.score(services, drills, AS_OF)}
        self.assertEqual((r["S1"]["status"], r["S2"]["status"]), ("DEPENDENCY", "DEPENDENCY"))
        self.assertIn("chain ends at svc-S3 (S3)", r["S1"]["reason"])

    def test_dependency_on_an_accepted_gap_blocks(self):
        services = [svc("S1", deps=["S2"]), svc("S2", tier=3, mode="none", secondary="", accepted=True)]
        self.assertEqual(status_of(services, [drill("D1", "S1")])["status"], "DEPENDENCY")

    def test_ready_dependency_does_not_block(self):
        services = [svc("S1", deps=["S2"]), svc("S2")]
        self.assertEqual(status_of(services, [drill("D1", "S1"), drill("D2", "S2")])["status"], "READY")

    def test_cycle_of_ready_services_stays_ready(self):
        services = [svc("S1", deps=["S2"]), svc("S2", deps=["S1"])]
        results = fs.score(services, [drill("D1", "S1"), drill("D2", "S2")], AS_OF)
        self.assertEqual([r["status"] for r in results], ["READY", "READY"])

    def test_cycle_with_an_unready_member_terminates_and_blocks_both(self):
        services = [svc("S1", deps=["S2"]), svc("S2", deps=["S1"]), svc("S3", deps=["S1"])]
        results = fs.score(services, [drill("D1", "S1"), drill("D3", "S3")], AS_OF)
        self.assertEqual([r["status"] for r in results], ["DEPENDENCY", "UNTESTED", "DEPENDENCY"])


class PolicyAndOrderTests(unittest.TestCase):
    def test_skipping_a_part_changes_the_result(self):
        policy = fs.default_policy()
        policy["skip"] = ("age",)
        self.assertEqual(status_of([svc()], [drill(age=400)], policy=policy)["status"], "READY")
        self.assertEqual(status_of([svc()], [drill(age=400)])["status"], "STALE")

    def test_default_policy_is_a_fresh_copy(self):
        a = fs.default_policy()
        a["window_days"][1] = 1
        self.assertEqual(fs.default_policy()["window_days"][1], 180)

    def test_input_order_does_not_change_the_output(self):
        services = [svc("S%d" % i) for i in range(1, 6)]
        drills = [drill("D%d" % i, "S%d" % i, age=i * 20) for i in range(1, 6)]
        forward = fs.score(services, drills, AS_OF)
        backward = fs.score(list(reversed(services)), list(reversed(drills)), AS_OF)
        self.assertEqual(forward, backward)

    def test_domain_line_groups_by_the_domain_field(self):
        services = [svc("S1", domain="cards", name="payments-looks-like-another-domain"), svc("S2", domain="payments")]
        line = fs.domain_line(fs.score(services, [drill("D1", "S1"), drill("D2", "S2")], AS_OF))
        self.assertEqual(line, "cards 1 of 1, payments 1 of 1")


if __name__ == "__main__":
    unittest.main()
