"""S02 read_reason_code: look the return reason up in the rule table."""

from __future__ import annotations

from ..errors import NotFoundError, RecordInvalid
from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    code = ctx.exception["reason_code"]
    try:
        rule = ctx.call("reason_codes", "lookup", code=code)
    except NotFoundError:
        raise RecordInvalid(f"reason code {code!r} is not in the rule table")
    ctx.rule = rule
    if rule["repair_rule"] == "NOT_REPAIRABLE":
        ctx.disposition = "RETURN_TO_ORIGINATOR"
        ctx.early_return = True
        return SkillResult("not_repairable", f"{code} ({rule['description']}) has no repair; return to originator",
                           {"repair_rule": rule["repair_rule"]})
    return SkillResult("repairable", f"{code} ({rule['description']}): rule {rule['repair_rule']} on "
                       f"{rule['field_to_correct']}", {"repair_rule": rule["repair_rule"]})


SKILL = Skill("S02", "read_reason_code", ("reason_codes",), run, requires=('exception',))
