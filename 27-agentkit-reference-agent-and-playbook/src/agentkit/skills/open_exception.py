"""S01 open_exception: fetch the exception, validate it, open the case, catch a duplicate delivery."""

from __future__ import annotations

from ..catalog import HUMAN_OUTCOMES
from ..errors import RecordInvalid
from .base import Skill, SkillResult

REQUIRED = ("case_id", "exception_ref", "payment_id", "reason_code", "returned_name")


def validate_exception(exc: dict) -> list:
    """Return the problems with a delivered exception record; an empty list means it is usable."""
    problems = []
    for k in REQUIRED:
        if not str(exc.get(k, "")).strip():
            problems.append(f"{k} is blank")
    try:
        if float(exc.get("amount", "")) <= 0:
            problems.append("amount is not positive")
    except (TypeError, ValueError):
        problems.append("amount is not a number")
    return problems


def run(ctx) -> SkillResult:
    exc = ctx.call("exception_queue", "fetch_exception", case_id=ctx.case_id)
    ctx.exception = exc
    problems = validate_exception(exc)
    if problems:
        raise RecordInvalid("exception record is malformed: " + "; ".join(problems))
    ctx.call("case_system", "open_case", idempotency_key=f"{ctx.case_id}:open", case_id=ctx.case_id,
             exception_ref=exc["exception_ref"])
    first = ctx.seen_refs.setdefault(exc["exception_ref"], ctx.case_id)
    if first != ctx.case_id:
        ctx.disposition = "DUPLICATE_CLOSED"
        ctx.facts["duplicate_of"] = first
        return SkillResult("duplicate_delivery", f"{exc['exception_ref']} was already delivered as {first}; "
                           "no second action is taken", {"duplicate_of": first})
    return SkillResult("opened", f"exception {exc['exception_ref']} validated and case opened",
                       {"exception_ref": exc["exception_ref"], "reason_code": exc["reason_code"]})


SKILL = Skill("S01", "open_exception", ("exception_queue", "case_system"), run)
