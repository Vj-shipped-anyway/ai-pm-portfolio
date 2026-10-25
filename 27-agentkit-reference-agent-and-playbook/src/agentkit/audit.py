"""Append-only audit trail: one JSONL line per decision, tool call, gate, approval and route.

Each event carries the hash of the previous one, so a deleted or edited line breaks the chain. There
is no update or delete method. Time is a sequence number, never the clock, so a replay is repeatable.

Event kinds written by the kit:
  case_start   a case enters the kit
  decision     a step finished (or was skipped) and says what it decided and why
  tool_call    one per call attempt, including blocked, dry-run, replayed and failed ones
  gate         a step was routed to a person (S07, S09)
  gate_violation  a step was refused because the approval it needs was missing or did not match
  approval     a person answered a gate; the answer was accepted or rejected
  retry        a transient tool failure is being retried
  fallback     the kit gave up on a tool and sends the case back to the human queue
  kill_switch  the operator switch stopped the case
  route        terminal event of a case: auto, to_person or human_queue, with the reason
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .errors import AuditError

GENESIS = "0" * 64
KINDS = ("case_start", "decision", "tool_call", "gate", "approval", "retry", "fallback", "kill_switch", "route",
         "gate_violation")


def _digest(prev: str, core: dict) -> str:
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev + blob).encode("utf-8")).hexdigest()


class AuditLog:
    """In-memory, optionally mirrored to a JSONL file. Appending is the only write operation."""

    def __init__(self, path: Optional[Path] = None):
        self._events: List[dict] = []
        self._last = GENESIS
        self._path = Path(path) if path else None
        self._fh = None
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "w", encoding="utf-8")

    def append(self, kind: str, case_id: str, step: Optional[str] = None, actor: str = "agent", **detail) -> dict:
        if kind not in KINDS:
            raise AuditError(f"unknown audit kind {kind!r}")
        core = {"seq": len(self._events) + 1, "case_id": case_id, "step": step, "kind": kind, "actor": actor,
                "detail": detail}
        event = dict(core)
        event["prev"] = self._last
        event["hash"] = _digest(self._last, core)
        self._last = event["hash"]
        self._events.append(event)
        if self._fh:
            self._fh.write(json.dumps(event, sort_keys=True, ensure_ascii=True) + "\n")
            self._fh.flush()
        return event

    def close(self) -> None:
        if self._fh:
            self._fh.close()
            self._fh = None

    def events(self, case_id: Optional[str] = None) -> List[dict]:
        if case_id is None:
            return [dict(e) for e in self._events]
        return [dict(e) for e in self._events if e["case_id"] == case_id]

    def __len__(self) -> int:
        return len(self._events)

    def kind_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self._events:
            out[e["kind"]] = out.get(e["kind"], 0) + 1
        return dict(sorted(out.items()))


def load_jsonl(path: Path) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def verify_chain(events: Iterable[dict]):
    """Return (ok, first_bad_seq). Checks hash links and contiguous sequence numbers."""
    prev = GENESIS
    expected = 1
    for e in events:
        core = {k: e[k] for k in ("seq", "case_id", "step", "kind", "actor", "detail")}
        if e.get("seq") != expected or e.get("prev") != prev or e.get("hash") != _digest(prev, core):
            return False, e.get("seq")
        prev = e["hash"]
        expected += 1
    return True, None


def completeness(events: List[dict], expected: Dict[str, dict]):
    """Compare the log with what the run says happened.

    `expected` maps case_id to counts taken from sources other than the log itself:
      deliveries   number of times the case was delivered (default 1); each needs a case_start and a route
      steps        number of steps that produced a decision
      tool_calls   number of call attempts counted by the tool registry
      gates        number of gates opened by the orchestrator
      approvals    number of answers a person gave at a gate (accepted, declined or rejected)
    Returns a dict: ok, fraction, expected_events, found_events, missing (list), chain_ok, first_bad_seq.
    """
    chain_ok, bad = verify_chain(events)
    found: Dict[str, Dict[str, int]] = {}
    for e in events:
        c = found.setdefault(e["case_id"], {})
        c[e["kind"]] = c.get(e["kind"], 0) + 1
    exp_total = got_total = 0
    missing = []
    for case_id, exp in expected.items():
        have = found.get(case_id, {})
        n_del = exp.get("deliveries", 1)
        wants = {"case_start": n_del, "route": n_del, "decision": exp.get("steps", 0), "tool_call": exp.get("tool_calls", 0),
                 "gate": exp.get("gates", 0),
                 "approval": exp.get("approvals", 0)}
        for kind, n in wants.items():
            exp_total += n
            g = min(have.get(kind, 0), n)
            got_total += g
            if g < n:
                missing.append({"case_id": case_id, "kind": kind, "expected": n, "found": have.get(kind, 0)})
    fraction = 1.0 if exp_total == 0 else got_total / exp_total
    return {"ok": chain_ok and not missing, "fraction": round(fraction, 6), "expected_events": exp_total,
            "found_events": got_total, "missing": missing, "chain_ok": chain_ok, "first_bad_seq": bad}
