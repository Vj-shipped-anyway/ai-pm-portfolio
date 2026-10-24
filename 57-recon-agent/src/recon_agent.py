"""recon_agent: match a bank-statement ledger (A) to a cash-book ledger (B) and show the evidence for every
match. Standard library only. Python 3.9 or newer. There is no model in this file: the proposer is a
ladder of five plain rules, the check is a function that re-runs a rule on the exact lines a match cites,
and the gate is a table of which matches may post on their own.

Command line (from src/):
    python3 recon_agent.py --demo
    python3 recon_agent.py reconcile LEDGER_A.csv LEDGER_B.csv [--approvals APPROVALS.csv] [--out DIR] [--fail-on-open]
    python3 recon_agent.py verify LEDGER_A.csv LEDGER_B.csv MATCHES.csv

Exit status: 0 when the command ran (reconcile) or every posted match re-checks (verify), 1 when verify finds a
problem or --fail-on-open finds an open item, 2 for bad or malformed input.

Ledger A columns: a_id, value_date, amount, currency, counterparty, narrative, customer_ref
Ledger B columns: b_id, posting_date, amount, currency, counterparty, reference, batch_id, memo
Amounts are signed from the cash account's side (money in is positive) with at most two decimals.
Approvals columns: key, decision (approve or reject), approver, note (optional). The key is printed with every
proposal as rule:A ids:B ids:amount in cents.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

AGENT_ID = "recon-agent"
RULES = ("ref_exact", "ref_fee", "batch_sum", "ref_near", "name_amount")
# Which rules may post on their own. Every other match waits for a person. Assumption, see the README.
GATE_POLICY = {"ref_exact": "auto", "ref_fee": "approval", "batch_sum": "approval", "ref_near": "approval", "name_amount": "approval"}
GATE_WHY = {"ref_fee": "the amounts differ by a scheduled fee", "batch_sum": "one bank line against several book lines",
            "ref_near": "the references differ by one edit", "name_amount": "no reference on one side"}
LEGAL_FORMS = frozenset({"ltd", "limited", "inc", "incorporated", "llc", "co", "company", "corp", "corporation", "plc"})
# The generator abbreviates four words. This table knows three of them on purpose.
ABBREVIATIONS = {"svcs": "services", "intl": "international", "dist": "distribution"}
SIDE_COLUMNS = {"A": ("a_id", "value_date", "amount", "currency", "counterparty", "narrative", "customer_ref"),
                "B": ("b_id", "posting_date", "amount", "currency", "counterparty", "reference", "batch_id", "memo")}
POSTED = ("posted_auto", "posted_approved")


@dataclass(frozen=True)
class Params:
    window: int = 3                     # days between the two dates; an assumption
    fees: tuple = (150, 250, 1500)      # fees the bank may net from a credit, in cents; an assumption
    limit_cents: int = 1000000          # a match above this amount needs a person; an assumption
    max_group: int = 6                  # most book lines in one batch match


DEFAULT_PARAMS = Params()


class InputError(ValueError):
    """Bad or malformed input: the command line prints one line and exits 2."""


# ---------------------------------------------------------------- text helpers
def money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def clean(text: str, limit: int = 48) -> str:
    """Make untrusted text safe to print: control characters become visible escapes, long text is cut."""
    s = "".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in text)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def csv_safe(text: str) -> str:
    """A cell a spreadsheet would read as a formula gets a leading apostrophe."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def norm_ref(text: str) -> str:
    """Upper case, letters and digits only, zeros after a letter prefix dropped. Empty when there is no digit."""
    k = re.sub(r"(?<=[A-Z])0+(?=[0-9])", "", re.sub(r"[^A-Z0-9]", "", text.upper()))
    return k if re.search(r"[0-9]", k) else ""


def norm_name(text: str) -> str:
    t = re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("&", " and "))
    return " ".join(sorted(w for w in (ABBREVIATIONS.get(w, w) for w in t.split()) if w not in LEGAL_FORMS))


