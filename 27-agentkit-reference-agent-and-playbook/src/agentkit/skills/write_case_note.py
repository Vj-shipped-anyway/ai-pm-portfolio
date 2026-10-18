"""S11 write_case_note: the STUB drafts the note; the skill appends it to the case."""

from __future__ import annotations

from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    handover = bool(ctx.facts.get("handover"))
    kind = "handover" if handover else "final"
    note = ctx.reasoner.draft_case_note(
        case_id=ctx.case_id, kind=kind, reason_code=ctx.exception["reason_code"], disposition=ctx.disposition,
        name_class=ctx.name_class, hits=ctx.hits, draft=ctx.draft, gate=ctx.facts.get("gate"),
        reason=ctx.facts.get("note_reason", ""))
    ctx.call("case_system", "append_note", idempotency_key=f"{ctx.case_id}:note:{kind}", case_id=ctx.case_id,
             text=note)
    return SkillResult("note_written", f"{kind} note appended (STUB text)", {"note_kind": kind, "stub": True})


SKILL = Skill("S11", "write_case_note", ("case_system",), run, requires=('exception',))
