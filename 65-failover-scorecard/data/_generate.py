"""Generate the synthetic data for project 65: a service map of 48 services, a drill log, and the
planted truth about which services would really recover from the loss of their primary region.

Everything is seeded, so the files are byte-for-byte reproducible. The truth label comes from the
story planted for each service (a drill that failed, a drill that tested only one availability
zone, a dependency nobody declared), not from the readiness rule in src/. The generator never
imports the rule.

Three kinds are hard on purpose.
  * Hard negatives, which a careless rule could flag: a drill that failed once and was fixed and
    passed again (failed_then_fixed), a passing drill that is old but still inside its window
    (proven_old_unchanged), and a low-tier service whose owner formally accepted having no way
    back (accepted_no_failover).
  * Hard misses, which the rule cannot see: hidden_dependency, a service with a clean drill and
    clean declared dependencies whose real recovery needs a service the map does not list.
  * Cases that look tested and are not: tabletop_only, az_only, slow_pass, stale_drill,
    changed_since_drill, wrong_region_drill.

The window lengths used below to plant a stale drill (180, 365 and 540 days by tier) are the same
assumption the rule uses. They are mine; no rule sets them.

Run (from data/):  python3 _generate.py
Writes:  services.csv, drills.csv, service_truth.csv, example_services.csv, example_drills.csv
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 65
OUT = Path(__file__).parent
AS_OF = date(2026, 10, 24)                  # a constant: no clock is read
WINDOW = {1: 180, 2: 365, 3: 540}           # assumption, see the README
REGIONS = ["region-a", "region-b", "region-c"]

NAMES = {
    "payments": ["orchestrator", "ledger-posting", "fx-quotes", "sanctions-screen", "payee-directory",
                 "settlement-feed", "limits-engine", "notifier", "reconciliation"],
    "cards": ["auth-gateway", "token-vault", "dispute-intake", "fraud-scoring", "limits",
              "statement-batch", "pin-service", "processor-bridge", "card-controls"],
    "lending": ["origination-api", "credit-decision", "document-store", "pricing", "servicing-core",
                "collections-queue", "payoff-quote", "escrow-calc"],
    "onboarding": ["identity-check", "kyc-rules", "account-opening", "e-signature", "welcome-comms",
                   "risk-rating", "address-verify"],
    "channels": ["mobile-bff", "web-bff", "ivr-routing", "teller-api", "push-gateway", "session-store",
                 "content-cache"],
    "data-platform": ["event-bus", "feature-store", "reporting-mart", "audit-log", "batch-scheduler",
                      "secrets-broker", "search-index", "metrics-pipeline"],
}

# story, how many, tier of each service of that story (in creation order)
CREATION = [
    ("proven", 10, [1, 1, 2, 2, 2, 3, 2, 1, 3, 2]),
    ("proven_old_unchanged", 3, [1, 2, 2]),
    ("failed_then_fixed", 3, [1, 2, 2]),
    ("never_drilled", 3, [1, 2, 1]),
    ("drill_failed", 3, [1, 2, 2]),
    ("tabletop_only", 2, [1, 2]),
    ("az_only", 2, [2, 1]),
    ("slow_pass", 2, [1, 2]),
    ("stale_drill", 3, [2, 1, 2]),
    ("changed_since_drill", 3, [1, 2, 2]),
    ("wrong_region_drill", 2, [2, 1]),
    ("no_path", 2, [2, 2]),
    ("accepted_no_failover", 4, [3, 3, 3, 3]),
    ("dependency_gap", 3, [1, 1, 2]),
    ("hidden_dependency", 3, [1, 2, 1]),
]
FOUNDATION = ("proven", "proven_old_unchanged", "failed_then_fixed")
GAP_TARGET = ("never_drilled", "dependency_gap", "drill_failed")   # the k-th dependency_gap service depends on the first service of this story
TRUTH_CLASS = {"proven": "ready", "proven_old_unchanged": "ready", "failed_then_fixed": "ready",
               "accepted_no_failover": "accepted"}                      # every other story: not_ready

FAIL_REASONS = ["traffic switch not applied in the secondary region",
                "secondary database replica was behind and was not promoted",
                "runbook step referred to a retired host",
                "on-call engineer lacked permission to promote the replica",
                "secrets were not replicated to the secondary region"]

SERVICE_FIELDS = ["service_id", "name", "domain", "tier", "primary_region", "secondary_region", "failover_mode",
                  "rto_target_min", "config_version", "depends_on", "accepted_risk", "failover_plan"]
DRILL_FIELDS = ["drill_id", "service_id", "drill_date", "drill_type", "scenario", "target_region",
                "config_version", "minutes_to_recover", "outcome", "failure_reason"]
TRUTH_FIELDS = ["service_id", "story", "truth_class", "hidden_depends_on"]


def write_csv(name: str, fields: list, rows: list) -> None:
    with open(OUT / name, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def scenario_for(mode: str) -> str:
    return "region_failover" if mode in ("active_active", "warm_standby") else "backup_restore"


def build(rng: random.Random):
    pairs = [(d, r) for d, roles in NAMES.items() for r in roles]
    rng.shuffle(pairs)
    slots = [(story, k, tiers[k]) for story, n, tiers in CREATION for k in range(n)]
    order = list(range(1, len(slots) + 1))
    rng.shuffle(order)

    services, drills, truth, by_story = [], [], [], {}
    pool = []                                   # foundation services created so far
    for (story, k, tier), num, (domain, role) in zip(slots, order, pairs):
        sid = "S%03d" % num
        primary = rng.choice(REGIONS[:2])
        secondary = rng.choice([r for r in REGIONS if r != primary])
        third = [r for r in REGIONS if r not in (primary, secondary)][0]
        mode = {1: rng.choice(["active_active", "warm_standby"]), 2: rng.choice(["warm_standby", "cold_restore"]),
                3: "cold_restore"}[tier]
        rto = {1: rng.choice([30, 60]), 2: rng.choice([120, 240]), 3: 480}[tier]
        version = rng.randint(2, 4) if story == "changed_since_drill" else rng.randint(1, 4)
        deps = set(rng.sample(pool, min(len(pool), rng.choice([0, 0, 1, 1, 2]))))
        accepted = "no"
        if story == "no_path":
            secondary, mode = "", "none"
        if story == "accepted_no_failover":
            secondary, mode, accepted = "", "none", "yes"
        if story == "dependency_gap":
            deps.add(by_story[GAP_TARGET[k]][0])
        hidden = by_story["never_drilled"][k % 3] if story == "hidden_dependency" else ""
        by_story.setdefault(story, []).append(sid)
        if story in FOUNDATION:
            pool.append(sid)
        svc = dict(service_id=sid, name=f"{domain}-{role}", domain=domain, tier=tier, primary_region=primary,
                   secondary_region=secondary, failover_mode=mode, rto_target_min=rto, config_version=version,
                   depends_on=";".join(sorted(deps)), accepted_risk=accepted,
                   failover_plan="no" if mode == "none" else "yes")
        services.append(svc)
        truth.append(dict(service_id=sid, story=story, truth_class=TRUTH_CLASS.get(story, "not_ready"),
                          hidden_depends_on=hidden))
        drills.extend(plant_drills(rng, story, svc, third))
    return services, drills, truth


def drill(svc: dict, age: int, *, kind="live", scenario=None, region=None, version=None, minutes=None,
          outcome="pass", reason="") -> dict:
    return dict(service_id=svc["service_id"], drill_date=(AS_OF - timedelta(days=age)).isoformat(), drill_type=kind,
                scenario=scenario or scenario_for(svc["failover_mode"]),
                target_region=region or svc["secondary_region"],
                config_version=svc["config_version"] if version is None else version,
                minutes_to_recover="" if minutes is None else minutes, outcome=outcome, failure_reason=reason)


def plant_drills(rng: random.Random, story: str, svc: dict, third: str) -> list:
    w, rto, ver = WINDOW[svc["tier"]], svc["rto_target_min"], svc["config_version"]

    def fast():
        return int(round(rto * rng.uniform(0.4, 0.85)))

    out = []
    if story in ("proven", "dependency_gap", "hidden_dependency"):
        age = rng.randint(15, w // 2)
        out.append(drill(svc, age, minutes=fast()))
        if rng.random() < 0.5:
            out.append(drill(svc, age + rng.randint(60, 150), version=max(1, ver - 1), minutes=fast()))
    elif story == "proven_old_unchanged":
        out.append(drill(svc, w - rng.randint(6, 20), minutes=int(round(rto * rng.uniform(0.6, 0.9)))))
    elif story == "failed_then_fixed":
        age = rng.randint(10, w // 3)
        out.append(drill(svc, age + rng.randint(25, 90), outcome="fail", reason=rng.choice(FAIL_REASONS)))
        out.append(drill(svc, age, minutes=fast()))
    elif story == "drill_failed":
        age = rng.randint(10, w // 2)
        out.append(drill(svc, age, outcome=rng.choice(["fail", "partial"]), reason=rng.choice(FAIL_REASONS)))
        if rng.random() < 0.5:
            out.append(drill(svc, age + rng.randint(40, 120), minutes=fast()))
    elif story == "tabletop_only":
        for _ in range(rng.randint(1, 2)):
            out.append(drill(svc, rng.randint(20, w // 2), kind="tabletop"))
    elif story == "az_only":
        for _ in range(rng.randint(1, 2)):
            out.append(drill(svc, rng.randint(20, w // 2), scenario="az_failover", region=svc["primary_region"],
                             minutes=int(round(rto * rng.uniform(0.2, 0.5)))))
    elif story == "slow_pass":
        out.append(drill(svc, rng.randint(15, w // 2), minutes=int(round(rto * rng.uniform(1.3, 2.4)))))
    elif story == "stale_drill":
        out.append(drill(svc, w + rng.randint(30, 220), minutes=fast()))
    elif story == "changed_since_drill":
        out.append(drill(svc, rng.randint(20, w // 2), version=ver - 1, minutes=fast()))
    elif story == "wrong_region_drill":
        out.append(drill(svc, rng.randint(20, w // 2), region=third, minutes=fast()))
    return out


EXAMPLE_SERVICES = [
    ("S01", "payments-orchestrator", "payments", 1, "region-a", "region-b", "warm_standby", 30, 3, "S02", "no", "yes"),
    ("S02", "payments-ledger-posting", "payments", 1, "region-a", "region-b", "active_active", 30, 2, "", "no", "yes"),
    ("S03", "cards-auth-gateway", "cards", 1, "region-a", "region-b", "warm_standby", 30, 5, "", "no", "yes"),
    ("S04", "channels-mobile-bff", "channels", 1, "region-b", "region-a", "active_active", 60, 4, "S03", "no", "yes"),
    ("S05", "onboarding-identity-check", "onboarding", 1, "region-a", "region-c", "warm_standby", 60, 1, "", "no", "yes"),
    ("S06", "payments-fx-quotes", "payments", 2, "region-a", "region-b", "warm_standby", 120, 2, "", "no", "yes"),
    ("S07", "cards-statement-batch", "cards", 2, "region-b", "region-a", "cold_restore", 240, 1, "", "no", "yes"),
    ("S08", "data-platform-reporting-mart", "data-platform", 3, "region-a", "", "none", 480, 1, "", "yes", "no"),
]
EXAMPLE_DRILLS = [
    ("D01", "S01", "2026-09-02", "live", "region_failover", "region-b", 3, "22", "pass", ""),
    ("D02", "S02", "2026-08-19", "live", "region_failover", "region-b", 2, "14", "pass", ""),
    ("D03", "S03", "2026-08-11", "live", "region_failover", "region-b", 5, "", "fail",
     "traffic switch not applied in the secondary region"),
    ("D04", "S04", "2026-07-07", "live", "region_failover", "region-a", 4, "41", "pass", ""),
    ("D05", "S05", "2026-06-15", "tabletop", "region_failover", "region-c", 1, "", "pass", ""),
    ("D06", "S06", "2026-05-12", "live", "region_failover", "region-b", 2, "140", "pass", ""),
    ("D07", "S07", "2025-08-14", "live", "backup_restore", "region-a", 1, "190", "pass", ""),
]


def main() -> None:
    rng = random.Random(SEED)
    services, drills, truth = build(rng)
    services.sort(key=lambda s: s["service_id"])
    truth.sort(key=lambda t: t["service_id"])
    drills.sort(key=lambda d: (d["drill_date"], d["service_id"], d["scenario"], d["drill_type"]))
    for i, d in enumerate(drills, 1):
        d["drill_id"] = "D%03d" % i
    write_csv("services.csv", SERVICE_FIELDS, services)
    write_csv("drills.csv", DRILL_FIELDS, drills)
    write_csv("service_truth.csv", TRUTH_FIELDS, truth)
    write_csv("example_services.csv", SERVICE_FIELDS, [dict(zip(SERVICE_FIELDS, r)) for r in EXAMPLE_SERVICES])
    write_csv("example_drills.csv", DRILL_FIELDS, [dict(zip(DRILL_FIELDS, r)) for r in EXAMPLE_DRILLS])
    print(f"wrote {len(services)} services, {len(drills)} drills")


if __name__ == "__main__":
    main()
