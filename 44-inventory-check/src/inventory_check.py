"""inventory_check: test an inventory of generative and agentic AI systems for completeness,
staleness and coverage. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 inventory_check.py --demo
    python3 inventory_check.py check INVENTORY.json [--usage USAGE.csv] [--as-of YYYY-MM-DD]
                                                    [--fail-on fail|review|never] [--format text|github]

Exit status: 0 when the decision is below --fail-on, 1 when it is at or above it, 2 for bad or malformed input.
The decision is FAIL (a record is incomplete, or a system runs that the inventory does not list),
REVIEW (the record is complete but out of date, or the traffic does not match it) or PASS.
There is no model in this file: every test is a plain rule.

Inventory: a JSON list of system records. Required fields: system_id, name, kind, status, business_owner,
technical_owner, risk_tier, purpose, provider_type, model_id, data_class, customer_facing, last_reviewed.
Conditional fields: tools, permission_scope and human_approval for an agentic system; evaluation_ref and
last_evaluated for a production system of tier 2 or higher; independent_review_date from tier 3;
fallback_plan at tier 4.
Usage: an optional CSV export from a model gateway with columns system_id, model_id, first_seen, last_seen, calls.
--as-of defaults to today's date; pass it for a repeatable result.

The field list, the cadences and the windows below are this project's own assumptions. SR 26-2 places generative
and agentic AI outside its scope and prescribes no inventory schema.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import sys

REQUIRED = ("system_id", "name", "kind", "status", "business_owner", "technical_owner", "risk_tier",
            "purpose", "provider_type", "model_id", "data_class", "customer_facing", "last_reviewed")
TEXT_FIELDS = ("system_id", "name", "business_owner", "technical_owner", "purpose", "model_id")
ENUMS = {
    "kind": ("generative", "agentic"),
    "status": ("development", "pilot", "production", "retired"),
    "provider_type": ("vendor_api", "self_hosted"),
    "data_class": ("public", "internal", "confidential", "restricted"),
    "customer_facing": ("yes", "no"),
    "permission_scope": ("read_only", "read_write", "transact"),
    "human_approval": ("none", "on_exception", "before_action"),
    "fallback_plan": ("yes", "no"),
}
AGENT_WHY = {
    "tools": "agentic system lists no `tools`, so what it can do cannot be reviewed",
    "permission_scope": "agentic system has no `permission_scope`, so the most it can change is unknown",
    "human_approval": "agentic system has no `human_approval` setting, so nobody knows when a person steps in",
}
TIERS = (1, 2, 3, 4)
CADENCE_DAYS = {1: 365, 2: 270, 3: 180, 4: 90}   # assumption: the longest gap allowed between reviews, by tier
IDLE_DAYS = 90                                   # assumption: a production system unseen this long is probably not in use
RETIRED_QUIET_DAYS = 30                          # assumption: a retired system seen this recently is still running
PLACEHOLDERS = frozenset(["tbd", "tba", "tbc", "n/a", "na", "none", "unknown", "null", "nil", "todo",
                          "-", "--", "?", "??", "xxx"])
USAGE_COLUMNS = ("system_id", "model_id", "first_seen", "last_seen", "calls")
TESTS = ("completeness", "staleness", "coverage")
DEMO_AS_OF = "2026-09-30"
RANK = {"PASS": 0, "REVIEW": 1, "FAIL": 2}


# ---------------------------------------------------------------- small helpers
def parse_date(v):
    """A date from a YYYY-MM-DD string, or None. Strict, so the answer does not change with the Python version."""
    if not isinstance(v, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
        return None
    try:
        return datetime.date(int(v[:4]), int(v[5:7]), int(v[8:10]))
    except ValueError:
        return None


def parse_tier(v):
    """1 to 4 from an integer or a one-digit string; None for anything else, a boolean included."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if v in TIERS else None
    if isinstance(v, str) and v.strip() in ("1", "2", "3", "4"):
        return int(v.strip())
    return None


