"""Step 4 - The fix: PortfolioBoard.

An evidence-based status for every program, instead of the status each owner picks. Plain rules,
no model. Five parts:

  1. Evidence status. A program is RED if any gate criterion in force at its stage is not met.
     It is AMBER if every criterion is met but some evidence is past its freshness rule, if the
     program is slipped (its target quarter has passed), or if it depends, directly or through a
     chain, on a program that is red by evidence or slipped. Otherwise GREEN.
  2. Capacity grid. Planned demand against supply for four teams over four quarters.
  3. Dependency propagation. For each program, the upstream programs that block it.
  4. Pull rule. When a stage is above its work-in-progress limit, suggest which programs to pause
     (ranked RED first, then blocked by an upstream program, then amber, then clear, and within each
     by the lowest owner-estimated value per scarce model-risk-review FTE). Programs that other
     programs depend on are never suggested. Then, quarter by quarter, spend the review team's
     supply on the rest, unblocked first and then by value per review FTE, and defer what does not fit.
  5. Benefit-at-risk rollup. Owner-estimated benefit on programs that are red by evidence.
     Modeled: these are owner estimates, never measured benefit.

Scored against data/program_truth.csv, which the generator wrote. The board reads only the
attested evidence, so it cannot see a criterion that was attested "met" but is not truly met.
Three such false attestations are planted. That is the known limit, printed at the end.

Run (from src/):
    python3 step_04_with_portfolioboard.py

Output: a readable summary, plus CSV and JSON files in out/.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict

from step_01_rag_status_report import (OUT_DIR, PROGRAMS_PER_SPONSOR, STAGES, TEAM_LABEL, TEAMS, load_all, pct,
                                       usd_m)
from step_03_deficiencies_exposed import (WINDOW_WEEKS, capacity_grid, evidence_flags, review_waits,
                                          slipped_programs, upstream_issues, wip_table)

SEVERITY = {"RED": 0, "AMBER": 1, "GREEN": 2}
TIER_NAME = {0: "clear", 1: "amber", 2: "blocked", 3: "red"}
SCARCE = "model_risk_review"


def _ids(items: list) -> str:
    return ", ".join(items)


def build_board(data: dict) -> dict:
    flags = evidence_flags(data)
    slipped = slipped_programs(data)
    issues = upstream_issues(data, flags, slipped)
    plan_q = data["quarters"][0]
    need = defaultdict(float)
    for r in data["demand"]:
        need[(r["program_id"], r["team"], r["quarter"])] += r["need_fte"]
    grid = capacity_grid(data)
    cell = {(c["team"], c["quarter"]): c for c in grid}
    prog = data["prog"]

    rows = []
    for p in data["programs"]:
        pid = p["program_id"]
        f, iss = flags[pid], issues[pid]
        parts, short = [], []
        if f["unmet"]:
            parts.append("gate criteria not met: " + ", ".join(data["crit"][c]["criterion"] for c in f["unmet"]))
            short.append(f"{len(f['unmet'])} unmet ({_ids(f['unmet'])})")
        if f["stale"]:
            parts.append("evidence past its freshness rule: " + ", ".join(data["crit"][c]["criterion"] for c in f["stale"]))
            short.append(f"{len(f['stale'])} stale ({_ids(f['stale'])})")
        if pid in slipped:
            parts.append(f"slipped: target {p['target_quarter']} has passed")
            short.append(f"slipped ({p['target_quarter']})")
        if iss:
            parts.append("depends on " + "; ".join(
                f"{i['program_id']} {prog[i['program_id']]['name']} ({i['why']}{'' if i['direct'] else ', through a chain'})"
                for i in iss))
            short.append("behind " + _ids([i["program_id"] for i in iss]))
        if not parts:
            parts.append("every criterion met with fresh evidence; no red or slipped upstream program")
            short.append("clear")
        if f["status"] == "RED":
            status = "RED"
        elif f["stale"] or pid in slipped or iss:
            status = "AMBER"
        else:
            status = "GREEN"
        tier = 3 if status == "RED" else (2 if iss else (1 if status == "AMBER" else 0))
        mr_need = round(need[(pid, SCARCE, plan_q)], 2)
        value = p["est_benefit_usd"] * p["benefit_confidence"]
        density = (value / mr_need) if mr_need > 0 else float("inf")
        short_teams = []
        for team in TEAMS:
            n = round(need[(pid, team, plan_q)], 2)
            c = cell[(team, plan_q)]
            if n > 0 and c["over"]:
                short_teams.append({"team": team, "need": n, "ratio_pct": round(100.0 * c["ratio"], 1),
                                    "pro_rata": round(n * c["supply"] / c["demand"], 2)})
        rows.append({
            "program_id": pid, "name": p["name"], "stage": p["stage"], "owner": p["owner"],
            "reported": p["self_reported_rag"].upper(), "evidence_status": f["status"], "board": status,
            "unmet": f["unmet"], "stale": f["stale"], "slipped": pid in slipped, "target_quarter": p["target_quarter"],
            "blocked_by": [dict(i) for i in iss], "reason": "; ".join(parts), "why_short": "; ".join(short),
            "tier": tier, "mr_need": mr_need, "value": round(value), "density": density,
            "est_benefit_usd": p["est_benefit_usd"], "benefit_confidence": p["benefit_confidence"],
            "short_teams": short_teams, "action": "", "action_reason": "", "actions": {},
            "deferred_later": [], "paused": False, "pause_rank": None,
        })
    blocks = defaultdict(int)
    for r in rows:
        for i in r["blocked_by"]:
            blocks[i["program_id"]] += 1
    for r in rows:
        r["blocks"] = blocks.get(r["program_id"], 0)
    return {"rows": rows, "flags": flags, "slipped": slipped, "issues": issues, "grid": grid, "plan_quarter": plan_q}


def pull_rule(data: dict, board: dict) -> dict:
    """Pause the lowest-priority programs in any stage above its limit. Then, quarter by quarter, spend
    the model-risk-review supply on the programs that remain, ranked unblocked first and then by owner-
    estimated value per review FTE; programs that do not fit are deferred."""
    rows = board["rows"]
    wip = wip_table(data)
    depended_on = {u for ups in data["ups"].values() for u in ups}
    pauses = []
    for w in wip:
        if not w["over"]:
            continue
        cands = [r for r in rows if r["stage"] == w["stage"] and r["program_id"] not in depended_on]
        order = sorted(cands, key=lambda r: (-r["tier"], r["density"], r["program_id"]))
        for rank, r in enumerate(order, 1):
            r["pause_rank"] = rank
        for r in order[:w["over_by"]]:
            r["paused"] = True
            pauses.append({"stage": w["stage"], "program_id": r["program_id"], "name": r["name"],
                           "tier": TIER_NAME[r["tier"]], "mr_need": r["mr_need"], "why": r["why_short"],
                           "benefit": r["est_benefit_usd"], "rank": r["pause_rank"], "of": len(order),
                           "wip": w["wip"], "limit": w["limit"]})
    paused_ids = {p["program_id"] for p in pauses}

    need_mr = defaultdict(float)
    for d in data["demand"]:
        if d["team"] == SCARCE:
            need_mr[(d["program_id"], d["quarter"])] += d["need_fte"]
    for r in rows:
        r["actions"] = {}
    quarters = []
    for q in data["quarters"]:
        supply = data["capacity"][(SCARCE, q)]
        demand_all = round(sum(need_mr[(r["program_id"], q)] for r in rows), 2)
        elig = [r for r in rows if r["program_id"] not in paused_ids and need_mr[(r["program_id"], q)] > 0]
        order = sorted(elig, key=lambda r: (1 if r["blocked_by"] else 0,
                                            -(r["value"] / need_mr[(r["program_id"], q)]), r["program_id"]))
        used, funded, deferred = 0.0, [], []
        for r in order:
            n = need_mr[(r["program_id"], q)]
            if used + n <= supply + 1e-9:
                used += n
                funded.append(r["program_id"])
                r["actions"][q] = "FUND"
            else:
                deferred.append(r["program_id"])
                r["actions"][q] = "DEFER"
        for r in rows:
            if r["program_id"] in paused_ids:
                r["actions"][q] = "PAUSE"
            elif q not in r["actions"]:
                r["actions"][q] = "FUND"     # needs no model risk review time this quarter
        quarters.append({"quarter": q, "supply": supply, "demand": demand_all,
                         "demand_after_pause": round(sum(need_mr[(r["program_id"], q)] for r in elig), 2),
                         "funded_fte": round(used, 2), "funded": funded, "deferred": deferred,
                         "deferred_fte": round(sum(need_mr[(pid, q)] for pid in deferred), 2)})
    plan_q = board["plan_quarter"]
    for r in rows:
        r["action"] = r["actions"][plan_q]
        later = [q for q in data["quarters"][1:] if r["actions"][q] == "DEFER"]
        r["deferred_later"] = later
        if r["action"] == "PAUSE":
            r["action_reason"] = (f"stage {r['stage']} holds {next(w['wip'] for w in wip if w['stage'] == r['stage'])} programs against a "
                                  f"limit of {next(w['limit'] for w in wip if w['stage'] == r['stage'])}; this one ranks "
                                  f"{r['pause_rank']} of {sum(1 for x in rows if x['stage'] == r['stage'] and x['program_id'] not in depended_on)} "
                                  f"for pausing ({TIER_NAME[r['tier']]}); programs other teams depend on are never paused")
        elif r["action"] == "DEFER":
            r["action_reason"] = ("ranked after unblocked programs and the supply is spent" if r["blocked_by"]
                                  else "lowest owner-estimated value per review FTE once the supply is spent")
        elif r["mr_need"] == 0:
            r["action_reason"] = "needs no model risk review time this quarter"
        else:
            r["action_reason"] = f"fits the {plan_q} model risk review supply"
        if r["action"] == "FUND" and r["blocked_by"]:
            r["action_reason"] += "; it still depends on " + _ids([i["program_id"] for i in r["blocked_by"]])
        if r["blocks"] and r["action"] != "PAUSE":
            r["action_reason"] += (f"; it is the root cause for {r['blocks']} other program{'s' if r['blocks'] != 1 else ''}, "
                                   "so its gaps are the first to close")
        if r["action"] != "PAUSE" and later:
            r["action_reason"] += f"; deferred in {_ids(later)}"

    # Demand with the paused programs taken out of every quarter (assumes the pause holds: modeled)
    need = defaultdict(float)
    for d in data["demand"]:
        if d["program_id"] not in paused_ids:
            need[(d["team"], d["quarter"])] += d["need_fte"]
    after = []
    for team in TEAMS:
        for q in data["quarters"]:
            sup = data["capacity"][(team, q)]
            dem = round(need[(team, q)], 2)
            after.append({"team": team, "quarter": q, "supply": sup, "demand": dem, "over": dem > sup,
                          "gap": round(max(0.0, dem - sup), 2)})
    effect = [{"stage": w["stage"], "wip": w["wip"], "limit": w["limit"], "little_weeks": w["little_weeks"],
               "weeks_at_limit": w["weeks_at_limit"]} for w in wip if w["over"]]
    return {"wip": wip, "pauses": pauses, "quarters": quarters, "after": after, "effect": effect,
            "paused_ids": sorted(paused_ids), "depended_on": sorted(depended_on)}


def benefit_rollup(rows: list) -> dict:
    cats = {"red_by_evidence": 0, "blocked_by_upstream": 0, "slipped": 0, "stale_evidence": 0, "clear": 0}
    counts = {k: 0 for k in cats}
    weighted_red = 0
    for r in rows:
        b = r["est_benefit_usd"]
        if r["evidence_status"] == "RED":
            k = "red_by_evidence"
            weighted_red += b * r["benefit_confidence"]
        elif r["blocked_by"]:
            k = "blocked_by_upstream"
        elif r["slipped"]:
            k = "slipped"
        elif r["stale"]:
            k = "stale_evidence"
        else:
            k = "clear"
        cats[k] += b
        counts[k] += 1
    return {"usd": cats, "programs": counts, "total": sum(cats.values()), "weighted_red": round(weighted_red)}


def analyze(data: dict = None) -> dict:
    data = data or load_all()
    board = build_board(data)
    pr = pull_rule(data, board)
    rows = board["rows"]
    truth = data["truth"]
    n = len(rows)

    # Scored against the truth file
    board_ok = [r for r in rows if r["board"] == truth[r["program_id"]]["true_status"]]
    rag_ok = [r for r in rows if r["reported"] == truth[r["program_id"]]["true_status"]]
    ev_ok = [r for r in rows if r["evidence_status"] == truth[r["program_id"]]["true_evidence_status"]]
    blocked_ok = [r for r in rows if sorted(i["program_id"] for i in r["blocked_by"]) ==
                  sorted(x for x in truth[r["program_id"]]["true_blocked_by"].split(";") if x)]
    board_wrong = [r for r in rows if r["board"] != truth[r["program_id"]]["true_status"]]
    planted = [(pid, t["false_attestation"]) for pid, t in sorted(truth.items()) if t["false_attestation"]]
    changed = [r for r in rows if r["board"] != r["reported"]]
    up = [r for r in changed if SEVERITY[r["board"]] > SEVERITY[r["reported"]]]      # greener than reported
    down = [r for r in changed if SEVERITY[r["board"]] < SEVERITY[r["reported"]]]    # worse than reported

    rollup = benefit_rollup(rows)
    stale_programs = [r for r in rows if r["stale"]]
    stale_criteria = sum(len(r["stale"]) for r in rows)
    owners = len({r["owner"] for r in rows})
    sponsors = int(math.ceil(n / float(PROGRAMS_PER_SPONSOR)))
    people = owners + sponsors
    lift = (len(board_ok) - len(rag_ok)) / float(n)
    utility = lift * people

    mr_before = [c for c in board["grid"] if c["team"] == SCARCE]
    mr_after = [c for c in pr["after"] if c["team"] == SCARCE]
    green_reported = [r for r in rows if r["reported"] == "GREEN"]
    green_reported_not_green = [r for r in green_reported if r["board"] != "GREEN"]
    green_reported_red = [r for r in green_reported if r["board"] == "RED"]
    qs = pr["quarters"]
    plan = qs[0]
    deferred_later_ids = {pid for q in qs[1:] for pid in q["deferred"]}
    act = defaultdict(int)
    for r in rows:
        act[r["action"]] += 1

    summary = {
        "programs": n, "changed": len(changed), "pct_changed": round(100.0 * len(changed) / n, 1),
        "changed_worse": len(down), "changed_better": len(up),
        "board_counts": {c: sum(1 for r in rows if r["board"] == c) for c in ("GREEN", "AMBER", "RED")},
        "reported_counts": {c: sum(1 for r in rows if r["reported"] == c) for c in ("GREEN", "AMBER", "RED")},
        "green_reported": len(green_reported), "green_reported_not_green": len(green_reported_not_green),
        "green_reported_red": len(green_reported_red),
        "board_correct": len(board_ok), "rag_correct": len(rag_ok), "evidence_correct": len(ev_ok),
        "blocked_correct": len(blocked_ok), "board_wrong": len(board_wrong),
        "pct_board_correct": round(100.0 * len(board_ok) / n, 1), "pct_rag_correct": round(100.0 * len(rag_ok) / n, 1),
        "planted_false_attestations": len(planted),
        "stale_programs": len(stale_programs), "stale_criteria": stale_criteria,
        "mr_over_before": sum(1 for c in mr_before if c["over"]), "mr_quarters": len(mr_before),
        "mr_over_after": sum(1 for c in mr_after if c["over"]),
        "mr_gap_before": round(sum(c["gap"] for c in mr_before), 2),
        "mr_gap_after": round(sum(c["gap"] for c in mr_after), 2),
        "cells_over_before": sum(1 for c in board["grid"] if c["over"]), "cells": len(board["grid"]),
        "cells_over_after": sum(1 for c in pr["after"] if c["over"]),
        "plan_quarter": plan["quarter"], "mr_supply_plan": plan["supply"],
        "mr_demand_plan_before": plan["demand"], "mr_demand_plan_after_pause": plan["demand_after_pause"],
        "deferred_plan": len(plan["deferred"]), "deferred_later_programs": len(deferred_later_ids),
        "deferred_fte_later": round(sum(q["deferred_fte"] for q in qs[1:]), 2),
        "quarters": [{"quarter": q["quarter"], "supply": q["supply"], "demand": q["demand"],
                      "demand_after_pause": q["demand_after_pause"], "funded_fte": q["funded_fte"],
                      "deferred_programs": len(q["deferred"]), "deferred_fte": q["deferred_fte"]} for q in qs],
        "paused": len(pr["pauses"]), "actions": dict(act),
        "pauses": [{"stage": p["stage"], "program_id": p["program_id"], "name": p["name"], "tier": p["tier"]}
                   for p in pr["pauses"]],
        "stages_over": [{"stage": e["stage"], "wip": e["wip"], "limit": e["limit"], "little_weeks": e["little_weeks"],
                         "weeks_at_limit": e["weeks_at_limit"]} for e in pr["effect"]],
        "benefit_total": rollup["total"], "benefit_red_by_evidence": rollup["usd"]["red_by_evidence"],
        "benefit_blocked": rollup["usd"]["blocked_by_upstream"], "benefit_slipped": rollup["usd"]["slipped"],
        "benefit_stale": rollup["usd"]["stale_evidence"], "benefit_clear": rollup["usd"]["clear"],
        "programs_red_by_evidence": rollup["programs"]["red_by_evidence"],
        "pct_benefit_red_by_evidence": round(100.0 * rollup["usd"]["red_by_evidence"] / rollup["total"], 1),
        "benefit_weighted_red": rollup["weighted_red"],
        "owners": owners, "sponsors_modeled": sponsors, "people": people, "programs_per_sponsor": PROGRAMS_PER_SPONSOR,
        "lift_programs": len(board_ok) - len(rag_ok), "utility_people": round(utility, 1),
    }
    return {"data": data, "board": board, "pull": pr, "rows": rows, "rollup": rollup, "summary": summary,
            "board_wrong": board_wrong, "planted": planted, "changed": changed, "mr_before": mr_before,
            "mr_after": mr_after}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    a = analyze()
    data, rows, pr, s = a["data"], a["rows"], a["pull"], a["summary"]
    n = s["programs"]

    print("\n" + "=" * 78)
    print("STEP 04 - With PortfolioBoard: status from gate evidence, capacity and dependencies")
    print("=" * 78)
    print("\nPlain rules, no model. Status reads the attested gate evidence; owners' picks are shown beside it.\n")

    print("BOARD STATUS (one row per program: red first, then by owner-estimated benefit)")
    print(f"{'program':<8}{'name':<34}{'stage':<10}{'reported':<9}{'board':<6}{'action':<7} why")
    order = sorted(rows, key=lambda r: (SEVERITY[r["board"]], -r["est_benefit_usd"], r["program_id"]))
    for r in order[:12]:
        print(f"{r['program_id']:<8}{r['name']:<34}{r['stage']:<10}{r['reported'].lower():<9}{r['board']:<6}"
              f"{r['action']:<7} {r['why_short']}")
    print(f"  ... {n - 12} more rows in out/step_04_board.csv")

    print("\nSTATUS CHANGES ONCE EVIDENCE IS APPLIED")
    print(f"  Reported:  green {s['reported_counts']['GREEN']}, amber {s['reported_counts']['AMBER']}, red {s['reported_counts']['RED']}")
    print(f"  Board:     green {s['board_counts']['GREEN']}, amber {s['board_counts']['AMBER']}, red {s['board_counts']['RED']}")
    print(f"  Programs whose status changes: {s['changed']} of {n} ({pct(s['changed'], n)}); "
          f"{s['changed_worse']} worse than reported, {s['changed_better']} better")
    print(f"  Reported green but not green on the board: {s['green_reported_not_green']} of {s['green_reported']} "
          f"({pct(s['green_reported_not_green'], s['green_reported'])}); {s['green_reported_red']} of them red")

    print("\nCAPACITY GRID (demand / supply in FTE; * = demand exceeds supply)")
    print(f"  {'team':<20}" + "".join(f"{q:>16}" for q in data["quarters"]))
    for team in TEAMS:
        cells = [c for c in a["board"]["grid"] if c["team"] == team]
        print(f"  {TEAM_LABEL[team]:<20}" + "".join(
            f"{c['demand']:>8.1f} /{c['supply']:>5.1f}{'*' if c['over'] else ' '}" for c in cells))
    print(f"  {s['cells_over_before']} of {s['cells']} team-quarters are over. Model risk review is over in "
          f"{s['mr_over_before']} of {s['mr_quarters']} quarters.")

    print("\nDEPENDENCY PROPAGATION (programs that block others)")
    roots = defaultdict(lambda: {"direct": 0, "chain": 0, "why": ""})
    for r in rows:
        for i in r["blocked_by"]:
            roots[i["program_id"]]["direct" if i["direct"] else "chain"] += 1
            roots[i["program_id"]]["why"] = i["why"]
    for pid, v in sorted(roots.items(), key=lambda kv: (-(kv[1]["direct"] + kv[1]["chain"]), kv[0])):
        k = v["direct"] + v["chain"]
        print(f"  {pid} {data['prog'][pid]['name']:<30} {v['why']:<16} blocks {k} program{'s' if k != 1 else ''} "
              f"({v['direct']} directly, {v['chain']} through a chain)")

    print("\nPULL RULE (suggestions, not decisions)")
    for w in pr["wip"]:
        mark = "above limit" if w["over"] else "within limit"
        print(f"  {w['stage']:<10} WIP {w['wip']} against a limit of {w['limit']}: {mark}")
    for p in pr["pauses"]:
        print(f"  PAUSE {p['program_id']} {p['name']} ({p['stage']}, {p['tier']}, rank {p['rank']} of {p['of']}): {p['why']}")
    print("  Programs that other programs depend on are never on the pause list.")
    for e in pr["effect"]:
        print(f"  {e['stage']}: held at {e['limit']} with today's throughput, WIP / throughput falls from "
              f"{e['little_weeks']} to {e['weeks_at_limit']} weeks (modeled)")

    print("\nMODEL RISK REVIEW SUPPLY, QUARTER BY QUARTER (FTE; paused programs taken out, modeled)")
    print(f"  {'quarter':<9}{'supply':>7}{'demand':>8}{'% of supply':>13}{'after pause':>13}{'funded':>8}{'programs deferred':>19}")
    for q in s["quarters"]:
        print(f"  {q['quarter']:<9}{q['supply']:>7.1f}{q['demand']:>8.1f}{100 * q['demand'] / q['supply']:>12.1f}%"
              f"{q['demand_after_pause']:>13.1f}{q['funded_fte']:>8.1f}{q['deferred_programs']:>19}")
    print(f"  Model risk review is over in {s['mr_over_before']} of {s['mr_quarters']} quarters as planned and in "
          f"{s['mr_over_after']} of {s['mr_quarters']} after the pauses (short by {s['mr_gap_before']} FTE-quarters, then "
          f"{s['mr_gap_after']}).")
    print(f"  Plan quarter {s['plan_quarter']}: {s['deferred_plan']} programs deferred. Later quarters: "
          f"{s['deferred_later_programs']} programs deferred at least once. Pausing and deferring is a scheduling "
          "answer; the rest is a hiring or scope decision.")

    print("\nBENEFIT AT RISK (modeled: owner estimates, never measured benefit)")
    ru = a["rollup"]
    labels = [("red_by_evidence", "red by evidence"), ("blocked_by_upstream", "blocked by a red or slipped upstream"),
              ("slipped", "slipped"), ("stale_evidence", "stale evidence only"), ("clear", "clear")]
    for k, label in labels:
        print(f"  {label:<38}{ru['programs'][k]:>3} programs{usd_m(ru['usd'][k]):>10}")
    print(f"  {'total':<38}{n:>3} programs{usd_m(ru['total']):>10}")
    print(f"  At risk = red by evidence: {usd_m(s['benefit_red_by_evidence'])} of {usd_m(s['benefit_total'])} "
          f"({pct(s['benefit_red_by_evidence'], s['benefit_total'])}). Weighted by the owners' own confidence: "
          f"{usd_m(s['benefit_weighted_red'])}.")

    print("\nMEASURED AGAINST THE TRUTH FILE")
    print(f"  Board status equals true status:     {s['board_correct']} of {n} ({pct(s['board_correct'], n)})")
    print(f"  Reported color equals true status:   {s['rag_correct']} of {n} ({pct(s['rag_correct'], n)})")
    print(f"  Evidence status equals true evidence status: {s['evidence_correct']} of {n}")
    print(f"  Blocked-by sets equal the truth:     {s['blocked_correct']} of {n}")
    print("  The board and the generator apply the same stated rules, so agreement is by construction")
    print(f"  except for the {s['planted_false_attestations']} false attestations the generator planted.")

    print("\nKNOWN LIMIT (left in on purpose)")
    print("  Status is only as good as the self-attested evidence.")
    print(f"  Programs with a criterion marked met whose evidence is older than its freshness rule: "
          f"{s['stale_programs']} of {n} ({s['stale_criteria']} criteria).")
    print("  The board shows them as stale; it cannot tell whether the criterion still holds.")
    print(f"  Programs where the board status differs from the true status: {s['board_wrong']} of {n}.")
    for r in a["board_wrong"]:
        t = data["truth"][r["program_id"]]
        crit = t["false_attestation"]
        what = (f"{crit} {data['crit'][crit]['criterion']} attested met with fresh evidence, not truly met"
                if crit else "its status depends on a program with a false attestation")
        print(f"    {r['program_id']} {r['name']}: board {r['board']}, true {t['true_status']}; {what}")
    print("  Benefit figures are owner estimates. Measured benefit would come from a holdout comparison")
    print("  (ValueLedger, 12), designed and not built.")

    print("\nUTILITY INPUTS")
    print(f"  Programs whose status changes once evidence is applied: {s['changed']} of {n}")
    print(f"  Programs shown with the true status: board {s['board_correct']} of {n}, reported {s['rag_correct']} of {n}")
    print(f"  Owners (distinct): {s['owners']}; sponsors (modeled, one per {s['programs_per_sponsor']} programs): "
          f"{s['sponsors_modeled']}; people affected (modeled): {s['people']}")
    print(f"  Utility = ({s['board_correct']} - {s['rag_correct']}) / {n} x {s['people']} = {s['utility_people']} "
          "owners and sponsors who see a true status for their program (modeled)")

    with open(OUT_DIR / "step_04_board.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["program_id", "name", "stage", "owner", "reported", "board", "action", "unmet", "stale",
                    "slipped", "blocked_by", "mr_need_fte", "est_benefit_usd", "reason"])
        for r in rows:
            w.writerow([r["program_id"], r["name"], r["stage"], r["owner"], r["reported"], r["board"], r["action"],
                        ";".join(r["unmet"]), ";".join(r["stale"]), int(r["slipped"]),
                        ";".join(i["program_id"] for i in r["blocked_by"]), r["mr_need"], r["est_benefit_usd"],
                        r["reason"]])
    with open(OUT_DIR / "step_04_capacity_grid.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["team", "quarter", "supply_fte", "demand_fte", "over", "demand_after_pause_fte", "over_after_pause"])
        aft = {(c["team"], c["quarter"]): c for c in pr["after"]}
        for c in a["board"]["grid"]:
            x = aft[(c["team"], c["quarter"])]
            w.writerow([c["team"], c["quarter"], c["supply"], c["demand"], int(c["over"]), x["demand"], int(x["over"])])
    with open(OUT_DIR / "step_04_pull_rule.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["stage", "program_id", "name", "tier", "mr_need_fte", "est_benefit_usd", "why"])
        for p in pr["pauses"]:
            w.writerow([p["stage"], p["program_id"], p["name"], p["tier"], p["mr_need"], p["benefit"], p["why"]])
    with open(OUT_DIR / "step_04_benefit_at_risk.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["category", "programs", "est_benefit_usd"])
        for k, _label in labels:
            w.writerow([k, ru["programs"][k], ru["usd"][k]])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_04_board.csv, step_04_capacity_grid.csv, step_04_pull_rule.csv, "
          "step_04_benefit_at_risk.csv and step_04_summary.json")


if __name__ == "__main__":
    main()
