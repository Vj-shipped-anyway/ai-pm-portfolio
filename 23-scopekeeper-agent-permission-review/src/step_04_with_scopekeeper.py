"""Step 4 - With ScopeKeeper: usage-versus-grant diff, least-privilege proposal, dry-run replay.

ScopeKeeper compares what each agent is allowed to do (its grants, wildcards expanded) with what
it did in the last 90 days (the call log), and proposes the smallest scope set that still covers
every call. Five parts, all plain rules. No model is used anywhere in this step.

  1. Usage-versus-grant diff. For every grant: was a scope it reaches called? A call with no agent
     tag (shared service account) is credited to every agent on that account who could have made
     it, so a grant in use is never marked unused. The price is a few unneeded grants kept.
  2. Breadth score per agent: the share of its effective entitlements it never touched.
  3. Proposed scope set per agent: keep what was called; remove what was not; replace a wildcard
     by the specific scopes called.
  4. Dry-run replay: replay the 90 days of calls under the proposal and count the calls denied.
  5. Risk ranking of agents: unused access weighted by impact and tier, plus calls logged without
     the human approval the catalog requires, plus a shared service account.

POLICY CONSTANTS below are assumptions of a modeled bank, not legal advice and not a standard.
Known limit, left in on purpose: a scope used once a quarter looks unused in a 90-day window.

Run (from src/):
    python3 step_04_with_scopekeeper.py

Output: a readable summary, plus CSV and JSON in out/.
"""

from __future__ import annotations

import csv
import json

from step_01_status_quo import (IMPACT_ORDER, OUT_DIR, WINDOW_DAYS, expand, grant_usage, load_all, replay_calls,
                                usage_index)
from step_02_annual_recertification import summarize as summarize_step2
from step_03_deficiencies_exposed import summarize as summarize_step3

# --- Policy constants: assumptions of a modeled bank -------------------------------------------
IMPACT_WEIGHT = {"read": 1, "write": 3, "external_message": 5, "money_movement": 8}
TIER_MULTIPLIER = {"high": 3, "medium": 2, "low": 1}
APPROVAL_POINTS = 2          # per call logged without the required approval (agent-tagged calls only)
SHARED_POINTS = 10           # flat, for holding a shared service account
AGENTS_IN_ESTATE = 200       # MODELED: agents in a bank's estate; edit to use your own
ESTATE_SENSITIVITY = (50, 100, 200, 500)


def pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


# ---------------------------------------------------------------------------
# The mechanic
# ---------------------------------------------------------------------------
def propose(data: dict, gu: list) -> list:
    """One proposal row per grant: keep, remove, or narrow (wildcard replaced by the scopes called)."""
    rows = []
    for g in gu:
        reach = expand(data, g["scope"])
        if not g["used"]:
            action, after = "remove", []
            why = "wildcard never called" if g["wildcard"] else "no call in 90 days"
        elif g["wildcard"] and len(g["touched"]) < len(reach):
            action, after = "narrow", list(g["touched"])
            why = f"{len(after)} of {len(reach)} scopes it reaches were called"
        else:
            action, after = "keep", list(reach)
            why = "every scope it reaches was called" if g["wildcard"] else "called in the window"
        rows.append({"agent_id": g["agent_id"], "scope": g["scope"], "action": action, "after": after,
                     "reason": why, "impact": g["impact"], "needs_approval": g["needs_approval"],
                     "wildcard": g["wildcard"], "post_launch": g["post_launch"], "has_ticket": g["has_ticket"],
                     "ticket_id": g["ticket_id"], "granted_on": g["granted_on"],
                     "calls_tagged": g["calls_tagged"], "calls_shared": g["calls_shared"], "used": g["used"],
                     "only_shared": g["only_shared"], "reach": len(reach)})
    return rows


def proposed_sets(data: dict, prop: list) -> dict:
    out = {a["agent_id"]: set() for a in data["agents"]}
    for r in prop:
        out[r["agent_id"]].update(r["after"])
    return out


