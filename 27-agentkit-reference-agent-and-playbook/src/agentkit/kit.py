"""Assembly: from a world and a brief to a runnable kit (environment, tools, audit log, orchestrator)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .audit import AuditLog
from .brief import WorkflowConfig, derive_config
from .environment import SimEnvironment
from .faults import FaultInjector
from .orchestrator import KillSwitch, Orchestrator
from .tools import ToolRegistry, build_tools


@dataclass
class Kit:
    env: SimEnvironment
    config: WorkflowConfig
    audit: AuditLog
    registry: ToolRegistry
    orchestrator: Orchestrator
    faults: Optional[FaultInjector]
    killswitch: KillSwitch


def build_kit(world: dict, brief: dict, *, mode: str = "shadow", fault_rows=None, killswitch=None, approver=None,
              max_attempts: int = 3, audit_path: Optional[Path] = None) -> Kit:
    config = derive_config(brief)
    env = SimEnvironment.from_world(world)
    audit = AuditLog(audit_path)
    faults = FaultInjector(fault_rows) if fault_rows else None
    ks = killswitch or KillSwitch()
    registry = ToolRegistry(build_tools(env), config.tool_scope, audit, faults=faults, killswitch=ks, mode=mode)
    orch = Orchestrator(config, registry, audit, killswitch=ks, approver=approver, max_attempts=max_attempts,
                        faults=faults)
    return Kit(env, config, audit, registry, orch, faults, ks)
