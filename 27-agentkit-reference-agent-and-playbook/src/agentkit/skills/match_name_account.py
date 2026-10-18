"""S05 match_name_account: compare the name on the return with the name on the original payment."""

from __future__ import annotations

from ..matching import AMBIGUOUS, EXACT, CLOSE, MISMATCH, classify_name_match, luhn_ok
from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    cls, score = classify_name_match(ctx.payment["beneficiary_name"], ctx.exception["returned_name"])
    ctx.name_class, ctx.name_score = cls, score
    acct_ok = luhn_ok(ctx.payment["beneficiary_account"])
    ctx.facts["payment_account_check_digit_ok"] = acct_ok
    fix_name = ctx.rule["repair_rule"] == "FIX_NAME"
    if cls == MISMATCH and fix_name:
        ctx.disposition = "RETURN_TO_ORIGINATOR"
        why = "the account belongs to a different party; return to originator"
    elif cls in (AMBIGUOUS, MISMATCH):
        ctx.needs_judgment = True
        why = "the match is not clear enough for a rule; S07 goes to a person"
    else:
        why = "names agree after normalization" if cls == EXACT else "names are a close match"
    return SkillResult(f"name_{cls.lower()}", f"{cls} ({score:.2f}): {why}",
                       {"name_class": cls, "score": score, "payment_account_check_digit_ok": acct_ok})


SKILL = Skill("S05", "match_name_account", (), run, requires=('payment', 'exception', 'rule'))