def agent_rows(data: dict, prop: list, P: dict, recert: dict) -> list:
    """Per-agent diff, breadth score and risk points."""
    cat = data["catalog"]
    removed_rec = {(r["agent_id"], r["scope"]) for r in recert["rows"] if r["verdict"] == "removed"}
    bad_tagged: dict = {}
    for c in data["calls"]:
        if c["agent_id"] and cat[c["scope"]]["needs_approval"] and c["human_approved"] == "no":
            bad_tagged[c["agent_id"]] = bad_tagged.get(c["agent_id"], 0) + 1
    rows = []
    for a in data["agents"]:
        aid = a["agent_id"]
        E = set(data["effective"][aid])
        unused = sorted(E - P[aid])
        mine = [r for r in prop if r["agent_id"] == aid]
        weight = sum(IMPACT_WEIGHT[cat[s]["impact"]] for s in unused)
        shared = a["service_account"] in data["shared_accounts"]
        points = (TIER_MULTIPLIER[a["risk_tier"]] * weight + APPROVAL_POINTS * bad_tagged.get(aid, 0)
                  + (SHARED_POINTS if shared else 0))
        rows.append({
            "agent_id": aid, "purpose": a["purpose"], "owner": a["owner"], "tier": a["risk_tier"],
            "service_account": a["service_account"], "shared": shared,
            "siblings": [x for x in data["sa_agents"][a["service_account"]] if x != aid],
            "launched_on": a["launched_on"], "grants": len(mine),
            "keep": sum(1 for r in mine if r["action"] == "keep"),
            "remove": sum(1 for r in mine if r["action"] == "remove"),
            "narrow": sum(1 for r in mine if r["action"] == "narrow"),
            "recert_removed": sum(1 for r in mine if (r["agent_id"], r["scope"]) in removed_rec),
            "reach": len(E), "proposed": len(P[aid]), "cut": len(unused),
            "breadth_pct": pct(len(unused), len(E)),
            "unused_scopes": unused, "proposed_scopes": sorted(P[aid]),
            "unused_weight": weight, "unapproved_tagged": bad_tagged.get(aid, 0), "risk_points": points,
            "calls": sum(1 for c in data["calls"] if c["agent_id"] == aid),
        })
    order = sorted(rows, key=lambda r: (-r["risk_points"], r["agent_id"]))
    for i, r in enumerate(order, 1):
        r["rank"] = i
    return rows


