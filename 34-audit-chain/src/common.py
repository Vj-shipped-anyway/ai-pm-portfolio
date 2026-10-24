"""Shared loading, planted edits and the baseline checks for the four step scripts of project 34.

The planted edits (apply_op) are what an attacker with write access to the log file does. They are
written separately from the verifier in audit_chain.py. Each one is applied to the lines of a log built
from data/actions.csv, and the truth label of every edit comes from data/tamper_plan.csv.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from typing import List

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA = os.path.join(HERE, "..", "data")
OUT_DIR = os.path.join(HERE, "out")

from audit_chain import AuditLog, CORE_KEYS, GENESIS, digest, dumps_event, make_anchor, verify_lines  # noqa: E402

DETECTORS = ("none", "records", "chain", "anchored")


def load_params() -> dict:
    with open(os.path.join(DATA, "params.json"), encoding="utf-8") as fh:
        return json.load(fh)


def build_log() -> list:
    """The events of the untouched log, written by the audit module from the agent's recorded actions."""
    log = AuditLog()
    with open(os.path.join(DATA, "actions.csv"), newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            log.append(r["kind"], r["case_id"], r["step"] or None, r["actor"], json.loads(r["detail_json"]))
    return log.events()


def load_plan() -> list:
    with open(os.path.join(DATA, "tamper_plan.csv"), newline="", encoding="utf-8") as fh:
        return [{"tamper_id": r["tamper_id"], "op": r["op"], "seq": int(r["seq"]), "count": int(r["count"]),
                 "region": r["region"], "truth": r["truth"]} for r in csv.DictReader(fh)]


def ensure_out() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------- planted edits
def _core(ev: dict) -> dict:
    return {k: ev[k] for k in CORE_KEYS}


def _rehash(ev: dict) -> None:
    """Recompute one event's own hash from the prev it already stores."""
    ev["hash"] = digest(ev["prev"], _core(ev))


def _renumber(evs: List[dict], start: int) -> None:
    """Fix sequence numbers and own hashes from position start on; the stored prev links are left as they are."""
    for j in range(start, len(evs)):
        evs[j]["seq"] = j + 1
        _rehash(evs[j])


def _relink(evs: List[dict], start: int) -> None:
    """Recompute prev and hash from position start on, so the chain is valid again after an edit."""
    for j in range(start, len(evs)):
        evs[j]["prev"] = evs[j - 1]["hash"] if j else GENESIS
        _rehash(evs[j])


def _edit_detail(detail: dict) -> dict:
    out = dict(detail)
    k = "answer" if "answer" in out else sorted(out)[0]
    out[k] = {"approved": "declined", "declined": "approved"}.get(out[k], str(out[k]) + "*")
    return out


def _forged(prev_event: dict) -> dict:
    ev = {"seq": prev_event["seq"] + 1, "case_id": prev_event["case_id"], "step": None, "kind": "approval",
          "actor": "reviewer.99", "detail": {"answer": "approved", "note": "added later"}, "prev": prev_event["hash"]}
    _rehash(ev)
    return ev


def _load(lines: List[str]) -> List[dict]:
    return [json.loads(x) for x in lines]


def _dump(evs: List[dict]) -> List[str]:
    return [dumps_event(e) for e in evs]


def edit_value(lines, seq, count):
    """Change a value in one event; nothing else is touched."""
    evs = _load(lines)
    evs[seq - 1]["detail"] = _edit_detail(evs[seq - 1]["detail"])
    return _dump(evs)


def edit_rehash(lines, seq, count):
    """Change a value and recompute that one event's own hash."""
    evs = _load(lines)
    evs[seq - 1]["detail"] = _edit_detail(evs[seq - 1]["detail"])
    _rehash(evs[seq - 1])
    return _dump(evs)


def delete_event(lines, seq, count):
    """Remove one line; nothing else is touched."""
    return lines[:seq - 1] + lines[seq:]


def delete_fix(lines, seq, count):
    """Remove one event, then renumber the later ones and recompute their own hashes."""
    evs = _load(lines)
    del evs[seq - 1]
    _renumber(evs, seq - 1)
    return _dump(evs)


def swap_fix(lines, seq, count):
    """Swap two neighbours, then fix the sequence numbers and own hashes."""
    evs = _load(lines)
    evs[seq - 1], evs[seq] = evs[seq], evs[seq - 1]
    _renumber(evs, seq - 1)
    return _dump(evs)


def insert_fix(lines, seq, count):
    """Insert a forged approval after event seq, then renumber the later events and recompute their own hashes."""
    evs = _load(lines)
    evs.insert(seq, _forged(evs[seq - 1]))
    _renumber(evs, seq)
    return _dump(evs)


def dup_key(lines, seq, count):
    """Put a second "kind" key in front of the real one. A parser that keeps the last value reads the original."""
    out = list(lines)
    out[seq - 1] = '{"kind": "route", ' + out[seq - 1][1:]
    return out


def add_field(lines, seq, count):
    """Add a field the hash does not cover."""
    evs = _load(lines)
    evs[seq - 1]["verified"] = True
    return _dump(evs)


def rewrite_all(lines, seq, count):
    """Change a value, then recompute every prev and hash from that event to the end."""
    evs = _load(lines)
    evs[seq - 1]["detail"] = _edit_detail(evs[seq - 1]["detail"])
    _relink(evs, seq - 1)
    return _dump(evs)


def truncate(lines, seq, count):
    """Cut the last count events."""
    return lines[:len(lines) - count]


def append_forged(lines, seq, count):
    """Add count events with a valid chain, written by someone who knows the algorithm."""
    evs = _load(lines)
    for _ in range(count):
        evs.append(_forged(evs[-1]))
    return _dump(evs)


def append_legit(lines, seq, count):
    """The real writer adds count events after the anchor was taken."""
    log = AuditLog(_load(lines))
    last = log.events()[-1]
    for _ in range(count):
        log.append("tool_call", last["case_id"], "S03", "agent", {"action": "write_note", "outcome": "ok", "tool": "case_notes"})
    return _dump(log.events())


def reformat_keys(lines, seq, count):
    """Same events, keys in reverse order, compact separators."""
    return [json.dumps(dict(reversed(list(e.items()))), separators=(",", ":")) for e in _load(lines)]


def reformat_unicode(lines, seq, count):
    """Same events, non-ASCII characters written raw instead of escaped."""
    return [json.dumps(e, ensure_ascii=False) for e in _load(lines)]


def reformat_crlf(lines, seq, count):
    """Same events, Windows line endings."""
    return [x + "\r" for x in lines]


def reformat_blank_lines(lines, seq, count):
    """Same events, a blank line after every tenth and at the end."""
    out = []
    for i, x in enumerate(lines, start=1):
        out.append(x)
        if i % 10 == 0:
            out.append("")
    return out + [""]


OPS = {f.__name__: f for f in (edit_value, edit_rehash, delete_event, delete_fix, swap_fix, insert_fix, dup_key, add_field,
                              rewrite_all, truncate, append_forged, append_legit, reformat_keys, reformat_unicode,
                              reformat_crlf, reformat_blank_lines)}


def apply_op(lines: List[str], row: dict) -> List[str]:
    return OPS[row["op"]](lines, row["seq"], row["count"])


# ---------------------------------------------------------------- the checks, weakest first
def detect_none(lines, anchor) -> bool:
    """Step 1: the log is read as written."""
    return False


def detect_records(lines, anchor) -> bool:
    """Step 2: each event carries a checksum of its own content, and the sequence numbers must run 1, 2, 3."""
    try:
        expected = 1
        for x in lines:
            if not x.strip():
                continue
            e = json.loads(x)
            if e["seq"] != expected or e["hash"] != digest(e["prev"], _core(e)):
                return True
            expected += 1
    except (ValueError, KeyError, TypeError):
        return True
    return False


def detect_chain(lines, anchor) -> bool:
    """The AgentKit audit module's verify_chain as it shipped: links, sequence and hashes, read with plain json.loads."""
    try:
        prev, expected = GENESIS, 1
        for x in lines:
            if not x.strip():
                continue
            e = json.loads(x)
            if e.get("seq") != expected or e.get("prev") != prev or e.get("hash") != digest(prev, _core(e)):
                return True
            prev, expected = e["hash"], expected + 1
    except (ValueError, KeyError, TypeError):
        return True
    return False


def detect_anchored(lines, anchor) -> bool:
    """Step 4: the strict chain check in audit_chain.py plus the anchor."""
    return not verify_lines(lines, anchor)["ok"]


CHECKS = {"none": detect_none, "records": detect_records, "chain": detect_chain, "anchored": detect_anchored}


def evaluate() -> dict:
    """Apply every planted edit to the untouched log and run all four checks on the result."""
    params, events, plan = load_params(), build_log(), load_plan()
    base = _dump(events)
    anchor = make_anchor(events, params["anchor_seq"])
    rows = []
    for row in plan:
        lines = apply_op(base, row)
        first = verify_lines(lines, anchor)["problems"]
        rows.append(dict(row, **{name: CHECKS[name](lines, anchor) for name in DETECTORS}, first_problem=first[0]["code"] if first else ""))
    return {"params": params, "events": len(events), "rows": rows, "anchor": anchor}


def tally(rows: list, check: str, **where) -> tuple:
    """(rows flagged by the check, rows matching) among the rows whose fields equal the keyword values."""
    sel = [r for r in rows if all(r[k] == v for k, v in where.items())]
    return sum(1 for r in sel if r[check]), len(sel)


def ops_in(rows: list, truth: str) -> list:
    return sorted({r["op"] for r in rows if r["truth"] == truth})
