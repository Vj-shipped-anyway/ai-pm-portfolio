"""audit_chain: an append-only, hash-chained audit log for agent actions, and a command that verifies it.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 audit_chain.py --demo
    python3 audit_chain.py verify LOG [--anchor ANCHOR]
    python3 audit_chain.py anchor LOG [--seq N] [--out FILE]
    python3 audit_chain.py append LOG --case ID --kind KIND [--step S] [--actor A] [--detail JSON]

Exit status of verify: 0 when nothing in the log shows a sign of alteration, 1 when it does, 2 when the
command could not run (a missing, unreadable or empty log, a bad anchor, bad arguments). A line that is
cut off, not JSON, or not an event counts as a sign of alteration, because that is what a damaged log is.

Each event carries the hash of the one before it, so an edited, removed or reordered event breaks the
chain. The chain alone cannot see two things: events cut from the end of the log, and a rewrite that
recomputes every hash after the edit. An anchor (the sequence number and hash of one event, kept
somewhere the log's writer cannot edit) catches both, for everything up to the anchored event. Events
written after the last anchor are protected only by the chain.

Taken from the AgentKit audit module (project 27): the event layout, the event kinds and the hash.
Changed: detail is a dict argument, not keyword arguments, so a detail key can never collide with a
parameter name; the log is verified strictly (see verify_lines); an anchor can be taken and checked.
Time is a sequence number, never the clock, so a replay is repeatable.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from typing import Iterable, List, Optional

GENESIS = "0" * 64
KINDS = ("case_start", "decision", "tool_call", "gate", "approval", "retry", "fallback", "kill_switch", "route",
         "gate_violation")
CORE_KEYS = ("seq", "case_id", "step", "kind", "actor", "detail")
EVENT_KEYS = CORE_KEYS + ("prev", "hash")
ANCHOR_VERSION = 1
MAX_SHOWN = 10
_HEX = frozenset("0123456789abcdef")


class AuditError(ValueError):
    """An event the writer refuses to append."""


class InputError(Exception):
    """The command cannot run: unreadable file, empty log, bad anchor or bad arguments. Exit status 2."""


class _Bad(Exception):
    """One line of the log is not a well-formed event."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- printing untrusted text
def escape(text) -> str:
    """Make text safe on one output line. Percent becomes %25, and every control or unprintable character
    becomes %XX (a line feed is %0A, a carriage return %0D), the way GitHub escapes workflow-command data."""
    out = []
    for ch in str(text):
        if ch == "%":
            out.append("%25")
        elif not ch.isprintable():
            code = ord(ch)
            out.append("%%%02X" % code if code < 256 else "%%u%04X" % code)
        else:
            out.append(ch)
    return "".join(out)


def _q(text) -> str:
    s = str(text)
    return "'" + escape(s if len(s) <= 40 else s[:40] + "...") + "'"


# ---------------------------------------------------------------- the writer
def digest(prev: str, core: dict) -> str:
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()


def dumps_event(event: dict) -> str:
    """One line of the log file: sorted keys, ASCII only, no line breaks."""
    return json.dumps(event, sort_keys=True, ensure_ascii=True, allow_nan=False)


class AuditLog:
    """In memory. Appending is the only write operation: there is no update, delete or insert."""

    def __init__(self, events: Optional[Iterable[dict]] = None):
        self._events = [copy.deepcopy(e) for e in (events or [])]
        self._last = self._events[-1]["hash"] if self._events else GENESIS

    def append(self, kind: str, case_id: str, step: Optional[str] = None, actor: str = "agent",
               detail: Optional[dict] = None) -> dict:
        if kind not in KINDS:
            raise AuditError("unknown audit kind " + _q(kind))
        if not isinstance(case_id, str) or not case_id:
            raise AuditError("case_id must be a non-empty string")
        if step is not None and not isinstance(step, str):
            raise AuditError("step must be a string or absent")
        if not isinstance(actor, str) or not actor:
            raise AuditError("actor must be a non-empty string")
        if detail is None:
            detail = {}
        if not isinstance(detail, dict):
            raise AuditError("detail must be a JSON object")
        try:
            detail = json.loads(json.dumps(detail, allow_nan=False))
        except (TypeError, ValueError, RecursionError) as e:
            raise AuditError("detail cannot be stored as JSON: " + escape(e))
        core = {"seq": len(self._events) + 1, "case_id": case_id, "step": step, "kind": kind, "actor": actor,
                "detail": detail}
        event = dict(core)
        event["prev"] = self._last
        event["hash"] = digest(self._last, core)
        self._last = event["hash"]
        self._events.append(event)
        return copy.deepcopy(event)

    def events(self) -> List[dict]:
        return copy.deepcopy(self._events)

    def __len__(self) -> int:
        return len(self._events)