def is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def is_placeholder(v: str) -> bool:
    """True when the whole value is a placeholder word. A sentence that contains one is not."""
    return " ".join(v.lower().split()).rstrip(".") in PLACEHOLDERS


def norm_id(s: str) -> str:
    return " ".join(s.lower().split())


def show(v, limit: int = 60) -> str:
    """A value made safe to print: control characters and non-ASCII escaped, long values cut."""
    s = json.dumps(v if isinstance(v, str) else str(v), ensure_ascii=True)[1:-1]
    return s if len(s) <= limit else s[:limit - 3] + "..."


def finding(system_id, test, kind, severity, field, message) -> dict:
    return {"system_id": system_id, "test": test, "kind": kind, "severity": severity, "field": field, "message": message}


def date_problem(field: str, v, as_of):
    """Why a date field is unusable, or None when it is a real date that is not after the as-of date."""
    d = parse_date(v)
    if d is None:
        return f"`{field}` is {show(v)}, not a date written YYYY-MM-DD"
    if d > as_of:
        return f"`{field}` is {v}, after the as-of date {as_of.isoformat()}"
    return None


# ---------------------------------------------------------------- completeness
def check_record(rec: dict, label: str, as_of) -> list:
    """Completeness tests on one record: required fields, valid values, and the fields its kind and tier require."""
    out = []

    def add(kind, severity, field, message):
        out.append(finding(label, "completeness", kind, severity, field, message))

    for f in REQUIRED:
        v = rec.get(f)
        if is_blank(v):
            add("missing_required", "fail", f, f"`{f}` is blank or absent")
        elif f in TEXT_FIELDS:
            if not isinstance(v, str):
                add("invalid_value", "fail", f, f"`{f}` must be text, got {show(v)}")
            elif is_placeholder(v):
                add("placeholder_value", "fail", f, f"`{f}` is {show(v)}, a placeholder and not a value")
        elif f == "risk_tier":
            if parse_tier(v) is None:
                add("invalid_value", "fail", f, f"`{f}` is {show(v)}; allowed: 1, 2, 3, 4")
        elif f == "last_reviewed":
            problem = date_problem(f, v, as_of)
            if problem:
                add("invalid_value", "fail", f, problem)
        elif not isinstance(v, str) or v not in ENUMS[f]:
            add("invalid_value", "fail", f, f"`{f}` is {show(v)}; allowed: {', '.join(ENUMS[f])}")

    tier, status, kind = parse_tier(rec.get("risk_tier")), rec.get("status"), rec.get("kind")
    if kind == "agentic":
        for f in ("tools", "permission_scope", "human_approval"):
            v = rec.get(f)
            if is_blank(v):
                add("agent_field_missing", "fail", f, AGENT_WHY[f])
            elif f == "tools":
                if not isinstance(v, list) or any(not isinstance(t, str) or not t.strip() for t in v):
                    add("invalid_value", "fail", f, f"`tools` must be a list of tool names, got {show(v)}")
            elif not isinstance(v, str) or v not in ENUMS[f]:
                add("invalid_value", "fail", f, f"`{f}` is {show(v)}; allowed: {', '.join(ENUMS[f])}")
    elif kind == "generative" and not is_blank(rec.get("tools")):
        add("kind_mismatch", "review", "tools",
            "`kind` is generative but `tools` are listed; an agent recorded as generative skips the agent fields")

    if status == "production" and tier is not None:
        need = (["evaluation_ref", "last_evaluated"] if tier >= 2 else []) \
            + (["independent_review_date"] if tier >= 3 else []) + (["fallback_plan"] if tier == 4 else [])
        for f in need:
            if is_blank(rec.get(f)):
                add("evidence_missing", "fail", f, f"tier {tier} production system has no `{f}`")
        if tier == 4 and rec.get("fallback_plan") == "no":
            add("evidence_missing", "fail", "fallback_plan", "tier 4 production system records no fallback plan (`fallback_plan` is no)")

    for f in ("last_evaluated", "independent_review_date"):
        if not is_blank(rec.get(f)):
            problem = date_problem(f, rec.get(f), as_of)
            if problem:
                add("invalid_value", "fail", f, problem)
    ref = rec.get("evaluation_ref")
    if not is_blank(ref):
        if not isinstance(ref, str):
            add("invalid_value", "fail", "evaluation_ref", f"`evaluation_ref` must be text, got {show(ref)}")
        elif is_placeholder(ref):
            add("placeholder_value", "fail", "evaluation_ref", f"`evaluation_ref` is {show(ref)}, a placeholder and not a value")
    fb = rec.get("fallback_plan")
    if not is_blank(fb) and (not isinstance(fb, str) or fb not in ENUMS["fallback_plan"]):
        add("invalid_value", "fail", "fallback_plan", f"`fallback_plan` is {show(fb)}; allowed: yes, no")
    return out


