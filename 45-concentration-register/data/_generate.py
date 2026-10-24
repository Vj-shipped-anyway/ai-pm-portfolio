"""Generate the synthetic data for project 45: a register of 64 services that run on four invented
cloud providers, the dependencies between them, and the truth about where each service really runs.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth is drawn first, from a
world the register never sees in full: true placements, a hidden set of dependencies the register does
not list, and warm standbys that do not actually take over. The register is then derived from that
world with gaps (placements a vendor will not disclose, dependencies nobody wrote down). The loss in
each outage scenario is computed here, in `lost_in`, by code that is separate from the tool's own
propagation in src/concentration_register.py.

Run (from data/):  python3 _generate.py
Writes:  services.csv, dependencies.csv, truth_services.csv, truth_edges.csv, truth_scenarios.csv,
         example_services.csv, example_deps.csv
"""
from __future__ import annotations

import csv
import random

SEED = 45
rng = random.Random(SEED)

REGIONS = {"CP-1": ["R1", "R2", "R3"], "CP-2": ["R1", "R2"], "CP-3": ["R1", "R2"], "CP-4": ["R1"]}
REGION_WEIGHTS = [0.55, 0.30, 0.15]
PLATFORM_PROVIDER_W = {"CP-1": 0.55, "CP-2": 0.25, "CP-3": 0.12, "CP-4": 0.08}
BUSINESS_PROVIDER_W = {"CP-1": 0.34, "CP-2": 0.30, "CP-3": 0.22, "CP-4": 0.14}

PLATFORM = ["identity platform", "message bus", "primary ledger database", "secrets vault", "api gateway",
            "file transfer hub", "observability stack", "document store", "job scheduler",
            "notification relay", "analytics warehouse", "edge cache"]
PLATFORM_SAAS = {0, 3, 6, 9, 10}
PLATFORM_CRITICAL = {0, 1, 2}
PLATFORM_DEP_WEIGHT = [0.25, 0.20, 0.15, 0.10, 0.08, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.01]
DOMAINS = ["card authorization", "wire transfers", "retail payments", "loan origination", "fraud screening",
           "customer onboarding", "statement delivery", "treasury reporting", "dispute handling",
           "mobile banking", "online banking", "regulatory reporting", "kyc checks"]
SUFFIXES = ["api", "portal", "batch", "engine"]
CRITICALITY_MIX = ["critical"] * 22 + ["important"] * 16 + ["standard"] * 14
# probability of (single, warm_standby, active_active) by service class
RESILIENCE_W = {"critical": [0.40, 0.30, 0.30], "other": [0.65, 0.22, 0.13], "platform": [0.70, 0.20, 0.10]}
P_STANDBY_SAME_AS_PRIMARY = 0.08
P_STANDBY_WORKS = 0.70
P_UNDISCLOSED = {"saas": 0.35, "internal": 0.03}
UNLISTED_EDGES = 6

SERVICE_FIELDS = ["service_id", "name", "owner_type", "criticality", "provider", "region", "resilience",
                  "standby_provider", "standby_region"]


def weighted(items, weights):
    r = rng.random() * sum(weights)
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if r < acc:
            return item
    return items[-1]


def place(wmap):
    keys = sorted(wmap)
    provider = weighted(keys, [wmap[k] for k in keys])
    regions = REGIONS[provider]
    return (provider, weighted(regions, REGION_WEIGHTS[:len(regions)]))


def second_placement(primary):
    """A second placement: the same provider in another region half the time, else another provider."""
    provider = primary[0]
    others = [r for r in REGIONS[provider] if r != primary[1]]
    if others and rng.random() < 0.5:
        return (provider, rng.choice(others))
    other_providers = sorted(p for p in REGIONS if p != provider)
    return place({p: BUSINESS_PROVIDER_W[p] for p in other_providers})


