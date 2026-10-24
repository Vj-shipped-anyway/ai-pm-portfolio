"""payment_repair: find missing fields in pacs.008-style payment messages, propose repairs from the
bank's own tables, and release nothing that changes who gets the money until a person approves
that exact change. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 payment_repair.py --demo
    python3 payment_repair.py check MESSAGES.json --refs DIR [--approvals APPROVALS.csv]
                              [--fail-on hold|return|never] [--out RELEASED.json] [--audit-out AUDIT.csv]

Exit status: 0 when nothing is held or returned (or --fail-on never), 1 when a message is held or
returned at or above the --fail-on level, 2 for bad or malformed input.

A message ends in one of four routes:
    PASS      no required field is missing or unusable; nothing is touched
    REPAIRED  every repair was applied: rule tier AUTO, or tier APPROVAL with a valid approval
    HOLD      repairs are proposed and wait for a person; nothing is applied
    RETURN    at least one field cannot be repaired from a table the policy allows; the message is
              untouched and goes back to the originator with the reasons

The policy table (POLICY) is mine. It is an assumption, not a reading of any rulebook. There is no
model in this file: detection, derivation, the digest and the approval check are plain rules.

Message shape: a JSON list of objects. Each object maps a dotted path named after the pacs.008
element (for example "CdtTrfTxInf.Cdtr.Nm") to a string; an absent key or null means missing. The
set is pacs.008-style and has not been validated against the ISO 20022 schema. One transaction per
message.

Reference tables in --refs (CSV with a header row):
    bic_directory.csv    country, bank_code, bic, status
    customer_master.csv  iban, customer_id, name, account_ccy, status
    payment_orders.csv   end_to_end_id, uetr, charge_bearer, initiator_id
    approvers.csv        approver_id, kind, role, active
Approvals CSV: msg_id, plan_digest, approver_id, decision (approve or reject).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata

MSG_ID = "GrpHdr.MsgId"
NB = "GrpHdr.NbOfTxs"
E2E = "CdtTrfTxInf.PmtId.EndToEndId"
UETR = "CdtTrfTxInf.PmtId.UETR"
AMT = "CdtTrfTxInf.IntrBkSttlmAmt"
CCY = "CdtTrfTxInf.IntrBkSttlmAmt@Ccy"
CHRG = "CdtTrfTxInf.ChrgBr"
DBTR_NM = "CdtTrfTxInf.Dbtr.Nm"
DBTR_IBAN = "CdtTrfTxInf.DbtrAcct.Id.IBAN"
DBTR_BIC = "CdtTrfTxInf.DbtrAgt.FinInstnId.BICFI"
CDTR_NM = "CdtTrfTxInf.Cdtr.Nm"
CDTR_CTRY = "CdtTrfTxInf.Cdtr.PstlAdr.Ctry"
CDTR_IBAN = "CdtTrfTxInf.CdtrAcct.Id.IBAN"
CDTR_BIC = "CdtTrfTxInf.CdtrAgt.FinInstnId.BICFI"
PURP = "CdtTrfTxInf.Purp.Cd"
RMT = "CdtTrfTxInf.RmtInf.Ustrd"

REQUIRED = [NB, E2E, UETR, AMT, CCY, CHRG, DBTR_NM, DBTR_IBAN, DBTR_BIC, CDTR_NM, CDTR_CTRY, CDTR_IBAN, CDTR_BIC]
OPTIONAL = [PURP, RMT]
LABELS = {
    NB: "number of transactions", E2E: "end-to-end id", UETR: "UETR", AMT: "amount", CCY: "currency",
    CHRG: "charge bearer", DBTR_NM: "debtor name", DBTR_IBAN: "debtor IBAN", DBTR_BIC: "debtor agent BIC",
    CDTR_NM: "creditor name", CDTR_CTRY: "creditor country", CDTR_IBAN: "creditor IBAN", CDTR_BIC: "creditor agent BIC",
}

AUTO, APPROVAL, NEVER = "AUTO", "APPROVAL", "NEVER"
# Who may fill a missing field. AUTO: derived from the message itself or from the bank's own record of
# its customer, applied without a person. APPROVAL: derived from a table, but it decides where the
# money goes or what the payment says, so a person approves that exact change. NEVER: only the
# originator can say; the tool refuses and the message goes back.
POLICY = {
    NB: AUTO, DBTR_NM: AUTO, DBTR_BIC: AUTO,
    UETR: APPROVAL, CHRG: APPROVAL, CDTR_CTRY: APPROVAL, CDTR_BIC: APPROVAL,
    E2E: NEVER, AMT: NEVER, CCY: NEVER, DBTR_IBAN: NEVER, CDTR_NM: NEVER, CDTR_IBAN: NEVER,
}
REVIEWER_ROLE = "payments_reviewer"
NEVER_REASON = {
    E2E: "the end-to-end id is the originator's key; no table may supply it",
    AMT: "an amount is never inferred",
    CCY: "a currency is never inferred, not even from the debit account",
    DBTR_IBAN: "no table may supply an account number",
    CDTR_NM: "no table may supply a beneficiary name; a saved payee list can be stale",
    CDTR_IBAN: "no table may supply an account number",
}

_SHAPES = {
    NB: re.compile(r"0*1"),
    UETR: re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
    AMT: re.compile(r"[0-9]+(\.[0-9]{1,2})?"),
    CCY: re.compile(r"[A-Z]{3}"),
    CHRG: re.compile(r"DEBT|CRED|SHAR|SLEV"),
    DBTR_IBAN: re.compile(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}"),
    CDTR_IBAN: re.compile(r"[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}"),
    DBTR_BIC: re.compile(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?"),
    CDTR_BIC: re.compile(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?"),
    CDTR_CTRY: re.compile(r"[A-Z]{2}"),
}
_PLACEHOLDERS = frozenset({"n/a", "na", "none", "null", "nil", "notprovided", "notapplicable", "unknown", "tbd", "tba",
                           "-", "--", "?", "xxx"})
REF_FILES = {
    "bic_directory.csv": ["country", "bank_code", "bic", "status"],
    "customer_master.csv": ["iban", "customer_id", "name", "account_ccy", "status"],
    "payment_orders.csv": ["end_to_end_id", "uetr", "charge_bearer", "initiator_id"],
    "approvers.csv": ["approver_id", "kind", "role", "active"],
}
ROUTE_RANK = {"PASS": 0, "REPAIRED": 0, "HOLD": 1, "RETURN": 2}


# ---------------------------------------------------------------- text safety
def clean(text, limit: int = 80) -> str:
    """Printable ASCII only, so a name with a newline or a control character cannot forge an output line."""
    out = []
    for ch in str(text):
        o = ord(ch)
        if 32 <= o < 127:
            out.append(ch)
        elif o < 256:
            out.append("\\x%02x" % o)
        elif o < 65536:
            out.append("\\u%04x" % o)
        else:
            out.append("\\U%08x" % o)
    s = "".join(out)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def csv_safe(text) -> str:
    """Stop a spreadsheet reading an audit cell as a formula."""
    s = "" if text is None else str(text)
    if s and (s[0] in "=+@\t\r" or (s[0] == "-" and len(s) > 1)):
        return "'" + s
    return s


# ---------------------------------------------------------------- detecting a missing field
def _norm(value: str) -> str:
    """Lower-case, with every control, format and space character removed (so a zero-width space is blank)."""
    return "".join(ch for ch in value if unicodedata.category(ch)[0] not in "CZ").lower()


def classify(path: str, value):
    """None when the value is usable, else 'missing', 'blank', 'placeholder' or 'malformed'."""
    if value is None:
        return "missing"
    norm = _norm(value)
    if norm == "":
        return "blank"
    if norm in _PLACEHOLDERS:
        return "placeholder"
    shape = _SHAPES.get(path)
    if shape is not None and not shape.fullmatch(value):
        return "malformed"
    if path == AMT and not any(ch in "123456789" for ch in value):
        return "malformed"
    return None


def find_defects(msg: dict) -> dict:
    """{path: kind} for every required field that is missing or unusable. Optional fields are never listed."""
    out = {}
    for p in REQUIRED:
        kind = classify(p, msg.get(p))
        if kind:
            out[p] = kind
    return out


# ---------------------------------------------------------------- reference tables
def build_refs(directory, master, orders, approvers) -> dict:
    refs = {"directory": {}, "master": {}, "orders": {}, "approvers": {}}
    for r in directory:
        refs["directory"].setdefault(r["bank_code"], []).append(r)
    for r in master:
        refs["master"].setdefault(r["iban"], []).append(r)
    for r in orders:
        refs["orders"].setdefault(r["end_to_end_id"], []).append(r)
    for r in approvers:
        refs["approvers"][r["approver_id"]] = r
    refs["sizes"] = {"directory": len(directory), "master": len(master), "orders": len(orders), "approvers": len(approvers)}
    return refs


def _read_csv(path: str, columns: list) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        missing = [c for c in columns if c not in (rd.fieldnames or [])]
        if missing:
            raise ValueError(f"{os.path.basename(path)}: missing column {missing[0]!r}")
        rows = list(rd)
    for i, r in enumerate(rows, start=2):
        if any(v is None for v in r.values()):
            raise ValueError(f"{os.path.basename(path)}: line {i} has fewer fields than the header")
    return rows


def load_refs(directory: str) -> dict:
    tables = {name: _read_csv(os.path.join(directory, name), cols) for name, cols in REF_FILES.items()}
    return build_refs(tables["bic_directory.csv"], tables["customer_master.csv"], tables["payment_orders.csv"],
                      tables["approvers.csv"])


def load_approvals(path: str) -> list:
    rows = _read_csv(path, ["msg_id", "plan_digest", "approver_id", "decision"])
    for i, r in enumerate(rows, start=2):
        if r["decision"] not in ("approve", "reject"):
            raise ValueError(f"{os.path.basename(path)}: line {i}: decision must be approve or reject")
    return rows


def load_messages(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return check_messages(data)


def check_messages(data) -> list:
    """Raise ValueError unless data is a non-empty list of flat objects with string values and unique message ids."""
    if not isinstance(data, list):
        raise ValueError(f"expected a JSON list of messages, got {type(data).__name__}")
    if not data:
        raise ValueError("the message list is empty")
    seen = set()
    for i, m in enumerate(data, start=1):
        if not isinstance(m, dict):
            raise ValueError(f"message {i}: expected an object, got {type(m).__name__}")
        for k, v in m.items():
            if v is not None and not isinstance(v, str):
                raise ValueError(f"message {i}: the value of {clean(k, 40)!r} must be a string, got {type(v).__name__}")
        mid = m.get(MSG_ID)
        if not isinstance(mid, str) or not mid.strip():
            raise ValueError(f"message {i}: {MSG_ID} is missing or empty, so the message cannot be identified")
        if mid in seen:
            raise ValueError(f"message {i}: {MSG_ID} {clean(mid, 40)!r} appears twice")
        seen.add(mid)
    return data


# ---------------------------------------------------------------- proposing a repair
def _refuse(reason: str) -> dict:
    return {"ok": False, "reason": reason}


def _offer(path: str, value, source: str, evidence: str) -> dict:
    if classify(path, value) is not None:
        return _refuse(f"the table value for {LABELS[path]} is itself unusable")
    return {"ok": True, "value": value, "source": source, "evidence": evidence}


def _directory_bic(path: str, iban_path: str, msg: dict, refs: dict, bad: dict) -> dict:
    if iban_path in bad:
        return _refuse(f"needs a usable {LABELS[iban_path]}, which is {bad[iban_path]}")
    iban = msg[iban_path]
    code, country = iban[4:12], iban[:2]
    rows = [r for r in refs["directory"].get(code, []) if r["status"] == "active" and r["country"] == country]
    if len(rows) == 1:
        return _offer(path, rows[0]["bic"], "bank directory", f"bank code {code}, one active row")
    if not rows:
        return _refuse(f"no active directory row for bank code {code}")
    return _refuse(f"{len(rows)} active directory rows for bank code {code}; a person has to choose")


def propose(path: str, msg: dict, refs: dict, bad: dict) -> dict:
    """{'ok': True, value, source, evidence} or {'ok': False, reason} for one defective required field."""
    if POLICY[path] == NEVER:
        return _refuse(NEVER_REASON[path])
    if path == NB:
        return _offer(path, "1", "message", "the message carries one transaction")
    if path == DBTR_BIC:
        return _directory_bic(path, DBTR_IBAN, msg, refs, bad)
    if path == CDTR_BIC:
        return _directory_bic(path, CDTR_IBAN, msg, refs, bad)
    if path == DBTR_NM:
        if DBTR_IBAN in bad:
            return _refuse(f"needs a usable debtor IBAN, which is {bad[DBTR_IBAN]}")
        rows = refs["master"].get(msg[DBTR_IBAN], [])
        if not rows:
            return _refuse("no customer master row for the debtor account")
        if len(rows) > 1:
            return _refuse(f"{len(rows)} holders on the debtor account; a person has to choose")
        if rows[0]["status"] != "open":
            return _refuse("the debtor account is not open")
        return _offer(path, rows[0]["name"], "customer master", f"customer {clean(rows[0]['customer_id'], 40)}, one holder")
    if path == CDTR_CTRY:
        if CDTR_IBAN in bad:
            return _refuse(f"needs a usable creditor IBAN, which is {bad[CDTR_IBAN]}")
        return _offer(path, msg[CDTR_IBAN][:2], "IBAN prefix",
                      "first two letters of the creditor IBAN; the creditor may live elsewhere")
    if path in (UETR, CHRG):
        if E2E in bad:
            return _refuse(f"needs a usable end-to-end id, which is {bad[E2E]}")
        rows = refs["orders"].get(msg[E2E], [])
        if len(rows) != 1:
            return _refuse("no payment order for this end-to-end id" if not rows else f"{len(rows)} payment orders share this end-to-end id")
        value = rows[0]["uetr"] if path == UETR else rows[0]["charge_bearer"]
        return _offer(path, value, "payment order", f"order with end-to-end id {clean(msg[E2E], 40)}")
    return _refuse("no source")


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def plan_digest(msg: dict, edits: list) -> str:
    """Hash of the message as it stands and of every proposed change, so an approval covers exactly this plan."""
    body = {"msg_id": msg[MSG_ID], "base": _sha(_canon(msg)),
            "edits": [[e["path"], e["old"], e["new"], e["source"], e["tier"]] for e in edits]}
    return _sha(_canon(body))


def make_plan(msg: dict, refs: dict) -> tuple:
    """(edits, refusals) for one message. Edits and refusals follow the order of REQUIRED."""
    bad = find_defects(msg)
    edits, refusals = [], []
    for path, kind in bad.items():
        out = propose(path, msg, refs, bad)
        if out["ok"]:
            edits.append({"path": path, "kind": kind, "old": msg.get(path), "new": out["value"],
                          "source": out["source"], "evidence": out["evidence"], "tier": POLICY[path]})
        else:
            refusals.append({"path": path, "kind": kind, "reason": out["reason"]})
    return edits, refusals


# ---------------------------------------------------------------- the approval gate
def order_initiator(msg: dict, refs: dict):
    """Who entered the payment order, or None when that cannot be told."""
    rows = refs["orders"].get(msg.get(E2E) or "", [])
    if len(rows) == 1 and rows[0]["initiator_id"].strip():
        return rows[0]["initiator_id"]
    return None


def judge_approval(approval: dict, digest: str, initiator, refs: dict) -> tuple:
    """('approve' | 'reject' | 'invalid', reason). Every check reads an explicit field of the registry."""
    if approval["plan_digest"] != digest:
        return "invalid", "the approval is for a different plan (digest does not match)"
    who = refs["approvers"].get(approval["approver_id"])
    if who is None:
        return "invalid", "the approver is not in the registry"
    if who["kind"] != "person":
        return "invalid", f"the approver is a {clean(who['kind'], 20)}, not a person"
    if who["active"] != "yes":
        return "invalid", "the approver is not active"
    if who["role"] != REVIEWER_ROLE:
        return "invalid", "the approver does not hold the reviewer role"
    if initiator is None:
        return "invalid", "the person who entered the order is unknown, so four-eyes cannot be checked"
    if approval["approver_id"] == initiator:
        return "invalid", "the approver entered the payment order"
    return approval["decision"], ""


def repair_message(msg: dict, refs: dict, approvals=()) -> dict:
    """Decide one message. `approvals` are the rows of the approvals file that name this message."""
    edits, refusals = make_plan(msg, refs)
    res = {"msg_id": msg[MSG_ID], "route": "PASS", "edits": [], "refusals": [], "digest": None, "approver": None,
           "hold_reason": None, "needs_approval": False, "message": msg}
    if not edits and not refusals:
        return res
    if refusals:
        res.update(route="RETURN", refusals=refusals)
        return res
    digest = plan_digest(msg, edits)
    res.update(edits=edits, digest=digest)
    if all(e["tier"] == AUTO for e in edits):
        res.update(route="REPAIRED", message=apply_edits(msg, edits))
        return res
    res.update(route="HOLD", needs_approval=True, hold_reason="waiting for a person to approve this plan")
    initiator = order_initiator(msg, refs)
    reasons = []
    for a in approvals:
        verdict, why = judge_approval(a, digest, initiator, refs)
        if verdict == "approve":
            res.update(route="REPAIRED", approver=a["approver_id"], hold_reason=None, message=apply_edits(msg, edits))
            return res
        if verdict == "reject":
            res.update(route="RETURN", edits=[], digest=None, approver=a["approver_id"], hold_reason=None,
                       refusals=[{"path": None, "kind": "rejected", "reason": "the reviewer rejected the plan"}])
            return res
        reasons.append(why)
    if reasons:
        res["hold_reason"] = "approval on file does not count: " + reasons[0]
    return res


def apply_edits(msg: dict, edits: list) -> dict:
    out = dict(msg)
    for e in edits:
        out[e["path"]] = e["new"]
    return out


def repair_all(messages: list, refs: dict, approvals: list) -> tuple:
    """(results, unused) where unused counts approval rows that did nothing: naming no message in this run,
    or naming a message that needed no approval. Messages are decided independently."""
    by_msg = {}
    for a in approvals:
        by_msg.setdefault(a["msg_id"], []).append(a)
    results = [repair_message(m, refs, by_msg.get(m[MSG_ID], [])) for m in messages]
    needs = {r["msg_id"]: r["needs_approval"] for r in results}
    unused = {"no_message": sum(1 for a in approvals if a["msg_id"] not in needs),
              "not_needed": sum(1 for a in approvals if a["msg_id"] in needs and not needs[a["msg_id"]])}
    return results, unused


# ---------------------------------------------------------------- audit and output
AUDIT_COLUMNS = ["msg_id", "path", "kind", "old", "new", "source", "tier", "approved_by", "plan_digest"]


def audit_rows(results: list) -> list:
    """One row per applied change: what, from where, under which tier, and who approved it."""
    rows = []
    for r in results:
        if r["route"] != "REPAIRED":
            continue
        for e in r["edits"]:
            who = r["approver"] if e["tier"] == APPROVAL else "(rule)"
            rows.append([r["msg_id"], e["path"], e["kind"], e["old"] or "", e["new"], e["source"], e["tier"], who,
                         r["digest"]])
    return rows


def write_audit(path: str, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh, lineterminator="\n")
        wr.writerow(AUDIT_COLUMNS)
        wr.writerows([[csv_safe(v) for v in row] for row in rows])


def write_released(path: str, results: list) -> None:
    released = [r["message"] for r in results if r["route"] in ("PASS", "REPAIRED")]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(released, fh, indent=1, sort_keys=True)
        fh.write("\n")


def render(results: list, unused: dict, refs: dict) -> str:
    lines = []
    for r in results:
        if r["route"] == "PASS":
            continue
        mid = clean(r["msg_id"], 40)
        if r["route"] == "REPAIRED":
            how = f"approved by {clean(r['approver'], 30)}" if r["approver"] else "rule tier AUTO, no person needed"
            lines.append(f"{mid}  REPAIRED  {len(r['edits'])} change(s) applied; {how}")
        elif r["route"] == "HOLD":
            lines.append(f"{mid}  HOLD      {r['hold_reason']}")
        else:
            lines.append(f"{mid}  RETURN    back to the originator; nothing was changed")
        for e in r["edits"]:
            lines.append(f"    {LABELS[e['path']]}: {e['kind']}, value from {e['source']} ({e['evidence']}) -> {clean(e['new'])}"
                         f"  [{e['tier']}]")
        for f in r["refusals"]:
            label = LABELS[f["path"]] if f["path"] else "(plan)"
            lines.append(f"    {label}: {f['kind']}; {f['reason']}")
        if r["route"] == "HOLD":
            lines.append(f"    digest {r['digest']}")
    count = {k: sum(1 for r in results if r["route"] == k) for k in ROUTE_RANK}
    lines.append(f"summary: {len(results)} messages: {count['PASS']} pass, {count['REPAIRED']} repaired, "
                 f"{count['HOLD']} hold, {count['RETURN']} return")
    if count["PASS"] == len(results):
        lines.append("nothing to repair: no required field was missing or unusable in any message")
    for name, key in (("bic_directory.csv", "directory"), ("customer_master.csv", "master"), ("payment_orders.csv", "orders")):
        if refs["sizes"][key] == 0:
            lines.append(f"note: {name} has no rows, so nothing can be derived from it")
    if unused["no_message"] or unused["not_needed"]:
        lines.append(f"note: approval rows ignored: {unused['no_message']} name no message in this run, "
                     f"{unused['not_needed']} name a message that needed no approval")
    return "\n".join(lines)


def run_check(messages_path, refs_dir, approvals_path, fail_on, out_path=None, audit_path=None) -> int:
    try:
        messages = load_messages(messages_path)
        refs = load_refs(refs_dir)
        approvals = load_approvals(approvals_path) if approvals_path else []
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, csv.Error) as e:
        print(f"input error: {clean(e, 200)}", file=sys.stderr)
        return 2
    results, unused = repair_all(messages, refs, approvals)
    try:
        if audit_path:
            write_audit(audit_path, audit_rows(results))
        if out_path:
            write_released(out_path, results)
    except OSError as e:
        print(f"cannot write output: {clean(e, 200)}", file=sys.stderr)
        return 2
    print(render(results, unused, refs))
    if fail_on == "never":
        return 0
    worst = max(ROUTE_RANK[r["route"]] for r in results)
    return 1 if worst >= {"hold": 1, "return": 2}[fail_on] else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="payment_repair")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_messages.json)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="decide a file of messages")
    c.add_argument("messages")
    c.add_argument("--refs", required=True, help="directory with the four reference CSV files")
    c.add_argument("--approvals", help="CSV of approvals: msg_id, plan_digest, approver_id, decision")
    c.add_argument("--fail-on", choices=["hold", "return", "never"], default="hold")
    c.add_argument("--out", help="write the released messages (PASS and REPAIRED) to this JSON file")
    c.add_argument("--audit-out", help="write one CSV row per applied change")
    a = ap.parse_args(argv)
    if a.demo:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_check(os.path.join(d, "example_messages.json"), d, None, "never")
    if a.cmd == "check":
        return run_check(a.messages, a.refs, a.approvals, a.fail_on, a.out, a.audit_out)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
