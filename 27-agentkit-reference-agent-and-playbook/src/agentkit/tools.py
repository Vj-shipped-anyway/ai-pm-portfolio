"""Tool registry: every tool declares its access (read or write) and its allowed actions, and every call
is checked against the brief's scope before it runs.

What a call goes through, in order:
  1. kill switch      engaged: the call is refused
  2. scope            the tool and action must be in the brief; otherwise ScopeError, logged, never run
  3. approval         a write that needs a person's approval (the payments gateway) refuses without one
  4. idempotency      a write whose key was already used returns the first answer and does not run again
  5. fault injection  a scheduled timeout is raised here (also in dry-run, so the call path is exercised)
  6. dry run          in shadow mode a write is acknowledged, never executed
  7. run + validate   the handler runs; its answer must match the declared output shape
Exactly one `tool_call` audit event is written per call, whatever happens.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Optional

from .audit import AuditLog
from .brief import ToolScope, scope_violation
from .errors import (GateViolation, KillSwitchEngaged, NotFoundError, ScopeError, ToolOutputError, ToolTimeout)

READ, WRITE = "read", "write"


@dataclass
class Tool:
    """A tool the kit may call. `access` and `allowed_actions` are checked against the brief."""
    name: str
    access: str
    allowed_actions: FrozenSet[str]
    handlers: Dict[str, Callable]
    output_schema: Dict[str, Dict[str, object]] = field(default_factory=dict)
    dry_run_handlers: Dict[str, Callable] = field(default_factory=dict)
    requires_approval: FrozenSet[str] = frozenset()
    forwards_key: FrozenSet[str] = frozenset()    # actions whose handler also receives the idempotency key

    def __post_init__(self):
        if self.access not in (READ, WRITE):
            raise ValueError(f"tool {self.name!r}: access must be 'read' or 'write'")
        self.allowed_actions = frozenset(self.allowed_actions)
        missing = self.allowed_actions - set(self.handlers)
        if missing:
            raise ValueError(f"tool {self.name!r}: no handler for {sorted(missing)}")


def validate_output(schema: Dict[str, object], result) -> Optional[str]:
    """None if `result` matches the declared shape, else the first problem."""
    if not isinstance(result, dict):
        return "answer is not an object"
    for key, typ in schema.items():
        if key not in result:
            return f"missing field {key!r}"
        v = result[key]
        if typ is not bool and isinstance(v, bool):
            return f"field {key!r} has the wrong type"
        if not isinstance(v, typ):
            return f"field {key!r} has the wrong type"
    return None


def _params_digest(params: dict) -> str:
    blob = json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class ToolRegistry:
    def __init__(self, tools: Dict[str, Tool], scope: Dict[str, ToolScope], audit: AuditLog, *, faults=None,
                 killswitch=None, mode: str = "shadow"):
        if mode not in ("shadow", "live"):
            raise ValueError("mode must be 'shadow' or 'live'")
        self.audit = audit
        self.faults = faults
        self.killswitch = killswitch
        self.mode = mode
        self.scope = scope
        # A tool that declares more than the brief allows is a configuration error, caught at build time.
        for name, tool in tools.items():
            if name in scope and scope[name].access != tool.access:
                raise ScopeError(f"tool {name!r} declares access {tool.access!r} but the brief says "
                                 f"{scope[name].access!r}")
        self.tools = dict(tools)
        self.calls_by_case: Dict[str, int] = {}
        self.blocked = 0
        self.executed = 0
        self._attempts: Dict[tuple, int] = {}
        self._replay: Dict[str, dict] = {}

    # ------------------------------------------------------------------------------------------
    def call(self, tool: str, action: str, params: Optional[dict] = None, *, case_id: str, step: Optional[str],
             idempotency_key: Optional[str] = None, approval=None) -> dict:
        params = dict(params or {})
        self.calls_by_case[case_id] = self.calls_by_case.get(case_id, 0) + 1
        akey = (case_id, tool, action)
        self._attempts[akey] = attempt = self._attempts.get(akey, 0) + 1
        rec = {"tool": tool, "action": action, "outcome": "error", "attempt": attempt,
               "param_keys": sorted(params), "params_digest": _params_digest(params)}
        if idempotency_key:
            rec["idempotency_key"] = idempotency_key
        try:
            if self.killswitch is not None and self.killswitch.engaged:
                rec["outcome"] = "blocked_killswitch"
                raise KillSwitchEngaged(self.killswitch.reason or "kill switch engaged")
            why = scope_violation(self.scope, tool, action)
            if why is None and (tool not in self.tools or action not in self.tools[tool].allowed_actions):
                why = f"tool {tool!r} does not declare action {action!r}"
            if why is not None:
                rec["outcome"] = "blocked_scope"
                rec["reason"] = why
                self.blocked += 1
                raise ScopeError(why)
            t = self.tools[tool]
            rec["access"] = t.access
            if approval is not None:
                rec["approver"] = str(getattr(approval, "approver_id", ""))
            if action in t.requires_approval:
                bad = self._approval_problem(approval, params)
                if bad:
                    rec["outcome"] = "blocked_gate"
                    rec["reason"] = bad
                    raise GateViolation(f"{tool}.{action} needs a valid person approval: {bad}")
            if t.access == WRITE and idempotency_key and idempotency_key in self._replay:
                rec["outcome"] = "replay"
                return dict(self._replay[idempotency_key])
            if self.faults is not None:
                try:
                    self.faults.before_call(case_id, tool, action, attempt)
                except ToolTimeout:
                    rec["outcome"] = "timeout"
                    raise
            if t.access == WRITE and self.mode == "shadow":
                rec["outcome"] = "dry_run"
                dry = t.dry_run_handlers.get(action)
                ack = dry(**params) if dry else {}
                result = {"dry_run": True, "tool": tool, "action": action}
                result.update(ack)
                return result
            kwargs = dict(params)
            if idempotency_key and action in t.forwards_key:
                kwargs["idempotency_key"] = idempotency_key
            try:
                result = t.handlers[action](**kwargs)
            except LookupError as exc:
                rec["outcome"] = "not_found"
                raise NotFoundError(str(exc))
            if t.access == WRITE:
                self.executed += 1
            if self.faults is not None:
                if t.access == WRITE and self.faults.timeout_after_write(case_id, tool, action, attempt):
                    rec["outcome"] = "timeout"
                    raise ToolTimeout(f"{tool}.{action} answer lost after the write (injected)")
                result = self.faults.corrupt(case_id, tool, action, attempt, result)
            schema = t.output_schema.get(action)
            if schema is not None:
                bad = validate_output(schema, result)
                if bad:
                    rec["outcome"] = "malformed"
                    rec["reason"] = bad
                    raise ToolOutputError(f"{tool}.{action}: {bad}")
            if t.access == WRITE and idempotency_key:
                self._replay[idempotency_key] = dict(result)
            rec["outcome"] = "ok"
            return result
        finally:
            self.audit.append("tool_call", case_id, step, **rec)

    @staticmethod
    def _approval_problem(approval, params: dict) -> Optional[str]:
        if approval is None:
            return "no approval given"
        if not getattr(approval, "approved", False):
            return "approval was not granted"
        if not str(getattr(approval, "approver_id", "")).startswith("person:"):
            return "approval is not from a person"
        if getattr(approval, "digest", None) != params.get("correction_digest"):
            return "approval does not match this correction"
        return None


# ---------------------------------------------------------------------------------------------------
# the kit's adapters over the simulated systems
# ---------------------------------------------------------------------------------------------------
EXCEPTION_SHAPE = {"case_id": str, "exception_ref": str, "payment_id": str, "reason_code": str,
                   "returned_name": str, "returned_account": str, "advised_value": str, "amount": str,
                   "currency": str, "opened_hour": int, "delivery_no": int}
PAYMENT_SHAPE = {"payment_id": str, "beneficiary_name": str, "beneficiary_account": str,
                 "beneficiary_bank_code": str, "amount": str, "currency": str}


def build_tools(env) -> Dict[str, Tool]:
    """Adapters over the simulated environment. Only the actions the wire-repair brief allows are wired
    up; the environment's other actions (update_payment, cancel_payment, export_list...) are not
    reachable through the kit at all."""
    return {
        "exception_queue": Tool("exception_queue", READ, frozenset({"fetch_exception"}),
                                {"fetch_exception": env.fetch_exception},
                                {"fetch_exception": EXCEPTION_SHAPE}),
        "case_system": Tool("case_system", WRITE, frozenset({"open_case", "append_note", "close_case",
                                                              "escalate_case"}),
                            {"open_case": env.open_case, "append_note": env.append_note,
                             "close_case": env.close_case, "escalate_case": env.escalate_case},
                            {"open_case": {"case_id": str, "status": str},
                             "append_note": {"case_id": str, "notes": int},
                             "close_case": {"case_id": str, "status": str},
                             "escalate_case": {"case_id": str, "status": str, "queue": str}}),
        "reason_codes": Tool("reason_codes", READ, frozenset({"lookup"}), {"lookup": env.lookup},
                             {"lookup": {"code": str, "description": str, "repair_rule": str,
                                         "field_to_correct": str}}),
        "payments_db": Tool("payments_db", READ, frozenset({"get_payment"}), {"get_payment": env.get_payment},
                            {"get_payment": PAYMENT_SHAPE}),
        "worksheet": Tool("worksheet", WRITE, frozenset({"write_fields"}), {"write_fields": env.write_fields},
                          {"write_fields": {"case_id": str, "stored": dict}},
                          dry_run_handlers={"write_fields": lambda case_id, fields, as_text=False: {
                              "case_id": case_id, "stored": env.preview_write_fields(fields, as_text)}}),
        "watchlist": Tool("watchlist", READ, frozenset({"screen_party"}), {"screen_party": env.screen_party},
                          {"screen_party": {"query": str, "candidates": list}}),
        "payments_gateway": Tool("payments_gateway", WRITE, frozenset({"resubmit"}), {"resubmit": env.resubmit},
                                 {"resubmit": {"status": str, "ledger_id": int}},
                                 requires_approval=frozenset({"resubmit"}), forwards_key=frozenset({"resubmit"})),
    }