def one_edit_apart(x: str, y: str) -> bool:
    """True when the strings differ by one substitution, one insertion or deletion, or one swap of neighbours."""
    if x == y or abs(len(x) - len(y)) > 1:
        return False
    if len(x) == len(y):
        diff = [i for i in range(len(x)) if x[i] != y[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and x[diff[0]] == y[diff[1]] and x[diff[1]] == y[diff[0]]
    s, longer = (x, y) if len(x) < len(y) else (y, x)
    i = 0
    while i < len(s) and s[i] == longer[i]:
        i += 1
    return s[i:] == longer[i + 1:]


# ---------------------------------------------------------------- loading
def _row(side: str, raw: dict, n: int, label: str) -> dict:
    cols = SIDE_COLUMNS[side]
    if None in raw:
        raise InputError(f"{label}, row {n}: more fields than the header has")
    vals = {}
    for c in cols:
        if raw.get(c) is None:
            raise InputError(f"{label}, row {n}: field {c!r} is missing (truncated line?)")
        vals[c] = raw[c].strip()
    ident, day, amount, ccy = vals[cols[0]], vals[cols[1]], vals["amount"], vals["currency"]
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", ident):
        raise InputError(f"{label}, row {n}: {cols[0]} must be 1 to 40 letters, digits, dots, hyphens or underscores")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise InputError(f"{label}, row {n}: {cols[1]} must look like 2026-03-31")
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise InputError(f"{label}, row {n}: {cols[1]} {clean(day)!r} is not a calendar date") from None
    if not re.fullmatch(r"-?\d{1,12}(\.\d{1,2})?", amount):
        raise InputError(f"{label}, row {n}: amount {clean(amount)!r} must be a number with at most two decimals")
    if not re.fullmatch(r"[A-Z]{3}", ccy):
        raise InputError(f"{label}, row {n}: currency must be three capital letters")
    ref_raw = vals["customer_ref"] if side == "A" else vals["reference"]
    batch_raw = "" if side == "A" else vals["batch_id"]
    row = {"side": side, "id": ident, "date": d, "cents": int(Decimal(amount) * 100), "currency": ccy,
           "name": vals["counterparty"], "text": vals["narrative"] if side == "A" else vals["memo"],
           "ref_raw": ref_raw, "ref_key": norm_ref(ref_raw), "batch_key": norm_ref(batch_raw),
           "name_key": norm_name(vals["counterparty"]), "line": n}
    row["sig"] = (d, row["cents"], ccy, row["ref_key"], row["name_key"], row["batch_key"])
    return row


def load_ledger(path: str, side: str) -> list:
    label = f"ledger {side} ({os.path.basename(path)})"
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{label}: the file is empty")
            missing = [c for c in SIDE_COLUMNS[side] if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
            raw = list(reader)
    except OSError as e:
        raise InputError(f"{label}: cannot read the file ({e.strerror or e})")
    except (csv.Error, UnicodeDecodeError) as e:
        raise InputError(f"{label}: not a UTF-8 CSV file ({e})")
    if not raw:
        raise InputError(f"{label}: the file has a header and no rows")
    rows, seen = [], set()
    for n, r in enumerate(raw, start=2):
        row = _row(side, r, n, label)
        if row["id"] in seen:
            raise InputError(f"{label}, row {n}: id {row['id']!r} appears twice")
        seen.add(row["id"])
        rows.append(row)
    return rows


def load_approvals(path: str) -> list:
    label = f"approvals ({os.path.basename(path)})"
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{label}: the file is empty")
            missing = [c for c in ("key", "decision", "approver") if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
            raw = list(reader)
    except OSError as e:
        raise InputError(f"{label}: cannot read the file ({e.strerror or e})")
    except (csv.Error, UnicodeDecodeError) as e:
        raise InputError(f"{label}: not a UTF-8 CSV file ({e})")
    out = []
    for n, r in enumerate(raw, start=2):
        if None in r or any(r.get(c) is None for c in ("key", "decision", "approver")):
            raise InputError(f"{label}, row {n}: a field is missing or there are too many")
        decision = r["decision"].strip().lower()
        if decision not in ("approve", "reject"):
            raise InputError(f"{label}, row {n}: decision must be approve or reject")
        if not r["approver"].strip() or not r["key"].strip():
            raise InputError(f"{label}, row {n}: key and approver must not be empty")
        out.append({"key": r["key"].strip(), "decision": decision, "approver": r["approver"].strip(), "note": (r.get("note") or "").strip()})
    return out


# ---------------------------------------------------------------- the rules
def names_agree(a: dict, bs: list) -> bool:
    return bool(a["name_key"]) and all(b["name_key"] == a["name_key"] for b in bs)


def gap_days(a: dict, b: dict) -> int:
    return abs((a["date"] - b["date"]).days)


def rule_problems(rule: str, a: dict, bs: list, p: Params) -> list:
    """Why a rule does not hold for these lines. An empty list means it holds. The search and the check both use it."""
    if rule not in RULES:
        return [f"unknown rule {clean(rule)!r}"]
    if rule == "batch_sum":
        if not 2 <= len(bs) <= p.max_group:
            return [f"a batch needs 2 to {p.max_group} book lines, got {len(bs)}"]
    elif len(bs) != 1:
        return [f"{rule} pairs one bank line with one book line, got {len(bs)}"]
    out = []
    for b in bs:
        if b["currency"] != a["currency"]:
            out.append(f"{b['id']}: currency {b['currency']} against {a['currency']}")
        if gap_days(a, b) > p.window:
            out.append(f"{b['id']}: dates {gap_days(a, b)} days apart, window is {p.window}")
    b = bs[0]
    if rule == "batch_sum":
        total = sum(x["cents"] for x in bs)
        if total != a["cents"]:
            out.append(f"book lines sum to {money(total)}, the bank line is {money(a['cents'])}")
        if not a["ref_key"] or any(x["batch_key"] != a["ref_key"] for x in bs):
            out.append("the batch id on the book lines is not the bank reference")
        return out
    if rule == "ref_fee":
        if not (a["cents"] > 0 and b["cents"] - a["cents"] in p.fees):
            out.append(f"{money(b['cents'])} less {money(a['cents'])} is not a scheduled fee")
    elif a["cents"] != b["cents"]:
        out.append(f"amounts differ: {money(a['cents'])} against {money(b['cents'])}")
    if rule in ("ref_exact", "ref_fee"):
        if not a["ref_key"] or a["ref_key"] != b["ref_key"]:
            out.append("the references are not equal")
    elif rule == "ref_near":
        if not (a["ref_key"] and b["ref_key"] and one_edit_apart(a["ref_key"], b["ref_key"])):
            out.append("the references do not differ by exactly one edit")
    elif a["ref_key"] and b["ref_key"]:
        out.append("both lines carry a reference, so a name match is not allowed")
    if rule in ("ref_near", "name_amount") and not names_agree(a, [b]):
        out.append("the counterparty names do not agree")
    return out


def evidence_lines(rule: str, a: dict, bs: list) -> list:
    """What a reader checks, in plain words, from the lines themselves."""
    b = bs[0]
    ccy = a["currency"]
    if rule == "batch_sum":
        amount = f"amount {money(a['cents'])} {ccy} = {' + '.join(money(x['cents']) for x in bs)}"
        ref = f"ref {clean(a['ref_raw'])} is the batch id on {len(bs)} book lines"
    elif rule == "ref_fee":
        amount = f"amount {money(a['cents'])} {ccy} + fee {money(b['cents'] - a['cents'])} = {money(b['cents'])}"
        ref = f"ref {clean(a['ref_raw'])} = {clean(b['ref_raw'])}"
    else:
        amount = f"amount {money(a['cents'])} {ccy} = {money(b['cents'])} {b['currency']}"
        if rule == "ref_exact":
            ref = f"ref {clean(a['ref_raw'])} = {clean(b['ref_raw'])}"
        elif rule == "ref_near":
            ref = f"ref {clean(a['ref_raw'])} vs {clean(b['ref_raw'])}, one edit apart"
        else:
            ref = f"ref bank {clean(a['ref_raw']) or 'blank'}, book {clean(b['ref_raw']) or 'blank'}"
    names = "names agree" if names_agree(a, bs) else f"names differ ({clean(a['name'], 24)} / {clean(b['name'], 24)})"
    gap = max(gap_days(a, x) for x in bs)
    return [ref, amount, f"gap {gap} day{'' if gap == 1 else 's'}", names]


def gate_for(rule: str, a: dict, bs: list, p: Params) -> tuple:
    """('auto', '') when the match may post on its own, else ('approval', why)."""
    if GATE_POLICY[rule] == "approval":
        return "approval", GATE_WHY[rule]
    if abs(a["cents"]) > p.limit_cents:
        return "approval", f"the amount is above {money(p.limit_cents)}"
    if not names_agree(a, bs):
        return "approval", "the counterparty text differs"
    return "auto", ""


def make_key(rule: str, a_ids: list, b_ids: list, cents: int) -> str:
    return f"{rule}:{'+'.join(sorted(a_ids))}:{'+'.join(sorted(b_ids))}:{cents}"


# ---------------------------------------------------------------- the search
def _find(rule: str, avail_a: dict, avail_b: dict, batches: dict, p: Params) -> list:
    """Every (A line, B lines) pair the rule allows among the lines still free. One A line may appear in several."""
    by_amount = {}
    for b in avail_b.values():
        by_amount.setdefault((b["currency"], b["cents"]), []).append(b)
    cands = []
    for a in avail_a.values():
        if rule == "batch_sum":
            group = batches.get(a["ref_key"], []) if a["ref_key"] else []
            if group and all(g["id"] in avail_b for g in group) and not rule_problems(rule, a, group, p):
                cands.append({"rule": rule, "a": a, "b": group})
            continue
        if rule == "ref_fee":
            pool = [b for f in p.fees for b in by_amount.get((a["currency"], a["cents"] + f), [])]
        else:
            pool = by_amount.get((a["currency"], a["cents"]), [])
        for b in pool:
            if not rule_problems(rule, a, [b], p):
                cands.append({"rule": rule, "a": a, "b": [b]})
    for c in cands:
        c["gap"] = max(gap_days(c["a"], b) for b in c["b"])
    return cands


def _rows(c: dict) -> list:
    return [c["a"]] + c["b"]


def _interchangeable(c: dict, o: dict) -> bool:
    """Two candidates that differ only by a line identical to the other in every compared field."""
    if c["a"] is o["a"]:
        return sorted(b["sig"] for b in c["b"]) == sorted(b["sig"] for b in o["b"])
    if len(c["b"]) == 1 and len(o["b"]) == 1 and c["b"][0] is o["b"][0]:
        return c["a"]["sig"] == o["a"]["sig"]
    return False


def _select(cands: list) -> tuple:
    """Take candidates nearest in date first. A line with two equally near rivals that are not
    interchangeable is parked for a person instead of being guessed."""
    cands = sorted(cands, key=lambda c: (c["gap"], c["a"]["id"], sorted(b["id"] for b in c["b"])))
    by_row = {}
    for i, c in enumerate(cands):
        for r in _rows(c):
            by_row.setdefault((r["side"], r["id"]), []).append(i)
    used, accepted, parked = set(), [], []
    for i, c in enumerate(cands):
        if any((r["side"], r["id"]) in used for r in _rows(c)):
            continue
        near = {j for r in _rows(c) for j in by_row[(r["side"], r["id"])] if j != i}
        rivals = [cands[j] for j in sorted(near) if cands[j]["gap"] == c["gap"] and not _interchangeable(c, cands[j])
                  and not any((r["side"], r["id"]) in used for r in _rows(cands[j]))]
        group = [c] + rivals
        for g in group:
            used.update((r["side"], r["id"]) for r in _rows(g))
        if rivals:
            parked.append(group)
        else:
            accepted.append(c)
    return accepted, parked


def _proposal(c: dict, p: Params) -> dict:
    a, bs = c["a"], sorted(c["b"], key=lambda b: b["id"])
    gate, why = gate_for(c["rule"], a, bs, p)
    return {"rule": c["rule"], "a": a, "bs": bs, "a_ids": [a["id"]], "b_ids": [b["id"] for b in bs], "cents": a["cents"],
            "currency": a["currency"], "gap": c["gap"], "evidence": evidence_lines(c["rule"], a, bs), "gate": gate,
            "gate_why": why, "problems": rule_problems(c["rule"], a, bs, p),
            "key": make_key(c["rule"], [a["id"]], [b["id"] for b in bs], a["cents"])}


def propose(a_rows: list, b_rows: list, p: Params = DEFAULT_PARAMS) -> tuple:
    """Run the ladder. Returns (proposals, parked) where parked maps (side, id) to the ids of the lines it could not be told apart from."""
    avail_a = {r["id"]: r for r in a_rows}
    avail_b = {r["id"]: r for r in b_rows}
    batches = {}
    for b in b_rows:
        if b["batch_key"]:
            batches.setdefault(b["batch_key"], []).append(b)
    proposals, parked = [], {}
    for rule in RULES:
        cands = _find(rule, avail_a, avail_b, batches, p)
        accepted, groups = _select(cands)
        for c in accepted:
            proposals.append(_proposal(c, p))
        for group in groups:
            for g in group:
                for r in _rows(g):
                    partners = sorted({x["id"] for h in group for x in _rows(h) if x["side"] != r["side"]})
                    parked[(r["side"], r["id"])] = partners
        taken = [r for c in accepted for r in _rows(c)] + [r for g in groups for h in g for r in _rows(h)]
        for r in taken:
            (avail_a if r["side"] == "A" else avail_b).pop(r["id"], None)
    proposals.sort(key=lambda q: (q["a"]["date"], q["a"]["id"], q["rule"]))
    for i, q in enumerate(proposals, start=1):
        q["match_id"] = f"M-{i:04d}"
    return proposals, parked


# ---------------------------------------------------------------- the gate
def apply_gate(proposals: list, approvals: list) -> list:
    """Set each proposal's status and return the approval records the gate refused, with the reason.
    A match posts on its own only if its rule allows it and its check passed. Anything else posts only on a
    recorded approval for exactly that proposal from someone other than the agent."""
    known = {q["key"] for q in proposals}
    by_key, refused = {}, []
    for ap in approvals:
        if ap["key"] not in known:
            refused.append({"key": ap["key"], "approver": ap["approver"], "why": "stale: no current proposal has this key"})
        elif ap["approver"].strip().casefold() == AGENT_ID:
            refused.append({"key": ap["key"], "approver": ap["approver"], "why": "self-approval: the proposer cannot approve"})
        else:
            by_key.setdefault(ap["key"], []).append(ap)
    for q in proposals:
        q["approver"] = ""
        if q["problems"]:
            q["status"] = "blocked"
        elif q["gate"] == "auto":
            q["status"] = "posted_auto"
        else:
            given = by_key.get(q["key"], [])
            decisions = {ap["decision"] for ap in given}
            if len(decisions) > 1:
                q["status"] = "pending"
                refused.append({"key": q["key"], "approver": ",".join(sorted(ap["approver"] for ap in given)),
                                "why": "conflicting decisions: left pending"})
            elif decisions == {"approve"}:
                q["status"], q["approver"] = "posted_approved", given[0]["approver"]
            elif decisions == {"reject"}:
                q["status"], q["approver"] = "rejected", given[0]["approver"]
            else:
                q["status"] = "pending"
    return refused


# ---------------------------------------------------------------- the open items
def _open_items(a_rows: list, b_rows: list, proposals: list, parked: dict, p: Params) -> list:
    posted = {(r["side"], r["id"]) for q in proposals if q["status"] in POSTED for r in [q["a"]] + q["bs"]}
    held = {}
    for q in proposals:
        if q["status"] not in POSTED:
            for r in [q["a"]] + q["bs"]:
                held[(r["side"], r["id"])] = q
    twin_of = {}
    for q in proposals:
        for r in [q["a"]] + q["bs"]:
            twin_of.setdefault((r["side"], r["sig"]), r)
    free = [r for r in a_rows + b_rows if (r["side"], r["id"]) not in posted]
    by_cents = {}
    for r in free:
        by_cents.setdefault((r["side"], r["cents"]), []).append(r)
    batch_sums = {}
    for b in b_rows:
        if b["batch_key"]:
            batch_sums[b["batch_key"]] = batch_sums.get(b["batch_key"], 0) + b["cents"]
    out = []
    for r in free:
        k = (r["side"], r["id"])
        reason, detail = "no_counterpart", "nothing on the other side meets any rule"
        twin = twin_of.get((r["side"], r["sig"]))
        if k in held:
            q = held[k]
            who = clean(q["approver"])
            reason = {"pending": "awaiting_approval", "rejected": "rejected_by_reviewer", "blocked": "failed_check"}[q["status"]]
            detail = {"pending": f"{q['match_id']} {q['rule']} needs a person because {q['gate_why']}",
                      "rejected": f"{q['match_id']} {q['rule']} rejected by {who}",
                      "blocked": f"{q['match_id']} {q['rule']} failed its check: {'; '.join(q['problems'])}"}[q["status"]]
        elif k in parked:
            reason, detail = "ambiguous_candidates", "cannot be told apart from: " + ", ".join(parked[k])
        elif twin is not None and twin is not r:
            reason, detail = "possible_duplicate", f"identical in every compared field to {twin['id']}, which is in a match or proposal"
        else:
            near = [o for o in by_cents.get(("B" if r["side"] == "A" else "A", r["cents"]), []) if abs((o["date"] - r["date"]).days) <= p.window]
            conflict = [o for o in near if o["currency"] == r["currency"] and o["ref_key"] and r["ref_key"] and o["ref_key"] != r["ref_key"] and names_agree(r, [o])]
            currency = [o for o in near if o["currency"] != r["currency"]]
            if conflict:
                o = conflict[0]
                reason, detail = "reference_conflict", f"same amount, counterparty and window as {o['id']}, but the references differ ({clean(r['ref_raw'])} against {clean(o['ref_raw'])})"
            elif currency:
                reason, detail = "currency_differs", f"same amount as {currency[0]['id']} within the window, in {currency[0]['currency']}"
            elif r["side"] == "A" and r["ref_key"] in batch_sums:
                reason, detail = "batch_sum_differs", f"the book lines of batch {clean(r['ref_raw'])} sum to {money(batch_sums[r['ref_key']])}, the bank line is {money(r['cents'])}"
        out.append({"ledger": r["side"], "id": r["id"], "date": r["date"].isoformat(), "amount": money(r["cents"]), "currency": r["currency"],
                    "counterparty": r["name"], "reason": reason, "detail": detail})
    return out


def reconcile(a_rows: list, b_rows: list, approvals: list = (), p: Params = DEFAULT_PARAMS) -> dict:
    proposals, parked = propose(a_rows, b_rows, p)
    refused = apply_gate(proposals, list(approvals))
    return {"proposals": proposals, "refused": refused, "open": _open_items(a_rows, b_rows, proposals, parked, p),
            "parked": parked, "a_rows": a_rows, "b_rows": b_rows, "params": p}


# ---------------------------------------------------------------- the check on a finished match list
def verify_matches(a_rows: list, b_rows: list, matches: list, p: Params = DEFAULT_PARAMS) -> list:
    """Re-run the rules on the lines each posted match cites. Returns a list of problems; empty means every posted match re-checks."""
    a_by, b_by = {r["id"]: r for r in a_rows}, {r["id"]: r for r in b_rows}
    batch_members = {}
    for b in b_rows:
        if b["batch_key"]:
            batch_members.setdefault(b["batch_key"], set()).add(b["id"])
    problems, used_a, used_b = [], set(), set()
    for m in matches:
        if m["status"] not in POSTED:
            continue
        mid = clean(m["match_id"])
        a_ids, b_ids = [x for x in m["a_ids"].split("+") if x], [x for x in m["b_ids"].split("+") if x]
        if len(a_ids) != 1 or not b_ids:
            problems.append(f"{mid}: a match needs one bank line and at least one book line")
            continue
        missing = [i for i in a_ids if i not in a_by] + [i for i in b_ids if i not in b_by]
        if missing:
            problems.append(f"{mid}: line(s) not in the ledgers: {', '.join(clean(i) for i in missing)}")
            continue
        reused = [i for i in a_ids if i in used_a] + [i for i in b_ids if i in used_b]
        if reused:
            problems.append(f"{mid}: line(s) already used by another posted match: {', '.join(reused)}")
        used_a.update(a_ids)
        used_b.update(b_ids)
        a, bs = a_by[a_ids[0]], sorted((b_by[i] for i in b_ids), key=lambda b: b["id"])
        failed = rule_problems(m["rule"], a, bs, p)
        problems.extend(f"{mid}: {why}" for why in failed)
        if failed:
            continue
        if m["rule"] == "batch_sum" and batch_members.get(a["ref_key"]) != set(b_ids):
            problems.append(f"{mid}: the match leaves out a book line of the same batch")
        if m["evidence"] != " | ".join(evidence_lines(m["rule"], a, bs)):
            problems.append(f"{mid}: the stored evidence is not what the cited lines show")
        gate, _ = gate_for(m["rule"], a, bs, p)
        if m["status"] == "posted_auto" and gate != "auto":
            problems.append(f"{mid}: posted without approval, but the policy requires one")
        if m["status"] == "posted_approved" and (not m["approver"] or m["approver"].strip().casefold() == AGENT_ID):
            problems.append(f"{mid}: posted on approval, but no approver other than the agent is recorded")
    return problems


def load_matches(path: str) -> list:
    label = f"matches ({os.path.basename(path)})"
    need = ("match_id", "rule", "status", "a_ids", "b_ids", "evidence", "approver")
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise InputError(f"{label}: the file is empty")
            missing = [c for c in need if c not in reader.fieldnames]
            if missing:
                raise InputError(f"{label}: missing column(s) {', '.join(missing)}")
            raw = list(reader)
    except OSError as e:
        raise InputError(f"{label}: cannot read the file ({e.strerror or e})")
    except (csv.Error, UnicodeDecodeError) as e:
        raise InputError(f"{label}: not a UTF-8 CSV file ({e})")
    for n, r in enumerate(raw, start=2):
        if None in r or any(r.get(c) is None for c in need):
            raise InputError(f"{label}, row {n}: a field is missing or there are too many")
    return raw


# ---------------------------------------------------------------- output
def write_outputs(result: dict, out_dir: str, prefix: str = "") -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, prefix + "matches.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["match_id", "key", "rule", "status", "gate", "gate_why", "a_ids", "b_ids", "amount", "currency", "gap_days", "evidence", "approver"])
        for q in result["proposals"]:
            w.writerow([q["match_id"], q["key"], q["rule"], q["status"], q["gate"], q["gate_why"], "+".join(q["a_ids"]), "+".join(q["b_ids"]),
                        money(q["cents"]), q["currency"], q["gap"], csv_safe(" | ".join(q["evidence"])), csv_safe(clean(q["approver"], 80))])
    with open(os.path.join(out_dir, prefix + "unmatched.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["ledger", "id", "date", "amount", "currency", "counterparty", "reason", "detail"])
        for o in result["open"]:
            w.writerow([o["ledger"], o["id"], o["date"], o["amount"], o["currency"], csv_safe(clean(o["counterparty"], 80)), o["reason"], csv_safe(o["detail"])])


def render(result: dict) -> str:
    p, props, open_items = result["params"], result["proposals"], result["open"]
    lines = [f"recon-agent: {len(result['a_rows'])} bank lines, {len(result['b_rows'])} book lines, date window {p.window} days, "
             f"a person approves above {money(p.limit_cents)} and for every rule except ref_exact"]
    if not props:
        lines.append("no matches found: no bank line meets any of the five rules against the book lines")
    for q in props:
        who = f" by {clean(q['approver'])}" if q["approver"] else ""
        lines.append(f"{q['match_id']} {q['status']:<15} {q['rule']:<11} {','.join(q['a_ids'])} = {','.join(q['b_ids'])}{who}")
        lines.append("    " + " | ".join(q["evidence"]))
    for r in result["refused"]:
        lines.append(f"refused: {clean(r['approver'])} on {clean(r['key'], 70)}: {r['why']}")
    lines.append(f"open items: {len(open_items)}")
    for o in open_items:
        lines.append(f"  {o['ledger']} {o['id']} {o['amount']:>9} {o['reason']}: {clean(o['detail'], 72)}")
    n = {s: sum(1 for q in props if q["status"] == s) for s in ("posted_auto", "posted_approved", "pending", "rejected", "blocked")}
    lines.append(f"posted {n['posted_auto'] + n['posted_approved']} ({n['posted_auto']} on their own, {n['posted_approved']} on approval); "
                 f"waiting {n['pending']}; rejected {n['rejected']}; blocked by the check {n['blocked']}; approvals refused {len(result['refused'])}")
    return "\n".join(lines)


# ---------------------------------------------------------------- command line
class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"recon_agent: {message}", file=sys.stderr)
        sys.exit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="recon_agent")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_*.csv)")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("reconcile", help="match two ledgers")
    r.add_argument("ledger_a")
    r.add_argument("ledger_b")
    r.add_argument("--approvals", help="CSV of recorded approvals")
    r.add_argument("--out", help="directory for matches.csv and unmatched.csv")
    r.add_argument("--fail-on-open", action="store_true", help="exit 1 when any line is still open")
    v = sub.add_parser("verify", help="re-check a matches.csv against the ledgers")
    v.add_argument("ledger_a")
    v.add_argument("ledger_b")
    v.add_argument("matches")
    a = ap.parse_args(argv)
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        if a.demo:
            d = os.path.join(here, "..", "data")
            a_rows, b_rows = load_ledger(os.path.join(d, "example_ledger_a.csv"), "A"), load_ledger(os.path.join(d, "example_ledger_b.csv"), "B")
            print(render(reconcile(a_rows, b_rows, load_approvals(os.path.join(d, "example_approvals.csv")))))
            return 0
        if a.cmd == "reconcile":
            a_rows, b_rows = load_ledger(a.ledger_a, "A"), load_ledger(a.ledger_b, "B")
            result = reconcile(a_rows, b_rows, load_approvals(a.approvals) if a.approvals else [])
            if a.out:
                write_outputs(result, a.out)
            print(render(result))
            return 1 if a.fail_on_open and result["open"] else 0
        if a.cmd == "verify":
            a_rows, b_rows = load_ledger(a.ledger_a, "A"), load_ledger(a.ledger_b, "B")
            matches = load_matches(a.matches)
            problems = verify_matches(a_rows, b_rows, matches)
            posted = sum(1 for m in matches if m["status"] in POSTED)
            for line in problems:
                print(line)
            print(f"checked {posted} posted matches: {len(problems)} problem(s)" if posted else "checked 0 posted matches: the file has none to check")
            return 1 if problems else 0
    except OSError as e:
        print(f"output error: {e.strerror or e}", file=sys.stderr)
        return 2
    except InputError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
