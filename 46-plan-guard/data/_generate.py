"""Generate the synthetic data for project 46: 86 Terraform plans in JSON form, each with a planted
truth, plus one worked example for the command line.

Everything is seeded, so the files are byte-for-byte reproducible. The truth of each plan comes from
the kind of change that was planted, not from the rules in src/plan_guard.py (this file does not
import them). Three kinds of hard case are in on purpose:
  hard misses     risky changes the rules do not see (a split world CIDR, a policy condition that
                  matches everything, a queue policy on a resource type with no rule)
  hard negatives  harmless plans a pattern match would flag (a Deny policy for Principal *, a
                  deleted public bucket, a world rule on port 443, an unchanged risky resource)
  decoys          a plain-HTTP listener on an internal load balancer, which only a cross-resource
                  join could tell from a public one; the rules do not join, so they raise a review

The plans keep only the parts of the Terraform plan JSON that plan_guard reads: format_version,
terraform_version, and resource_changes with address, mode, type, name, provider_name and a change
object (actions, before, after, after_unknown). They were written by hand-built functions, not by a
Terraform run.

Run (from data/):  python3 _generate.py
Writes:  plans.csv, plan_truth.csv, example_plan.json
"""
from __future__ import annotations

import csv
import json
import random

rng = random.Random(46)
PROVIDER = "registry.terraform.io/hashicorp/aws"
WORDS = ["ledger", "statements", "recon", "intake", "reports", "archive", "batch", "audit", "kyc",
         "settlement", "exports", "scratch", "uploads", "feeds", "staging", "queue", "gateway", "vault"]
ACCOUNT = "111122223333"
SG_ID = "sg-0123456789abcdef0"
DB_PORTS = [1433, 1521, 3306, 5432, 6379, 27017]


class Ctx:
    """Names and module prefixes for one plan, so addresses never collide inside it."""

    def __init__(self):
        self.n = 0

    def name(self):
        self.n += 1
        return f"{rng.choice(WORDS)}_{self.n}"

    def mod(self):
        return rng.choice([None, None, None, "platform", "data"])


def resource(rtype, name, actions, before, after, unknown=None, module=None, mode="managed"):
    address = f"{rtype}.{name}" if mode == "managed" else f"data.{rtype}.{name}"
    if module:
        address = f"module.{module}.{address}"
    rc = {"address": address, "mode": mode, "type": rtype, "name": name, "provider_name": PROVIDER,
          "change": {"actions": actions, "before": before, "after": after, "after_unknown": unknown or {}}}
    if module:
        rc["module_address"] = f"module.{module}"
    return rc


def create(c, rtype, after, unknown=None, name=None):
    return resource(rtype, name or c.name(), ["create"], None, after, unknown, c.mod())


def delete(c, rtype, before):
    return resource(rtype, c.name(), ["delete"], before, None, {}, c.mod())


def noop(c, rtype, attrs):
    return resource(rtype, c.name(), ["no-op"], attrs, attrs, {}, c.mod())


def bucket_name():
    return f"{rng.choice(WORDS)}-{rng.randint(1000, 9999)}"


def policy_json(bucket, effect, principal, condition=None, action="s3:GetObject"):
    stmt = {"Sid": "S1", "Effect": effect, "Principal": principal, "Action": action,
            "Resource": f"arn:aws:s3:::{bucket}/*"}
    if condition:
        stmt["Condition"] = condition
    return json.dumps({"Version": "2012-10-17", "Statement": [stmt]}, sort_keys=True)


# ---------------------------------------------------------------- attribute sets
def bucket_attrs(b, acl="private"):
    return {"bucket": b, "acl": acl, "force_destroy": False, "tags": {"owner": "ops"}}


def sg_attrs(variant, cidrs4, cidrs6, lo, hi, proto):
    if proto == "-1":
        lo = hi = None if variant == "vpc" else 0
    if variant == "inline":
        return "aws_security_group", {"name": f"sg-{rng.randint(100, 999)}", "vpc_id": "vpc-0a1b2c3d4e5f60718",
                                      "ingress": [{"cidr_blocks": cidrs4, "ipv6_cidr_blocks": cidrs6, "from_port": lo,
                                                   "to_port": hi, "protocol": proto, "description": "",
                                                   "prefix_list_ids": [], "security_groups": [], "self": False}],
                                      "egress": [], "tags": {}}
    if variant == "rule":
        return "aws_security_group_rule", {"type": "ingress", "security_group_id": SG_ID, "cidr_blocks": cidrs4,
                                           "ipv6_cidr_blocks": cidrs6, "from_port": lo, "to_port": hi, "protocol": proto}
    return "aws_vpc_security_group_ingress_rule", {
        "security_group_id": SG_ID, "cidr_ipv4": cidrs4[0] if cidrs4 else None,
        "cidr_ipv6": cidrs6[0] if cidrs6 else None, "from_port": lo, "to_port": hi, "ip_protocol": proto}