def analyze(data: dict | None = None) -> dict:
    data = data or load_all()
    u = usage_index(data)
    gu = grant_usage(data, u)
    prop = propose(data, gu)
    P = proposed_sets(data, prop)
    s2, s3 = summarize_step2(data), summarize_step3(data)
    ag = agent_rows(data, prop, P, s2)
    cat = data["catalog"]

    # dry-run replay of the 90 days under the proposal
    denied = replay_calls(data, P)
    held = [c for c in data["calls"] if cat[c["scope"]]["needs_approval"] and c["human_approved"] == "no"]

    # truth scoring: grants
    needed_grant = {k: v["needed"] for k, v in data["needed"].items()}
    unneeded = {k for k, v in needed_grant.items() if not v}
    sk_removed = {(r["agent_id"], r["scope"]) for r in prop if r["action"] == "remove"}
    rec_removed = {(r["agent_id"], r["scope"]) for r in s2["rows"] if r["verdict"] == "removed"}
    sk_narrow = [r for r in prop if r["action"] == "narrow"]

    # truth scoring: entitlements
    E = {(aid, s) for aid, scopes in data["effective"].items() for s in scopes}
    Pset = {(aid, s) for aid, scopes in P.items() for s in scopes}
    N = {(aid, s) for (aid, _), v in data["needed"].items() if v["needed"] for s in v["needed_scopes"]}
    assert N <= E and Pset <= E
    unneeded_ent = E - N
    cut_ent = E - Pset

    # known limit: rare-use scopes
    rare_rows = []
    for r in data["rare"]:
        removed = r["scope"] not in P[r["agent_id"]]
        rare_rows.append({**r, "removed": removed})
    rare_removed = [r for r in rare_rows if r["removed"]]
    rare_kept = [r for r in rare_rows if not r["removed"]]
    next_q_denied = sum(r["calls_next_quarter"] for r in rare_removed)

    # unneeded grants the proposal keeps because a sibling's untagged calls were credited
    kept_unneeded = sorted(unneeded - sk_removed)
    kept_unneeded_rows = [r for r in prop if (r["agent_id"], r["scope"]) in set(kept_unneeded)]

    n = len(prop)
    y = len(unneeded & sk_removed)
    x = len(unneeded & rec_removed)
    per_agent_sk = y / len(data["agents"])
    per_agent_rec = x / len(data["agents"])
    per_agent_denied = next_q_denied / len(data["agents"])
    summary = {
        "agents": len(data["agents"]), "grants": n, "calls": len(data["calls"]),
        "reach_before": len(E), "reach_after": len(Pset), "reach_cut": len(cut_ent),
        "reach_cut_pct": pct(len(cut_ent), len(E)),
        "keep": sum(1 for r in prop if r["action"] == "keep"),
        "remove": len(sk_removed), "narrow": len(sk_narrow),
        "narrow_cut": sum(r["reach"] - len(r["after"]) for r in sk_narrow),
        "replay_calls": len(data["calls"]), "replay_denied": len(denied),
        "approval_held": len(held),
        "recert_replay_denied": s2["replay_denied"],
        "unneeded_grants": len(unneeded), "unneeded_pct": pct(len(unneeded), n),
        "sk_removed_unneeded": y, "sk_removed_unneeded_pct": pct(y, len(unneeded)),
        "sk_removed_needed": len(sk_removed - unneeded),
        "sk_kept_unneeded": len(kept_unneeded),
        "rec_removed": len(rec_removed), "rec_removed_unneeded": x, "rec_removed_unneeded_pct": pct(x, len(unneeded)),
        "rec_removed_needed": len(rec_removed - unneeded),
        "unused_grants_log": s3["d1"]["unused"],
        "ent_needed": len(N), "ent_unneeded": len(unneeded_ent),
        "ent_unneeded_cut": len(unneeded_ent & cut_ent), "ent_unneeded_kept": len(unneeded_ent & Pset),
        "ent_needed_cut": len(N & cut_ent),
        "rare_grants": len(rare_rows), "rare_removed": len(rare_removed), "rare_kept": len(rare_kept),
        "next_q_denied": next_q_denied,
        "next_q_denied_by_rare": {f"{r['agent_id']} {r['scope']}": r["calls_next_quarter"] for r in rare_removed},
        "per_agent_sk": round(per_agent_sk, 2), "per_agent_rec": round(per_agent_rec, 2),
        "per_agent_denied": round(per_agent_denied, 2),
        "agents_in_estate": AGENTS_IN_ESTATE,
        "utility_grants": round((per_agent_sk - per_agent_rec) * AGENTS_IN_ESTATE),
        "utility_denied_calls": round(per_agent_denied * AGENTS_IN_ESTATE),
        "utility_sensitivity": {str(k): round((per_agent_sk - per_agent_rec) * k) for k in ESTATE_SENSITIVITY},
        "top_risk_agent": min(ag, key=lambda r: r["rank"])["agent_id"],
    }
    return {"data": data, "usage": u, "grant_usage": gu, "proposal": prop, "proposed": P, "agents": ag,
            "recert": s2, "deficiencies": s3, "summary": summary, "denied": denied, "held": held,
            "rare": rare_rows, "kept_unneeded": kept_unneeded_rows, "unneeded": unneeded,
            "sk_removed": sk_removed, "rec_removed": rec_removed}