# ---------------------------------------------------------------- staleness and coverage
def _age(d, as_of) -> int:
    return (as_of - d).days


def latest_row(rows: list) -> dict:
    """The usage row seen most recently; ties go to the larger model id so the answer is stable."""
    return max(rows, key=lambda r: (r["last_seen"], norm_id(r["model_id"])))


def check_dates(rec: dict, label: str, as_of) -> list:
    """Review and evaluation dates against the cadence for the record's tier. A retired system is exempt."""
    tier = parse_tier(rec.get("risk_tier"))
    if tier is None or rec.get("status") == "retired":
        return []
    out = []
    pairs = [("last_reviewed", "review_overdue", "last reviewed")]
    if rec.get("status") == "production" and tier >= 2:
        pairs.append(("last_evaluated", "evaluation_overdue", "last evaluated"))
    for field, kind, words in pairs:
        d = parse_date(rec.get(field))
        if d is not None and d <= as_of and _age(d, as_of) > CADENCE_DAYS[tier]:
            out.append(finding(label, "staleness", kind, "review", field,
                               f"{words} {d.isoformat()} ({_age(d, as_of)} days ago); tier {tier} cadence is {CADENCE_DAYS[tier]} days"))
    return out


def check_model(rec: dict, label: str, rows: list, as_of) -> list:
    """The record's model id against the model that recent traffic actually used."""
    recorded = rec.get("model_id")
    if rec.get("status") == "retired" or not rows or not isinstance(recorded, str) or is_blank(recorded) or is_placeholder(recorded):
        return []
    cur = latest_row(rows)
    if _age(cur["last_seen"], as_of) > IDLE_DAYS or norm_id(cur["model_id"]) == norm_id(recorded):
        return []
    return [finding(label, "staleness", "model_changed", "review", "model_id",
                    f"traffic last seen {cur['last_seen'].isoformat()} ran on {show(cur['model_id'])}; the record says {show(recorded)}")]


def check_traffic(rec: dict, label: str, rows: list, as_of) -> list:
    """A retired system that still runs, and a production system that does not."""
    status = rec.get("status")
    if status == "retired" and rows:
        last = latest_row(rows)["last_seen"]
        if _age(last, as_of) <= RETIRED_QUIET_DAYS:
            return [finding(label, "coverage", "retired_still_running", "fail", "status",
                            f"status is retired but traffic was seen {last.isoformat()} ({_age(last, as_of)} days ago); quiet limit is {RETIRED_QUIET_DAYS} days")]
    if status == "production":
        if not rows:
            return [finding(label, "coverage", "no_traffic", "review", "status", "production system has no usage rows")]
        last = latest_row(rows)["last_seen"]
        if _age(last, as_of) > IDLE_DAYS:
            return [finding(label, "coverage", "no_traffic", "review", "status",
                            f"production system last seen {last.isoformat()} ({_age(last, as_of)} days ago); idle limit is {IDLE_DAYS} days")]
    return []