def sg_world(variants, ports, world=None):
    variant = rng.choice(variants)
    lo, hi, proto = ports
    world = world or rng.choice([(["0.0.0.0/0"], []), ([], ["::/0"])])
    return sg_attrs(variant, world[0], world[1], lo, hi, proto)


def ebs_attrs(encrypted):
    a = {"availability_zone": "us-east-1a", "size": rng.choice([50, 100, 500]), "type": "gp3"}
    if encrypted != "absent":
        a["encrypted"] = encrypted
    return a


def rds_attrs(encrypted, public):
    a = {"identifier": f"{rng.choice(WORDS)}-db-{rng.randint(10, 99)}", "engine": "postgres", "instance_class": "db.t3.medium",
         "allocated_storage": 100, "publicly_accessible": public, "skip_final_snapshot": False}
    if encrypted != "absent":
        a["storage_encrypted"] = encrypted
    return a


def efs_attrs(encrypted):
    a = {"creation_token": f"{rng.choice(WORDS)}-{rng.randint(10, 99)}", "performance_mode": "generalPurpose"}
    if encrypted != "absent":
        a["encrypted"] = encrypted
    return a


def listener_attrs(action):
    return {"port": 80, "protocol": "HTTP", "default_action": [action]}


FORWARD = {"type": "forward", "redirect": [], "target_group_arn": f"arn:aws:elasticloadbalancing:us-east-1:{ACCOUNT}:targetgroup/web/0123456789abcdef"}
REDIRECT = {"type": "redirect", "redirect": [{"protocol": "HTTPS", "port": "443", "status_code": "HTTP_301"}]}
LISTENER_UNKNOWN = {"arn": True, "id": True, "load_balancer_arn": True}


# ---------------------------------------------------------------- clean noise
def n_vpc(c):
    return create(c, "aws_vpc", {"cidr_block": "10.0.0.0/16", "enable_dns_hostnames": True}, {"id": True, "arn": True})


def n_subnet(c):
    return create(c, "aws_subnet", {"cidr_block": "10.0.1.0/24", "availability_zone": "us-east-1a"}, {"id": True, "vpc_id": True})


def n_role(c):
    return create(c, "aws_iam_role", {"name": f"{rng.choice(WORDS)}-role", "path": "/"}, {"arn": True, "id": True})


def n_instance(c):
    return create(c, "aws_instance", {"instance_type": "t3.small", "associate_public_ip_address": False}, {"id": True, "arn": True})


def n_instance_update(c):
    return resource("aws_instance", c.name(), ["update"], {"instance_type": "t3.small", "tags": {}},
                    {"instance_type": "t3.small", "tags": {"owner": "ops"}}, {}, c.mod())


def n_log_group(c):
    return create(c, "aws_cloudwatch_log_group", {"name": f"/ops/{rng.choice(WORDS)}", "retention_in_days": 365}, {"arn": True, "id": True})


def n_kms(c):
    return create(c, "aws_kms_key", {"description": "data key", "enable_key_rotation": True}, {"arn": True, "id": True, "key_id": True})


def n_bucket_private(c):
    return create(c, "aws_s3_bucket", bucket_attrs(bucket_name()), {"arn": True, "id": True})


def n_pab_all_on(c):
    return create(c, "aws_s3_bucket_public_access_block", {"bucket": bucket_name(), "block_public_acls": True,
                  "block_public_policy": True, "ignore_public_acls": True, "restrict_public_buckets": True}, {"id": True})


def n_ebs_ok(c):
    return create(c, "aws_ebs_volume", ebs_attrs(True), {"arn": True, "id": True})


def n_rds_ok(c):
    return create(c, "aws_db_instance", rds_attrs(True, False), {"arn": True, "id": True})


def n_efs_ok(c):
    return create(c, "aws_efs_file_system", efs_attrs(True), {"arn": True, "id": True})


