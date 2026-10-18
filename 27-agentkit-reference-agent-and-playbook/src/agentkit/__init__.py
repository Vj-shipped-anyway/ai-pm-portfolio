"""AgentKit: reusable pieces behind an agent that takes over a rule-based operations workflow.

A build brief (build-brief/v1) is validated and turned into a workflow config. Skills do the agent steps,
a tool registry enforces the brief's scope, an orchestrator routes S07 and S09 to a person and refuses a
resubmit without an approval, an append-only audit log records every decision, and a shadow harness scores
the agent against recorded human outcomes. A deterministic STUB stands in for a language model in two
places; there is no model in this package.
"""

from __future__ import annotations

__version__ = "0.1.0"