def build_world():
    services = []
    for i, name in enumerate(PLATFORM):
        services.append({"id": f"P-{i + 1:02d}", "name": name, "owner": "saas" if i in PLATFORM_SAAS else "internal",
                         "crit": "critical" if i in PLATFORM_CRITICAL else "important", "layer": "platform"})
    mix = CRITICALITY_MIX[:]
    rng.shuffle(mix)
    names = [f"{d} {s}" for d in DOMAINS for s in SUFFIXES]
    for i, name in enumerate(names):
        services.append({"id": f"S-{i + 1:02d}", "name": name, "owner": "internal" if rng.random() < 0.8 else "saas",
                         "crit": mix[i], "layer": "business"})
    for s in services:
        wmap = PLATFORM_PROVIDER_W if s["layer"] == "platform" else BUSINESS_PROVIDER_W
        s["primary"] = place(wmap)
        cls = "platform" if s["layer"] == "platform" else ("critical" if s["crit"] == "critical" else "other")
        s["mode"] = weighted(["single", "warm_standby", "active_active"], RESILIENCE_W[cls])
        s["second"] = None
        s["works"] = None
        if s["mode"] != "single":
            if s["mode"] == "warm_standby" and rng.random() < P_STANDBY_SAME_AS_PRIMARY:
                s["second"] = s["primary"]
            else:
                s["second"] = second_placement(s["primary"])
            s["works"] = True if s["mode"] == "active_active" else rng.random() < P_STANDBY_WORKS
    # dependencies: platform services lean on the first two platform services; business services on platform ones
    hard, soft = {}, {}
    for i in range(len(PLATFORM)):
        hard[f"P-{i + 1:02d}"], soft[f"P-{i + 1:02d}"] = [], []
        if i >= 1 and rng.random() < 0.5:
            hard[f"P-{i + 1:02d}"].append(f"P-{rng.randrange(min(i, 2)) + 1:02d}")
    plat_ids = [f"P-{i + 1:02d}" for i in range(len(PLATFORM))]
    for s in services:
        if s["layer"] != "business":
            continue
        k = weighted([1, 2, 3], [0.35, 0.45, 0.20])
        pool, w = plat_ids[:], PLATFORM_DEP_WEIGHT[:]
        chosen = []
        for _ in range(k):
            pick = weighted(pool, w)
            chosen.append(pick)
            idx = pool.index(pick)
            pool.pop(idx)
            w.pop(idx)
        hard[s["id"]] = sorted(chosen)
        n_soft = weighted([0, 1, 2], [0.4, 0.4, 0.2])
        soft[s["id"]] = sorted(rng.sample(pool, n_soft))
    # hidden hard edges: a critical business service that also needs a platform service nobody listed
    def closure(sid):
        seen, stack = set(), list(hard[sid])
        while stack:
            d = stack.pop()
            if d not in seen:
                seen.add(d)
                stack.extend(hard[d])
        return seen
    crit_business = [s["id"] for s in services if s["layer"] == "business" and s["crit"] == "critical"]
    rng.shuffle(crit_business)
    unlisted = []
    for sid in crit_business:
        if len(unlisted) == UNLISTED_EDGES:
            break
        free = [p for p in plat_ids if p not in closure(sid)]
        if free:
            unlisted.append((sid, rng.choice(free)))
    for sid, p in unlisted:
        hard[sid] = sorted(hard[sid] + [p])
    # what the register shows: some placements are not disclosed
    for s in services:
        s["disclosed"] = rng.random() >= P_UNDISCLOSED[s["owner"]]
    return services, hard, soft, set(unlisted)


def lost_in(services, hard, failed):
    """Services that are down when every placement (provider, region) with failed(...) true goes dark."""
    down = set()
    for s in services:
        if not failed(*s["primary"]):
            continue
        takes_over = s["second"] is not None and s["works"] and not failed(*s["second"])
        if not takes_over:
            down.add(s["id"])
    while True:
        more = {sid for sid, deps in hard.items() if sid not in down and any(d in down for d in deps)}
        if not more:
            return down
        down |= more


