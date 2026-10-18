"""Exceptions raised by the kit. Each one maps to a named route in the orchestrator."""

from __future__ import annotations


class AgentKitError(Exception):
    """Base class for every error the kit raises on purpose."""


class BriefError(AgentKitError):
    """The build brief failed validation. `problems` lists every problem found."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) if self.problems else "invalid brief")


class ScopeError(AgentKitError):
    """A tool call fell outside the scope the brief allows. The call never reached the system."""


class GateViolation(AgentKitError):
    """A step ran, or tried to run, without the person-held approval the brief requires."""


class ToolTimeout(AgentKitError):
    """A tool did not answer in time. Transient: the orchestrator retries."""


class ToolOutputError(AgentKitError):
    """A tool answered with output that does not match its declared shape. Transient: retried."""


class ToolFailure(AgentKitError):
    """A tool kept failing after the retries were used up. The case goes back to the human queue."""


class NotFoundError(AgentKitError):
    """A lookup found nothing. Deterministic: not retried."""


class RecordInvalid(AgentKitError):
    """The exception record is malformed or inconsistent. Deterministic: not retried."""


class UnsupportedStepError(AgentKitError):
    """A brief names a step this kit has no skill for. The brief validates; running it is refused."""


class PrerequisiteMissing(AgentKitError):
    """A step needs a result from an earlier step that this pack does not include or that did not run."""


class KillSwitchEngaged(AgentKitError):
    """The operator kill switch is engaged. Nothing new runs."""


class AuditError(AgentKitError):
    """The audit log failed an integrity or completeness check."""