# ---------------------------------------------------------------- the verifier
def _reject_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise _Bad("duplicate_key", "key " + _q(k) + " appears twice in one object; a reader that keeps the first would see another value")
        out[k] = v
    return out


def _finite(text: str) -> float:
    v = float(text)
    if not math.isfinite(v):
        raise _Bad("not_json", "a number is outside the range JSON allows")
    return v


def _no_constant(name: str):
    raise _Bad("not_json", name + " is not valid JSON")


def _parse_line(raw):
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise _Bad("not_json", "the line is not valid UTF-8")
    else:
        text = raw
    try:
        return json.loads(text, object_pairs_hook=_reject_pairs, parse_float=_finite, parse_constant=_no_constant)
    except RecursionError:
        raise _Bad("not_json", "the line is nested too deeply to be an event")
    except ValueError:
        raise _Bad("not_json", "the line is not valid JSON (cut off or edited by hand)")


def _is_hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in _HEX for c in v)


def _check_event(obj) -> dict:
    if not isinstance(obj, dict):
        raise _Bad("not_object", "the line is not a JSON object")
    missing = [k for k in EVENT_KEYS if k not in obj]
    if missing:
        raise _Bad("missing_field", "missing " + ", ".join(missing))
    extra = sorted(k for k in obj if k not in EVENT_KEYS)
    if extra:
        raise _Bad("extra_field", "field outside the hash: " + ", ".join(_q(k) for k in extra))
    if not isinstance(obj["seq"], int) or isinstance(obj["seq"], bool):
        raise _Bad("bad_field", "seq is not an integer")
    for k in ("case_id", "kind", "actor"):
        if not isinstance(obj[k], str):
            raise _Bad("bad_field", k + " is not a string")
    if obj["step"] is not None and not isinstance(obj["step"], str):
        raise _Bad("bad_field", "step is not a string")
    if not isinstance(obj["detail"], dict):
        raise _Bad("bad_field", "detail is not an object")
    if not _is_hex64(obj["prev"]) or not _is_hex64(obj["hash"]):
        raise _Bad("bad_field", "prev or hash is not 64 lowercase hex digits")
    if obj["kind"] not in KINDS:
        raise _Bad("unknown_kind", "the event kind " + _q(obj["kind"]) + " is not one the writer produces")
    return obj


def _blank(raw) -> bool:
    return not raw.strip(b" \t\r\n" if isinstance(raw, bytes) else " \t\r\n")


def _strip_bom(raw):
    if isinstance(raw, bytes):
        return raw[3:] if raw.startswith(b"\xef\xbb\xbf") else raw
    return raw[1:] if raw.startswith("﻿") else raw


def _problem(line: int, seq: Optional[int], code: str, message: str) -> dict:
    return {"line": line, "seq": seq, "code": code, "message": message}


