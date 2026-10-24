"""Generate the synthetic data for project 71: one month of a cloud billing export for a fictional
bank, the cost-center registry, the account map, the tag policy, and the planted truth about who
should pay for each line.

Everything is seeded, so the files are byte-for-byte reproducible. The truth comes from the story
told here (every resource belongs to an app, every app to a cost center) before any tag defect is
applied. It does not come from the allocation rules. Several defects are hard on purpose: a valid tag
on the wrong cost center, an untagged resource of one team sitting in another team's account, a
tag key spelled in a way the policy does not list, and a value with the hyphen dropped. The rules
cannot see those. Others are hard negatives: zero-cost untagged lines, shared-service lines, credits,
and resources tagged correctly for a cost center other than their account's.

Run (from data/):  python3 _generate.py
Writes:  billing_export.csv, billing_truth.csv, cost_centers.csv, accounts.csv, policy.json,
         example_bill.csv
"""
import csv
import json
import random

rng = random.Random(71)

# ---------------------------------------------------------------- registry and accounts
CC_ROWS = [
    ("CC-1001", "Retail Deposits", "retail", "team-deposits", "true"),
    ("CC-1002", "Card Services", "cards", "team-cards", "true"),
    ("CC-1003", "Payments Operations", "payments", "team-payments", "true"),
    ("CC-1004", "Fraud Analytics", "risk", "team-fraud", "true"),
    ("CC-1005", "Consumer Lending", "lending", "team-lending", "true"),
    ("CC-1006", "Wealth Platforms", "wealth", "team-wealth", "true"),
    ("CC-1007", "Treasury Systems", "treasury", "team-treasury", "true"),
    ("CC-1008", "Customer Support Tooling", "operations", "team-support", "true"),
    ("CC-1009", "Data Platform", "technology", "team-data", "true"),
    ("CC-1010", "Security Engineering", "technology", "team-security", "true"),
    ("CC-1011", "Regulatory Reporting", "finance", "team-regreport", "true"),
    ("CC-1012", "Digital Channels", "retail", "team-digital", "true"),
    ("CC-1013", "Branch Systems", "retail", "team-branch", "false"),
    ("CC-1014", "Legacy Cards Migration", "cards", "team-legacy-cards", "false"),
]
ACTIVE = [r[0] for r in CC_ROWS if r[4] == "true"]
CLOSED = [r[0] for r in CC_ROWS if r[4] == "false"]

DEDICATED = ["deposits-prod", "cards-prod", "payments-prod", "fraud-prod", "lending-prod", "wealth-prod",
             "treasury-prod", "support-prod"]
SHARED_ACCOUNTS = ["platform-shared", "data-lake-shared", "sandbox-shared", "tooling-shared"]


def acct(n):
    return "4100000000%02d" % n


ACCOUNT_ROWS = [(acct(i + 1), name, "CC-100%d" % (i + 1), "no") for i, name in enumerate(DEDICATED)]
ACCOUNT_ROWS += [(acct(9 + i), name, "", "yes") for i, name in enumerate(SHARED_ACCOUNTS)]

POLICY = {
    "required_tags": [
        {"key": "cost-center", "aliases": ["CostCenter", "cost_center"], "values": "registry"},
        {"key": "app", "aliases": ["Application"], "values": "any"},
        {"key": "env", "aliases": ["Environment"], "values": ["prod", "stage", "dev", "test"]},
    ],
    "shared_services": ["Support Plan", "Security Monitoring", "Network Backbone", "Log Archive"],
    "max_unallocated_pct": 10.0,
}
ENVS = ["prod", "stage", "dev", "test"]

# ---------------------------------------------------------------- apps and resources
APP_WORDS = ["ledger", "statements", "onboarding", "alerts", "limits", "recon", "reporting", "scoring",
             "rules-engine", "notifications", "gateway", "search", "batch", "portal", "vault", "feeds", "archive"]
apps = []


def add_app(cc, account, foreign):
    apps.append({"name": "%s-%02d" % (rng.choice(APP_WORDS), len(apps) + 1), "cc": cc, "account": account, "foreign": foreign})


for i in range(1, 9):
    for _ in range(3):
        add_app("CC-100%d" % i, acct(i), False)
for cc, account in (("CC-1009", acct(1)), ("CC-1012", acct(4)), ("CC-1010", acct(6))):
    add_app(cc, account, True)            # a team's app living in another team's dedicated account
for n in range(9, 13):
    for _ in range(4):
        add_app(rng.choice(ACTIVE), acct(n), False)

SERVICES = [("Compute", "Instance hours"), ("Database", "Instance hours"), ("Object Storage", "Storage GB-month"),
            ("Kubernetes", "Cluster hours"), ("Analytics", "Query units"), ("Queue", "Requests"),
            ("Load Balancer", "Capacity units")]
