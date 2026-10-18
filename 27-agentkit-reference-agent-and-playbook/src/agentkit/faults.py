"""Fault injection driven by data/fault_schedule.csv (or rows built in a test).

Fault types
  timeout            the tool call raises ToolTimeout on the listed attempts
  timeout_after_write  the write is applied, then the call raises ToolTimeout (the answer was lost)
  malformed_output   the tool answers with a garbled payload on the listed attempts
  rogue_call         before the named step, the agent tries a call outside the brief's scope
  duplicate_delivery the replay delivers the same case twice

`attempts` is "1", "1,2" or "*" (every attempt). The attempt number counts calls of the same
(case, tool, action), starting at 1.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from .errors import ToolTimeout


def _parse_attempts(spec: str):
    spec = (spec or "1").strip()
    if spec == "*":
        return None
    return {int(x) for x in spec.split(",") if x.strip()}


class FaultInjector:
    def __init__(self, rows: Iterable[dict] = ()):
        self.rows: List[dict] = [dict(r) for r in rows]
        self._call: Dict[Tuple[str, str, str], List[dict]] = {}
        self._rogue: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}
        self._dups: Set[str] = set()
        for r in self.rows:
            ft = r["fault_type"]
            if ft in ("timeout", "malformed_output", "timeout_after_write"):
                self._call.setdefault((r["case_id"], r["tool"], r["action"]), []).append(
                    {"type": ft, "attempts": _parse_attempts(r.get("attempts", "1"))})
            elif ft == "rogue_call":
                tool, action = r["payload"].split(".", 1)
                self._rogue.setdefault((r["case_id"], r["step"]), []).append((tool, action))
            elif ft == "duplicate_delivery":
                self._dups.add(r["case_id"])
            else:
                raise ValueError(f"unknown fault type {ft!r}")

    def _hit(self, case_id: str, tool: str, action: str, attempt: int, ftype: str) -> bool:
        for f in self._call.get((case_id, tool, action), []):
            if f["type"] == ftype and (f["attempts"] is None or attempt in f["attempts"]):
                return True
        return False

    def before_call(self, case_id: str, tool: str, action: str, attempt: int) -> None:
        if self._hit(case_id, tool, action, attempt, "timeout"):
            raise ToolTimeout(f"{tool}.{action} timed out (injected, attempt {attempt})")

    def corrupt(self, case_id: str, tool: str, action: str, attempt: int, result):
        if self._hit(case_id, tool, action, attempt, "malformed_output"):
            return {"error": "garbled payload (injected)"}
        return result

    def timeout_after_write(self, case_id: str, tool: str, action: str, attempt: int) -> bool:
        return self._hit(case_id, tool, action, attempt, "timeout_after_write")

    def rogue_calls(self, case_id: str, step: str) -> List[Tuple[str, str]]:
        return list(self._rogue.get((case_id, step), []))

    def redeliveries(self) -> Set[str]:
        return set(self._dups)

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for r in self.rows:
            out[r["fault_type"]] = out.get(r["fault_type"], 0) + 1
        return out
