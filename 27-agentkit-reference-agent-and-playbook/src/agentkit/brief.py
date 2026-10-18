"""Load and validate a build-brief/v1 JSON, then derive the workflow config and acceptance tests.

The shape is the hand-off pack StepScout (project 26) emits. This file checks the exact set of keys at
every level with plain Python (no jsonschema), then checks the parts of the brief that must agree with
each other. A brief that tries to drop a person from S07 or S09, or to let a read tool carry a write
action, is rejected before anything runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .catalog import HUMAN_STEPS, STEP_ORDER, STEPS
from .errors import BriefError, UnsupportedStepError

SCHEMA = "build-brief/v1"
TOP = ("schema", "brief_id", "candidate", "scope", "inputs", "tools", "controls", "acceptance", "test_plan",
       "rollout", "handoff", "estimate")
KEYS = {
    "candidate": ("name", "workflow", "steps", "automation_class"),
    "scope": ("in_scope", "out_of_scope"),
    "input": ("name", "source", "fields"),
    "tool": ("name", "access", "allowed_actions"),
    "controls": ("hitl_gates", "four_eyes", "kill_switch", "audit"),
    "gate": ("step", "reason", "approver_role"),
    "four_eyes": ("step", "rule"),
    "acceptance": ("id", "metric", "threshold", "how_measured"),
    "test_plan": ("golden_cases", "fault_injections", "shadow_mode_cases"),
    "rollout": ("stages", "exit_criteria"),
    "handoff": ("owner_role", "runbook_items", "monitoring"),
    "estimate": ("hours_at_stake_modeled", "assumption"),
}
WRITE_VERBS = frozenset({"update", "delete", "write", "set", "cancel", "remove", "submit", "resubmit", "close",
                         "open", "append", "create", "escalate", "insert", "approve"})
STEP_RE = re.compile(r"^S\d\d$")


def _is_str(x) -> bool:
    return isinstance(x, str) and x.strip() != ""


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _keys(obj, expected, path: str, problems: List[str]) -> bool:
    if not isinstance(obj, dict):
        problems.append(f"{path}: expected an object")
        return False
    missing = [k for k in expected if k not in obj]
    extra = [k for k in obj if k not in expected]
    for k in missing:
        problems.append(f"{path}: missing key {k!r}")
    for k in extra:
        problems.append(f"{path}: unexpected key {k!r}")
    return not missing


def _str_list(obj, path: str, problems: List[str], allow_empty: bool = False) -> List[str]:
    if not isinstance(obj, list) or (not obj and not allow_empty):
        problems.append(f"{path}: expected a non-empty list of strings")
        return []
    bad = [x for x in obj if not _is_str(x)]
    if bad:
        problems.append(f"{path}: every item must be a non-empty string")
    return [x for x in obj if _is_str(x)]


def check_brief(d) -> List[str]:
    """Return every problem found. An empty list means the brief is valid."""
    p: List[str] = []
    if not _keys(d, TOP, "brief", p):
        return p
    if d["schema"] != SCHEMA:
        p.append(f"schema: expected {SCHEMA!r}, got {d['schema']!r}")
    if not (isinstance(d["brief_id"], str) and re.fullmatch(r"BB-\d{3,}", d["brief_id"])):
        p.append("brief_id: expected a value like 'BB-001'")

    steps: List[str] = []        # step ids the kit's catalog knows
    raw_steps: List[str] = []    # every well-formed step id in the brief, in the brief's order
    if _keys(d["candidate"], KEYS["candidate"], "candidate", p):
        c = d["candidate"]
        for k in ("name", "workflow"):
            if not _is_str(c[k]):
                p.append(f"candidate.{k}: expected a non-empty string")
        if c["automation_class"] not in ("AGENT", "AGENT_HITL"):
            p.append("candidate.automation_class: expected 'AGENT' or 'AGENT_HITL'")
        if not isinstance(c["steps"], list) or not c["steps"]:
            p.append("candidate.steps: expected a non-empty list of step ids")
        else:
            for s in c["steps"]:
                if not (isinstance(s, str) and STEP_RE.match(s)):
                    p.append(f"candidate.steps: {s!r} is not a step id (expected S and two digits)")
                else:
                    raw_steps.append(s)
                    if s in STEPS:
                        steps.append(s)      # a well-formed id outside the catalog is a warning, not a problem
            if len(set(raw_steps)) != len(raw_steps):
                p.append("candidate.steps: duplicate step id")
            if steps != sorted(steps):
                p.append("candidate.steps: step ids must be in workflow order")
            for s in steps:
                if s in HUMAN_STEPS and c.get("automation_class") == "AGENT":
                    p.append(f"candidate.automation_class: AGENT cannot include person-held step {s}")

    if _keys(d["scope"], KEYS["scope"], "scope", p):
        _str_list(d["scope"]["in_scope"], "scope.in_scope", p)
        _str_list(d["scope"]["out_of_scope"], "scope.out_of_scope", p)

    if not isinstance(d["inputs"], list) or not d["inputs"]:
        p.append("inputs: expected a non-empty list")
    else:
        for i, it in enumerate(d["inputs"]):
            if _keys(it, KEYS["input"], f"inputs[{i}]", p):
                if not _is_str(it["name"]) or not _is_str(it["source"]):
                    p.append(f"inputs[{i}]: name and source must be non-empty strings")
                _str_list(it["fields"], f"inputs[{i}].fields", p)

    tool_names: List[str] = []
    if not isinstance(d["tools"], list) or not d["tools"]:
        p.append("tools: expected a non-empty list")
    else:
        for i, t in enumerate(d["tools"]):
            if not _keys(t, KEYS["tool"], f"tools[{i}]", p):
                continue
            if not _is_str(t["name"]):
                p.append(f"tools[{i}].name: expected a non-empty string")
                continue
            if t["name"] in tool_names:
                p.append(f"tools[{i}]: duplicate tool name {t['name']!r}")
            tool_names.append(t["name"])
            if t["access"] not in ("read", "write"):
                p.append(f"tools[{i}].access: expected 'read' or 'write'")
            acts = _str_list(t["allowed_actions"], f"tools[{i}].allowed_actions", p)
            if t["access"] == "read":
                for a in acts:
                    if WRITE_VERBS & set(a.lower().split("_")):
                        p.append(f"tools[{i}]: read tool {t['name']!r} lists write-like action {a!r}")

    gate_steps: List[str] = []
    four_steps: List[str] = []
    four_entries: List[dict] = []
    if _keys(d["controls"], KEYS["controls"], "controls", p):
        ctl = d["controls"]
        if not isinstance(ctl["hitl_gates"], list):
            p.append("controls.hitl_gates: expected a list")
        else:
            for i, g in enumerate(ctl["hitl_gates"]):
                if _keys(g, KEYS["gate"], f"controls.hitl_gates[{i}]", p):
                    if not (isinstance(g["step"], str) and STEP_RE.match(g["step"])):
                        p.append(f"controls.hitl_gates[{i}].step: {g['step']!r} is not a step id")
                    elif g["step"] not in raw_steps:
                        p.append(f"controls.hitl_gates[{i}].step: {g['step']} is not in candidate.steps")
                    else:
                        gate_steps.append(g["step"])
                    if not _is_str(g["reason"]) or not _is_str(g["approver_role"]):
                        p.append(f"controls.hitl_gates[{i}]: reason and approver_role must be non-empty strings")
        if not isinstance(ctl["four_eyes"], list):
            p.append("controls.four_eyes: expected a list")
        else:
            for i, f in enumerate(ctl["four_eyes"]):
                if _keys(f, KEYS["four_eyes"], f"controls.four_eyes[{i}]", p):
                    # A four-eyes control may name a step outside the pack: the control then stays with a person
                    # who is not part of what the agent does.
                    if not (isinstance(f["step"], str) and STEP_RE.match(f["step"])):
                        p.append(f"controls.four_eyes[{i}].step: {f['step']!r} is not a step id")
                    else:
                        four_steps.append(f["step"])
                        four_entries.append(f)
                    if not _is_str(f["rule"]):
                        p.append(f"controls.four_eyes[{i}].rule: expected a non-empty string")
        for k in ("kill_switch", "audit"):
            if not _is_str(ctl[k]):
                p.append(f"controls.{k}: expected a non-empty string")
        # person-held steps can never be dropped from the gates
        for s in steps:
            if s in HUMAN_STEPS and s not in gate_steps:
                p.append(f"controls.hitl_gates: {s} ({STEPS[s][0]}) is person-held and must have a gate")
        if "S09" in steps and "S09" not in four_steps:
            p.append("controls.four_eyes: S09 must carry a four-eyes rule")
        # A resubmit cannot be in the pack without the four-eyes approval behind it. S09 itself may sit outside
        # the pack; the brief must then say so in a four-eyes entry for S09, or in an S10 entry that names S09.
        if "S10" in steps:
            names_s09 = any(f["step"] == "S10" and "S09" in f["rule"] for f in four_entries)
            if "S09" not in four_steps and not names_s09:
                p.append("controls.four_eyes: S10 resubmit_payment needs a four-eyes entry for S09, "
                         "or an S10 entry whose rule names the S09 approval")

    ids: List[str] = []
    if not isinstance(d["acceptance"], list) or not d["acceptance"]:
        p.append("acceptance: expected a non-empty list")
    else:
        for i, a in enumerate(d["acceptance"]):
            if _keys(a, KEYS["acceptance"], f"acceptance[{i}]", p):
                if not _is_str(a["id"]) or a["id"] in ids:
                    p.append(f"acceptance[{i}].id: expected a unique non-empty string")
                else:
                    ids.append(a["id"])
                if not _is_str(a["metric"]) or not _is_str(a["how_measured"]):
                    p.append(f"acceptance[{i}]: metric and how_measured must be non-empty strings")
                if not _is_num(a["threshold"]):
                    p.append(f"acceptance[{i}].threshold: expected a number")

    if _keys(d["test_plan"], KEYS["test_plan"], "test_plan", p):
        tp = d["test_plan"]
        for k in ("golden_cases", "shadow_mode_cases"):
            if not _is_int(tp[k]) or tp[k] < 0:
                p.append(f"test_plan.{k}: expected a non-negative integer")
        _str_list(tp["fault_injections"], "test_plan.fault_injections", p)

    if _keys(d["rollout"], KEYS["rollout"], "rollout", p):
        _str_list(d["rollout"]["stages"], "rollout.stages", p)
        _str_list(d["rollout"]["exit_criteria"], "rollout.exit_criteria", p)

    if _keys(d["handoff"], KEYS["handoff"], "handoff", p):
        if not _is_str(d["handoff"]["owner_role"]):
            p.append("handoff.owner_role: expected a non-empty string")
        _str_list(d["handoff"]["runbook_items"], "handoff.runbook_items", p)
        _str_list(d["handoff"]["monitoring"], "handoff.monitoring", p)

    if _keys(d["estimate"], KEYS["estimate"], "estimate", p):
        if not _is_num(d["estimate"]["hours_at_stake_modeled"]) or d["estimate"]["hours_at_stake_modeled"] < 0:
            p.append("estimate.hours_at_stake_modeled: expected a non-negative number")
        if not _is_str(d["estimate"]["assumption"]):
            p.append("estimate.assumption: the modeled estimate must name its assumption")
    return p


def unsupported_steps(d: dict) -> List[str]:
    """Well-formed step ids in the brief (steps, gates, four-eyes) that this kit's catalog does not contain."""
    ids = list(d["candidate"]["steps"])
    ids += [g["step"] for g in d["controls"]["hitl_gates"]] + [f["step"] for f in d["controls"]["four_eyes"]]
    out: List[str] = []
    for s in ids:
        if s not in STEPS and s not in out:
            out.append(s)
    return out