TIERS = [(4000, 30000), (30000, 150000), (150000, 600000)]
used_ids = set()


def new_id(prefix):
    while True:
        rid = "%s-%08x" % (prefix, rng.getrandbits(32))
        if rid not in used_ids:
            used_ids.add(rid)
            return rid


resources = []
for app in apps:
    for k in range(6):
        lo, hi = rng.choices(TIERS, weights=[60, 30, 10])[0]
        svc, usage = rng.choice(SERVICES)
        defect = "clean"
        if app["foreign"]:
            defect = "wrong_default" if k % 2 == 0 else "foreign_tagged"
        resources.append({"rid": new_id("res"), "app": app["name"], "cc": app["cc"], "account": app["account"],
                          "service": svc, "usage": usage, "base": rng.randint(lo, hi),
                          "env": rng.choices(ENVS, weights=[55, 20, 20, 5])[0], "defect": defect,
                          "kids": rng.random() < 0.4})

QUOTA = [("alias_key", 12), ("alias_unlisted", 6), ("value_format", 14), ("value_nohyphen", 4), ("unknown_value", 5),
         ("closed_cc", 6), ("conflict", 5), ("wrong_valid", 6), ("missing", 16), ("empty_value", 4), ("partial_tag", 10)]
pool = [r for r in resources if r["defect"] == "clean"]
rng.shuffle(pool)
pos = 0
for kind, n in QUOTA:
    for r in pool[pos:pos + n]:
        r["defect"] = kind
    pos += n


def build_tags(res):
    """The tags a resource carries, after its planted defect."""
    d, cc = res["defect"], res["cc"]
    tags = {"app": res["app"], "env": res["env"]}
    u = rng.random()
    if u < 0.06:
        del tags["env"]
    elif u < 0.11:
        tags["env"] = "production"
    elif u < 0.16:
        del tags["app"]
    if d in ("clean", "foreign_tagged", "partial_tag"):
        tags["cost-center"] = cc
    elif d == "alias_key":
        tags[rng.choice(["CostCenter", "cost_center"])] = cc
    elif d == "alias_unlisted":
        tags[rng.choice(["costcentre", "Cost Center"])] = cc
    elif d == "value_format":
        tags["cost-center"] = rng.choice([cc.lower(), " " + cc, cc + " "])
    elif d == "value_nohyphen":
        tags["cost-center"] = cc.replace("-", "")
    elif d == "unknown_value":
        tags["cost-center"] = "CC-%d" % rng.randint(1100, 1199)
    elif d == "closed_cc":
        tags["cost-center"] = rng.choice(CLOSED)
    elif d == "conflict":
        tags["cost-center"] = cc
        tags["CostCenter"] = rng.choice([c for c in ACTIVE if c != cc])
    elif d == "wrong_valid":
        tags["cost-center"] = rng.choice([c for c in ACTIVE if c != cc])
    elif d == "empty_value":
        tags["cost-center"] = ""
    return tags                           # missing and wrong_default carry no cost-center key at all


def planted_compliant(tags):
    """Strict compliance read straight off the dictionary: canonical keys, exact values."""
    return (tags.get("cost-center") in ACTIVE and bool(str(tags.get("app", "")).strip())
            and tags.get("env") in ENVS)