def check_unlisted(known: set, by_id: dict) -> list:
    """Usage that has no inventory record, and usage with no system id at all."""
    out = []
    for sid in sorted(by_id):
        rows = by_id[sid]
        calls = sum(r["calls"] for r in rows)
        if sid == "":
            out.append(finding("", "coverage", "untagged_traffic", "review", "system_id",
                               f"{len(rows)} usage rows with {calls} calls carry no system_id, so they cannot be matched to a record"))
        elif sid not in known:
            first = min(r["first_seen"] for r in rows).isoformat()
            last = max(r["last_seen"] for r in rows).isoformat()
            out.append(finding(sid, "coverage", "unregistered_system", "fail", "system_id",
                               f"{show(sid)} made {calls} calls from {first} to {last} and has no inventory record"))
    return out


def check(records: list, usage, as_of, tests=TESTS) -> list:
    """Run the chosen tests. usage is a list of rows (see load_usage) or None when no export was given."""
    seen, entries = set(), []
    for n, rec in enumerate(records, 1):
        sid = rec.get("system_id")
        has_id = isinstance(sid, str) and bool(sid.strip())
        label = sid.strip() if has_id else f"(record {n})"
        entries.append((label, rec, has_id and label in seen))
        if has_id:
            seen.add(label)
    out = []
    for label, rec, dup in entries:
        if "completeness" in tests:
            out.extend(check_record(rec, label, as_of))
            if dup:
                out.append(finding(label, "completeness", "duplicate_id", "fail", "system_id",
                                   f"`system_id` {show(label)} appears more than once; only the first record is used for the other tests"))
    live = {label: rec for label, rec, dup in entries if not dup}
    by_id = {}
    for row in usage or []:
        by_id.setdefault(row["system_id"], []).append(row)
    for label, rec in live.items():
        rows = by_id.get(label, []) if label in seen else []
        if "staleness" in tests:
            out.extend(check_dates(rec, label, as_of))
            if usage is not None:
                out.extend(check_model(rec, label, rows, as_of))
        if "coverage" in tests and usage is not None:
            out.extend(check_traffic(rec, label, rows, as_of))
    if "coverage" in tests and usage is not None:
        out.extend(check_unlisted({k for k in live if k in seen}, by_id))
    order = {t: i for i, t in enumerate(TESTS)}
    return sorted(out, key=lambda f: (f["system_id"] == "", f["system_id"], order[f["test"]], f["kind"], f["field"]))


def decide(findings: list) -> str:
    sev = {f["severity"] for f in findings}
    return "FAIL" if "fail" in sev else "REVIEW" if "review" in sev else "PASS"


def notes_for(records: list, usage) -> list:
    """Things a reader must know about what did not run or did not match, so that nothing is silent."""
    if usage is None:
        return ["no usage file was given, so the model-change, unregistered-system, retired-still-running and no-traffic tests did not run"]
    ids = {r["system_id"].strip() for r in records if isinstance(r.get("system_id"), str) and r["system_id"].strip()}
    if not any(row["system_id"] in ids for row in usage):
        return ["no usage row matches an inventory system_id; check that both files use the same identifiers"]
    return []


