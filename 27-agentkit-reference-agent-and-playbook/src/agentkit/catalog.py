"""The fixed step catalog shared by the brief, the skills and the orchestrator.

truth_class is the catalog's own classification of each step:
  AGENT           rule-based and data-complete: an agent can do it end to end
  AGENT_HITL      an agent drafts or acts, a person approves
  HUMAN_JUDGMENT  leave to a person
  HUMAN_CONTROL   a control that must stay with a person (four-eyes)
"""

from __future__ import annotations

STEPS = {
    "S01": ("open_exception", "AGENT"),
    "S02": ("read_reason_code", "AGENT"),
    "S03": ("lookup_original_payment", "AGENT"),
    "S04": ("copy_beneficiary_fields", "AGENT"),
    "S05": ("match_name_account", "AGENT"),
    "S06": ("screen_watchlist", "AGENT"),
    "S07": ("judge_ambiguous_match", "HUMAN_JUDGMENT"),
    "S08": ("draft_correction", "AGENT_HITL"),
    "S09": ("approve_four_eyes", "HUMAN_CONTROL"),
    "S10": ("resubmit_payment", "AGENT_HITL"),
    "S11": ("write_case_note", "AGENT"),
    "S12": ("close_case", "AGENT"),
}
STEP_ORDER = tuple(sorted(STEPS))
HUMAN_STEPS = frozenset(s for s, (_n, c) in STEPS.items() if c in ("HUMAN_JUDGMENT", "HUMAN_CONTROL"))
SKILL_STEPS = tuple(s for s in STEP_ORDER if s not in HUMAN_STEPS)

# Outcomes a human worker recorded, and the proposals the kit can make.
HUMAN_OUTCOMES = ("RESUBMIT", "RETURN_TO_ORIGINATOR", "ESCALATE_COMPLIANCE", "DUPLICATE_CLOSED")
DEFER = "DEFER_TO_PERSON"
QUEUE = "HUMAN_QUEUE"
PROPOSALS = HUMAN_OUTCOMES + (DEFER, QUEUE)

ROUTES = ("auto", "to_person", "human_queue")


def step_name(step_id: str) -> str:
    return STEPS[step_id][0]
