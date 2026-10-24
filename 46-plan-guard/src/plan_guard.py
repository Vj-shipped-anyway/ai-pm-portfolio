"""plan_guard: policy checks on a Terraform plan in JSON form, before it is applied. Standard library
only. Python 3.9 or newer.

Command line (from src/):
    python3 plan_guard.py --demo
    python3 plan_guard.py check PLAN.json [--fail-on block|review|never] [--format text|github]

Make the input with `terraform show -json PLAN_FILE > plan.json`. Only `resource_changes` is read.

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or malformed
input. A decision is BLOCK (a rule is broken by a resource the plan creates or updates), REVIEW (a medium
rule is broken, or a value the rule needs is not known until apply) or ALLOW. There is no model in this
file: ten rules, each tied to exact resource types, read the attributes of the planned resource.

What is checked: resource changes whose actions include create or update, of a type that has a rule.
Deletes, no-ops and data sources are skipped. The address is a label only; the `type` field decides
which rules apply. Rules look at one resource at a time and never join two resources.
Supported: AWS provider resource types named in RULES. Not supported: modules' configuration,
`planned_values`, other providers, values that Terraform marks sensitive.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import namedtuple

DECISION_RANK = {"ALLOW": 0, "REVIEW": 1, "BLOCK": 2}
CHANGING = {"create", "update"}
WORLD_CIDRS = ("0.0.0.0/0", "::/0")
PUBLIC_ACLS = ("public-read", "public-read-write", "authenticated-read")
PAB_FLAGS = ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets")
ADMIN_PORTS = (22, 3389)
DB_PORTS = (1433, 1521, 3306, 5432, 6379, 27017)
SG_WATCH = {
    "aws_security_group": ("ingress",),
    "aws_security_group_rule": ("type", "cidr_blocks", "ipv6_cidr_blocks", "from_port", "to_port", "protocol"),
    "aws_vpc_security_group_ingress_rule": ("cidr_ipv4", "cidr_ipv6", "from_port", "to_port", "ip_protocol"),
}


# ---------------------------------------------------------------- helpers
def _has_unknown(v) -> bool:
    """True when `after_unknown` marks the value, or anything inside it, as known only after apply."""
    if v is True:
        return True
    if isinstance(v, dict):
        return any(_has_unknown(x) for x in v.values())
    if isinstance(v, list):
        return any(_has_unknown(x) for x in v)
    return False


def _unknown(unk: dict, attr: str) -> bool:
    return _has_unknown(unk.get(attr))


def _show(v) -> str:
    return "not set" if v is None else json.dumps(v)[:60]


def _port(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and v.isascii() and v.isdigit():
        return int(v)
    return None


def _strs(v) -> list:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []


def _must_be_true(after: dict, unk: dict, attr: str, what: str) -> list:
    if _unknown(unk, attr):
        return [("unverified", f"`{attr}` is not known until apply, so {what} cannot be checked in the plan")]
    if after.get(attr) is True:
        return []
    return [("violation", f"`{attr}` is {_show(after.get(attr))}, so {what} is off")]


# ---------------------------------------------------------------- the ten rules
# A rule returns hits: ("violation", text) when the resource breaks it, ("unverified", text) when the
# plan does not carry the value the rule needs.
def rule_s3_public_acl(rtype, after, unk):
    if _unknown(unk, "acl"):
        return [("unverified", "`acl` is not known until apply")]
    acl = after.get("acl")
    if isinstance(acl, str) and acl in PUBLIC_ACLS:
        return [("violation", f"acl is {acl}, a canned ACL that opens the bucket beyond its owner")]
    return []


def rule_s3_pab_off(rtype, after, unk):
    hits = []
    for flag in PAB_FLAGS:
        if _unknown(unk, flag):
            hits.append(("unverified", f"`{flag}` is not known until apply"))
        elif after.get(flag) is not True:
            hits.append(("violation", f"`{flag}` is {_show(after.get(flag))}, so the public access block is not fully on"))
    return hits


def _star(v) -> bool:
    return v == "*" or (isinstance(v, list) and "*" in v)


def _world_principal(p) -> bool:
    return _star(p) or (isinstance(p, dict) and _star(p.get("AWS")))


def rule_s3_policy_world(rtype, after, unk):
    if _unknown(unk, "policy"):
        return [("unverified", "`policy` is not known until apply")]
    try:
        doc = json.loads(after.get("policy"))
    except (TypeError, ValueError, RecursionError):
        return [("unverified", "`policy` is not a JSON document, so it cannot be checked")]
    stmts = doc.get("Statement") if isinstance(doc, dict) else None
    if isinstance(stmts, dict):
        stmts = [stmts]
    if not isinstance(stmts, list) or not all(isinstance(s, dict) for s in stmts):
        return [("unverified", "`policy` has no readable Statement list")]
    for s in stmts:
        if s.get("Effect") == "Allow" and _world_principal(s.get("Principal")) and not s.get("Condition"):
            return [("violation", "the policy allows Principal * with no Condition")]
    return []


def _ingress_entries(rtype, after) -> list:
    """Ingress rules of the three security-group resource types as {cidrs, lo, hi, proto}."""
    if rtype == "aws_security_group":
        raw = [e for e in (after.get("ingress") if isinstance(after.get("ingress"), list) else []) if isinstance(e, dict)]
        return [{"cidrs": _strs(e.get("cidr_blocks")) + _strs(e.get("ipv6_cidr_blocks")), "lo": e.get("from_port"),
                 "hi": e.get("to_port"), "proto": e.get("protocol")} for e in raw]
    if rtype == "aws_security_group_rule":
        if after.get("type") != "ingress":
            return []
        return [{"cidrs": _strs(after.get("cidr_blocks")) + _strs(after.get("ipv6_cidr_blocks")), "lo": after.get("from_port"),
                 "hi": after.get("to_port"), "proto": after.get("protocol")}]
    return [{"cidrs": _strs(after.get("cidr_ipv4")) + _strs(after.get("cidr_ipv6")), "lo": after.get("from_port"),
             "hi": after.get("to_port"), "proto": after.get("ip_protocol")}]


def _reached(entry, ports):
    """Ports from `ports` the entry opens, or None when a TCP entry's port range cannot be read."""
    proto = str(entry["proto"]).lower()
    if proto in ("-1", "all"):
        return list(ports)
    if proto not in ("tcp", "6"):
        return []
    lo, hi = _port(entry["lo"]), _port(entry["hi"])
    if lo is None or hi is None:
        return None
    return [p for p in ports if lo <= p <= hi]


