"""S08 draft_correction: the STUB drafts the correction, then the rules check it.

The stub writes the draft. The check is separate and plain: the field must be the one the reason code
repairs, the new value must have the right format, a name must match the payment's name. A draft that
fails the check is not shown to an approver; the case goes back to the human queue.
"""

from __future__ import annotations

from ..errors import RecordInvalid
from ..matching import AMBIGUOUS, CLOSE, EXACT, account_format_ok, bank_code_ok, classify_name_match, luhn_ok
from .base import Skill, SkillResult


def check_draft(draft, rule: dict, payment: dict, same_party: bool = False) -> list:
    problems = []
    field = rule["field_to_correct"]
    if draft.field != field:
        problems.append(f"draft changes {draft.field}, the rule repairs {field}")
    if not draft.new_value:
        problems.append("new value is blank")
    elif draft.new_value == draft.old_value:
        problems.append("new value equals the old value")
    elif field == "beneficiary_account":
        if not account_format_ok(draft.new_value) or not luhn_ok(draft.new_value):
            problems.append("new account fails the format or check-digit rule")
    elif field == "beneficiary_bank_code":
        if not bank_code_ok(draft.new_value):
            problems.append("new bank code fails the format rule")
    elif field == "beneficiary_name":
        cls, _score = classify_name_match(payment["beneficiary_name"], draft.new_value)
        if cls not in (EXACT, CLOSE) and not (cls == AMBIGUOUS and same_party):
            problems.append(f"new name is a {cls} match to the payment name")
    return problems


def run(ctx) -> SkillResult:
    draft = ctx.reasoner.draft_correction(
        case_id=ctx.case_id, reason_code=ctx.exception["reason_code"], rule=ctx.rule, payment=ctx.payment,
        advised_value=ctx.exception["advised_value"], name_class=ctx.name_class or "", name_score=ctx.name_score or 0.0)
    problems = check_draft(draft, ctx.rule, ctx.payment, bool(ctx.same_party))
    if problems:
        raise RecordInvalid("draft failed the rule check: " + "; ".join(problems))
    ctx.draft = draft
    return SkillResult("drafted", f"STUB drafted {draft.field} -> {draft.new_value}; rule check passed",
                       {"field": draft.field, "new_value": draft.new_value, "digest": draft.digest,
                        "stub": True})


SKILL = Skill("S08", "draft_correction", (), run, requires=('exception', 'rule', 'payment'))
