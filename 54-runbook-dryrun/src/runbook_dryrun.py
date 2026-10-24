"""runbook_dryrun: read an incident runbook written in a small YAML subset and dry-run it against a
snapshot of system state, stopping at every approval gate. Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 runbook_dryrun.py --demo
    python3 runbook_dryrun.py check RUNBOOK.yml [--format text|github]
    python3 runbook_dryrun.py dryrun RUNBOOK.yml --world WORLD.json --requester NAME
                              [--approvals APPROVALS.json] [--param name=value ...]
                              [--fail-on blocked|waiting|never] [--format text|github]

Exit status: 0 when the verdict is below --fail-on, 1 when it is at or above it, 2 for bad or malformed input.
Verdicts: READY (every precondition holds and every gate has a valid approval), WAITING (everything holds,
at least one gate has no approval record yet) and BLOCKED (a defect, a failed precondition or an invalid
approval). Nothing is ever executed: the tool renders commands, evaluates conditions against a copy of the
snapshot and applies the `sets` each step declares. It trusts those declarations; it cannot see what a
command really does. There is no model in this file.

Runbook format (YAML subset, see data/README.md): runbook, title, reads, params, steps. A step has id, title,
effect (read|write|notify), risk (low|medium|high), run, requires, sets, approval, rollback, note.
Not supported in YAML: anchors, aliases, tags, block scalars, multi-line values, several documents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

MAX_BYTES = 262144
MAX_DEPTH = 8
MAX_STEPS = 200
DEFAULT_TTL_MINUTES = 30      # assumption: how long an approval stays valid when a gate does not say
GATED_RISK = "high"           # assumption: a write at this risk needs an approval gate
ROLLBACK_RISKS = ("medium", "high")   # assumption: a write at these risks should name a rollback
EFFECTS = ("read", "write", "notify")
RISKS = ("low", "medium", "high")
DECISION_RANK = {"READY": 0, "WAITING": 1, "BLOCKED": 2}

_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_NAME = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_PARAM = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
_COND = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")
_INT = re.compile(r"^-?\d{1,15}$")
_FLOAT = re.compile(r"^-?\d{1,15}\.\d{1,15}$")
_COLON = re.compile(r":(?: |$)")
_ESC = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


class RunbookError(ValueError):
    """The input is not something this tool can read. The command line turns it into exit status 2."""


# ------------------------------------------------------------------ YAML subset
def _strip_comment(s: str) -> str:
    quote, prev, i = None, " ", 0
    while i < len(s):
        ch = s[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                if quote == "'" and s[i + 1:i + 2] == "'":
                    i += 2
                    continue
                quote = None
        elif ch in "\"'" and prev in " [{,":
            quote = ch
        elif ch == "#" and prev == " ":
            return s[:i]
        prev = ch
        i += 1
    return s


def _lines(text: str) -> list:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise RunbookError(f"file is larger than {MAX_BYTES} bytes")
    text = text.replace("\r\n", "\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in text):
        raise RunbookError("file contains a control character")
    out = []
    for no, raw in enumerate(text.split("\n"), 1):
        body = _strip_comment(raw).rstrip()
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        if body[indent] == "\t":
            raise RunbookError(f"line {no}: a tab is used for indentation")
        out.append([no, indent, body[indent:]])
    return out


def _is_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _scalar(s: str):
    if s[:1] == '"':
        out, i = [], 1
        while i < len(s):
            ch = s[i]
            if ch == "\\":
                if s[i + 1:i + 2] not in _ESC:
                    raise RunbookError(f"unsupported escape \\{s[i + 1:i + 2]}")
                out.append(_ESC[s[i + 1]])
                i += 2
                continue
            if ch == '"':
                if s[i + 1:].strip():
                    raise RunbookError("text after the closing quote")
                return "".join(out)
            out.append(ch)
            i += 1
        raise RunbookError("unterminated double quote")
    if s[:1] == "'":
        out, i = [], 1
        while i < len(s):
            if s[i] == "'":
                if s[i + 1:i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                if s[i + 1:].strip():
                    raise RunbookError("text after the closing quote")
                return "".join(out)
            out.append(s[i])
            i += 1
        raise RunbookError("unterminated single quote")
    if s[:1] in ("[", "{"):
        return _flow(s)
    if s and s[0] in "&*!|>%@`":
        raise RunbookError(f"unsupported YAML syntax starting with {s[0]!r}")
    if s == "true":
        return True
    if s == "false":
        return False
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    return s


def _flow_items(inner: str) -> list:
    items, cur, quote, prev, i = [], [], None, " ", 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            cur.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(inner):
                cur.append(inner[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'" and prev in " ,":
            quote = ch
            cur.append(ch)
        elif ch == ",":
            items.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        prev = ch
        i += 1
    if quote:
        raise RunbookError("unterminated quote inside [ ] or { }")
    items.append("".join(cur).strip())
    return items


def _flow(s: str):
    seq = s[0] == "["
    if s[-1] != ("]" if seq else "}"):
        raise RunbookError("a [ ] or { } value must close on the same line")
    inner = s[1:-1].strip()
    if not inner:
        return [] if seq else {}
    items = _flow_items(inner)
    if any(not it for it in items):
        raise RunbookError("empty item in [ ] or { }")
    if any(it[0] in "[{" for it in items):
        raise RunbookError("nested [ ] or { } is not supported")
    if seq:
        for it in items:
            if it[0] not in "\"'" and _COLON.search(it):
                raise RunbookError("quote a list item that contains ': '")
        return [_scalar(it) for it in items]
    out = {}
    for it in items:
        kv = _split_key(it)
        if kv is None or not kv[1]:
            raise RunbookError("each item in { } must read key: value")
        if kv[0] in out:
            raise RunbookError(f"duplicate key {kv[0]!r}")
        out[kv[0]] = _scalar(kv[1])
    return out


def _split_key(s: str):
    """(key, rest) when s starts a mapping entry, else None."""
    if s[0] in "\"'":
        q, i = s[0], 1
        while i < len(s):
            if s[i] == "\\" and q == '"':
                i += 2
                continue
            if s[i] == q:
                if q == "'" and s[i + 1:i + 2] == "'":
                    i += 2
                    continue
                break
            i += 1
        else:
            return None
        rest = s[i + 1:]
        if rest[:1] == ":" and (len(rest) == 1 or rest[1] == " "):
            return _scalar(s[:i + 1]), rest[1:].strip()
        return None
    if s[0] in "[{":
        return None
    m = _COLON.search(s)
    if not m or m.start() == 0:
        return None
    return s[:m.start()].strip(), s[m.end():].strip()


def _at(no: int, fn, *args):
    try:
        return fn(*args)
    except RunbookError as e:
        raise RunbookError(f"line {no}: {e}") from None


def _value(s: str, no: int):
    if s[0] not in "\"'[{" and _COLON.search(s):
        raise RunbookError(f"line {no}: quote a value that contains ': '")
    return _at(no, _scalar, s)


def _block(L: list, i: int, indent: int, depth: int):
    if depth > MAX_DEPTH:
        raise RunbookError(f"line {L[i][0]}: nesting is deeper than {MAX_DEPTH}")
    return (_seq if _is_item(L[i][2]) else _map)(L, i, indent, depth)


def _map(L: list, i: int, indent: int, depth: int):
    out = {}
    while i < len(L) and L[i][1] == indent:
        no, _, content = L[i]
        if _is_item(content):
            raise RunbookError(f"line {no}: a list item where a key was expected")
        kv = _at(no, _split_key, content)
        if kv is None:
            raise RunbookError(f"line {no}: expected 'key: value'")
        key, rest = kv
        if key in out:
            raise RunbookError(f"line {no}: duplicate key {key!r}")
        i += 1
        if rest == "":
            if i < len(L) and (L[i][1] > indent or (L[i][1] == indent and _is_item(L[i][2]))):
                out[key], i = _block(L, i, L[i][1], depth + 1)
            else:
                out[key] = None
        else:
            out[key] = _value(rest, no)
            if i < len(L) and L[i][1] > indent:
                raise RunbookError(f"line {L[i][0]}: unexpected indentation (multi-line values are not supported)")
    if i < len(L) and L[i][1] > indent:
        raise RunbookError(f"line {L[i][0]}: unexpected indentation")
    return out, i


def _seq(L: list, i: int, indent: int, depth: int):
    out = []
    while i < len(L) and L[i][1] == indent and _is_item(L[i][2]):
        no, _, content = L[i]
        rest = content[1:].lstrip(" ")
        offset = len(content) - len(rest)
        if rest == "":
            i += 1
            if i < len(L) and L[i][1] > indent:
                v, i = _block(L, i, L[i][1], depth + 1)
            else:
                v = None
            out.append(v)
        elif _is_item(rest):
            raise RunbookError(f"line {no}: a list inside a list item on one line is not supported")
        elif _at(no, _split_key, rest) is not None:
            L[i] = [no, indent + offset, rest]
            v, i = _map(L, i, indent + offset, depth + 1)
            out.append(v)
        else:
            out.append(_value(rest, no))
            i += 1
            if i < len(L) and L[i][1] > indent:
                raise RunbookError(f"line {L[i][0]}: unexpected indentation")
    if i < len(L) and L[i][1] > indent:
        raise RunbookError(f"line {L[i][0]}: unexpected indentation")
    return out, i


def parse_yaml(text: str):
    L = _lines(text)
    if L and L[0][2] == "---":
        L.pop(0)
    if not L:
        raise RunbookError("the file is empty")
    for no, _, content in L:
        if content in ("---", "..."):
            raise RunbookError(f"line {no}: several YAML documents are not supported")
    if L[0][1] != 0:
        raise RunbookError(f"line {L[0][0]}: the first line must not be indented")
    value, i = _block(L, 0, 0, 0)
    if i < len(L):
        raise RunbookError(f"line {L[i][0]}: unexpected content")
    return value


# ------------------------------------------------------------------ runbook schema
def _text(v, what: str, maxlen: int = 400) -> str:
    if not isinstance(v, str) or not v.strip():
        raise RunbookError(f"{what} must be a non-empty string")
    if len(v) > maxlen:
        raise RunbookError(f"{what} is longer than {maxlen} characters")
    return v


def _plain(v, what: str):
    if isinstance(v, (str, int, float)):
        return v
    raise RunbookError(f"{what} must be a string, number or true/false")


def _allowed(d: dict, names: tuple, what: str) -> None:
    extra = sorted(k for k in d if k not in names)
    if extra:
        raise RunbookError(f"{what}: unknown field {extra[0]!r}")


def _mapping(v, what: str) -> dict:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise RunbookError(f"{what} must be a mapping")
    return v


def _step(raw, n: int) -> dict:
    where = f"step {n}"
    if not isinstance(raw, dict):
        raise RunbookError(f"{where} must be a mapping")
    _allowed(raw, ("id", "title", "effect", "risk", "run", "requires", "sets", "approval", "rollback", "note"), where)
    sid = raw.get("id")
    if not isinstance(sid, str) or not _ID.match(sid):
        raise RunbookError(f"{where}: id must be 1 to 32 letters, digits, hyphens or underscores")
    where = f"step {sid}"
    effect, risk = raw.get("effect"), raw.get("risk")
    if effect not in EFFECTS:
        raise RunbookError(f"{where}: effect must be one of {', '.join(EFFECTS)}")
    if risk not in RISKS:
        raise RunbookError(f"{where}: risk must be one of {', '.join(RISKS)}")
    reqs = raw.get("requires")
    if reqs is None:
        reqs = []
    if not isinstance(reqs, list):
        raise RunbookError(f"{where}: requires must be a list")
    conds = []
    for c in reqs:
        m = _COND.match(c) if isinstance(c, str) else None
        if not m:
            raise RunbookError(f"{where}: a condition must read 'key == value' (also !=, >=, <=, >, <)")
        try:
            want = _scalar(m.group(3))
        except RunbookError as e:
            raise RunbookError(f"{where}: condition value: {e}") from None
        conds.append((m.group(1), m.group(2), _plain(want, f"{where}: condition value")))
    sets = _mapping(raw.get("sets"), f"{where}: sets")
    for k, v in sets.items():
        if not _KEY.match(str(k)):
            raise RunbookError(f"{where}: sets key {str(k)[:40]!r} is not a plain key")
        _plain(v, f"{where}: sets value")
    approval = raw.get("approval")
    if approval is not None:
        approval = _mapping(approval, f"{where}: approval")
        _allowed(approval, ("role", "ttl_minutes"), f"{where}: approval")
        ttl = approval.get("ttl_minutes", DEFAULT_TTL_MINUTES)
        if isinstance(ttl, bool) or not isinstance(ttl, int) or not 1 <= ttl <= 10080:
            raise RunbookError(f"{where}: approval ttl_minutes must be a whole number from 1 to 10080")
        approval = {"role": _text(approval.get("role"), f"{where}: approval role", 80), "ttl_minutes": ttl}
    rollback = raw.get("rollback")
    if rollback is not None:
        rollback = _text(rollback, f"{where}: rollback (a command, or the word none)")
    return {"id": sid, "title": "" if raw.get("title") is None else _text(raw["title"], f"{where}: title"),
            "effect": effect, "risk": risk, "run": _text(raw.get("run"), f"{where}: run", 500),
            "requires": conds, "sets": dict(sets), "approval": approval, "rollback": rollback,
            "note": "" if raw.get("note") is None else _text(raw["note"], f"{where}: note")}


def load_runbook(text: str) -> dict:
    doc = parse_yaml(text)
    if not isinstance(doc, dict):
        raise RunbookError("a runbook must be a mapping at the top level")
    _allowed(doc, ("runbook", "title", "reads", "params", "steps"), "runbook")
    rid = doc.get("runbook")
    if not isinstance(rid, str) or not _ID.match(rid):
        raise RunbookError("runbook: the id must be 1 to 32 letters, digits, hyphens or underscores")
    reads = doc.get("reads")
    if reads is None:
        reads = []
    if not isinstance(reads, list) or any(not isinstance(k, str) or not _KEY.match(k) for k in reads):
        raise RunbookError("reads must be a list of plain state keys")
    params = _mapping(doc.get("params"), "params")
    for name, v in params.items():
        if not _NAME.match(str(name)):
            raise RunbookError(f"params: name {str(name)[:40]!r} must be letters, digits or underscores")
        _plain(v, f"params {name}")
    steps = doc.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RunbookError("steps must be a non-empty list")
    if len(steps) > MAX_STEPS:
        raise RunbookError(f"more than {MAX_STEPS} steps")
    return {"runbook": rid, "title": "" if doc.get("title") is None else _text(doc["title"], "title"),
            "reads": list(reads), "params": dict(params), "steps": [_step(s, n) for n, s in enumerate(steps, 1)]}


# ------------------------------------------------------------------ rendering, lint, gates, state
def _show(v) -> str:
    return ("true" if v else "false") if isinstance(v, bool) else str(v)


def render(text: str, params: dict) -> str:
    """Fill {{name}}; a name that is not in params is left as written so it stays visible."""
    return _PARAM.sub(lambda m: _show(params[m.group(1)]) if m.group(1) in params else m.group(0), text)


def digest(runbook_id: str, step_id: str, rendered: str) -> str:
    """What an approval binds to: the runbook, the step and the exact command after parameters are filled in."""
    return hashlib.sha256(f"{runbook_id}\n{step_id}\n{rendered}".encode("utf-8")).hexdigest()[:12]


def _finding(kind: str, severity: str, step: str, reason: str) -> dict:
    return {"kind": kind, "severity": severity, "step": step, "reason": reason}


def lint(rb: dict) -> list:
    """Defects visible in the runbook alone, with no snapshot and no approvals."""
    out, seen, produced, reads = [], set(), set(), set(rb["reads"])
    for st in rb["steps"]:
        sid = st["id"]
        if sid in seen:
            out.append(_finding("duplicate_id", "error", sid, f"a second step is called {sid}; an approval cannot tell them apart"))
        seen.add(sid)
        texts = [("run", st["run"])]
        if st["rollback"] not in (None, "none"):
            texts.append(("rollback", st["rollback"]))
        for where, text in texts:
            for name in sorted(set(_PARAM.findall(text))):
                if name not in rb["params"]:
                    out.append(_finding("undefined_param", "error", sid, f"{where} uses {{{{{name}}}}}, which params does not define"))
        for key, _, _ in st["requires"]:
            if key not in reads and key not in produced:
                out.append(_finding("undeclared_state_key", "error", sid, f"requires {key}, which is neither in reads nor set by an earlier step"))
        if st["effect"] == "write" and st["risk"] == GATED_RISK and st["approval"] is None:
            out.append(_finding("write_ungated", "error", sid, f"a {GATED_RISK}-risk write has no approval gate"))
        if st["effect"] == "write" and st["risk"] in ROLLBACK_RISKS and st["rollback"] is None:
            out.append(_finding("no_rollback", "warning", sid, "a write at this risk names no rollback (write `rollback: none` to say there is none)"))
        produced.update(st["sets"])
    return out


def _kind(v) -> str:
    return "bool" if isinstance(v, bool) else "number" if isinstance(v, (int, float)) else "text"


def _compare(actual, op: str, want):
    """(True or False, None), or (None, reason) when the two values cannot be compared."""
    if _kind(actual) != _kind(want):
        return None, f"cannot compare {_kind(actual)} {actual!r} with {_kind(want)} {want!r}"
    if op in ("==", "!="):
        return (actual == want) == (op == "=="), None
    if _kind(actual) != "number":
        return None, f"{op} needs numbers, not {_kind(actual)}"
    return {">=": actual >= want, "<=": actual <= want, ">": actual > want, "<": actual < want}[op], None


def _same_person(a: str, b: str) -> bool:
    return a.strip().casefold() == b.strip().casefold()


def _reject_reason(rec: dict, gate: dict, want_digest: str, requester: str):
    if _same_person(rec["approver"], requester):
        return "self_approval (the approver is the requester)"
    if rec["role"] != gate["role"]:
        return f"wrong_role (has {rec['role']}, gate needs {gate['role']})"
    if rec["digest"] != want_digest:
        return f"digest_mismatch (approved {rec['digest']}, this rendering is {want_digest})"
    if rec["age_minutes"] > gate["ttl_minutes"]:
        return f"stale_approval ({rec['age_minutes']} min old, limit {gate['ttl_minutes']})"
    return None


def _gate(step: dict, want_digest: str, approvals: list, requester: str):
    """('ok'|'waiting'|'rejected', reasons) for one gated step."""
    recs = [a for a in approvals if a["step"] == step["id"]]
    if not recs:
        return "waiting", []
    reasons = []
    for a in recs:
        why = _reject_reason(a, step["approval"], want_digest, requester)
        if why is None:
            return "ok", []
        reasons.append(f"{a['approver']}: {why}")
    return "rejected", reasons


def dry_run(rb: dict, world: dict, params: dict, approvals: list, requester: str,
            checks: tuple = ("lint", "state", "gate")) -> dict:
    """Walk the steps in order against a copy of the snapshot. Nothing runs. `checks` picks the parts to apply."""
    run_params = dict(rb["params"])
    run_params.update(params)
    findings = lint(rb) if "lint" in checks else []
    notes, state, set_by, rows, stopped = [], dict(world), {}, [], False
    gates = [st for st in rb["steps"] if st["approval"] is not None]
    if "state" in checks and not any(st["requires"] for st in rb["steps"]):
        notes.append("no step has a requires condition, so the snapshot was not read")
    if "gate" in checks:
        ids = {st["id"] for st in gates}
        for a in approvals:
            if a["step"] not in ids:
                findings.append(_finding("approval_unmatched", "warning", a["step"], f"{a['approver']} approved a step that has no gate"))
    for st in rb["steps"]:
        rendered = render(st["run"], run_params)
        row = {"id": st["id"], "effect": st["effect"], "risk": st["risk"], "run": rendered, "status": "ok", "gate": None}
        rows.append(row)
        if stopped:
            row["status"] = "not reached"
            continue
        if "state" in checks:
            for key, op, want in st["requires"]:
                if key not in state:
                    findings.append(_finding("state_unknown", "error", st["id"], f"requires {key}, which the snapshot does not hold and no earlier step sets"))
                    stopped = True
                    break
                ok, why = _compare(state[key], op, want)
                if ok is None:
                    findings.append(_finding("state_type_mismatch", "error", st["id"], f"requires {key} {op} {want!r}: {why}"))
                    stopped = True
                    break
                if not ok:
                    by = f" (set by {set_by[key]})" if key in set_by else ""
                    findings.append(_finding("precondition_false", "error", st["id"], f"requires {key} {op} {want!r}; the state holds {state[key]!r}{by}"))
                    stopped = True
                    break
            if stopped:
                row["status"] = "STOPS"
                continue
        if st["approval"] is not None and "gate" in checks:
            d = digest(rb["runbook"], st["id"], rendered)
            outcome, reasons = _gate(st, d, approvals, requester)
            row["gate"] = {"role": st["approval"]["role"], "ttl_minutes": st["approval"]["ttl_minutes"], "digest": d}
            if outcome == "waiting":
                row["status"] = "WAITING"
            elif outcome == "rejected":
                row["status"] = "REJECTED"
                for why in reasons:
                    findings.append(_finding("approval_invalid", "error", st["id"], why))
        if "state" in checks:
            state.update(st["sets"])
            set_by.update({k: st["id"] for k in st["sets"]})
    if any(f["severity"] == "error" for f in findings):
        verdict = "BLOCKED"
    elif any(r["status"] == "WAITING" for r in rows):
        verdict = "WAITING"
    else:
        verdict = "READY"
    return {"verdict": verdict, "rows": rows, "findings": findings, "notes": notes}


# ------------------------------------------------------------------ input files and output
def safe(value) -> str:
    """Printable text only: a newline or control character in input cannot start a new output line."""
    out = []
    for c in str(value):
        if c.isprintable():
            out.append(c)
        elif ord(c) < 256:
            out.append(f"\\x{ord(c):02x}")
        else:
            out.append(f"\\u{ord(c):04x}" if ord(c) <= 0xFFFF else f"\\U{ord(c):08x}")
    return "".join(out)


def escape_annotation(text) -> str:
    """Escape a workflow-command message the way GitHub documents, so input text cannot start a new command."""
    return str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _read(path: str) -> str:
    if os.path.getsize(path) > MAX_BYTES:
        raise RunbookError(f"{path}: file is larger than {MAX_BYTES} bytes")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _no_constants(name: str):
    raise ValueError(f"{name} is not a valid JSON value here")


def load_world(path: str) -> dict:
    obj = json.loads(_read(path), parse_constant=_no_constants)
    if not isinstance(obj, dict):
        raise RunbookError(f"{path}: the world file must be a JSON object of key: value")
    for k, v in obj.items():
        _plain(v, f"{path}: value of {safe(k)[:40]!r}")
    return obj


def load_approvals(path: str) -> list:
    obj = json.loads(_read(path), parse_constant=_no_constants)
    if not isinstance(obj, list):
        raise RunbookError(f"{path}: the approvals file must be a JSON list of records")
    for n, rec in enumerate(obj, 1):
        if not isinstance(rec, dict):
            raise RunbookError(f"{path}: record {n} must be an object")
        for field in ("step", "approver", "role", "digest"):
            if not isinstance(rec.get(field), str) or not rec[field].strip():
                raise RunbookError(f"{path}: record {n} needs a non-empty text field {field!r}")
        age = rec.get("age_minutes")
        if isinstance(age, bool) or not isinstance(age, int) or age < 0:
            raise RunbookError(f"{path}: record {n} needs age_minutes as a whole number of 0 or more")
    return obj


def parse_params(rb: dict, pairs: list) -> dict:
    out = {}
    for p in pairs:
        name, sep, val = p.partition("=")
        if not sep or name not in rb["params"]:
            raise RunbookError(f"--param {safe(p)[:60]!r}: use name=value with a name the runbook declares under params")
        out[name] = val
    return out


def render_text(rb: dict, requester: str, res: dict) -> str:
    lines = [f"runbook: {safe(rb['runbook'])}   {len(rb['steps'])} steps   requester: {safe(requester)}"]
    for r in res["rows"]:
        lines.append(f"  {safe(r['id']):<4} {r['effect']:<6} {r['risk']:<6} {r['status']:<11} {safe(r['run'])}")
        if r["gate"]:
            lines.append(f"       gate {safe(r['gate']['role'])}, {r['gate']['ttl_minutes']} min, digest {r['gate']['digest']}")
    for n in res["notes"]:
        lines.append(f"note: {n}")
    if res["findings"]:
        lines.append("findings:")
        for f in res["findings"]:
            lines.append(f"  {f['severity']:<7} {f['kind']:<21} {safe(f['step']):<4} {safe(f['reason'])}")
    else:
        lines.append("findings: none")
    waiting = next((r["id"] for r in res["rows"] if r["status"] == "WAITING"), None)
    lines.append(f"verdict: {res['verdict']}" + (f" at {safe(waiting)}" if res["verdict"] == "WAITING" and waiting else ""))
    return "\n".join(lines)


def render_github(rb: dict, res: dict) -> str:
    lines = []
    for f in res["findings"]:
        level = "error" if f["severity"] == "error" else "warning"
        lines.append(f"::{level} title=runbook-dryrun {f['kind']}::" + escape_annotation(f"{rb['runbook']} {f['step']}: {f['reason']}"))
    lines.append(f"::notice title=runbook-dryrun::{escape_annotation(rb['runbook'])} verdict {res['verdict']}")
    return "\n".join(lines)


def run_check(path: str, fmt: str) -> int:
    try:
        rb = load_runbook(_read(path))
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {safe(e)}", file=sys.stderr)
        return 2
    found = lint(rb)
    errors = sum(1 for f in found if f["severity"] == "error")
    res = {"verdict": "BLOCKED" if errors else "READY", "rows": [], "findings": found, "notes": []}
    if fmt == "github":
        print(render_github(rb, res))
    else:
        print(f"runbook: {safe(rb['runbook'])}   {len(rb['steps'])} steps")
        for f in found:
            print(f"  {f['severity']:<7} {f['kind']:<21} {safe(f['step']):<4} {safe(f['reason'])}")
        print(f"check: {errors} errors, {len(found) - errors} warnings")
    return 1 if errors else 0


def run_dryrun(path: str, world_path: str, approvals_path, requester: str, param_pairs: list, fail_on: str, fmt: str) -> int:
    try:
        rb = load_runbook(_read(path))
        world = load_world(world_path)
        approvals = load_approvals(approvals_path) if approvals_path else []
        params = parse_params(rb, param_pairs)
        if not requester.strip():
            raise RunbookError("--requester must name the person who asked for the change")
        res = dry_run(rb, world, params, approvals, requester)
        out = render_github(rb, res) if fmt == "github" else render_text(rb, requester, res)
    except (OSError, ValueError, RecursionError) as e:
        print(f"input error: {safe(e)}", file=sys.stderr)
        return 2
    print(out)
    if fail_on == "never":
        return 0
    return 1 if DECISION_RANK[res["verdict"]] >= DECISION_RANK[fail_on.upper()] else 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"usage error: {message}", file=sys.stderr)
        raise SystemExit(2)


def main(argv=None) -> int:
    ap = _Parser(prog="runbook_dryrun")
    ap.add_argument("--demo", action="store_true", help="dry-run the bundled example (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="lint one runbook, no snapshot needed")
    c.add_argument("runbook")
    c.add_argument("--format", choices=["text", "github"], default="text")
    d = sub.add_parser("dryrun", help="walk a runbook against a state snapshot and approval records")
    d.add_argument("runbook")
    d.add_argument("--world", required=True, help="JSON object of state key: value")
    d.add_argument("--requester", required=True, help="who asked for the change; cannot approve it")
    d.add_argument("--approvals", help="JSON list of approval records")
    d.add_argument("--param", action="append", default=[], help="name=value, overrides a runbook param")
    d.add_argument("--fail-on", choices=["blocked", "waiting", "never"], default="blocked")
    d.add_argument("--format", choices=["text", "github"], default="text")
    a = ap.parse_args(argv)
    if a.demo:
        data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
        return run_dryrun(os.path.join(data, "example_runbook.yml"), os.path.join(data, "example_world.json"),
                          os.path.join(data, "example_approvals.json"), "dana", [], "never", "text")
    if a.cmd == "check":
        return run_check(a.runbook, a.format)
    if a.cmd == "dryrun":
        return run_dryrun(a.runbook, a.world, a.approvals, a.requester, a.param, a.fail_on, a.format)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