def n_sg_internal(c):
    rtype, attrs = sg_attrs(rng.choice(["inline", "rule", "vpc"]), ["10.0.0.0/16"], [], 5432, 5432, "tcp")
    return create(c, rtype, attrs, {"id": True})


def n_queue(c):
    return create(c, "aws_sqs_queue", {"name": f"{rng.choice(WORDS)}-q", "sqs_managed_sse_enabled": True}, {"arn": True, "id": True})


def n_listener_https(c):
    return create(c, "aws_lb_listener", {"port": 443, "protocol": "HTTPS", "default_action": [FORWARD]}, LISTENER_UNKNOWN)


def n_data(c):
    return resource("aws_caller_identity", "current", ["read"], None, {"account_id": ACCOUNT}, {"id": True}, None, mode="data")


NOISE = [n_vpc, n_subnet, n_role, n_instance, n_instance_update, n_log_group, n_kms, n_bucket_private, n_pab_all_on,
         n_ebs_ok, n_rds_ok, n_efs_ok, n_sg_internal, n_queue, n_listener_https, n_data]


# ---------------------------------------------------------------- planted kinds
# Each builder returns (resources, target_address, expected_rule). expected_rule is the rule a reviewer
# would want to fire; it is empty when the plan is harmless.
def k_s3_acl_public(c):
    acl = rng.choice(["public-read", "public-read-write", "authenticated-read"])
    if rng.random() < 0.5:
        r = create(c, "aws_s3_bucket", bucket_attrs(bucket_name(), acl), {"arn": True, "id": True})
    else:
        r = create(c, "aws_s3_bucket_acl", {"bucket": bucket_name(), "acl": acl}, {"id": True})
    return [r], r["address"], "PG01"


def k_s3_pab_off(c):
    flags = ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"]
    off = rng.sample(flags, rng.randint(1, 4))
    attrs = {"bucket": bucket_name()}
    for f in flags:
        attrs[f] = rng.choice([False, None]) if f in off else True
    r = create(c, "aws_s3_bucket_public_access_block", attrs, {"id": True})
    return [r], r["address"], "PG02"


def k_s3_policy_world(c):
    b = bucket_name()
    principal = rng.choice(["*", {"AWS": "*"}, {"AWS": ["*"]}])
    r = create(c, "aws_s3_bucket_policy", {"bucket": b, "policy": policy_json(b, "Allow", principal)}, {"id": True})
    return [r], r["address"], "PG03"


def k_sg_admin_world(c):
    ports = rng.choice([(22, 22, "tcp"), (3389, 3389, "tcp"), (20, 30, "tcp"), (3380, 3400, "tcp"), (0, 0, "-1")])
    rtype, attrs = sg_world(["inline", "rule", "vpc"], ports)
    r = create(c, rtype, attrs, {"id": True})
    return [r], r["address"], "PG04"


def k_sg_db_world(c):
    p = rng.choice(DB_PORTS)
    rtype, attrs = sg_world(["inline", "rule", "vpc"], (p, p, "tcp"))
    r = create(c, rtype, attrs, {"id": True})
    return [r], r["address"], "PG05"


def k_ebs_plain(c):
    r = create(c, "aws_ebs_volume", ebs_attrs(rng.choice([False, "absent"])), {"arn": True, "id": True})
    return [r], r["address"], "PG06"


def k_rds_plain(c):
    r = create(c, "aws_db_instance", rds_attrs(rng.choice([False, "absent"]), False), {"arn": True, "id": True})
    return [r], r["address"], "PG07"


def k_rds_public(c):
    r = create(c, "aws_db_instance", rds_attrs(True, True), {"arn": True, "id": True})
    return [r], r["address"], "PG08"


def k_efs_plain(c):
    r = create(c, "aws_efs_file_system", efs_attrs(rng.choice([False, "absent"])), {"arn": True, "id": True})
    return [r], r["address"], "PG09"


def k_lb_http_forward(c):
    r = create(c, "aws_lb_listener", listener_attrs(FORWARD), dict(LISTENER_UNKNOWN, default_action=[{"target_group_arn": True}]))
    return [r], r["address"], "PG10"


def k_unknown_encryption(c):
    kind = rng.choice(["ebs", "rds", "efs"])
    if kind == "ebs":
        r, rule = create(c, "aws_ebs_volume", ebs_attrs("absent"), {"arn": True, "id": True, "encrypted": True}), "PG06"
    elif kind == "rds":
        r, rule = create(c, "aws_db_instance", rds_attrs("absent", False), {"arn": True, "id": True, "storage_encrypted": True}), "PG07"
    else:
        r, rule = create(c, "aws_efs_file_system", efs_attrs("absent"), {"arn": True, "id": True, "encrypted": True}), "PG09"
    return [r], r["address"], rule


