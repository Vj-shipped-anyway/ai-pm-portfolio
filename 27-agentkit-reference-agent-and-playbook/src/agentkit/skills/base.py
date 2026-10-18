"""What every skill sees: a case context and a result type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..audit import AuditLog
from ..errors import ToolFailure, ToolOutputError, ToolTimeout


@dataclass
class SkillResult:
    decision: str
    rationale: str
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Skill:
    step: str
    name: str
    tools: tuple
    fn: Callable
    requires: tuple = ()     # ctx attributes an earlier step must have set


class CaseContext:
    """State for one case. Skills read and write plain attributes; every tool call goes through `call`,
    which retries transient failures and then gives up with ToolFailure."""

    def __init__(self, case_id, config, registry, audit: AuditLog, reasoner, seen_refs: Dict[str, str],
                 max_attempts: int = 3, preparer: str = "agent:wire-repair"):
        self.case_id = case_id
        self.config = config
        self.registry = registry
        self.audit = audit
        self.reasoner = reasoner
        self.seen_refs = seen_refs
        self.max_attempts = max_attempts
        self.preparer = preparer
        self.step: Optional[str] = None
        self.exception: Optional[dict] = None
        self.rule: Optional[dict] = None
        self.payment: Optional[dict] = None
        self.worksheet: Optional[dict] = None
        self.name_class: Optional[str] = None
        self.name_score: Optional[float] = None
        self.hits: List[dict] = []
        self.disposition: Optional[str] = None
        self.early_return = False
        self.needs_judgment = False
        self.same_party: Optional[bool] = None
        self.judge_id: Optional[str] = None
        self.draft = None
        self.approval = None
        self.resubmit_result: Optional[dict] = None
        self.gates_used: List[str] = []
        self.facts: dict = {}

    def call(self, tool: str, action: str, *, idempotency_key: Optional[str] = None, approval=None, **params):
        attempts = 0
        while True:
            attempts += 1
            try:
                return self.registry.call(tool, action, params, case_id=self.case_id, step=self.step,
                                          idempotency_key=idempotency_key, approval=approval)
            except (ToolTimeout, ToolOutputError) as exc:
                if attempts >= self.max_attempts:
                    raise ToolFailure(f"{tool}.{action} failed {attempts} times: {exc}") from exc
                self.audit.append("retry", self.case_id, self.step, tool=tool, action=action, attempt=attempts,
                                  error=type(exc).__name__, backoff_ms=200 * 2 ** (attempts - 1))
