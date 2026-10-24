"""payment_mandate_check: check an agent's payment instructions against the customer's mandate before
anything is released. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 payment_mandate_check.py --demo
    python3 payment_mandate_check.py check MANDATES.json INSTRUCTIONS.csv [--audit AUDIT.jsonl]
                                           [--fail-on reject|hold|never] [--show exceptions|all]
    python3 payment_mandate_check.py verify AUDIT.jsonl [--head HEX]

Exit status: 0 when no instruction reaches --fail-on (default: REJECT), 1 when one does or an audit
chain is broken, 2 for bad or malformed input. There is no model in this file: every decision is a
plain rule over the mandate and the instruction.

Decisions: RELEASE (inside the mandate), HOLD (inside the mandate but a person should look) and
REJECT (outside it). Instructions are processed in the order the gateway received them; the daily
total and the duplicate checks count only instructions that were released.

Mandate file: a JSON list of objects with mandate_id, customer_id, agent_id, currency,
per_payment_limit, daily_limit, human_confirm_above (or null), valid_from, expires_at, revoked_at (or
null), rails, categories and payees (each with payee_id and account_ref, and optionally name).
Instruction file: CSV with submission_id (assigned by the gateway, unique), instruction_id (the
agent's idempotency key), mandate_id, agent_id, received_at (stamped by the gateway), payee_id,
payee_account_ref, amount, currency, rail, category; payee_name and memo are accepted and ignored.
Times are YYYY-MM-DDTHH:MM:SSZ. Amounts are plain decimals with at most two places.
"""
from __future__ import annotations

import io
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal

RULE_SET = "pmc-1"
NEAR_DUPLICATE_SECONDS = 600
GENESIS = "0" * 64
RELEASE, HOLD, REJECT = "RELEASE", "HOLD", "REJECT"
DECISION_RANK = {RELEASE: 0, HOLD: 1, REJECT: 2}
GROUPS = ("identity", "window", "payee", "terms", "amount", "ledger")
ALL_GROUPS = frozenset(GROUPS)

# code: class. The detail text is built where the reason is raised.
REASONS = {
    "UNKNOWN_MANDATE": REJECT,
    "AGENT_NOT_DELEGATE": REJECT,
    "NOT_YET_VALID": REJECT,
    "EXPIRED": REJECT,
    "REVOKED": REJECT,
    "PAYEE_NOT_LISTED": REJECT,
    "PAYEE_ACCOUNT_CHANGED": HOLD,
    "CURRENCY_MISMATCH": REJECT,
    "RAIL_NOT_ALLOWED": REJECT,
    "CATEGORY_NOT_ALLOWED": REJECT,
    "BAD_AMOUNT": REJECT,
    "OVER_PER_PAYMENT_LIMIT": REJECT,
    "OVER_CONFIRM_THRESHOLD": HOLD,
    "OVER_DAILY_LIMIT": REJECT,
    "DUPLICATE_ID": REJECT,
    "NEAR_DUPLICATE": HOLD,
}

_TS_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_AMOUNT_RE = re.compile(r"[0-9]{1,12}(?:\.[0-9]{1,2})?")
_CCY_RE = re.compile(r"[A-Z]{3}")
INSTRUCTION_COLUMNS = ("submission_id", "instruction_id", "mandate_id", "agent_id", "received_at", "payee_id",
                       "payee_account_ref", "amount", "currency", "rail", "category")


# ---------------------------------------------------------------- text safety
def safe(text, limit: int = 120) -> str:
    """Make untrusted text one printable line: control characters and line separators become escapes."""
    out = []
    for ch in str(text):
        o = ord(ch)
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 32 or 127 <= o < 160 or o in (0x2028, 0x2029):
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    s = "".join(out)
    return s if len(s) <= limit else s[:limit - 3] + "..."


