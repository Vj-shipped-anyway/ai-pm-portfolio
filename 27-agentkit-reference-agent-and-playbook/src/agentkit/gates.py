"""Types for the person-held steps. A gate is where the kit stops and a person answers.

Judgement   the S07 answer: is this the same party?
Approval    the S09 answer: may this exact correction be resubmitted?
Neither can be produced by the kit. `ApprovalProvider` is the seam a real queue would implement; the test
doubles in approvers.py are scripted stand-ins, not people.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class GateRequest:
    case_id: str
    step: str
    reason: str
    approver_role: str
    summary: dict = field(default_factory=dict)
    digest: Optional[str] = None
    judge_id: Optional[str] = None


@dataclass(frozen=True)
class Judgement:
    same_party: bool
    judge_id: str
    role: str
    note: str = ""


@dataclass(frozen=True)
class Approval:
    approved: bool
    approver_id: str
    role: str
    digest: str
    note: str = ""


class ApprovalProvider:
    """Base class: returns None, which means nobody answered and the case stays parked at the gate."""

    def judge(self, request: GateRequest) -> Optional[Judgement]:
        return None

    def approve(self, request: GateRequest) -> Optional[Approval]:
        return None
