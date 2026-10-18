"""Scripted TEST DOUBLES for the person-held gates. These are not people and not a model.

They exist so the enforcement run and the tests can exercise the control paths: a valid approval, an
approval by the same person who judged, an approval for a different correction, a decline, a silent gate.
"""

from __future__ import annotations

from typing import Callable, Optional

from .gates import Approval, ApprovalProvider, GateRequest, Judgement


class ScriptedApprover(ApprovalProvider):
    def __init__(self, *, same_party: Callable[[GateRequest], bool] = lambda r: True,
                 approve: Callable[[GateRequest], bool] = lambda r: True, judge_id: str = "person:judge-1",
                 approver_id: str = "person:reviewer-1", judge_role: str = "payments_operations_analyst",
                 approver_role: str = "payments_operations_reviewer", digest_override: Optional[str] = None,
                 answer_judge: bool = True, answer_approve: bool = True):
        self._same = same_party
        self._approve = approve
        self.judge_id, self.approver_id = judge_id, approver_id
        self.judge_role, self.approver_role = judge_role, approver_role
        self.digest_override = digest_override
        self.answer_judge, self.answer_approve = answer_judge, answer_approve
        self.judged = 0
        self.approvals = 0

    def judge(self, request: GateRequest) -> Optional[Judgement]:
        if not self.answer_judge:
            return None
        self.judged += 1
        return Judgement(self._same(request), self.judge_id, self.judge_role, "scripted test double")

    def approve(self, request: GateRequest) -> Optional[Approval]:
        if not self.answer_approve:
            return None
        self.approvals += 1
        return Approval(self._approve(request), self.approver_id, self.approver_role,
                        self.digest_override or (request.digest or ""), "scripted test double")
