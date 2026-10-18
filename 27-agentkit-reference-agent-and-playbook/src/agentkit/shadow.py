"""Shadow mode: replay historical cases through the kit and compare its proposal with the recorded human outcome.

In shadow mode every write is a dry run and both person gates park the case, so the kit proposes and
never acts. The recorded human outcome is never an input to the kit; it is only used afterwards, here.

A proposal is scored like this:
  agree                same outcome (and, for a resubmit, the same field and the same corrected value)
  disagree_outcome     a different outcome
  disagree_correction  both say resubmit, but the corrected value differs
  deferred             the kit sent the case to a person to judge (S07): not scored either way
  queued               the kit sent the case back to the human queue: not scored either way
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .catalog import DEFER, HUMAN_OUTCOMES, QUEUE


def judge_pair(result, human: dict) -> str:
    p = result.proposed_outcome
    if p == DEFER:
        return "deferred"
    if p == QUEUE:
        return "queued"
    if p != human["human_outcome"]:
        return "disagree_outcome"
    if p == "RESUBMIT":
        c = result.correction
        if not c or c["field"] != human["corrected_field"] or c["new"] != human["corrected_value"]:
            return "disagree_correction"
    return "agree"


def replay(kit, case_ids: Optional[Iterable[str]] = None, world: Optional[dict] = None) -> list:
    """Run the cases in arrival order. Returns the orchestrator's results (redeliveries included)."""
    if case_ids is None:
        if world is None:
            raise ValueError("pass case_ids or a world")
        case_ids = [c["case_id"] for c in world["cases"]]
    return kit.orchestrator.run_all(list(case_ids))


def _rate(a: int, b: int) -> Optional[float]:
    return None if a + b == 0 else round(a / (a + b), 4)


def score(results: List, outcomes: Dict[str, dict], truth: Optional[Dict[str, dict]] = None) -> dict:
    kinds: Dict[str, int] = {}
    by_class: Dict[str, dict] = {}
    by_proposal: Dict[str, dict] = {}
    confusion: Dict[str, Dict[str, int]] = {}
    routes = {"auto": 0, "to_person": 0, "human_queue": 0}
    to_person: Dict[str, int] = {}
    queue_reasons: Dict[str, int] = {}
    disagreements = []
    n = 0
    for r in results:
        if r.redelivery:
            continue
        n += 1
        h = outcomes[r.case_id]
        k = judge_pair(r, h)
        kinds[k] = kinds.get(k, 0) + 1
        routes[r.route] += 1
        if r.route == "to_person":
            key = r.gate or ("escalation" if r.state == "ESCALATED" else "approved")
            to_person[key] = to_person.get(key, 0) + 1
        if r.route == "human_queue":
            queue_reasons[r.reason_kind] = queue_reasons.get(r.reason_kind, 0) + 1
        hc = by_class.setdefault(h["human_outcome"], {"n": 0, "agree": 0, "disagree": 0, "deferred": 0, "queued": 0})
        hc["n"] += 1
        pc = by_proposal.setdefault(r.proposed_outcome, {"n": 0, "agree": 0, "disagree": 0})
        pc["n"] += 1
        confusion.setdefault(r.proposed_outcome, {}).setdefault(h["human_outcome"], 0)
        confusion[r.proposed_outcome][h["human_outcome"]] += 1
        if k == "agree":
            hc["agree"] += 1
            pc["agree"] += 1
        elif k.startswith("disagree"):
            hc["disagree"] += 1
            pc["disagree"] += 1
            disagreements.append({"case_id": r.case_id, "proposed": r.proposed_outcome, "human": h["human_outcome"],
                                  "kind": k, "route": r.route,
                                  "scenario": (truth or {}).get(r.case_id, {}).get("scenario", "")})
        else:
            hc[k] += 1
    for hc in by_class.values():
        hc["agreement_rate"] = _rate(hc["agree"], hc["disagree"])
    for pc in by_proposal.values():
        pc["agreement_rate"] = _rate(pc["agree"], pc["disagree"])
    agree = kinds.get("agree", 0)
    dis = kinds.get("disagree_outcome", 0) + kinds.get("disagree_correction", 0)
    return {"cases": n, "scored": agree + dis, "agree": agree, "disagree": dis,
            "agreement_rate": _rate(agree, dis), "deferred": kinds.get("deferred", 0), "queued": kinds.get("queued", 0),
            "kinds": dict(sorted(kinds.items())), "by_human_class": dict(sorted(by_class.items())),
            "by_proposal": dict(sorted(by_proposal.items())),
            "confusion": {p: dict(sorted(v.items())) for p, v in sorted(confusion.items())}, "routes": routes,
            "to_person_detail": dict(sorted(to_person.items())), "queue_reasons": dict(sorted(queue_reasons.items())),
            "disagreements": disagreements}


def auto_wrong(results: List, outcomes: Dict[str, dict]) -> dict:
    """Cases the kit finished on its own (route auto) whose recorded human outcome is different."""
    auto = [r for r in results if not r.redelivery and r.route == "auto"]
    wrong = [r for r in auto if judge_pair(r, outcomes[r.case_id]) != "agree"]
    return {"auto": len(auto), "wrong": len(wrong), "rate": (len(wrong) / len(auto)) if auto else 0.0,
            "cases": [r.case_id for r in wrong]}