# ---------------------------------------------------------------------------
# Self-checks
# ---------------------------------------------------------------------------
def selftest(a: dict) -> int:
    data, P = a["data"], a["proposed"]
    n = 0
    for aid, scopes in P.items():
        assert scopes <= set(data["effective"][aid])           # never proposes more than the agent had
        n += 1
    assert not a["denied"]                                      # in-sample replay denies nothing
    n += 1
    # the replay is not vacuous: take the busiest tagged scope away from one agent and calls are denied
    busy = max(((c["agent_id"], c["scope"]) for c in data["calls"] if c["agent_id"]),
               key=lambda k: sum(1 for c in data["calls"] if (c["agent_id"], c["scope"]) == k))
    cut = {k: set(v) for k, v in P.items()}
    cut[busy[0]].discard(busy[1])
    assert len(replay_calls(data, cut)) > 0
    n += 1
    assert a["summary"]["keep"] + a["summary"]["remove"] + a["summary"]["narrow"] == a["summary"]["grants"]
    n += 1
    return n


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_outputs(a: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_proposal.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_id", "scope", "action", "replace_with", "calls_tagged", "calls_untagged_credited", "reason"])
        for r in a["proposal"]:
            w.writerow([r["agent_id"], r["scope"], r["action"], ";".join(r["after"]) if r["action"] == "narrow" else "",
                        r["calls_tagged"], r["calls_shared"], r["reason"]])
    with open(OUT_DIR / "step_04_agent_summary.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["rank", "agent_id", "tier", "reach", "proposed", "cut", "breadth_pct", "keep", "remove", "narrow",
                    "unapproved_tagged", "risk_points"])
        for r in sorted(a["agents"], key=lambda r: r["rank"]):
            w.writerow([r["rank"], r["agent_id"], r["tier"], r["reach"], r["proposed"], r["cut"], r["breadth_pct"],
                        r["keep"], r["remove"], r["narrow"], r["unapproved_tagged"], r["risk_points"]])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(a["summary"], f, indent=2)


