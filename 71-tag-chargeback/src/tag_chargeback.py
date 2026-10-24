"""tag_chargeback: allocate one month of a cloud billing export to cost centers from the tags on each
line, report tag compliance, and list the spend nobody owns. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 tag_chargeback.py --demo
    python3 tag_chargeback.py report BILL.csv --policy policy.json --cost-centers cost_centers.csv \
        --accounts accounts.csv [--max-unallocated-pct N] [--format text|github] \
        [--chargeback-csv OUT.csv] [--lines-csv OUT.csv]

Exit status: 0 when unallocated spend is at or below the limit, 1 when it is above, 2 for bad input.

Rules, applied to each line in this order, first match wins. There is no model in this file.
  0. zero_cost       a line that costs nothing has nothing to allocate and is not reported as unallocated.
  1. tag             the cost-center tag (the policy key or a listed alias) names an active cost center.
                     Matching ignores case and surrounding spaces; that match is reported as tag_repaired.
                     A tag that is present but unknown, closed or contradictory is never overridden by a
                     later rule: the line is unallocated with that reason.
  2. shared_split    no cost-center tag and the service is listed as shared in the policy: split across
                     cost centers in proportion to what the other rules allocated to each in the bill.
  3. inherit         no cost-center tag and the same resource_id has tagged lines that agree.
  4. account_default no tag, no tagged sibling, and the account is dedicated to one active cost center.
  5. otherwise       unallocated, reason no_owner_found.
Money is held in millionths of a dollar as integers, so allocated plus unallocated equals the bill.

Bill columns: line_id, usage_date, account_id, service, resource_id, usage_type, cost_usd, tags_json.
tags_json is a JSON object of strings; write {} for an untagged line. An empty tag value counts as absent.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys
from decimal import Decimal, InvalidOperation

MICROS = 1_000_000
EXTRAS = frozenset({"inherit", "shared_split", "account_default"})
RULE_ORDER = ("tag", "tag_repaired", "shared_split", "inherit", "account_default", "zero_cost", "unallocated")
BILL_COLUMNS = ("line_id", "usage_date", "account_id", "service", "resource_id", "usage_type", "cost_usd", "tags_json")
CC_COLUMNS = ("cost_center", "name", "business_line", "owner_team", "active")
ACCOUNT_COLUMNS = ("account_id", "account_name", "default_cost_center", "shared")


# ---------------------------------------------------------------- text helpers
def norm(value: str) -> str:
    return value.strip().casefold()


def clean(text) -> str:
    """Make any text safe to print on one line: control characters become visible escapes."""
    return "".join(c if c.isprintable() else repr(c)[1:-1] for c in str(text))


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so bill text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def fmt_usd(micros: int) -> str:
    cents = (abs(micros) + 5000) // 10000
    return "%s$%s.%02d" % ("-" if micros < 0 and cents else "", format(cents // 100, ","), cents % 100)


def plain_usd(micros: int) -> str:
    cents = (abs(micros) + 5000) // 10000
    return "%s%d.%02d" % ("-" if micros < 0 and cents else "", cents // 100, cents % 100)


def exact_usd(micros: int) -> str:
    """Dollars with every stored decimal and at least two, for the CSV files, so their totals reconcile to the bill."""
    whole, frac = divmod(abs(micros), MICROS)
    return "%s%d.%s" % ("-" if micros < 0 else "", whole, ("%06d" % frac).rstrip("0").ljust(2, "0"))


def pct(part: int, whole: int) -> str:
    return "n/a" if whole == 0 else "%.1f%%" % (100.0 * part / whole)


# ---------------------------------------------------------------- loading
def _read_csv(path: str, columns: tuple, label: str) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("%s: the file is empty" % label)
        missing = [c for c in columns if c not in reader.fieldnames]
        if missing:
            raise ValueError("%s: missing column(s) %s" % (label, ", ".join(missing)))
        rows = []
        for n, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError("%s row %d: more fields than the header" % (label, n))
            short = [c for c in columns if row.get(c) is None]
            if short:
                raise ValueError("%s row %d: truncated, no value for %s" % (label, n, short[0]))
            rows.append((n, row))
    return rows


def _parse_usd(text: str, where: str) -> int:
    try:
        d = Decimal(text.strip())
    except InvalidOperation:
        raise ValueError("%s: cost_usd %r is not a number" % (where, text)) from None
    if not d.is_finite():
        raise ValueError("%s: cost_usd %r is not a number" % (where, text))
    if d.as_tuple().exponent < -6:
        raise ValueError("%s: cost_usd %r has more than 6 decimal places" % (where, text))
    if abs(d) > 10 ** 9:
        raise ValueError("%s: cost_usd %r is out of range" % (where, text))
    return int(d * MICROS)


def _parse_tags(text: str, where: str) -> dict:
    try:
        tags = json.loads(text)
    except (ValueError, RecursionError):
        raise ValueError("%s: tags_json is not valid JSON (use {} for no tags)" % where) from None
    if not isinstance(tags, dict):
        raise ValueError("%s: tags_json must be a JSON object" % where)
    for k, v in tags.items():
        if v is not None and not isinstance(v, str):
            raise ValueError("%s: tag %r must be a string" % (where, k))
    return {k: v for k, v in tags.items() if v is not None}


def load_bill(path: str) -> list:
    rows = _read_csv(path, BILL_COLUMNS, "bill")
    if not rows:
        raise ValueError("bill: the file has a header and no billing lines")
    bill, seen = [], set()
    for n, row in rows:
        where = "bill row %d" % n
        if not row["line_id"].strip():
            raise ValueError("%s: line_id is empty" % where)
        if row["line_id"] in seen:
            raise ValueError("%s: line_id %r appears twice" % (where, row["line_id"]))
        seen.add(row["line_id"])
        try:
            if len(row["usage_date"]) != 10:
                raise ValueError
            day = datetime.date.fromisoformat(row["usage_date"])
        except ValueError:
            raise ValueError("%s: usage_date %r is not YYYY-MM-DD" % (where, row["usage_date"])) from None
        bill.append({"line_id": row["line_id"], "month": "%04d-%02d" % (day.year, day.month), "account_id": row["account_id"],
                     "service": row["service"], "resource_id": row["resource_id"], "usage_type": row["usage_type"],
                     "usd": _parse_usd(row["cost_usd"], where), "tags": _parse_tags(row["tags_json"], where)})
    months = sorted({b["month"] for b in bill})
    if len(months) > 1:
        raise ValueError("bill: lines from %d months (%s); run one billing month at a time" % (len(months), ", ".join(months)))
    if sum(b["usd"] for b in bill) <= 0:
        raise ValueError("bill: net spend is not positive, so there is nothing to apportion")
    return bill


def _string_list(value, where: str) -> list:
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError("%s must be a list of non-empty strings" % where)
    return value


def load_policy(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        p = json.load(fh)
    if not isinstance(p, dict):
        raise ValueError("policy: expected a JSON object")
    req = p.get("required_tags")
    if not isinstance(req, list) or not req:
        raise ValueError("policy: required_tags must be a non-empty list")
    specs, names = [], set()
    for i, s in enumerate(req):
        where = "policy: required_tags[%d]" % i
        if not isinstance(s, dict) or not isinstance(s.get("key"), str) or not s["key"].strip():
            raise ValueError("%s needs a key" % where)
        aliases = _string_list(s.get("aliases", []), where + ".aliases")
        values = s.get("values", "any")
        if values not in ("any", "registry"):
            values = _string_list(values, where + ".values")
        for name in [s["key"]] + aliases:
            if name in names:
                raise ValueError("%s: tag name %r is used twice in the policy" % (where, name))
            names.add(name)
        specs.append({"key": s["key"], "aliases": aliases, "values": values})
    if sum(1 for s in specs if s["values"] == "registry") != 1:
        raise ValueError("policy: exactly one required tag must have values \"registry\" (the cost-center tag)")
    shared = _string_list(p.get("shared_services", []), "policy: shared_services")
    limit = p.get("max_unallocated_pct", 10.0)
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not 0 <= limit <= 100:
        raise ValueError("policy: max_unallocated_pct must be a number from 0 to 100")
    return {"required_tags": specs, "shared_services": frozenset(shared), "max_unallocated_pct": float(limit)}


def load_cost_centers(path: str) -> dict:
    """{normalized id: record}, in file order."""
    registry = {}
    for n, row in _read_csv(path, CC_COLUMNS, "cost centers"):
        where = "cost centers row %d" % n
        if not row["cost_center"].strip():
            raise ValueError("%s: cost_center is empty" % where)
        if row["active"] not in ("true", "false"):
            raise ValueError("%s: active must be true or false" % where)
        key = norm(row["cost_center"])
        if key in registry:
            raise ValueError("%s: cost_center %r repeats an earlier id once case and spaces are ignored" % (where, row["cost_center"]))
        registry[key] = {"cost_center": row["cost_center"], "name": row["name"], "active": row["active"] == "true"}
    if not registry:
        raise ValueError("cost centers: the file has a header and no rows")
    return registry


def load_accounts(path: str, registry: dict) -> dict:
    accounts = {}
    for n, row in _read_csv(path, ACCOUNT_COLUMNS, "accounts"):
        where = "accounts row %d" % n
        if row["shared"] not in ("yes", "no"):
            raise ValueError("%s: shared must be yes or no" % where)
        default = row["default_cost_center"]
        if row["shared"] == "yes" and default.strip():
            raise ValueError("%s: a shared account cannot have a default cost center" % where)
        if default.strip():
            rec = registry.get(norm(default))
            if rec is None or not rec["active"]:
                raise ValueError("%s: default cost center %r is not an active cost center" % (where, default))
            default = rec["cost_center"]
        accounts[row["account_id"]] = {"shared": row["shared"] == "yes", "default": default.strip()}
    return accounts


# ---------------------------------------------------------------- tags
def alloc_spec(policy: dict) -> dict:
    return next(s for s in policy["required_tags"] if s["values"] == "registry")


def _present(tags: dict, keys: list) -> list:
    return [(k, tags[k]) for k in keys if isinstance(tags.get(k), str) and tags[k].strip()]


def resolve_direct(tags: dict, spec: dict, registry: dict, repair: bool = True) -> tuple:
    """(status, cost_center, repaired) for the cost-center tag of one line.
    status is ok, absent, unknown_cost_center, closed_cost_center or conflicting_tags.
    With repair False only the policy key counts and the value must equal the registry id exactly."""
    found = _present(tags, [spec["key"]] + (spec["aliases"] if repair else []))
    if not found:
        return ("absent", None, False)
    if len({norm(v) for _, v in found}) > 1:
        return ("conflicting_tags", None, False)
    rec = registry.get(norm(found[0][1]))
    if rec is None or (not repair and rec["cost_center"] != found[0][1]):
        return ("unknown_cost_center", None, False)
    if not rec["active"]:
        return ("closed_cost_center", None, False)
    repaired = any(k != spec["key"] or v != rec["cost_center"] for k, v in found)
    return ("ok", rec["cost_center"], repaired)


def _tag_ok(tags: dict, spec: dict, registry: dict, repair: bool) -> bool:
    if spec["values"] == "registry":
        return resolve_direct(tags, spec, registry, repair)[0] == "ok"
    for _, v in _present(tags, [spec["key"]] + (spec["aliases"] if repair else [])):
        if spec["values"] == "any":
            return True
        allowed = spec["values"]
        if (norm(v) in {norm(a) for a in allowed}) if repair else (v in allowed):
            return True
    return False


def line_compliance(line: dict, policy: dict, registry: dict, repair: bool):
    """True or False for a line that needs tags; None for a line that does not (zero cost or a shared service)."""
    if line["usd"] == 0 or line["service"] in policy["shared_services"]:
        return None
    return all(_tag_ok(line["tags"], s, registry, repair) for s in policy["required_tags"])


def compliance_summary(bill: list, policy: dict, registry: dict) -> dict:
    out = {"lines": 0, "exempt": 0, "strict": 0, "repaired": 0, "usd": 0, "strict_usd": 0, "repaired_usd": 0}
    for line in bill:
        strict = line_compliance(line, policy, registry, False)
        if strict is None:
            out["exempt"] += 1
            continue
        repaired = line_compliance(line, policy, registry, True)
        out["lines"] += 1
        out["usd"] += line["usd"]
        out["strict"] += strict
        out["repaired"] += repaired
        out["strict_usd"] += line["usd"] if strict else 0
        out["repaired_usd"] += line["usd"] if repaired else 0
    return out


# ---------------------------------------------------------------- allocation
def _resource_outcome(statuses: list) -> tuple:
    """What the tagged lines of one resource say, for its untagged lines: ('ok', cc) or ('fail', reason)."""
    ccs = {s[1] for s in statuses if s[0] == "ok"}
    fails = {s[0] for s in statuses if s[0] != "ok"}
    if not fails and len(ccs) == 1:
        return ("ok", next(iter(ccs)))
    if len(fails) == 1 and not ccs:
        return ("fail", next(iter(fails)))
    return ("fail", "resource_conflict")


def split_amount(amount: int, basis: list) -> list:
    """Split integer micros over [(cost_center, weight)] in proportion to weight; remainders go to the largest fractions."""
    total = sum(w for _, w in basis)
    sign = -1 if amount < 0 else 1
    a = abs(amount)
    parts = [(a * w) // total for _, w in basis]
    order = sorted(range(len(basis)), key=lambda i: (-((a * basis[i][1]) % total), basis[i][0]))
    for i in order[:a - sum(parts)]:
        parts[i] += 1
    return [(basis[i][0], sign * parts[i]) for i in range(len(basis)) if parts[i]]


def _result(line, cc, rule, reason=""):
    return {"line_id": line["line_id"], "cost_center": cc, "rule": rule, "reason": reason, "usd": line["usd"],
            "shares": [(cc, line["usd"])] if cc else []}


def allocate(bill: list, policy: dict, registry: dict, accounts: dict, extras: frozenset = EXTRAS, repair: bool = True) -> list:
    """One result per line, in bill order. extras picks which of inherit, shared_split and account_default run;
    repair False turns off alias keys and case or space matching, which is the exact-match report."""
    spec = alloc_spec(policy)
    direct = [resolve_direct(line["tags"], spec, registry, repair) for line in bill]
    seen = {}
    for line, d in zip(bill, direct):
        if line["resource_id"] and d[0] != "absent" and line["usd"] != 0:
            seen.setdefault(line["resource_id"], []).append(d)
    outcome = {rid: _resource_outcome(ds) for rid, ds in seen.items()}
    results, pending = [], []
    for idx, (line, d) in enumerate(zip(bill, direct)):
        status, cc, repaired = d
        acct = accounts.get(line["account_id"])
        if line["usd"] == 0:
            results.append(_result(line, "", "zero_cost"))
        elif status == "ok":
            results.append(_result(line, cc, "tag_repaired" if repaired else "tag"))
        elif status != "absent":
            results.append(_result(line, "", "unallocated", status))
        elif "shared_split" in extras and line["service"] in policy["shared_services"]:
            results.append(None)
            pending.append(idx)
        elif "inherit" in extras and line["resource_id"] in outcome:
            kind, value = outcome[line["resource_id"]]
            results.append(_result(line, value, "inherit") if kind == "ok" else _result(line, "", "unallocated", value))
        elif "account_default" in extras and acct and not acct["shared"] and acct["default"]:
            results.append(_result(line, acct["default"], "account_default"))
        else:
            results.append(_result(line, "", "unallocated", "no_owner_found"))
    basis = {}
    for r in results:
        if r is not None and r["cost_center"]:
            basis[r["cost_center"]] = basis.get(r["cost_center"], 0) + r["usd"]
    weights = sorted((cc, w) for cc, w in basis.items() if w > 0)
    for idx in pending:
        line = bill[idx]
        if not weights:
            results[idx] = _result(line, "", "unallocated", "no_basis_for_split")
            continue
        res = _result(line, "", "shared_split")
        res["shares"] = split_amount(line["usd"], weights)
        results[idx] = res
    return results


# ---------------------------------------------------------------- summary
def summarize(bill: list, results: list) -> dict:
    by_rule = {r: [0, 0] for r in RULE_ORDER}
    by_reason, chargeback, unowned = {}, {}, {}
    for line, r in zip(bill, results):
        by_rule[r["rule"]][0] += 1
        by_rule[r["rule"]][1] += r["usd"]
        if r["rule"] == "unallocated":
            slot = by_reason.setdefault(r["reason"], [0, 0])
            slot[0] += 1
            slot[1] += r["usd"]
            if r["usd"]:
                key = (line["resource_id"] or "(no resource id)", r["reason"])
                unowned[key] = unowned.get(key, 0) + r["usd"]
        bucket = {"tag": "direct", "tag_repaired": "direct", "inherit": "inherit", "account_default": "account_default",
                  "shared_split": "shared"}.get(r["rule"])
        for cc, usd in r["shares"]:
            row = chargeback.setdefault(cc, {"direct": 0, "inherit": 0, "account_default": 0, "shared": 0})
            row[bucket] += usd
    total = sum(line["usd"] for line in bill)
    unalloc = by_rule["unallocated"][1]
    return {"total": total, "by_rule": by_rule, "by_reason": by_reason, "chargeback": chargeback, "unallocated": unalloc,
            "allocated": total - unalloc, "top_unallocated": sorted(unowned.items(), key=lambda kv: (-kv[1], kv[0]))[:5]}


# ---------------------------------------------------------------- output
def render_text(label: str, bill: list, summ: dict, comp: dict, registry: dict, unmapped: list, limit: float) -> str:
    total = summ["total"]
    L = ["bill: %s   %d lines   period %s   net spend %s" % (clean(label), len(bill), bill[0]["month"], fmt_usd(total)),
         "tag compliance: %d of %d lines that need tags carry every required tag (%d exempt: zero cost or shared service)"
         % (comp["strict"], comp["lines"], comp["exempt"]),
         "  after alias and format repair: %d of %d; by dollars %s strict, %s repaired"
         % (comp["repaired"], comp["lines"], pct(comp["strict_usd"], comp["usd"]), pct(comp["repaired_usd"], comp["usd"])),
         "%-22s%7s%16s%9s" % ("allocation by rule", "lines", "usd", "share")]
    for rule in RULE_ORDER:
        n, usd = summ["by_rule"][rule]
        L.append("  %-20s%7d%16s%9s" % (rule, n, fmt_usd(usd), pct(usd, total)))
    if summ["allocated"] == 0:
        L.append("note: no line matched an allocation rule; check the tag keys in the policy against the tag keys in the bill")
    if summ["by_reason"]:
        L.append("%-22s%7s%16s" % ("unallocated by reason", "lines", "usd"))
        for reason, (n, usd) in sorted(summ["by_reason"].items(), key=lambda kv: (-kv[1][1], kv[0])):
            L.append("  %-20s%7d%16s" % (reason, n, fmt_usd(usd)))
        L.append("largest unallocated resources")
        for (rid, reason), usd in summ["top_unallocated"]:
            L.append("  %-24s%14s  %s" % (clean(rid), fmt_usd(usd), reason))
    L.append("%-12s%12s%11s%14s%11s%15s" % ("chargeback", "direct", "inherited", "acct default", "shared", "total"))
    for key, rec in registry.items():
        row = summ["chargeback"].get(rec["cost_center"])
        if row:
            L.append("  %-10s%12s%11s%14s%11s%15s" % (clean(rec["cost_center"]), fmt_usd(row["direct"]), fmt_usd(row["inherit"]),
                                                    fmt_usd(row["account_default"]), fmt_usd(row["shared"]), fmt_usd(sum(row.values()))))
    if unmapped:
        L.append("note: %d account id(s) in the bill are not in the account map, so account_default cannot apply to them: %s"
                 % (len(unmapped), ", ".join(clean(a) for a in unmapped[:3]) + (", ..." if len(unmapped) > 3 else "")))
    over = 100.0 * summ["unallocated"] / total > limit
    L.append("result: unallocated %s of net spend, limit %.1f%%: %s" % (pct(summ["unallocated"], total), limit, "OVER" if over else "within"))
    return "\n".join(L)


def render_github(summ: dict, limit: float) -> str:
    L = []
    for reason, (n, usd) in sorted(summ["by_reason"].items(), key=lambda kv: (-kv[1][1], kv[0])):
        L.append("::warning title=tag-chargeback %s::%s" % (reason, escape_annotation("%s on %d lines" % (fmt_usd(usd), n))))
    for (rid, reason), usd in summ["top_unallocated"]:
        L.append("::warning title=tag-chargeback resource::" + escape_annotation("%s: %s unallocated (%s)" % (rid, fmt_usd(usd), reason)))
    over = 100.0 * summ["unallocated"] / summ["total"] > limit
    L.append("::%s title=tag-chargeback::unallocated %s of net spend, limit %.1f%%"
             % ("error" if over else "notice", pct(summ["unallocated"], summ["total"]), limit))
    return "\n".join(L)


def write_chargeback(path: str, summ: dict, registry: dict) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["cost_center", "name", "direct", "inherit", "account_default", "shared", "total"])
        for rec in registry.values():
            row = summ["chargeback"].get(rec["cost_center"], {"direct": 0, "inherit": 0, "account_default": 0, "shared": 0})
            w.writerow([rec["cost_center"], rec["name"]] + [exact_usd(row[k]) for k in ("direct", "inherit", "account_default", "shared")]
                       + [exact_usd(sum(row.values()))])
        w.writerow(["UNALLOCATED", "", "", "", "", "", exact_usd(summ["unallocated"])])


def write_lines(path: str, results: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["line_id", "cost_center", "rule", "reason", "usd"])
        for r in results:
            for cc, usd in (r["shares"] or [("", r["usd"])]):
                w.writerow([r["line_id"], cc, r["rule"], r["reason"], exact_usd(usd)])


# ---------------------------------------------------------------- command line
def run_report(bill_path, policy_path, cc_path, accounts_path, limit, fmt, enforce, chargeback_csv=None, lines_csv=None) -> int:
    try:
        registry = load_cost_centers(cc_path)
        policy = load_policy(policy_path)
        accounts = load_accounts(accounts_path, registry)
        bill = load_bill(bill_path)
        if limit is None:
            limit = policy["max_unallocated_pct"]
        results = allocate(bill, policy, registry, accounts)
        summ = summarize(bill, results)
        if chargeback_csv:
            write_chargeback(chargeback_csv, summ, registry)
        if lines_csv:
            write_lines(lines_csv, results)
    except (OSError, ValueError, csv.Error, RecursionError) as e:
        print("input error: " + clean(e), file=sys.stderr)
        return 2
    unmapped = sorted({b["account_id"] for b in bill} - set(accounts))
    if fmt == "github":
        print(render_github(summ, limit))
    else:
        print(render_text(os.path.basename(bill_path), bill, summ, compliance_summary(bill, policy, registry), registry, unmapped, limit))
    over = 100.0 * summ["unallocated"] / summ["total"] > limit
    return 1 if (enforce and over) else 0


def _pct_arg(text: str) -> float:
    try:
        v = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not a number" % text) from None
    if not 0 <= v <= 100:
        raise argparse.ArgumentTypeError("%r is not between 0 and 100" % text)
    return v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tag_chargeback")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_bill.csv)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("report", help="allocate a billing export")
    r.add_argument("bill", help="the billing export CSV for one month")
    r.add_argument("--policy", required=True, help="tag policy JSON: required tags, aliases, shared services, unallocated limit")
    r.add_argument("--cost-centers", required=True, help="cost-center registry CSV")
    r.add_argument("--accounts", required=True, help="account map CSV: which cost center a dedicated account defaults to")
    r.add_argument("--max-unallocated-pct", type=_pct_arg, help="exit 1 above this share of net spend (default: the policy value)")
    r.add_argument("--format", choices=["text", "github"], default="text", help="text, or github for workflow annotations")
    r.add_argument("--chargeback-csv", help="write the per-cost-center totals here")
    r.add_argument("--lines-csv", help="write the per-line allocation here")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_report(os.path.join(d, "example_bill.csv"), os.path.join(d, "policy.json"), os.path.join(d, "cost_centers.csv"),
                          os.path.join(d, "accounts.csv"), None, "text", False)
    if a.cmd == "report":
        return run_report(a.bill, a.policy, a.cost_centers, a.accounts, a.max_unallocated_pct, a.format, True,
                          a.chargeback_csv, a.lines_csv)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