def _world_ingress(rtype, after, unk, ports, label):
    if rtype == "aws_security_group_rule" and after.get("type") == "egress":
        return []
    hits = []
    if any(_unknown(unk, a) for a in SG_WATCH[rtype]):
        hits.append(("unverified", "an ingress value is not known until apply, so the rule cannot be fully checked"))
    for e in _ingress_entries(rtype, after):
        world = [c for c in e["cidrs"] if c in WORLD_CIDRS]
        if not world:
            continue
        reached = _reached(e, ports)
        if reached is None:
            hits.append(("unverified", f"ingress from {world[0]} has a port range that cannot be read"))
        elif reached:
            hits.append(("violation", f"ingress from {world[0]} reaches {label} {', '.join(str(p) for p in reached)}"))
    return hits


def rule_sg_world_admin_port(rtype, after, unk):
    return _world_ingress(rtype, after, unk, ADMIN_PORTS, "admin port")


def rule_sg_world_database_port(rtype, after, unk):
    return _world_ingress(rtype, after, unk, DB_PORTS, "database port")


def rule_ebs_unencrypted(rtype, after, unk):
    return _must_be_true(after, unk, "encrypted", "volume encryption")


def rule_rds_unencrypted(rtype, after, unk):
    return _must_be_true(after, unk, "storage_encrypted", "database storage encryption")


