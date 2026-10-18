"""S12 close_case: close the case with its disposition, or escalate it to compliance on a watch-list hit."""

from __future__ import annotations

from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    if ctx.disposition == "ESCALATE_COMPLIANCE":
        ctx.call("case_system", "escalate_case", idempotency_key=f"{ctx.case_id}:escalate", case_id=ctx.case_id,
                 queue="compliance", reason="watch-list hit")
        return SkillResult("escalated", "case escalated to the compliance queue; not closed by the agent", {})
    final = ctx.disposition or "RESUBMIT"
    ctx.call("case_system", "close_case", idempotency_key=f"{ctx.case_id}:close", case_id=ctx.case_id,
             disposition=final)
    return SkillResult("closed", f"case closed as {final}", {"disposition": final})


SKILL = Skill("S12", "close_case", ("case_system",), run)