def k_unknown_policy(c):
    r = create(c, "aws_s3_bucket_policy", {"bucket": bucket_name()}, {"id": True, "policy": True})
    return [r], r["address"], "PG03"


def k_clean_baseline(c):
    return [], "", ""


def k_web_world_ok(c):
    p = rng.choice([80, 443])
    rtype, attrs = sg_world(["inline", "rule", "vpc"], (p, p, "tcp"))
    r = create(c, rtype, attrs, {"id": True})
    return [r], r["address"], ""


def k_private_cidr_admin(c):
    p = rng.choice([22, 3389, 5432, 3306])
    cidr = rng.choice(["10.0.0.0/8", "172.16.0.0/12", "192.168.10.0/24"])
    rtype, attrs = sg_world(["inline", "rule", "vpc"], (p, p, "tcp"), ([cidr], []))
    r = create(c, rtype, attrs, {"id": True})
    return [r], r["address"], ""


def k_deny_world_policy(c):
    b = bucket_name()
    doc = policy_json(b, "Deny", "*", {"Bool": {"aws:SecureTransport": "false"}}, action="s3:*")
    r = create(c, "aws_s3_bucket_policy", {"bucket": b, "policy": doc}, {"id": True})
    return [r], r["address"], ""


def k_policy_vpce(c):
    b = bucket_name()
    doc = policy_json(b, "Allow", "*", {"StringEquals": {"aws:SourceVpce": f"vpce-{rng.randint(10**9, 10**10 - 1):x}"}})
    r = create(c, "aws_s3_bucket_policy", {"bucket": b, "policy": doc}, {"id": True})
    return [r], r["address"], ""


def k_lb_redirect_https(c):
    r = create(c, "aws_lb_listener", listener_attrs(REDIRECT), LISTENER_UNKNOWN)
    return [r], r["address"], ""


def k_delete_violating(c):
    which = rng.choice(["bucket", "sg", "ebs"])
    if which == "bucket":
        r = delete(c, "aws_s3_bucket", bucket_attrs(bucket_name(), "public-read"))
    elif which == "sg":
        rtype, attrs = sg_world(["inline", "rule", "vpc"], (22, 22, "tcp"))
        r = delete(c, rtype, attrs)
    else:
        r = delete(c, "aws_ebs_volume", ebs_attrs(False))
    return [r], r["address"], ""


def k_noop_violating(c):
    which = rng.choice(["bucket", "sg", "ebs"])
    if which == "bucket":
        r = noop(c, "aws_s3_bucket", bucket_attrs(bucket_name(), "public-read"))
    elif which == "sg":
        rtype, attrs = sg_world(["inline", "rule", "vpc"], (3389, 3389, "tcp"))
        r = noop(c, rtype, attrs)
    else:
        r = noop(c, "aws_ebs_volume", ebs_attrs(False))
    return [r], r["address"], ""


def k_lb_internal_http(c):
    lb = create(c, "aws_lb", {"name": f"{rng.choice(WORDS)}-int", "internal": True, "load_balancer_type": "application"},
                {"arn": True, "id": True, "dns_name": True})
    r = create(c, "aws_lb_listener", listener_attrs(FORWARD), dict(LISTENER_UNKNOWN, default_action=[{"target_group_arn": True}]))
    return [lb, r], r["address"], ""


def k_split_world_cidr(c):
    rtype, attrs = sg_world(["inline", "rule"], (22, 22, "tcp"), (["0.0.0.0/1", "128.0.0.0/1"], []))
    r = create(c, rtype, attrs, {"id": True})
    return [r], r["address"], "PG04"


def k_policy_weak_condition(c):
    b = bucket_name()
    doc = policy_json(b, "Allow", "*", {"StringLike": {"aws:Referer": "*"}})
    r = create(c, "aws_s3_bucket_policy", {"bucket": b, "policy": doc}, {"id": True})
    return [r], r["address"], "PG03"


def k_queue_policy_world(c):
    doc = json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "sqs:SendMessage",
                      "Resource": f"arn:aws:sqs:us-east-1:{ACCOUNT}:{rng.choice(WORDS)}-q"}]}, sort_keys=True)
    r = create(c, "aws_sqs_queue_policy", {"queue_url": f"https://sqs.us-east-1.amazonaws.com/{ACCOUNT}/{rng.choice(WORDS)}-q", "policy": doc}, {"id": True})
    return [r], r["address"], "none"