def verify_lines(lines, anchor: Optional[dict] = None) -> dict:
    """Check a log given as a sequence of lines (bytes or str). Blank lines are skipped, a leading byte-order
    mark and trailing carriage returns are tolerated, key order and escaping do not matter.

    Strict on purpose: a duplicate key, a field outside the hash, an unknown event kind, NaN or an
    out-of-range number each count as a problem, because each lets a line parse to one value for this
    check and another for a different reader.

    Returns {"ok", "events", "head", "problems", "parsed"}. Each problem is {"line", "seq", "code", "message"}.
    """
    problems, parsed, positions = [], [], []
    expected_seq, expected_prev, count = 1, GENESIS, 0
    for no, raw in enumerate(lines, start=1):
        if no == 1:
            raw = _strip_bom(raw)
        if _blank(raw):
            continue
        count += 1
        try:
            ev = _check_event(_parse_line(raw))
        except _Bad as bad:
            problems.append(_problem(no, None, bad.code, bad.message))
            expected_seq += 1
            expected_prev = None
            continue
        if ev["seq"] != expected_seq:
            problems.append(_problem(no, ev["seq"], "seq_gap", "sequence number is %d, expected %d" % (ev["seq"], expected_seq)))
        if expected_prev is not None and ev["prev"] != expected_prev:
            problems.append(_problem(no, ev["seq"], "link_broken", "prev does not match the hash of the event before it"))
        if ev["hash"] != digest(ev["prev"], {k: ev[k] for k in CORE_KEYS}):
            problems.append(_problem(no, ev["seq"], "hash_mismatch", "hash does not match the event content"))
        parsed.append(ev)
        positions.append(no)
        expected_seq, expected_prev = ev["seq"] + 1, ev["hash"]
    if count == 0 and anchor is None:
        problems.append(_problem(0, None, "empty", "no events, so there is nothing to verify"))
    if anchor is not None:
        n = anchor["seq"]
        if len(parsed) < n:
            problems.append(_problem(0, None, "shorter_than_anchor", "only %d readable events, but the anchor was taken at event %d; events were removed or cannot be read" % (len(parsed), n)))
        elif parsed[n - 1]["hash"] != anchor["hash"]:
            problems.append(_problem(positions[n - 1], parsed[n - 1]["seq"], "anchor_mismatch", "event %d no longer has the hash the anchor recorded; something at or before it changed" % n))
    return {"ok": not problems, "events": count, "head": parsed[-1]["hash"] if parsed else None, "problems": problems,
            "parsed": parsed}


def make_anchor(events: List[dict], seq: Optional[int] = None) -> dict:
    """The anchor for event number seq (the last event when seq is absent) of a log that already verifies."""
    n = len(events) if seq is None else seq
    if n < 1 or n > len(events):
        raise ValueError("seq %d is outside 1..%d" % (n, len(events)))
    return {"version": ANCHOR_VERSION, "seq": n, "hash": events[n - 1]["hash"]}


