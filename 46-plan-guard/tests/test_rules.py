import json
import unittest

import _bootstrap  # noqa: F401
from plan_guard import check_plan, decide


def rc(rtype, after, actions=("create",), unknown=None, name="x", address=None, mode="managed", before=None):
    return {"address": address or f"{rtype}.{name}", "mode": mode, "type": rtype, "name": name,
            "change": {"actions": list(actions), "before": before, "after": after, "after_unknown": unknown or {}}}


def plan(*rcs):
    return {"format_version": "1.2", "resource_changes": list(rcs)}


def found(*rcs, **opts):
    return [(f["rule"], f["class"]) for f in check_plan(plan(*rcs), **opts)["findings"]]


def policy(effect="Allow", principal="*", condition=None):
    stmt = {"Effect": effect, "Principal": principal, "Action": "s3:GetObject", "Resource": "arn:aws:s3:::b/*"}
    if condition:
        stmt["Condition"] = condition
    return json.dumps({"Version": "2012-10-17", "Statement": [stmt]})


def sg_inline(cidr, lo, hi, proto="tcp", v6=False):
    return rc("aws_security_group", {"ingress": [{"cidr_blocks": [] if v6 else [cidr], "ipv6_cidr_blocks": [cidr] if v6 else [],
                                                  "from_port": lo, "to_port": hi, "protocol": proto}]})


class BucketRules(unittest.TestCase):
    def test_public_acl_on_both_types(self):
        for rtype in ("aws_s3_bucket", "aws_s3_bucket_acl"):
            self.assertEqual(found(rc(rtype, {"acl": "public-read"})), [("PG01", "block")])
        self.assertEqual(found(rc("aws_s3_bucket", {"acl": "private"})), [])

    def test_unknown_acl_is_review(self):
        self.assertEqual(found(rc("aws_s3_bucket", {}, unknown={"acl": True})), [("PG01", "review")])

    def test_public_access_block(self):
        on = {"block_public_acls": True, "block_public_policy": True, "ignore_public_acls": True, "restrict_public_buckets": True}
        t = "aws_s3_bucket_public_access_block"
        self.assertEqual(found(rc(t, on)), [])
        self.assertEqual(found(rc(t, dict(on, block_public_acls=False))), [("PG02", "block")])
        self.assertEqual(found(rc(t, dict(on, ignore_public_acls=None))), [("PG02", "block")])
        self.assertEqual(found(rc(t, {k: v for k, v in on.items() if k != "restrict_public_buckets"})), [("PG02", "block")])
        self.assertEqual(found(rc(t, {k: True for k in on if k != "block_public_policy"}, unknown={"block_public_policy": True})), [("PG02", "review")])

    def test_policy_world_principal(self):
        t = "aws_s3_bucket_policy"
        for principal in ("*", {"AWS": "*"}, {"AWS": ["*"]}):
            self.assertEqual(found(rc(t, {"policy": policy(principal=principal)})), [("PG03", "block")])
        self.assertEqual(found(rc(t, {"policy": policy(principal={"AWS": "arn:aws:iam::111122223333:root"})})), [])

    def test_policy_hard_negatives(self):
        t = "aws_s3_bucket_policy"
        self.assertEqual(found(rc(t, {"policy": policy(effect="Deny", condition={"Bool": {"aws:SecureTransport": "false"}})})), [])
        self.assertEqual(found(rc(t, {"policy": policy(condition={"StringEquals": {"aws:SourceVpce": "vpce-1"}})})), [])

    def test_policy_condition_that_matches_everything_is_a_known_miss(self):
        # pinned on purpose: any Condition passes, even StringLike "*"
        self.assertEqual(found(rc("aws_s3_bucket_policy", {"policy": policy(condition={"StringLike": {"aws:Referer": "*"}})})), [])

    def test_policy_statement_object_and_bad_shapes(self):
        t = "aws_s3_bucket_policy"
        as_object = json.dumps({"Statement": {"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"}})
        self.assertEqual(found(rc(t, {"policy": as_object})), [("PG03", "block")])
        for bad in ("{not json", "[]", json.dumps({"Statement": "x"}), json.dumps({"Statement": [1]}), None, 5):
            self.assertEqual(found(rc(t, {"policy": bad})), [("PG03", "review")], bad)
        self.assertEqual(found(rc(t, {}, unknown={"policy": True})), [("PG03", "review")])

    def test_deeply_nested_policy_does_not_crash(self):
        deep = "[" * 5000 + "]" * 5000
        self.assertEqual(found(rc("aws_s3_bucket_policy", {"policy": deep})), [("PG03", "review")])