def money(cents):
    c = abs(cents)
    return "%s%d.%02d" % ("-" if cents < 0 else "", c // 100, c % 100)


lines = []


def add(date, account, service, rid, usage, cents, tags, true_cc, kind, exempt=False):
    ok = "exempt" if exempt or cents == 0 else ("yes" if planted_compliant(tags) else "no")
    lines.append({"date": date, "account": account, "service": service, "rid": rid, "usage": usage, "cents": cents,
                  "tags": tags, "true_cc": true_cc, "kind": kind, "compliant": ok})


WEEKS = ["2026-03-08", "2026-03-15", "2026-03-22", "2026-03-29"]
for res in resources:
    res["tags"] = build_tags(res)
    for w, date in enumerate(WEEKS):
        cents = res["base"] * rng.randint(85, 115) // 100
        tags = {} if res["defect"] == "partial_tag" and w < 2 else res["tags"]
        add(date, res["account"], res["service"], res["rid"], res["usage"], cents, tags, res["cc"], res["defect"])
    if res["kids"]:
        for date, usage in (("2026-03-15", "Data transfer out"), ("2026-03-29", "Snapshot copy")):
            add(date, res["account"], "Data Transfer", res["rid"], usage, max(100, res["base"] * rng.randint(2, 8) // 100),
                {}, res["cc"], "child_untagged")

for res in rng.sample([r for r in resources if r["defect"] == "clean"], 10):
    add("2026-03-31", res["account"], res["service"], res["rid"], "Credit: committed use",
        -(res["base"] * rng.randint(5, 20) // 100), res["tags"], res["cc"], "credit")

for service, n in (("Support Plan", 12), ("Log Archive", 12), ("Security Monitoring", 9), ("Network Backbone", 9)):
    for date in WEEKS:
        add(date, acct(n), service, "shared-" + service.lower().replace(" ", "-"), "Monthly charge",
            rng.randint(150000, 450000), {}, "SHARED", "shared_service", exempt=True)

for i in range(24):
    svc, _ = rng.choice(SERVICES)
    add(rng.choice(WEEKS), acct(rng.randint(1, 12)), svc, "free-%03d" % (i + 1), "Free tier", 0, {}, "NONE", "zero_cost")

lines.sort(key=lambda x: (x["date"], x["account"], x["rid"], x["service"], x["usage"], x["cents"]))


def write_csv(name, header, rows):
    with open(name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def tags_json(tags):
    return json.dumps(tags, sort_keys=True, separators=(",", ":"))


ids = ["L%05d" % (i + 1) for i in range(len(lines))]
write_csv("billing_export.csv", ["line_id", "usage_date", "account_id", "service", "resource_id", "usage_type", "cost_usd", "tags_json"],
          [[ids[i], x["date"], x["account"], x["service"], x["rid"], x["usage"], money(x["cents"]), tags_json(x["tags"])]
           for i, x in enumerate(lines)])
write_csv("billing_truth.csv", ["line_id", "true_cost_center", "defect_kind", "compliant"],
          [[ids[i], x["true_cc"], x["kind"], x["compliant"]] for i, x in enumerate(lines)])
write_csv("cost_centers.csv", ["cost_center", "name", "business_line", "owner_team", "active"], CC_ROWS)
write_csv("accounts.csv", ["account_id", "account_name", "default_cost_center", "shared"], ACCOUNT_ROWS)
with open("policy.json", "w", encoding="utf-8") as fh:
    fh.write(json.dumps(POLICY, indent=2) + "\n")

# ---------------------------------------------------------------- the worked example behind --demo
EX = [
    (acct(1), "Compute", "res-demo-01", "Instance hours", "1200.00", {"cost-center": "CC-1001", "app": "ledger-01", "env": "prod"}),
    (acct(9), "Database", "res-demo-02", "Instance hours", "2500.00", {"CostCenter": "CC-1004", "app": "scoring-02", "env": "prod"}),
    (acct(9), "Kubernetes", "res-demo-03", "Cluster hours", "1800.00", {"cost-center": " cc-1005 ", "app": "batch-03", "env": "stage"}),
    (acct(9), "Data Transfer", "res-demo-02", "Data transfer out", "140.00", {}),
    (acct(3), "Compute", "res-demo-04", "Instance hours", "900.00", {}),
    (acct(10), "Object Storage", "res-demo-05", "Storage GB-month", "650.00", {}),
    (acct(9), "Database", "res-demo-06", "Instance hours", "1100.00", {"cost-center": "CC-1013", "app": "portal-04", "env": "prod"}),
    (acct(11), "Queue", "res-demo-07", "Requests", "300.00", {"cost-center": "CC-1099", "app": "feeds-05", "env": "dev"}),
    (acct(12), "Compute", "res-demo-08", "Instance hours", "700.00", {"cost-center": "CC-1002", "CostCenter": "CC-1006", "app": "gateway-06", "env": "prod"}),
    (acct(12), "Support Plan", "shared-support-plan", "Monthly charge", "1000.00", {}),
    (acct(1), "Compute", "res-demo-01", "Credit: committed use", "-100.00", {"cost-center": "CC-1001", "app": "ledger-01", "env": "prod"}),
    (acct(10), "Object Storage", "free-demo-01", "Free tier", "0.00", {}),
    (acct(2), "Compute", "res-demo-09", "Instance hours", "800.00", {"cost-center": "CC-1002", "app": "alerts-07", "env": "prod"}),
    (acct(9), "Compute", "res-demo-10", "Instance hours", "500.00", {"costcentre": "CC-1007", "app": "vault-08", "env": "prod"}),
]
write_csv("example_bill.csv", ["line_id", "usage_date", "account_id", "service", "resource_id", "usage_type", "cost_usd", "tags_json"],
          [["E%02d" % (i + 1), "2026-03-%02d" % (i + 10), a, s, r, u, c, tags_json(t)] for i, (a, s, r, u, c, t) in enumerate(EX)])
print("wrote %d billing lines, %d resources, %d apps" % (len(lines), len(resources), len(apps)))
