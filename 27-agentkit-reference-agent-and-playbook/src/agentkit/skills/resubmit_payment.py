"""S10 resubmit_payment: the only write that moves money. It refuses to run without a person's S09 approval."""

from __future__ import annotations

from ..errors import GateViolation
from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    ap = ctx.approval
    if ctx.draft is None:
        raise GateViolation("S10 has no drafted correction to resubmit")
    if ap is None or not getattr(ap, "approved", False) or getattr(ap, "digest", None) != ctx.draft.digest:
        raise GateViolation("S10 resubmit_payment needs an approved S09 for this exact correction")
    payload = dict(ctx.worksheet)
    payload[ctx.draft.field] = ctx.draft.new_value
    ref = ctx.exception["exception_ref"]
    res = ctx.call("payments_gateway", "resubmit", idempotency_key=f"resubmit:{ref}", approval=ap,
                   payment_id=ctx.payment["payment_id"], payload=payload, correction_digest=ctx.draft.digest)
    ctx.resubmit_result = res
    return SkillResult("resubmitted", f"{res.get('status')} (ledger {res.get('ledger_id')}), approver "
                       f"{ap.approver_id}", {"status": res.get("status"), "ledger_id": res.get("ledger_id")})


SKILL = Skill("S10", "resubmit_payment", ("payments_gateway",), run, requires=('exception', 'payment', 'worksheet', 'draft'))