# ---------------------------------------------------------------- parsing
def parse_ts(s) -> datetime:
    """Strict UTC timestamp, YYYY-MM-DDTHH:MM:SSZ. Raises ValueError for anything else."""
    if not isinstance(s, str) or not _TS_RE.fullmatch(s):
        raise ValueError(f"time {safe(s, 40)!r} is not YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def parse_amount(s):
    """A plain decimal with at most two places, or None. No sign, no exponent, no separators."""
    if not isinstance(s, str) or not _AMOUNT_RE.fullmatch(s):
        return None
    return Decimal(s)


def _money(v, label: str) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        raise ValueError(f"{label} must be a plain decimal amount")
    d = parse_amount(str(v))
    if d is None or d <= 0:
        raise ValueError(f"{label} must be a positive amount with at most two decimal places")
    return d


def _text(obj: dict, key: str, label: str) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v:
        raise ValueError(f"{label}: {key} must be a non-empty string")
    return v


def _text_list(obj: dict, key: str, label: str) -> frozenset:
    v = obj.get(key)
    if not isinstance(v, list) or not v or not all(isinstance(x, str) and x for x in v):
        raise ValueError(f"{label}: {key} must be a non-empty list of strings")
    return frozenset(v)


def parse_mandates(obj, source: str = "mandates") -> dict:
    """Validate a decoded mandate list and return {mandate_id: normalized mandate}. Raises ValueError."""
    if not isinstance(obj, list) or not obj:
        raise ValueError(f"{source}: expected a non-empty JSON list of mandates")
    out = {}
    for i, m in enumerate(obj):
        label = f"{source}: mandate {i + 1}"
        if not isinstance(m, dict):
            raise ValueError(f"{label} must be an object")
        mid = _text(m, "mandate_id", label)
        if mid in out:
            raise ValueError(f"{label}: duplicate mandate_id {safe(mid, 40)!r}")
        ccy = _text(m, "currency", label)
        if not _CCY_RE.fullmatch(ccy):
            raise ValueError(f"{label}: currency must be three capital letters")
        limit = _money(m.get("per_payment_limit"), f"{label}: per_payment_limit")
        daily = _money(m.get("daily_limit"), f"{label}: daily_limit")
        confirm = m.get("human_confirm_above")
        confirm = None if confirm is None else _money(confirm, f"{label}: human_confirm_above")
        if daily < limit:
            raise ValueError(f"{label}: daily_limit is below per_payment_limit")
        if confirm is not None and confirm > limit:
            raise ValueError(f"{label}: human_confirm_above is above per_payment_limit")
        valid_from = parse_ts(m.get("valid_from"))
        expires_at = parse_ts(m.get("expires_at"))
        if expires_at < valid_from:
            raise ValueError(f"{label}: expires_at is before valid_from")
        revoked = m.get("revoked_at")
        payees = {}
        plist = m.get("payees")
        if not isinstance(plist, list) or not plist:
            raise ValueError(f"{label}: payees must be a non-empty list")
        for p in plist:
            if not isinstance(p, dict):
                raise ValueError(f"{label}: each payee must be an object")
            pid = _text(p, "payee_id", label)
            if pid in payees:
                raise ValueError(f"{label}: duplicate payee_id {safe(pid, 40)!r}")
            payees[pid] = _text(p, "account_ref", label)
        out[mid] = {"mandate_id": mid, "customer_id": _text(m, "customer_id", label), "agent_id": _text(m, "agent_id", label),
                    "currency": ccy, "per_payment_limit": limit, "daily_limit": daily, "human_confirm_above": confirm,
                    "valid_from": valid_from, "expires_at": expires_at,
                    "revoked_at": None if revoked is None else parse_ts(revoked),
                    "rails": _text_list(m, "rails", label), "categories": _text_list(m, "categories", label),
                    "payees": payees}
    return out


def load_mandates(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return parse_mandates(json.load(fh), os.path.basename(path))


def _open_csv(path, name):
    """Open a CSV as text. A NUL byte is refused here because csv.reader refused it only before Python 3.11."""
    with open(path, newline="", encoding="utf-8-sig") as fh:
        text = fh.read()
    if "\x00" in text:
        raise ValueError(f"{name}: contains a NUL byte")
    return io.StringIO(text, newline="")


def load_instructions(path: str) -> list:
    """Read the instruction CSV. Raises ValueError (or OSError) on a file that cannot be read as one."""
    name = os.path.basename(path)
    rows, seen = [], set()
    with _open_csv(path, name) as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in INSTRUCTION_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{name}: missing columns {', '.join(missing)}")
        for r in reader:
            line = reader.line_num
            if None in r:
                raise ValueError(f"{name}: line {line} has more fields than the header")
            if any(v is None for v in r.values()):
                raise ValueError(f"{name}: line {line} has fewer fields than the header (truncated file?)")
            if not r["submission_id"] or r["submission_id"] in seen:
                raise ValueError(f"{name}: line {line}: submission_id must be present and unique")
            seen.add(r["submission_id"])
            try:
                parse_ts(r["received_at"])
            except ValueError as e:
                raise ValueError(f"{name}: line {line}: {e}") from None
            rows.append(dict(r))
    if not rows:
        raise ValueError(f"{name}: no instruction rows")
    return rows


# ---------------------------------------------------------------- the check
def _row_digest(row: dict) -> str:
    blob = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _reason(code: str, detail: str) -> dict:
    return {"code": code, "class": REASONS[code], "detail": detail}


def check_batch(mandates: dict, rows: list, enabled=ALL_GROUPS, near_duplicate_seconds: int = NEAR_DUPLICATE_SECONDS) -> list:
    """Decide every instruction. `enabled` names the rule groups to run (a subset is for comparison only).

    Returns one dict per instruction, in processing order (received_at, then file order).
    """
    times = [parse_ts(r["received_at"]) for r in rows]
    order = sorted(range(len(rows)), key=lambda i: (times[i], i))
    day_total, last_release, seen_ids = {}, {}, set()
    results = []
    for i in order:
        row, t = rows[i], times[i]
        mid, pid, ccy = row["mandate_id"], row["payee_id"], row["currency"]
        m = mandates.get(mid)
        amt = parse_amount(row["amount"])
        bad_amount = amt is None or amt == 0
        reasons = []
        if m is None:
            if "identity" in enabled:
                reasons.append(_reason("UNKNOWN_MANDATE", "no mandate with this id"))
        else:
            if "identity" in enabled and row["agent_id"] != m["agent_id"]:
                reasons.append(_reason("AGENT_NOT_DELEGATE", f"the mandate was issued to {m['agent_id']}"))
            if "window" in enabled:
                if t < m["valid_from"]:
                    reasons.append(_reason("NOT_YET_VALID", f"valid from {m['valid_from']:%Y-%m-%dT%H:%M:%SZ}"))
                if t > m["expires_at"]:
                    reasons.append(_reason("EXPIRED", f"expired at {m['expires_at']:%Y-%m-%dT%H:%M:%SZ}"))
                if m["revoked_at"] is not None and t >= m["revoked_at"]:
                    reasons.append(_reason("REVOKED", f"revoked at {m['revoked_at']:%Y-%m-%dT%H:%M:%SZ}"))
            if "payee" in enabled:
                pinned = m["payees"].get(pid)
                if pinned is None:
                    reasons.append(_reason("PAYEE_NOT_LISTED", "payee_id is not on the mandate"))
                elif row["payee_account_ref"] != pinned:
                    reasons.append(_reason("PAYEE_ACCOUNT_CHANGED", "the account differs from the one the mandate pins"))
            if "terms" in enabled:
                if ccy != m["currency"]:
                    reasons.append(_reason("CURRENCY_MISMATCH", f"the mandate is in {m['currency']}"))
                if row["rail"] not in m["rails"]:
                    reasons.append(_reason("RAIL_NOT_ALLOWED", "the rail is not on the mandate"))
                if row["category"] not in m["categories"]:
                    reasons.append(_reason("CATEGORY_NOT_ALLOWED", "the category is not on the mandate"))
            if "amount" in enabled:
                if bad_amount:
                    reasons.append(_reason("BAD_AMOUNT", "not a positive decimal with at most two places"))
                elif amt > m["per_payment_limit"]:
                    reasons.append(_reason("OVER_PER_PAYMENT_LIMIT", f"limit is {m['per_payment_limit']}"))
                elif m["human_confirm_above"] is not None and amt > m["human_confirm_above"]:
                    reasons.append(_reason("OVER_CONFIRM_THRESHOLD", f"a person confirms above {m['human_confirm_above']}"))
        counted = m is not None and not bad_amount and ccy == m["currency"]
        if "ledger" in enabled:
            if (mid, row["instruction_id"]) in seen_ids:
                reasons.append(_reason("DUPLICATE_ID", "this instruction_id was already submitted on this mandate"))
            if counted:
                so_far = day_total.get((mid, t.date()), Decimal(0))
                if so_far + amt > m["daily_limit"]:
                    reasons.append(_reason("OVER_DAILY_LIMIT", f"{so_far} already released today, limit {m['daily_limit']}"))
                prior = last_release.get((mid, pid, amt, ccy))
                if prior is not None and (t - prior).total_seconds() <= near_duplicate_seconds:
                    reasons.append(_reason("NEAR_DUPLICATE", f"same payee and amount released {int((t - prior).total_seconds())} s earlier"))
        seen_ids.add((mid, row["instruction_id"]))
        classes = {r["class"] for r in reasons}
        decision = REJECT if REJECT in classes else HOLD if HOLD in classes else RELEASE
        if decision == RELEASE and counted:
            day_total[(mid, t.date())] = day_total.get((mid, t.date()), Decimal(0)) + amt
            last_release[(mid, pid, amt, ccy)] = t
        results.append({"row": i + 1, "submission_id": row["submission_id"], "instruction_id": row["instruction_id"],
                        "mandate_id": mid, "agent_id": row["agent_id"], "payee_id": pid, "amount": row["amount"],
                        "currency": ccy, "received_at": row["received_at"], "decision": decision, "reasons": reasons,
                        "input_sha256": _row_digest(row)})
    return results


# ---------------------------------------------------------------- audit record
def _chain_hash(prev: str, core: dict) -> str:
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()


def audit_records(results: list) -> list:
    """One hash-chained record per decision. Each record carries the hash of the one before it."""
    prev, records = GENESIS, []
    for seq, r in enumerate(results, start=1):
        core = {"seq": seq, "submission_id": r["submission_id"], "instruction_id": r["instruction_id"],
                "mandate_id": r["mandate_id"], "agent_id": r["agent_id"], "payee_id": r["payee_id"],
                "amount": r["amount"], "currency": r["currency"], "received_at": r["received_at"],
                "input_sha256": r["input_sha256"], "decision": r["decision"],
                "reasons": [x["code"] for x in r["reasons"]], "rule_set": RULE_SET, "prev": prev}
        h = _chain_hash(prev, core)
        records.append(dict(core, hash=h))
        prev = h
    return records


def verify_audit(records: list, head=None):
    """Returns (ok, message). Checks sequence, links and hashes; with `head`, also the last hash."""
    prev = GENESIS
    for n, rec in enumerate(records, start=1):
        if not isinstance(rec, dict) or not all(k in rec for k in ("seq", "prev", "hash")):
            raise ValueError(f"record {n} is not an audit record")
        core = {k: v for k, v in rec.items() if k != "hash"}
        if rec["seq"] != n:
            return False, f"record {n}: sequence number is {safe(rec['seq'], 20)} (a record was removed, added or moved)"
        if rec["prev"] != prev:
            return False, f"record {n}: does not follow the record before it"
        if _chain_hash(prev, core) != rec["hash"]:
            return False, f"record {n}: contents do not match the hash (edited after it was written)"
        prev = rec["hash"]
    if head is not None and prev != head:
        return False, f"the last hash {prev[:12]} is not the head you gave (records may have been cut off the end)"
    return True, f"{len(records)} records, chain ok, head {prev[:12]}"


def read_audit(path: str) -> list:
    records = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                raise ValueError(f"{os.path.basename(path)}: line {n} is not JSON") from None
    if not records:
        raise ValueError(f"{os.path.basename(path)}: no audit records")
    return records


# ---------------------------------------------------------------- command line
def render(results: list, show: str = "exceptions") -> str:
    lines = []
    for r in results:
        if show == "exceptions" and r["decision"] == RELEASE:
            continue
        why = "; ".join(f"{x['code']}: {x['detail']}" for x in r["reasons"]) or "inside the mandate"
        lines.append(safe(f"  {r['submission_id']} {r['decision']:<7} {r['amount']:>9} {r['currency']} to {r['payee_id']} "
                          f"on {r['mandate_id']}  {why}", 240))
    counts = Counter(r["decision"] for r in results)
    lines.append(f"{len(results)} instructions: {counts[RELEASE]} RELEASE, {counts[HOLD]} HOLD, {counts[REJECT]} REJECT")
    return "\n".join(lines)


def run_check(mandates_path, instructions_path, audit_path, fail_on: str, show: str) -> int:
    try:
        mandates = load_mandates(mandates_path)
        rows = load_instructions(instructions_path)
        results = check_batch(mandates, rows)
        records = audit_records(results)
        if audit_path:
            with open(audit_path, "w", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")
    except (OSError, ValueError, RecursionError, csv.Error) as e:
        print(f"input error: {safe(e, 300)}", file=sys.stderr)
        return 2
    print(render(results, show))
    if all(r["mandate_id"] not in mandates for r in results):
        print("note: no instruction names a mandate in the mandate file, so every one was rejected; check the mandate_id column")
    print(f"audit: {verify_audit(records)[1]}" + (f" (written to {safe(audit_path, 80)})" if audit_path else ""))
    worst = max(DECISION_RANK[r["decision"]] for r in results)
    threshold = {"reject": DECISION_RANK[REJECT], "hold": DECISION_RANK[HOLD]}.get(fail_on)
    return 1 if threshold is not None and worst >= threshold else 0


def run_verify(path: str, head) -> int:
    try:
        ok, msg = verify_audit(read_audit(path), head)
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {safe(e, 300)}", file=sys.stderr)
        return 2
    print(f"audit: {msg}")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="payment_mandate_check")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="decide each instruction against its mandate")
    c.add_argument("mandates")
    c.add_argument("instructions")
    c.add_argument("--audit", help="write the hash-chained audit record to this JSONL file")
    c.add_argument("--fail-on", choices=["reject", "hold", "never"], default="reject")
    c.add_argument("--show", choices=["exceptions", "all"], default="exceptions")
    v = sub.add_parser("verify", help="check an audit file's hash chain")
    v.add_argument("audit")
    v.add_argument("--head", help="the head hash you recorded earlier (catches records cut off the end)")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_mandates.json"), os.path.join(d, "example_instructions.csv"), None, "never", "all")
    if a.cmd == "check":
        return run_check(a.mandates, a.instructions, a.audit, a.fail_on, a.show)
    if a.cmd == "verify":
        return run_verify(a.audit, a.head)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