def brief_warnings(d: dict) -> List[str]:
    """Non-fatal findings on a valid brief."""
    out = []
    for s in unsupported_steps(d):
        out.append(f"unsupported step {s!r}: no skill in this kit; the brief validates but running it is refused")
    for a in d.get("acceptance", []):
        if not (a["metric"].endswith("_min") or a["metric"].endswith("_max")):
            out.append(f"acceptance {a['id']}: metric {a['metric']!r} has no _min/_max suffix; read as a minimum")
    return out


def validate_brief(d) -> dict:
    problems = check_brief(d)
    if problems:
        raise BriefError(problems)
    return d


def load_brief(path) -> dict:
    with open(Path(path), encoding="utf-8") as fh:
        try:
            d = json.load(fh)
        except json.JSONDecodeError as exc:
            raise BriefError([f"not valid JSON: {exc}"])
    return validate_brief(d)


# ---------------------------------------------------------------------------------------------------
# derived configuration
# ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ToolScope:
    access: str
    allowed_actions: frozenset


@dataclass(frozen=True)
class Gate:
    step: str
    reason: str
    approver_role: str


@dataclass(frozen=True)
class AcceptanceTest:
    id: str
    metric: str
    name: str
    direction: str      # "min" or "max"
    threshold: float
    how_measured: str

    def passes(self, value) -> bool:
        if value is None:
            return False
        return value >= self.threshold if self.direction == "min" else value <= self.threshold


