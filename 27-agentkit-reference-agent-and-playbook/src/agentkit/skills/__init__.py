"""Reusable skills for the steps an agent may perform. S07 and S09 have no skill: they are person-held."""

from __future__ import annotations

from . import (close_case, copy_beneficiary_fields, draft_correction, lookup_original_payment, match_name_account,
               open_exception, read_reason_code, resubmit_payment, screen_watchlist, write_case_note)
from .base import CaseContext, Skill, SkillResult

SKILLS = {s.SKILL.step: s.SKILL for s in (
    open_exception, read_reason_code, lookup_original_payment, copy_beneficiary_fields, match_name_account,
    screen_watchlist, draft_correction, resubmit_payment, write_case_note, close_case)}

__all__ = ["SKILLS", "CaseContext", "Skill", "SkillResult"]