QUOTA = [("s3_acl_public", "block", 4, k_s3_acl_public), ("s3_pab_off", "block", 4, k_s3_pab_off),
         ("s3_policy_world", "block", 4, k_s3_policy_world), ("sg_admin_world", "block", 5, k_sg_admin_world),
         ("sg_db_world", "block", 4, k_sg_db_world), ("ebs_plain", "block", 3, k_ebs_plain),
         ("rds_plain", "block", 3, k_rds_plain), ("rds_public", "block", 3, k_rds_public),
         ("efs_plain", "block", 3, k_efs_plain),
         ("lb_http_forward", "review", 3, k_lb_http_forward), ("unknown_encryption", "review", 4, k_unknown_encryption),
         ("unknown_policy", "review", 3, k_unknown_policy),
         ("clean_baseline", "ok", 8, k_clean_baseline), ("web_world_ok", "ok", 4, k_web_world_ok),
         ("private_cidr_admin", "ok", 3, k_private_cidr_admin), ("deny_world_policy", "ok", 3, k_deny_world_policy),
         ("policy_vpce", "ok", 3, k_policy_vpce), ("lb_redirect_https", "ok", 3, k_lb_redirect_https),
         ("delete_violating", "ok", 4, k_delete_violating), ("noop_violating", "ok", 3, k_noop_violating),
         ("lb_internal_http", "ok", 3, k_lb_internal_http),
         ("split_world_cidr", "block", 3, k_split_world_cidr), ("policy_weak_condition", "block", 3, k_policy_weak_condition),
         ("queue_policy_world", "block", 3, k_queue_policy_world)]


def plan_of(resources):
    return {"format_version": "1.2", "terraform_version": "1.x-synthetic", "resource_changes": resources}


def example_plan():
    """A fixed worked example for the command line: two blocking findings, two reviews, one delete that is ignored."""
    return plan_of([
        resource("aws_vpc", "main", ["create"], None, {"cidr_block": "10.0.0.0/16"}, {"id": True}),
        resource("aws_security_group", "bastion", ["create"], None,
           sg_attrs("inline", ["0.0.0.0/0"], [], 22, 22, "tcp")[1], {"id": True}),
        resource("aws_s3_bucket", "exports", ["create"], None, bucket_attrs("exports-4821", "public-read"), {"id": True}),
        resource("aws_ebs_volume", "ledger_data", ["create"], None, ebs_attrs(True), {"id": True}),
        resource("aws_lb_listener", "web", ["create"], None, listener_attrs(FORWARD), dict(LISTENER_UNKNOWN, default_action=[{"target_group_arn": True}])),
        resource("aws_db_instance", "reports", ["create"], None, rds_attrs("absent", False), {"id": True, "storage_encrypted": True}),
        resource("aws_s3_bucket", "old_public", ["delete"], bucket_attrs("old-public-1207", "public-read"), None, {}),
    ])


def main():
    cases = []
    for kind, cls, count, build in QUOTA:
        for _ in range(count):
            c = Ctx()
            planted, target, expected = build(c)
            noise = [rng.choice(NOISE)(c) for _ in range(rng.randint(2, 5))]
            resources = noise + planted
            rng.shuffle(resources)
            cases.append((plan_of(resources), kind, cls, target, expected))
    order = list(range(len(cases)))
    rng.shuffle(order)
    with open("plans.csv", "w", newline="", encoding="utf-8") as f, open("plan_truth.csv", "w", newline="", encoding="utf-8") as g:
        w, t = csv.writer(f), csv.writer(g)
        w.writerow(["plan_id", "plan_json"])
        t.writerow(["plan_id", "kind", "truth_class", "target_address", "expected_rule"])
        for i, j in enumerate(order, 1):
            pid = f"PLAN-{i:03d}"
            plan, kind, cls, target, expected = cases[j]
            w.writerow([pid, json.dumps(plan, sort_keys=True)])
            t.writerow([pid, kind, cls, target, expected])
    with open("example_plan.json", "w", encoding="utf-8") as f:
        json.dump(example_plan(), f, indent=1, sort_keys=True)
        f.write("\n")
    print(f"wrote {len(cases)} plans")


if __name__ == "__main__":
    main()