def load_anchor(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except OSError as e:
        raise InputError("cannot read anchor %s: %s" % (escape(path), escape(e.strerror or "error")))
    except (ValueError, RecursionError):
        raise InputError("anchor %s is not valid JSON" % escape(path))
    if (not isinstance(obj, dict) or obj.get("version") != ANCHOR_VERSION or not isinstance(obj.get("seq"), int)
            or isinstance(obj.get("seq"), bool) or obj["seq"] < 1 or not _is_hex64(obj.get("hash"))):
        raise InputError("anchor %s must be an object with version 1, an integer seq of 1 or more and a 64-digit hash" % escape(path))
    return obj


# ---------------------------------------------------------------- command line
def read_lines(path: str) -> List[bytes]:
    try:
        with open(path, "rb") as fh:
            return fh.read().split(b"\n")
    except OSError as e:
        raise InputError("cannot read %s: %s" % (escape(path), escape(e.strerror or "error")))


def render(path: str, report: dict, anchor: Optional[dict]) -> str:
    head = report["head"][:16] if report["head"] else "none"
    out = ["verify: %s   %d events   head %s" % (escape(path), report["events"], head)]
    shown = report["problems"][:MAX_SHOWN]
    for p in shown:
        if p["line"]:
            where = "line %d" % p["line"] + (" (seq %d)" % p["seq"] if p["seq"] is not None else "")
        else:
            where = "log"
        out.append("  %s: %s" % (where, p["message"]))
    if len(report["problems"]) > len(shown):
        out.append("  ... and %d more" % (len(report["problems"]) - len(shown)))
    if report["ok"]:
        if anchor is not None:
            out.append("  anchor at event %d: hash matches" % anchor["seq"])
        else:
            out.append("  note: no anchor given, so events removed from the end of the log would not be noticed")
        out.append("verdict: OK")
    else:
        n = len(report["problems"])
        out.append("verdict: ALTERED (%d problem%s)" % (n, "" if n == 1 else "s"))
    return "\n".join(out)


def _verified(path: str, anchor: Optional[dict]) -> dict:
    report = verify_lines(read_lines(path), anchor)
    if any(p["code"] == "empty" for p in report["problems"]):
        raise InputError("%s has no events, so there is nothing to verify (a log that was emptied looks the same without an anchor)" % escape(path))
    return report


def run_verify(log_path: str, anchor_path: Optional[str]) -> int:
    anchor = load_anchor(anchor_path) if anchor_path else None
    report = _verified(log_path, anchor)
    print(render(log_path, report, anchor))
    return 0 if report["ok"] else 1


def run_anchor(log_path: str, seq: Optional[int], out_path: Optional[str]) -> int:
    report = _verified(log_path, None)
    if not report["ok"]:
        print(render(log_path, report, None))
        print("refusing to anchor a log that does not verify", file=sys.stderr)
        return 1
    try:
        anchor = make_anchor(report["parsed"], seq)
    except ValueError as e:
        raise InputError("--seq: " + escape(e))
    text = json.dumps(anchor, sort_keys=True, indent=1) + "\n"
    if out_path is None:
        sys.stdout.write(text)
        return 0
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as e:
        raise InputError("cannot write %s: %s" % (escape(out_path), escape(e.strerror or "error")))
    print("anchor: event %d, hash %s, written to %s" % (anchor["seq"], anchor["hash"][:16], escape(out_path)))
    return 0


def run_append(path: str, case_id: str, kind: str, step: Optional[str], actor: str, detail_text: Optional[str]) -> int:
    detail = None
    if detail_text is not None:
        try:
            detail = json.loads(detail_text)
        except (ValueError, RecursionError):
            raise InputError("--detail is not valid JSON")
    data = b""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        pass
    except OSError as e:
        raise InputError("cannot read %s: %s" % (escape(path), escape(e.strerror or "error")))
    report = verify_lines(data.split(b"\n"))
    if [p for p in report["problems"] if p["code"] != "empty"]:
        print(render(path, report, None))
        print("refusing to append to a log that does not verify", file=sys.stderr)
        return 1
    try:
        event = AuditLog(report["parsed"]).append(kind, case_id, step, actor, detail)
    except AuditError as e:
        raise InputError(str(e))
    payload = (b"\n" if data and not data.endswith(b"\n") else b"") + dumps_event(event).encode("ascii") + b"\n"
    try:
        with open(path, "ab") as fh:
            fh.write(payload)
    except OSError as e:
        raise InputError("cannot write %s: %s" % (escape(path), escape(e.strerror or "error")))
    print("appended event %d, hash %s" % (event["seq"], event["hash"][:16]))
    return 0


def run_demo() -> int:
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    anchor = load_anchor(os.path.join(data, "example_anchor.json"))
    for title, name in (("a log nobody touched", "example_log.jsonl"),
                        ("one approval changed after the fact", "example_log_edited.jsonl"),
                        ("the last 10 events removed", "example_log_cut.jsonl")):
        print("[%s]" % title)
        print(render(name, verify_lines(read_lines(os.path.join(data, name)), anchor), anchor))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="audit_chain")
    ap.add_argument("--demo", action="store_true", help="verify the bundled sample logs (data/example_*)")
    sub = ap.add_subparsers(dest="cmd")
    v = sub.add_parser("verify", help="check a log; exit 1 when it shows a sign of alteration")
    v.add_argument("log")
    v.add_argument("--anchor", help="anchor file taken earlier with the anchor command")
    a = sub.add_parser("anchor", help="print (or write) the anchor for an event of a log that verifies")
    a.add_argument("log")
    a.add_argument("--seq", type=int, help="event number to anchor (default: the last event)")
    a.add_argument("--out", help="write the anchor to this file instead of printing it")
    p = sub.add_parser("append", help="add one event to a log (creates it when absent)")
    p.add_argument("log")
    p.add_argument("--case", required=True, dest="case_id")
    p.add_argument("--kind", required=True)
    p.add_argument("--step")
    p.add_argument("--actor", default="agent")
    p.add_argument("--detail", help="a JSON object")
    args = ap.parse_args(argv)
    try:
        if args.demo:
            return run_demo()
        if args.cmd == "verify":
            return run_verify(args.log, args.anchor)
        if args.cmd == "anchor":
            return run_anchor(args.log, args.seq, args.out)
        if args.cmd == "append":
            return run_append(args.log, args.case_id, args.kind, args.step, args.actor, args.detail)
    except InputError as e:
        print("input error: %s" % e, file=sys.stderr)
        return 2
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