class NetworkRules(unittest.TestCase):
    def test_world_admin_ports(self):
        self.assertEqual(found(sg_inline("0.0.0.0/0", 22, 22)), [("PG04", "block")])
        self.assertEqual(found(sg_inline("::/0", 3389, 3389, v6=True)), [("PG04", "block")])
        self.assertEqual(found(sg_inline("0.0.0.0/0", 20, 30)), [("PG04", "block")])

    def test_all_protocols_open_both_port_lists(self):
        self.assertEqual(found(sg_inline("0.0.0.0/0", 0, 0, "-1")), [("PG04", "block"), ("PG05", "block")])

    def test_database_port_is_its_own_rule(self):
        self.assertEqual(found(sg_inline("0.0.0.0/0", 5432, 5432)), [("PG05", "block")])

    def test_hard_negatives(self):
        self.assertEqual(found(sg_inline("0.0.0.0/0", 443, 443)), [])
        self.assertEqual(found(sg_inline("0.0.0.0/0", 80, 80)), [])
        self.assertEqual(found(sg_inline("10.0.0.0/8", 22, 22)), [])
        self.assertEqual(found(sg_inline("0.0.0.0/0", 22, 22, "udp")), [])
        self.assertEqual(found(rc("aws_security_group", {"ingress": []})), [])

    def test_split_world_is_a_known_miss(self):
        # pinned on purpose: 0.0.0.0/1 plus 128.0.0.0/1 is the whole internet, and the rule reads exact CIDRs
        r = rc("aws_security_group", {"ingress": [{"cidr_blocks": ["0.0.0.0/1", "128.0.0.0/1"], "from_port": 22, "to_port": 22, "protocol": "tcp"}]})
        self.assertEqual(found(r), [])

    def test_standalone_rule_types(self):
        rule = {"type": "ingress", "cidr_blocks": ["0.0.0.0/0"], "ipv6_cidr_blocks": [], "from_port": 22, "to_port": 22, "protocol": "tcp"}
        self.assertEqual(found(rc("aws_security_group_rule", rule)), [("PG04", "block")])
        self.assertEqual(found(rc("aws_security_group_rule", dict(rule, type="egress"))), [])
        v = {"cidr_ipv4": "0.0.0.0/0", "cidr_ipv6": None, "from_port": None, "to_port": None, "ip_protocol": "-1"}
        self.assertEqual(found(rc("aws_vpc_security_group_ingress_rule", v)), [("PG04", "block"), ("PG05", "block")])

    def test_unreadable_ports_and_unknown_values_are_review(self):
        rule = {"type": "ingress", "cidr_blocks": ["0.0.0.0/0"], "from_port": None, "to_port": None, "protocol": "tcp"}
        self.assertEqual(found(rc("aws_security_group_rule", rule)), [("PG04", "review"), ("PG05", "review")])
        self.assertEqual(found(rc("aws_security_group", {"ingress": []}, unknown={"ingress": [{"cidr_blocks": [True]}]})),
                         [("PG04", "review"), ("PG05", "review")])

    def test_ports_given_as_strings_or_floats_are_read_and_junk_is_not(self):
        self.assertEqual(found(sg_inline("0.0.0.0/0", "22", "22")), [("PG04", "block")])
        self.assertEqual(found(sg_inline("0.0.0.0/0", 22.0, 22.0)), [("PG04", "block")])
        self.assertEqual(found(sg_inline("0.0.0.0/0", True, True)), [("PG04", "review"), ("PG05", "review")])
        self.assertEqual(found(sg_inline("0.0.0.0/0", "²²", "²²")), [("PG04", "review"), ("PG05", "review")])