def rule_rds_public(rtype, after, unk):
    if _unknown(unk, "publicly_accessible"):
        return [("unverified", "`publicly_accessible` is not known until apply")]
    if after.get("publicly_accessible") is True:
        return [("violation", "`publicly_accessible` is true, so the database gets a public endpoint")]
    return []


def rule_efs_unencrypted(rtype, after, unk):
    return _must_be_true(after, unk, "encrypted", "file system encryption")


def rule_lb_plain_http(rtype, after, unk):
    if _unknown(unk, "protocol"):
        return [("unverified", "`protocol` is not known until apply")]
    proto = after.get("protocol")
    if not (isinstance(proto, str) and proto.upper() == "HTTP"):
        return []
    actions = after.get("default_action") if isinstance(after.get("default_action"), list) else []
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "redirect":
            for r in a.get("redirect") if isinstance(a.get("redirect"), list) else []:
                if isinstance(r, dict) and str(r.get("protocol")).upper() == "HTTPS":
                    return []
    return [("violation", "the listener accepts plain HTTP and its default action does not redirect to HTTPS")]


Rule = namedtuple("Rule", "id name severity types fn")
RULES = (
    Rule("PG01", "s3_public_acl", "high", ("aws_s3_bucket", "aws_s3_bucket_acl"), rule_s3_public_acl),
    Rule("PG02", "s3_public_access_block_off", "high", ("aws_s3_bucket_public_access_block",), rule_s3_pab_off),
    Rule("PG03", "s3_policy_world_principal", "high", ("aws_s3_bucket_policy",), rule_s3_policy_world),
    Rule("PG04", "sg_world_admin_port", "high", tuple(SG_WATCH), rule_sg_world_admin_port),
    Rule("PG05", "sg_world_database_port", "high", tuple(SG_WATCH), rule_sg_world_database_port),
    Rule("PG06", "ebs_unencrypted", "high", ("aws_ebs_volume",), rule_ebs_unencrypted),
    Rule("PG07", "rds_unencrypted", "high", ("aws_db_instance",), rule_rds_unencrypted),
    Rule("PG08", "rds_public", "high", ("aws_db_instance",), rule_rds_public),
    Rule("PG09", "efs_unencrypted", "high", ("aws_efs_file_system",), rule_efs_unencrypted),
    Rule("PG10", "lb_plain_http_listener", "medium", ("aws_lb_listener", "aws_alb_listener"), rule_lb_plain_http),
)


# ---------------------------------------------------------------- the check
def check_plan(plan: dict, changed_only: bool = True, flag_unknown: bool = True) -> dict:
    """Run the rules over a validated plan. Returns {"findings", "changes", "checked"}.

    changed_only=False also reads deletes and no-ops (step 3 shows what that costs); flag_unknown=False
    drops the hits for values the plan cannot know yet (step 3 shows what that hides)."""
    findings, checked = [], 0
    changes = plan.get("resource_changes", [])
    for rc in changes:
        if rc.get("mode") == "data":
            continue
        change = rc["change"]
        if changed_only and not CHANGING & set(change["actions"]):
            continue
        state = change.get("after") if change.get("after") is not None else change.get("before")
        rules = [r for r in RULES if rc["type"] in r.types]
        if not rules or not isinstance(state, dict):
            continue
        checked += 1
        unk = change.get("after_unknown") or {}
        for rule in rules:
            for kind, text in rule.fn(rc["type"], state, unk):
                if kind == "unverified" and not flag_unknown:
                    continue
                cls = "block" if kind == "violation" and rule.severity == "high" else "review"
                findings.append({"rule": rule.id, "name": rule.name, "class": cls, "kind": kind,
                                 "address": rc["address"], "reason": text})
    return {"findings": findings, "changes": len(changes), "checked": checked}


def decide(findings: list) -> str:
    classes = {f["class"] for f in findings}
    return "BLOCK" if "block" in classes else "REVIEW" if "review" in classes else "ALLOW"