# ---------------------------------------------------------------- loading
def load_inventory(path: str) -> list:
    """The inventory as a list of dicts. Raises ValueError (or OSError) for anything that is not one."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of system records, got {type(data).__name__}")
    if not data:
        raise ValueError(f"{path}: the inventory has no records, so there is nothing to check")
    for n, rec in enumerate(data, 1):
        if not isinstance(rec, dict):
            raise ValueError(f"{path}: record {n} must be a JSON object, got {type(rec).__name__}")
    return data


def load_usage(path: str, as_of) -> list:
    """Usage rows with real dates and integer call counts. Raises ValueError (or OSError) for a bad file."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in USAGE_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing columns {', '.join(missing)}")
        rows = []
        for n, r in enumerate(reader, 2):
            where = f"{path} line {n}"
            if any(r.get(c) is None for c in USAGE_COLUMNS):
                raise ValueError(f"{where}: the row has fewer than {len(USAGE_COLUMNS)} fields")
            first, last = parse_date(r["first_seen"].strip()), parse_date(r["last_seen"].strip())
            if first is None or last is None:
                raise ValueError(f"{where}: first_seen and last_seen must be dates written YYYY-MM-DD")
            if first > last:
                raise ValueError(f"{where}: first_seen is after last_seen")
            if last > as_of:
                raise ValueError(f"{where}: last_seen {last.isoformat()} is after the as-of date {as_of.isoformat()}")
            if not re.fullmatch(r"[0-9]{1,12}", r["calls"].strip()):
                raise ValueError(f"{where}: calls must be a whole number of 0 or more")
            if not r["model_id"].strip():
                raise ValueError(f"{where}: model_id is blank")
            rows.append({"system_id": r["system_id"].strip(), "model_id": r["model_id"].strip(),
                         "first_seen": first, "last_seen": last, "calls": int(r["calls"].strip())})
    if not rows:
        raise ValueError(f"{path}: the usage file has no rows, so there is nothing to compare")
    return rows


# ---------------------------------------------------------------- command line
def escape_annotation(text: str) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def counts(findings: list) -> tuple:
    return (sum(1 for f in findings if f["severity"] == "fail"), sum(1 for f in findings if f["severity"] == "review"))


def render(records, usage, as_of, findings, decision, notes, fmt) -> str:
    n_fail, n_review = counts(findings)
    if fmt == "github":
        lines = []
        for f in findings:
            level = "error" if f["severity"] == "fail" else "warning"
            lines.append(f"::{level} title=inventory-check {f['kind']}::" + escape_annotation(f"{show(f['system_id'] or '(usage)')}: {f['message']}"))
        for note in notes:
            lines.append("::notice title=inventory-check::" + escape_annotation(note))
        lines.append("::notice title=inventory-check::" + escape_annotation(f"decision {decision}; {n_fail} fail, {n_review} review"))
        return "\n".join(lines)
    usage_text = f"{len(usage)} usage rows" if usage is not None else "no usage file"
    lines = [f"inventory: {len(records)} systems as of {as_of.isoformat()}; {usage_text}"]
    lines += [f"  note: {note}" for note in notes]
    for f in findings:
        lines.append(f"  [{f['severity']:<6}] {show(f['system_id'] or '(usage)', 24):<18} {f['kind']:<22} {f['message']}")
    if not findings:
        lines.append("  no findings")
    lines.append(f"decision: {decision} ({n_fail} fail, {n_review} review)")
    return "\n".join(lines)


def run_check(inventory_path, usage_path, as_of, fail_on, fmt) -> int:
    try:
        records = load_inventory(inventory_path)
        usage = load_usage(usage_path, as_of) if usage_path else None
    except (OSError, ValueError, RecursionError, csv.Error) as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    findings = check(records, usage, as_of)
    decision = decide(findings)
    print(render(records, usage, as_of, findings, decision, notes_for(records, usage), fmt))
    if fail_on == "never":
        return 0
    return 1 if RANK[decision] >= RANK[{"fail": "FAIL", "review": "REVIEW"}[fail_on]] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="inventory_check")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="test an inventory file")
    c.add_argument("inventory")
    c.add_argument("--usage", help="gateway usage export (CSV) to compare the inventory with")
    c.add_argument("--as-of", dest="as_of", help="the date to measure age from, YYYY-MM-DD (default: today)")
    c.add_argument("--fail-on", choices=["fail", "review", "never"], default="fail")
    c.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_inventory.json"), os.path.join(d, "example_usage.csv"),
                         parse_date(DEMO_AS_OF), "never", "text")
    if a.cmd == "check":
        as_of = datetime.date.today() if a.as_of is None else parse_date(a.as_of)
        if as_of is None:
            print("input error: --as-of must be a date written YYYY-MM-DD", file=sys.stderr)
            return 2
        return run_check(a.inventory, a.usage, as_of, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