@dataclass(frozen=True)
class WorkflowConfig:
    brief_id: str
    name: str
    workflow: str
    automation_class: str
    steps: Tuple[str, ...]
    gates: Dict[str, Gate]
    four_eyes: Dict[str, str]
    approval_required: Dict[str, str]
    tool_scope: Dict[str, ToolScope]
    in_scope: Tuple[str, ...]
    out_of_scope: Tuple[str, ...]
    kill_switch: str
    audit_rule: str
    acceptance: Tuple[AcceptanceTest, ...]
    golden_cases: int
    shadow_cases: int
    fault_injections: Tuple[str, ...]
    rollout_stages: Tuple[str, ...]
    exit_criteria: Tuple[str, ...]
    owner_role: str
    runbook_items: Tuple[str, ...]
    monitoring: Tuple[str, ...]
    hours_at_stake: float
    estimate_assumption: str
    unsupported_steps: Tuple[str, ...] = ()


def acceptance_tests(brief: dict) -> List[AcceptanceTest]:
    out = []
    for a in brief["acceptance"]:
        m = a["metric"]
        if m.endswith("_max"):
            name, direction = m[:-4], "max"
        elif m.endswith("_min"):
            name, direction = m[:-4], "min"
        else:
            name, direction = m, "min"
        out.append(AcceptanceTest(a["id"], m, name, direction, float(a["threshold"]), a["how_measured"]))
    return out


