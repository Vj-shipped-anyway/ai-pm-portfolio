"""S03 lookup_original_payment: read the original payment the exception refers to."""

from __future__ import annotations

from ..errors import NotFoundError, RecordInvalid
from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    pid = ctx.exception["payment_id"]
    try:
        pay = ctx.call("payments_db", "get_payment", payment_id=pid)
    except NotFoundError:
        raise RecordInvalid(f"original payment {pid!r} was not found")
    if not str(pay.get("beneficiary_name", "")).strip():
        raise RecordInvalid(f"original payment {pid} has no beneficiary name")
    ctx.payment = pay
    return SkillResult("found", f"payment {pid} found", {"payment_id": pid})


SKILL = Skill("S03", "lookup_original_payment", ("payments_db",), run, requires=('exception',))
