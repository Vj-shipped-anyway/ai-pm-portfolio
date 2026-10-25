"""The step state machine: retries, idempotency keys, person gates, four-eyes rules, a kill switch and a
fallback to the human queue. Gates and four-eyes rules are read from the brief's derived config.

Per case, in the brief's step order:
  * a skill step runs, is retried on a transient tool failure, and writes a decision to the audit log
  * S07 and S09 are gates: the kit stops and a person answers. In shadow mode, or with no provider, the
    case parks at the gate. Nothing in this file can produce an S07 judgment or an S09 approval.
  * S10 resubmit runs only if an approval from a person, for this exact correction and from someone other
    than the S07 judge, is on the case. It is checked here and again in the tool registry.
  * the kill switch is checked before every step and every tool call; an engaged switch routes the case
    back to the human queue with its trace and stops all tool use
  * a record that is malformed, a tool that keeps failing, a call outside scope or a failed rule check
    sends the case to the human queue; nothing is dropped and nothing is guessed

Routes (the three-way split every run reports):
  auto          the agent finished the case with no person step
  to_person     the case is parked at S07 or S09, or escalated to compliance, or a person approved it
  human_queue   the kit could not or should not proceed
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .audit import AuditLog
from .catalog import DEFER, QUEUE
from .errors import (AgentKitError, GateViolation, KillSwitchEngaged, PrerequisiteMissing, RecordInvalid, ScopeError,
                     ToolFailure, UnsupportedStepError)
from .gates import Approval, ApprovalProvider, GateRequest
from .reasoning_stub import StubReasoner
from .skills import SKILLS, CaseContext


class KillSwitch:
    """The operator switch. Engaged: no new step runs and no tool call is made."""

    def __init__(self):
        self.engaged = False
        self.reason = ""
        self.by = ""
        self.history: List[tuple] = []

    def engage(self, reason: str = "operator", by: str = "operator") -> None:
        self.engaged, self.reason, self.by = True, reason, by
        self.history.append(("engage", by, reason))

    def release(self, by: str = "operator") -> None:
        self.engaged, self.reason, self.by = False, "", ""
        self.history.append(("release", by, ""))


class ApprovalDeclined(AgentKitError):
    """A person looked at the correction and said no."""


@dataclass
class CaseResult:
    case_id: str
    exception_ref: str = ""
    state: str = ""
    route: str = ""
    gate: Optional[str] = None
    proposed_outcome: str = ""
    correction: Optional[dict] = None
    name_class: Optional[str] = None
    name_score: Optional[float] = None
    hits: List[dict] = field(default_factory=list)
    reason_kind: str = ""
    reason: str = ""
    steps_done: List[str] = field(default_factory=list)
    steps_skipped: List[str] = field(default_factory=list)
    tool_calls: int = 0
    redelivery: bool = False
    mode: str = "shadow"
    resubmitted: bool = False
    ledger_id: Optional[int] = None
    draft_message: Optional[str] = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


class Orchestrator:
    def __init__(self, config, registry, audit: AuditLog, *, killswitch: Optional[KillSwitch] = None,
                 approver: Optional[ApprovalProvider] = None, max_attempts: int = 3, reasoner=None, faults=None,
                 preparer: str = "agent:wire-repair"):
        if getattr(config, "unsupported_steps", ()):
            raise UnsupportedStepError(
                f"brief {config.brief_id} names step(s) {', '.join(config.unsupported_steps)} that this kit has no "
                "skill for; the brief validates, but running it is refused")
        self.config = config
        self.registry = registry
        self.audit = audit
        self.killswitch = killswitch or registry.killswitch or KillSwitch()
        registry.killswitch = self.killswitch
        self.approver = approver
        self.max_attempts = max_attempts
        self.reasoner = reasoner or StubReasoner()
        self.faults = faults
        self.preparer = preparer
        self.seen_refs: Dict[str, str] = {}
        self.processed: Dict[str, CaseResult] = {}
        self.results: List[CaseResult] = []
        self.expect: Dict[str, dict] = {}
        self.step_hook = None      # optional callable(step, ctx), run before each step (used by drills)

    @property
    def mode(self) -> str:
        return self.registry.mode

    def new_context(self, case_id: str) -> CaseContext:
        self.expect.setdefault(case_id, {"deliveries": 0, "steps": 0, "gates": 0, "approvals": 0})
        return CaseContext(case_id, self.config, self.registry, self.audit, self.reasoner, self.seen_refs,
                           self.max_attempts, self.preparer)

    def expected_trace(self) -> Dict[str, dict]:
        out = {}
        for cid, e in self.expect.items():
            out[cid] = {"deliveries": e["deliveries"], "steps": e["steps"], "gates": e["gates"],
                        "approvals": e["approvals"], "tool_calls": self.registry.calls_by_case.get(cid, 0)}
        return out

    # ------------------------------------------------------------------------------------------
    def run_all(self, case_ids) -> List[CaseResult]:
        again = self.faults.redeliveries() if self.faults else set()
        out = []
        for cid in case_ids:
            out.append(self.run_case(cid))
            if cid in again:
                out.append(self.run_case(cid))
        return out

    def run_case(self, case_id: str) -> CaseResult:
        exp = self.expect.setdefault(case_id, {"deliveries": 0, "steps": 0, "gates": 0, "approvals": 0})
        exp["deliveries"] += 1
        self.audit.append("case_start", case_id, mode=self.mode, brief=self.config.brief_id,
                          redelivery=case_id in self.processed)
        if case_id in self.processed:
            return self._redelivery(case_id)
        ctx = self.new_context(case_id)
        try:
            stopped = False
            for step in self.config.steps:
                if self.step_hook is not None:
                    self.step_hook(step, ctx)
                self._check_kill(ctx, step)
                why = self._skip_reason(step, ctx)
                if why:
                    self._decision(ctx, step, "skipped", why)
                    ctx_skipped = ctx.facts.setdefault("skipped", [])
                    ctx_skipped.append(step)
                    continue
                ctx.step = step
                if step in self.config.gates:
                    if self._gate(step, ctx):
                        stopped = True
                        break
                    continue
                self._rogue(ctx, step)
                self._run_skill(step, ctx)
            if stopped:
                self._handover(ctx)
                return self._finish(ctx, f"WAITING_{ctx.facts['gate']}", "to_person")
            if ctx.disposition == "ESCALATE_COMPLIANCE":
                return self._finish(ctx, "ESCALATED", "to_person")
            state = "CLOSED_DUPLICATE" if ctx.disposition == "DUPLICATE_CLOSED" else "CLOSED"
            return self._finish(ctx, state, "to_person" if ctx.gates_used else "auto")
        except KillSwitchEngaged as exc:
            self.audit.append("kill_switch", case_id, ctx.step, reason=str(exc), by=self.killswitch.by)
            return self._finish(ctx, "KILLED", "human_queue", "kill_switch", str(exc))
        except ApprovalDeclined as exc:
            return self._queue(ctx, "declined", str(exc), "DECLINED")
        except RecordInvalid as exc:
            return self._queue(ctx, "record_invalid", str(exc))
        except PrerequisiteMissing as exc:
            return self._queue(ctx, "prerequisite_missing", str(exc))
        except ToolFailure as exc:
            return self._queue(ctx, "tool_failure", str(exc))
        except ScopeError as exc:
            return self._queue(ctx, "scope_violation", str(exc))
        except GateViolation as exc:
            return self._queue(ctx, "gate_violation", str(exc))
        except AgentKitError as exc:
            return self._queue(ctx, "kit_error", f"{type(exc).__name__}: {exc}")
        except Exception as exc:   # a bug in a skill must still end in the human queue, with a trace
            return self._queue(ctx, "unexpected_error", f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------------------------------
    def run_step(self, step: str, ctx: CaseContext):
        """Run one step directly, with every guard applied. Used by tests and the enforcement run."""
        ctx.step = step
        return self._run_skill(step, ctx)

    def _check_kill(self, ctx, step) -> None:
        if self.killswitch.engaged:
            ctx.step = step
            raise KillSwitchEngaged(self.killswitch.reason or "kill switch engaged")

    def _skip_reason(self, step: str, ctx: CaseContext) -> Optional[str]:
        d = ctx.disposition
        if step == "S01":
            return None
        if d == "DUPLICATE_CLOSED" and step not in ("S11", "S12"):
            return "duplicate delivery; nothing else runs"
        if ctx.early_return and step not in ("S11", "S12"):
            return "the reason code has no repair"
        if step == "S07":
            if not ctx.needs_judgment:
                return "the match was clear; no judgment needed"
            if d is not None:
                return f"already decided ({d})"
        if step == "S08" and d is not None:
            return f"already decided ({d})"
        if step in ("S09", "S10") and ctx.draft is None:
            return "no correction was drafted"
        return None

    def _decision(self, ctx, step, decision, rationale, **data) -> None:
        self.expect[ctx.case_id]["steps"] += 1
        self.audit.append("decision", ctx.case_id, step, decision=decision, rationale=rationale, **data)

    def _run_skill(self, step: str, ctx: CaseContext):
        skill = SKILLS.get(step)
        if skill is None:
            raise RecordInvalid(f"no skill is registered for {step}")
        need = self.config.approval_required.get(step)
        if need is not None:
            bad = self._approval_problem(ctx)
            if bad:
                self.audit.append("gate_violation", ctx.case_id, step, needs=need, problem=bad)
                self._decision(ctx, step, "refused", f"{step} needs an approved {need}: {bad}")
                raise GateViolation(f"{step} needs an approved {need}: {bad}")
        missing = [a for a in skill.requires if getattr(ctx, a, None) is None]
        if missing:
            msg = (f"{step} needs {', '.join(missing)} from an earlier step this pack does not include or that "
                   "did not run")
            self._decision(ctx, step, "refused", msg)
            raise PrerequisiteMissing(msg)
        try:
            res = skill.fn(ctx)
        except AgentKitError as exc:
            self._decision(ctx, step, "failed", f"{type(exc).__name__}: {exc}")
            raise
        ctx.facts.setdefault("done", []).append(step)
        self._decision(ctx, step, res.decision, res.rationale, **res.data)
        return res

    @staticmethod
    def _approval_problem(ctx) -> Optional[str]:
        ap = ctx.approval
        if ap is None:
            return "no approval on the case"
        if not ap.approved:
            return "approval was not granted"
        if ctx.draft is None or ap.digest != ctx.draft.digest:
            return "approval is for a different correction"
        return None

    def _rogue(self, ctx, step) -> None:
        if not self.faults:
            return
        for tool, action in self.faults.rogue_calls(ctx.case_id, step):
            ctx.call(tool, action, case_id=ctx.case_id)

    # ---- gates -----------------------------------------------------------------------------------
    def _gate(self, step: str, ctx: CaseContext) -> bool:
        """Open a gate. Returns True when the case must stop here."""
        gate = self.config.gates[step]
        summary = {"reason_code": ctx.exception["reason_code"] if ctx.exception else None,
                   "name_class": ctx.name_class, "name_score": ctx.name_score}
        if ctx.draft is not None:
            summary["correction"] = {"field": ctx.draft.field, "old": ctx.draft.old_value,
                                     "new": ctx.draft.new_value}
        digest = ctx.draft.digest if ctx.draft is not None else None
        req = GateRequest(ctx.case_id, step, gate.reason, gate.approver_role, summary, digest, ctx.judge_id)
        self.expect[ctx.case_id]["gates"] += 1
        ctx.gates_used.append(step)
        self.audit.append("gate", ctx.case_id, step, reason=gate.reason, approver_role=gate.approver_role,
                          mode=self.mode, digest=digest)
        if self.mode == "shadow" or self.approver is None:
            ctx.facts["gate"] = step
            return True
        if step == "S07":
            j = self.approver.judge(req)
            if j is None:
                ctx.facts["gate"] = step
                return True
            ok, why = self._person_problem(j.judge_id, j.role, gate.approver_role, ctx, check_distinct=False)
            self._approval_event(ctx, step, actor=j.judge_id, result="accepted" if not why
                              else "rejected_invalid", problem=why, same_party=j.same_party)
            if why:
                ctx.facts["gate"] = step
                return True
            ctx.same_party, ctx.judge_id = j.same_party, j.judge_id
            ctx.needs_judgment = True
            if not j.same_party:
                ctx.disposition = "RETURN_TO_ORIGINATOR"
            return False
        a = self.approver.approve(req)
        if a is None:
            ctx.facts["gate"] = step
            return True
        _ok, why = self._person_problem(a.approver_id, a.role, gate.approver_role, ctx,
                                      check_distinct=step in self.config.four_eyes)
        if not why and a.digest != digest:
            why = "approval is for a different correction"
        if why:
            self._approval_event(ctx, step, actor=a.approver_id, result="rejected_invalid",
                              problem=why)
            ctx.facts["gate"] = step
            ctx.facts["blocked_reason"] = why
            return True
        if not a.approved:
            self._approval_event(ctx, step, actor=a.approver_id, result="declined")
            raise ApprovalDeclined(f"{a.approver_id} declined the correction")
        self._approval_event(ctx, step, actor=a.approver_id, result="accepted", digest=a.digest)
        ctx.approval = a
        return False

    def _approval_event(self, ctx, step, **detail) -> None:
        self.expect[ctx.case_id]["approvals"] += 1
        self.audit.append("approval", ctx.case_id, step, **detail)

    def _person_problem(self, pid: str, role: str, want_role: str, ctx, check_distinct: bool):
        why = None
        if not str(pid).startswith("person:"):
            why = "the answer is not from a person"
        elif role != want_role:
            why = f"role {role!r} is not the gate's approver role {want_role!r}"
        elif check_distinct and pid in (ctx.judge_id, self.preparer):
            why = "four-eyes: the approver must differ from the person or agent who prepared the case"
        return (why is None), why

    def _handover(self, ctx: CaseContext) -> None:
        """A parked case gets a note so the person starts with the context."""
        if "S11" not in self.config.steps:
            return
        ctx.facts["handover"] = True
        ctx.step = "S11"
        try:
            self._run_skill("S11", ctx)
        except AgentKitError:
            pass    # the failure is already in the trace; the case is still parked for a person

    # ---- endings ---------------------------------------------------------------------------------
    def _queue(self, ctx, kind: str, message: str, state: str = "QUEUED_HUMAN") -> CaseResult:
        self.audit.append("fallback", ctx.case_id, ctx.step, reason_kind=kind, message=message)
        written = "ok"
        try:
            ctx.step = ctx.step or "S01"
            ctx.call("case_system", "escalate_case", idempotency_key=f"{ctx.case_id}:queue", case_id=ctx.case_id,
                     queue="human_queue", reason=f"{kind}: {message}"[:200])
        except AgentKitError as exc:
            written = f"failed: {type(exc).__name__}"
        ctx.facts["queue_write"] = written
        return self._finish(ctx, state, "human_queue", kind, message)

    def _redelivery(self, case_id: str) -> CaseResult:
        first = self.processed[case_id]
        self.expect[case_id]["steps"] += 1
        self.audit.append("decision", case_id, "S01", decision="redelivery_ignored",
                          rationale="this case was already delivered; no second action is taken")
        res = CaseResult(case_id=case_id, exception_ref=first.exception_ref, state="REDELIVERY_IGNORED",
                         route="auto", proposed_outcome="DUPLICATE_CLOSED", redelivery=True, mode=self.mode,
                         reason_kind="redelivery", reason="same case id delivered again")
        self.audit.append("route", case_id, None, route="auto", state=res.state, proposed_outcome=res.proposed_outcome,
                          reason_kind="redelivery")
        self.results.append(res)
        return res

    def _finish(self, ctx, state: str, route: str, kind: str = "", message: str = "") -> CaseResult:
        if state.startswith("WAITING_S07"):
            proposed = DEFER
        elif state.startswith("WAITING_S09"):
            proposed = "RESUBMIT"
        elif state == "ESCALATED":
            proposed = "ESCALATE_COMPLIANCE"
        elif state in ("QUEUED_HUMAN", "KILLED", "DECLINED"):
            proposed = QUEUE
        else:
            proposed = ctx.disposition or "RESUBMIT"
        resubmitted = ctx.resubmit_result is not None and ctx.resubmit_result.get("status") in (
            "ACCEPTED", "DUPLICATE_IGNORED")
        res = CaseResult(
            case_id=ctx.case_id, exception_ref=(ctx.exception or {}).get("exception_ref", ""), state=state,
            route=route, gate=ctx.facts.get("gate"), proposed_outcome=proposed,
            correction=({"field": ctx.draft.field, "old": ctx.draft.old_value, "new": ctx.draft.new_value,
                         "digest": ctx.draft.digest, "stub": True} if ctx.draft is not None
                        and proposed == "RESUBMIT" else None),
            name_class=ctx.name_class, name_score=ctx.name_score, hits=list(ctx.hits), reason_kind=kind,
            reason=message or ctx.facts.get("blocked_reason", ""), steps_done=list(ctx.facts.get("done", [])),
            steps_skipped=list(ctx.facts.get("skipped", [])), tool_calls=self.registry.calls_by_case.get(
                ctx.case_id, 0), mode=self.mode, resubmitted=resubmitted,
            ledger_id=(ctx.resubmit_result or {}).get("ledger_id"),
            draft_message=ctx.draft.message if ctx.draft is not None else None)
        self.audit.append("route", ctx.case_id, ctx.step, route=route, state=state, proposed_outcome=proposed,
                          reason_kind=kind, reason=res.reason[:200], gate=res.gate)
        self.processed[ctx.case_id] = res
        self.results.append(res)
        return res