def derive_config(brief: dict, allow_unsupported: bool = False) -> WorkflowConfig:
    """Derive the workflow config. A brief that names a step the kit has no skill for validates, but this
    refuses to derive a runnable config from it unless `allow_unsupported` is set (for inspection only)."""
    validate_brief(brief)
    steps = tuple(brief["candidate"]["steps"])
    unsupported = tuple(s for s in steps if s not in STEPS)
    if unsupported and not allow_unsupported:
        raise UnsupportedStepError(
            f"brief {brief['brief_id']} names step(s) {', '.join(unsupported)} that this kit has no skill for; "
            "the brief validates, but running it is refused")
    gates = {g["step"]: Gate(g["step"], g["reason"], g["approver_role"]) for g in brief["controls"]["hitl_gates"]}
    four = {f["step"]: f["rule"] for f in brief["controls"]["four_eyes"]}
    # A resubmit in the pack always needs the S09 approval. check_brief guarantees the brief carries the
    # four-eyes entry for it; the approval itself may come from a person outside the pack.
    approval_required: Dict[str, str] = {}
    if "S10" in steps:
        approval_required["S10"] = "S09"
    scope = {t["name"]: ToolScope(t["access"], frozenset(t["allowed_actions"])) for t in brief["tools"]}
    return WorkflowConfig(
        brief_id=brief["brief_id"], name=brief["candidate"]["name"], workflow=brief["candidate"]["workflow"],
        automation_class=brief["candidate"]["automation_class"], steps=steps, gates=gates, four_eyes=four,
        approval_required=approval_required, tool_scope=scope,
        in_scope=tuple(brief["scope"]["in_scope"]), out_of_scope=tuple(brief["scope"]["out_of_scope"]),
        kill_switch=brief["controls"]["kill_switch"], audit_rule=brief["controls"]["audit"],
        acceptance=tuple(acceptance_tests(brief)), golden_cases=brief["test_plan"]["golden_cases"],
        shadow_cases=brief["test_plan"]["shadow_mode_cases"],
        fault_injections=tuple(brief["test_plan"]["fault_injections"]),
        rollout_stages=tuple(brief["rollout"]["stages"]), exit_criteria=tuple(brief["rollout"]["exit_criteria"]),
        owner_role=brief["handoff"]["owner_role"], runbook_items=tuple(brief["handoff"]["runbook_items"]),
        monitoring=tuple(brief["handoff"]["monitoring"]), hours_at_stake=float(brief["estimate"]["hours_at_stake_modeled"]),
        estimate_assumption=brief["estimate"]["assumption"], unsupported_steps=unsupported)


def evaluate_acceptance(tests, measured: Dict[str, Optional[float]]) -> List[dict]:
    """Pass or fail for each acceptance test. A metric that was not measured fails."""
    out = []
    for t in tests:
        v = measured.get(t.name)
        out.append({"id": t.id, "metric": t.name, "direction": t.direction, "threshold": t.threshold,
                    "value": v, "passed": t.passes(v), "how_measured": t.how_measured})
    return out


def scope_violation(scope: Dict[str, ToolScope], tool: str, action: str) -> Optional[str]:
    """None if the call is inside the brief's scope, otherwise the reason it is not."""
    if tool not in scope:
        return f"tool {tool!r} is not in the brief"
    if action not in scope[tool].allowed_actions:
        allowed = ", ".join(sorted(scope[tool].allowed_actions))
        return f"action {action!r} is not allowed on {tool!r} (allowed: {allowed})"
    return None