# ---------------------------------------------------------------- loading and input checks
def check_shape(plan, label: str) -> None:
    """Raise ValueError when the file is not a plan this tool can read, so bad input exits 2, not 1."""
    if not isinstance(plan, dict):
        raise ValueError(f"{label}: expected a JSON object, got {type(plan).__name__}")
    fv = plan.get("format_version")
    if not isinstance(fv, str) or not fv.startswith("1."):
        raise ValueError(f"{label}: format_version must be a string starting with '1.'; is this the output of `terraform show -json`?")
    changes = plan.get("resource_changes", [])
    if not isinstance(changes, list):
        raise ValueError(f"{label}: resource_changes must be a list")
    for i, rc in enumerate(changes):
        where = f"{label}: resource_changes[{i}]"
        if not isinstance(rc, dict):
            raise ValueError(f"{where} must be an object")
        for key in ("address", "type"):
            if not isinstance(rc.get(key), str):
                raise ValueError(f"{where} needs a string `{key}`")
        change = rc.get("change")
        if not isinstance(change, dict):
            raise ValueError(f"{where} needs a `change` object")
        actions = change.get("actions")
        if not isinstance(actions, list) or not all(isinstance(a, str) for a in actions):
            raise ValueError(f"{where}.change.actions must be a list of strings")
        for key in ("before", "after"):
            if change.get(key) is not None and not isinstance(change[key], dict):
                raise ValueError(f"{where}.change.{key} must be an object or null")
        if change.get("after_unknown") is not None and not isinstance(change["after_unknown"], dict):
            raise ValueError(f"{where}.change.after_unknown must be an object")


def load_plan(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh)
    check_shape(plan, "plan")
    return plan


# ---------------------------------------------------------------- output
def visible(text) -> str:
    """Make untrusted text safe to print: control characters become visible escapes, so a value from the
    plan cannot start a new log line or a workflow command."""
    return "".join(ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in str(text))[:300]


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so plan text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _scope_line(result: dict) -> str:
    if result["changes"] == 0:
        return "the plan has no resource changes; nothing was checked"
    if result["checked"] == 0:
        return (f"none of the {result['changes']} resource changes creates or updates a type that has a rule; "
                f"nothing was checked")
    return ""


def render(label: str, plan: dict, result: dict, decision: str, fmt: str) -> str:
    lines = []
    scope = _scope_line(result)
    if fmt == "github":
        for f in result["findings"]:
            level = "error" if f["class"] == "block" else "warning"
            lines.append(f"::{level} title=plan-guard {f['rule']}::" + escape_annotation(f"{f['address']}: {f['reason']}"))
        summary = f"decision {decision}; {result['checked']} of {result['changes']} resource changes checked"
        lines.append("::notice title=plan-guard::" + summary + (f"; {scope}" if scope else ""))
        return "\n".join(lines)
    lines.append(f"plan: {visible(label)}   format_version {visible(plan['format_version'])}   "
                 f"{result['changes']} resource changes, {result['checked']} checked")
    for f in result["findings"]:
        lines.append(f"  [{f['class']:<6}] {f['rule']} {f['name']:<27} {visible(f['address'])}: {visible(f['reason'])}")
    if scope:
        lines.append(f"  {scope}")
    elif not result["findings"]:
        lines.append(f"  no finding in {result['checked']} checked resource changes")
    lines.append(f"decision: {decision}")
    return "\n".join(lines)


def run_check(path: str, fail_on: str, fmt: str) -> int:
    try:
        plan = load_plan(path)
        result = check_plan(plan)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as e:
        print(f"input error: {visible(e)}", file=sys.stderr)
        return 2
    decision = decide(result["findings"])
    print(render(os.path.basename(path), plan, result, decision, fmt))
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[decision] >= DECISION_RANK[{"block": "BLOCK", "review": "REVIEW"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plan_guard")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_plan.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check a plan JSON file")
    c.add_argument("plan")
    c.add_argument("--fail-on", choices=["block", "review", "never"], default="block")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_plan.json"), "never", "text")
    if a.cmd == "check":
        return run_check(a.plan, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
