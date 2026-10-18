"""S04 copy_beneficiary_fields: copy the beneficiary fields into the repair worksheet and read the copy back.

The worksheet turns a number-looking cell into a number, which drops leading zeros from an account. The
skill writes the cells as text and then compares what was stored with what it sent; a difference is a
malformed copy and the case goes back to the human queue.
"""

from __future__ import annotations

from ..errors import RecordInvalid
from .base import Skill, SkillResult

FIELDS = ("beneficiary_name", "beneficiary_account", "beneficiary_bank_code", "amount", "currency")


def run(ctx) -> SkillResult:
    fields = {k: ctx.payment[k] for k in FIELDS}
    res = ctx.call("worksheet", "write_fields", idempotency_key=f"{ctx.case_id}:worksheet", case_id=ctx.case_id,
                   fields=fields, as_text=True)
    stored = res["stored"]
    bad = sorted(k for k in FIELDS if str(stored.get(k)) != str(fields[k]))
    if bad:
        raise RecordInvalid("worksheet copy differs from the source on " + ", ".join(bad))
    ctx.worksheet = dict(stored)
    return SkillResult("copied", f"{len(FIELDS)} fields copied and read back equal", {"fields": list(FIELDS)})


SKILL = Skill("S04", "copy_beneficiary_fields", ("worksheet",), run, requires=('payment',))