def main() -> None:
    a = analyze()
    checks = selftest(a)
    s, data = a["summary"], a["data"]
    write_outputs(a)

    print("\n" + "=" * 78)
    print("Step 4 - ScopeKeeper: usage-versus-grant diff, least-privilege proposal, dry-run replay")
    print("=" * 78)
    print(f"\nSelf-checks passed: {checks}. No model is used in this step. Everything is a rule you can read.")
    print(f"Input: {s['grants']} grants, {s['reach_before']} effective entitlements, {s['calls']:,} calls over {WINDOW_DAYS} days.\n")

    print("USAGE VERSUS GRANT (one row per agent, largest breadth first)")
    print(f"{'agent':<6} {'tier':<7} {'reach':>5} {'proposed':>8} {'cut':>4} {'breadth':>8} {'keep':>5} {'remove':>7} {'narrow':>7}")
    print(f"{'-' * 6} {'-' * 7} {'-' * 5} {'-' * 8} {'-' * 4} {'-' * 8} {'-' * 5} {'-' * 7} {'-' * 7}")
    for r in sorted(a["agents"], key=lambda r: (-r["breadth_pct"], r["agent_id"])):
        print(f"{r['agent_id']:<6} {r['tier']:<7} {r['reach']:>5} {r['proposed']:>8} {r['cut']:>4} "
              f"{r['breadth_pct']:>7.1f}% {r['keep']:>5} {r['remove']:>7} {r['narrow']:>7}")

    print("\nPROPOSAL")
    print(f"  Grants: keep {s['keep']}, remove {s['remove']}, narrow {s['narrow']} (a wildcard replaced by the scopes called)")
    print(f"  Effective entitlements: {s['reach_before']} before, {s['reach_after']} after "
          f"({s['reach_cut']} cut, {s['reach_cut_pct']}%); narrowing the wildcards accounts for {s['narrow_cut']} of the cut")

    print("\nDRY-RUN REPLAY (the 90 days of calls under the proposed sets)")
    print(f"  Calls replayed: {s['replay_calls']:,}; denied: {s['replay_denied']}")
    print("  By construction: the proposal is built from these same calls, so in-sample denials are 0 by design.")
    print(f"  The replay is not vacuous: the self-check removes one busy scope from one agent and calls are denied.")
    print(f"  Calls to approval-required scopes logged without approval: {s['approval_held']} "
          "(the proposal keeps the scope; these calls would be held for a human)")
    print(f"  For comparison, the recertification result replayed the same way denies {s['recert_replay_denied']} calls.")

    print("\nRISK RANKING (unused access by impact and tier, plus unapproved calls, plus a shared account)")
    print(f"  points = tier x sum of impact weights of unused entitlements + {APPROVAL_POINTS} x unapproved calls + {SHARED_POINTS} if the account is shared")
    print(f"  weights (assumptions of a modeled bank): " + ", ".join(f"{k} {v}" for k, v in IMPACT_WEIGHT.items())
          + "; tier " + ", ".join(f"{k} x{v}" for k, v in TIER_MULTIPLIER.items()))
    print(f"{'#':>2} {'agent':<6} {'tier':<7} {'unused scopes':>13} {'unapproved':>10} {'shared':>6} {'points':>7}")
    for r in sorted(a["agents"], key=lambda r: r["rank"])[:8]:
        print(f"{r['rank']:>2} {r['agent_id']:<6} {r['tier']:<7} {r['cut']:>13} {r['unapproved_tagged']:>10} "
              f"{'yes' if r['shared'] else 'no':>6} {r['risk_points']:>7}")

    print("\nMEASURED AGAINST THE GENERATOR'S TRUTH (data/needed_truth.csv)")
    print(f"  Grants the agent does not need: {s['unneeded_grants']} of {s['grants']} ({s['unneeded_pct']}%)")
    print(f"  Removed by recertification: {s['rec_removed_unneeded']} of {s['unneeded_grants']} ({s['rec_removed_unneeded_pct']}%); "
          f"needed grants it removed: {s['rec_removed_needed']}")
    print(f"  Removed by ScopeKeeper:     {s['sk_removed_unneeded']} of {s['unneeded_grants']} ({s['sk_removed_unneeded_pct']}%); "
          f"needed grants it removed: {s['sk_removed_needed']} (the quarterly ones, see the known limit)")
    print(f"  Entitlements the agents do not need: {s['ent_unneeded']} of {s['reach_before']}; "
          f"cut {s['ent_unneeded_cut']}, kept {s['ent_unneeded_kept']}; needed entitlements cut: {s['ent_needed_cut']}")

    print("\nKNOWN LIMIT (left in on purpose)")
    print(f"  A scope used once a quarter looks unused in a 90-day window. {s['rare_grants']} grants in the data are "
          "legitimate and quarterly (data/rare_use_truth.csv).")
    print(f"  The proposal removes {s['rare_removed']} of them. Their next use falls after the review date, so the first quarter after")
    print(f"  the cut would deny {s['next_q_denied']} legitimate calls (by construction, from rare_use_truth.csv):")
    for r in a["rare"]:
        if r["removed"]:
            print(f"    {r['agent_id']} {r['scope']:<28} next use {r['next_use_date']}, {r['calls_next_quarter']} calls  ({r['why']})")
    for r in a["rare"]:
        if not r["removed"]:
            print(f"    {r['agent_id']} {r['scope']:<28} kept only because a sibling on the shared account called the scope")
    print(f"  Owners would see {s['remove']} removal proposals; {s['rare_removed']} of them ({pct(s['rare_removed'], s['remove'])}%) are periodic scopes.")
    print("  The logs cannot show this. The fix is an owner attestation flag on each removal proposal")
    print("  (\"is this scope periodic?\"). It is designed, not built, and not tested with real owners.")

    print("\nALSO KEPT (second miss, from shared service accounts)")
    print(f"  {s['sk_kept_unneeded']} grants the agent does not need stay in the proposal, because untagged calls on a shared")
    print("  account are credited to every agent that could have made them:")
    for r in a["kept_unneeded"]:
        print(f"    {r['agent_id']} {r['scope']}")
    print("  The fix is one service account per agent, not something the logs can show either.")

    print("\nUTILITY (unneeded grants removed per agent, then scaled to an estate)")
    print(f"  Recertification: {s['rec_removed_unneeded']} unneeded grant removed over {s['agents']} agents -> {s['per_agent_rec']} per agent")
    print(f"  ScopeKeeper:     {s['sk_removed_unneeded']} unneeded grants removed over {s['agents']} agents -> {s['per_agent_sk']} per agent")
    print(f"  Cost side: {s['next_q_denied']} legitimate calls denied next quarter over {s['agents']} agents -> {s['per_agent_denied']} per agent")
    print(f"  MODELED: {s['agents_in_estate']} agents in a bank's estate (assumption, not measured; edit AGENTS_IN_ESTATE).")
    print(f"  Utility = ({s['per_agent_sk']} - {s['per_agent_rec']}) x {s['agents_in_estate']} = about {s['utility_grants']} unneeded grants removed")
    print(f"  and about {s['utility_denied_calls']} legitimate calls denied next quarter until owners attest the periodic scopes")
    print("  Sensitivity to estate size: " + ", ".join(f"{k} agents: {v}" for k, v in s["utility_sensitivity"].items()))

    print("\nWrote step_04_proposal.csv, step_04_agent_summary.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