def scenario_list():
    out = [("P:" + p, "provider", p, "") for p in sorted(REGIONS)]
    out += [(f"R:{p}/{r}", "region", p, r) for p in sorted(REGIONS) for r in REGIONS[p]]
    return out


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_example():
    services = [
        ("P-1", "identity platform", "saas", "critical", "CP-2", "R1", "single", "", ""),
        ("P-2", "message bus", "internal", "important", "CP-2", "R1", "single", "", ""),
        ("S-01", "card authorization api", "internal", "critical", "CP-1", "R1", "single", "", ""),
        ("S-02", "wire transfers engine", "internal", "critical", "CP-1", "R2", "warm_standby", "CP-3", "R1"),
        ("S-03", "retail payments api", "internal", "critical", "CP-3", "R1", "single", "", ""),
        ("S-04", "online banking portal", "internal", "critical", "CP-3", "R2", "active_active", "CP-1", "R1"),
        ("S-05", "fraud screening engine", "saas", "critical", "", "", "", "", ""),
        ("S-06", "statement delivery batch", "internal", "important", "CP-1", "R1", "warm_standby", "CP-1", "R1"),
        ("S-07", "treasury reporting portal", "internal", "standard", "CP-1", "R2", "single", "", ""),
        ("S-08", "dispute handling portal", "internal", "critical", "CP-1", "R1", "single", "", ""),
    ]
    deps = [("P-2", "P-1", "hard"), ("S-01", "P-1", "hard"), ("S-02", "P-1", "hard"), ("S-02", "P-2", "soft"),
            ("S-03", "P-2", "hard"), ("S-04", "P-1", "hard"), ("S-05", "P-2", "hard"), ("S-06", "P-1", "hard"),
            ("S-07", "P-2", "soft")]
    write_csv("example_services.csv", SERVICE_FIELDS, services)
    write_csv("example_deps.csv", ["service_id", "depends_on", "kind"], deps)


def main():
    services, hard, soft, unlisted = build_world()
    write_csv("services.csv", SERVICE_FIELDS, [
        (s["id"], s["name"], s["owner"], s["crit"],
         s["primary"][0] if s["disclosed"] else "", s["primary"][1] if s["disclosed"] else "",
         s["mode"] if s["disclosed"] else "",
         s["second"][0] if s["disclosed"] and s["second"] else "", s["second"][1] if s["disclosed"] and s["second"] else "")
        for s in services])
    edges = [(sid, d, "hard") for sid in sorted(hard) for d in hard[sid] if (sid, d) not in unlisted]
    edges += [(sid, d, "soft") for sid in sorted(soft) for d in soft[sid]]
    write_csv("dependencies.csv", ["service_id", "depends_on", "kind"], sorted(edges))
    write_csv("truth_services.csv",
              ["service_id", "true_provider", "true_region", "true_resilience", "true_standby_provider",
               "true_standby_region", "failover_works", "disclosed"],
              [(s["id"], s["primary"][0], s["primary"][1], s["mode"],
                s["second"][0] if s["second"] else "", s["second"][1] if s["second"] else "",
                "" if s["works"] is None else ("yes" if s["works"] else "no"), "yes" if s["disclosed"] else "no")
               for s in services])
    write_csv("truth_edges.csv", ["service_id", "depends_on", "kind", "listed"],
              [(sid, d, "hard", "no" if (sid, d) in unlisted else "yes") for sid in sorted(hard) for d in hard[sid]]
              + [(sid, d, "soft", "yes") for sid in sorted(soft) for d in soft[sid]])
    critical = sorted(s["id"] for s in services if s["crit"] == "critical")
    rows = []
    for sid, kind, provider, region in scenario_list():
        failed = (lambda p, r, provider=provider, region=region: p == provider and (not region or r == region))
        down = lost_in(services, hard, failed)
        lost_crit = [c for c in critical if c in down]
        rows.append((sid, kind, provider, region, len(down), len(lost_crit), len(critical), ";".join(lost_crit)))
    write_csv("truth_scenarios.csv",
              ["scenario_id", "kind", "provider", "region", "services_lost", "critical_lost", "critical_total",
               "critical_lost_ids"], rows)
    write_example()
    print(f"wrote {len(services)} services, {len(edges)} listed dependencies, {len(unlisted)} unlisted, "
          f"{len(rows)} scenarios")


if __name__ == "__main__":
    main()
