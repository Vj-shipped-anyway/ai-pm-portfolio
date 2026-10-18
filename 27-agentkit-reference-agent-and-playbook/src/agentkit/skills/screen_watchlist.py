"""S06 screen_watchlist: screen both names against the watch list. Every hit is logged in the decision."""

from __future__ import annotations

from ..matching import HIT_AT
from .base import Skill, SkillResult


def run(ctx) -> SkillResult:
    names = []
    for nm in (ctx.payment["beneficiary_name"], ctx.exception["returned_name"]):
        if nm and nm not in names:
            names.append(nm)
    hits = []
    for nm in names:
        res = ctx.call("watchlist", "screen_party", name=nm)
        for c in res["candidates"]:
            if c["score"] >= HIT_AT:
                hits.append({"party_id": c["party_id"], "list_name": c["name"], "score": c["score"], "queried": nm})
    ctx.hits = hits
    if hits:
        ctx.disposition = "ESCALATE_COMPLIANCE"
        ctx.needs_judgment = False
        top = max(hits, key=lambda h: h["score"])
        return SkillResult("watchlist_hit", f"{len(hits)} hit(s); highest {top['party_id']} at {top['score']:.2f}; "
                           "escalate to compliance", {"hits": hits})
    return SkillResult("no_hit", f"{len(names)} name(s) screened, no candidate at or above {HIT_AT}",
                       {"hits": [], "screened": len(names)})


SKILL = Skill("S06", "screen_watchlist", ("watchlist",), run, requires=('payment', 'exception'))