class StorageAndListenerRules(unittest.TestCase):
    def test_encryption_flags(self):
        for rtype, attr, rule in (("aws_ebs_volume", "encrypted", "PG06"), ("aws_db_instance", "storage_encrypted", "PG07"),
                                  ("aws_efs_file_system", "encrypted", "PG09")):
            self.assertEqual(found(rc(rtype, {attr: True})), [])
            self.assertEqual(found(rc(rtype, {attr: False})), [(rule, "block")])
            self.assertEqual(found(rc(rtype, {attr: None})), [(rule, "block")])
            self.assertEqual(found(rc(rtype, {})), [(rule, "block")])
            self.assertEqual(found(rc(rtype, {}, unknown={attr: True})), [(rule, "review")])

    def test_public_database(self):
        self.assertEqual(found(rc("aws_db_instance", {"storage_encrypted": True, "publicly_accessible": True})), [("PG08", "block")])
        self.assertEqual(found(rc("aws_db_instance", {"storage_encrypted": True, "publicly_accessible": False})), [])
        self.assertEqual(found(rc("aws_db_instance", {"storage_encrypted": True}, unknown={"publicly_accessible": True})), [("PG08", "review")])

    def test_plain_http_listener_is_medium(self):
        fwd = {"protocol": "HTTP", "default_action": [{"type": "forward", "redirect": []}]}
        for rtype in ("aws_lb_listener", "aws_alb_listener"):
            self.assertEqual(found(rc(rtype, fwd)), [("PG10", "review")])
        self.assertEqual(check_plan(plan(rc("aws_lb_listener", fwd)))["findings"][0]["kind"], "violation")

    def test_listener_hard_negatives(self):
        redirect = {"type": "redirect", "redirect": [{"protocol": "HTTPS", "port": "443"}]}
        self.assertEqual(found(rc("aws_lb_listener", {"protocol": "HTTP", "default_action": [redirect]})), [])
        self.assertEqual(found(rc("aws_lb_listener", {"protocol": "HTTPS", "default_action": [{"type": "forward"}]})), [])
        keeps_http = {"type": "redirect", "redirect": [{"protocol": "#{protocol}"}]}
        self.assertEqual(found(rc("aws_lb_listener", {"protocol": "HTTP", "default_action": [keeps_http]})), [("PG10", "review")])


class ScopeAndDecision(unittest.TestCase):
    BAD = {"encrypted": False}

    def test_only_create_and_update_are_read(self):
        self.assertEqual(found(rc("aws_ebs_volume", None, ("delete",), before=self.BAD)), [])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, ("no-op",), before=self.BAD)), [])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, ("update",), before={"encrypted": True})), [("PG06", "block")])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, ("delete", "create"))), [("PG06", "block")])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, ("read",), mode="data")), [])

    def test_state_scan_option_reads_deletes_too(self):
        r = rc("aws_ebs_volume", None, ("delete",), before=self.BAD)
        self.assertEqual(found(r, changed_only=False), [("PG06", "block")])

    def test_unknown_option_drops_unverified(self):
        r = rc("aws_ebs_volume", {}, unknown={"encrypted": True})
        self.assertEqual(found(r), [("PG06", "review")])
        self.assertEqual(found(r, flag_unknown=False), [])

    def test_type_field_decides_not_the_address(self):
        self.assertEqual(found(rc("aws_instance", self.BAD, address="aws_ebs_volume.fake")), [])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, address="aws_instance.fake")), [("PG06", "block")])
        self.assertEqual(found(rc("aws_ebs_volume", self.BAD, address="module.a.module.b.aws_ebs_volume.v[3]")), [("PG06", "block")])

    def test_counts_and_decide(self):
        out = check_plan(plan(rc("aws_vpc", {}), rc("aws_ebs_volume", self.BAD), rc("aws_ebs_volume", {"encrypted": True}, name="y")))
        self.assertEqual((out["changes"], out["checked"]), (3, 2))
        self.assertEqual(decide([]), "ALLOW")
        self.assertEqual(decide([{"class": "review"}]), "REVIEW")
        self.assertEqual(decide([{"class": "review"}, {"class": "block"}]), "BLOCK")


if __name__ == "__main__":
    unittest.main()
