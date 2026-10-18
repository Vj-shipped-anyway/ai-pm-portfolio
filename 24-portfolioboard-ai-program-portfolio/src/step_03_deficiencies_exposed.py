"""Step 3 - Where the red-amber-green report breaks: six named deficiencies, each with a count.

Step 2 showed that reading the owners' statuses as sent catches part of the problem. This step
asks what a status report cannot do, using the gate evidence, capacity, dependency and stage
history files in data/. Each deficiency is a plain count; no status layer is involved yet.

  (a) Green programs that fail their gate criteria.
  (b) Team-quarters where demand exceeds supply (and the model risk review team in particular).
  (c) Green programs that depend on a red or slipped upstream program.
  (d) Stages above their work-in-progress limit, and the average time in stage there
      (average time in stage = work in progress / throughput, computed from stage_history.csv).
  (e) Benefit at risk: owner-estimated benefit on programs that are red by evidence (modeled).
  (f) The review queue as the bottleneck: weeks waiting at the review gate against other gates.

Definitions used here (assumptions of a modeled bank, not legal advice):
  * Evidence is met when the attestation says yes. It is stale when its age exceeds the
    criterion's max_age_days in gate_criteria.csv.
  * A program is red by evidence if any criterion in force at its stage is not met.
  * A program is slipped if it is not yet at scale and its target quarter is before the as-of
    quarter.
  * Throughput of a stage is the visits that exited it in the last 26 weeks, per week.

The functions below are the measures the later step and the app import.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict

from step_01_rag_status_report import (OUT_DIR, STAGES, TEAMS, TEAM_LABEL, load_all, pct, usd_m)

WINDOW_WEEKS = 26          # trailing window for throughput (assumption)


# ---------------------------------------------------------------------------
# Measures (importable)
# ---------------------------------------------------------------------------
def evidence_flags(data: dict) -> dict:
    """Per program: unmet criteria, stale criteria and the evidence status, from the attested file."""
    out = {}
    for p in data["programs"]:
        pid = p["program_id"]
        rows = data["ev_by_prog"].get(pid, [])
        unmet = sorted(r["criterion_id"] for r in rows if not r["met"])
        stale = sorted(r["criterion_id"] for r in rows
                       if r["met"] and r["age"] > data["crit"][r["criterion_id"]]["max_age_days"])
        out[pid] = {"unmet": unmet, "stale": stale, "in_force": len(rows),
                    "status": "RED" if unmet else ("AMBER" if stale else "GREEN")}
    return out


def slipped_programs(data: dict) -> set:
    return {p["program_id"] for p in data["programs"]
            if p["stage"] != "scale" and p["target_quarter"] < data["as_of_quarter"]}


def ancestors_map(data: dict) -> dict:
    """Every program a program depends on, directly or through a chain."""
    ups = data["ups"]
    out = {}
    for p in data["programs"]:
        seen, stack = set(), list(ups.get(p["program_id"], []))
        while stack:
            u = stack.pop()
            if u not in seen:
                seen.add(u)
                stack.extend(ups.get(u, []))
        out[p["program_id"]] = sorted(seen)
    return out


def upstream_issues(data: dict, flags: dict, slipped: set) -> dict:
    """Per program: the upstream programs (direct or through a chain) that are red by evidence or slipped."""
    anc = ancestors_map(data)
    out = {}
    for pid, a in anc.items():
        issues = []
        for u in a:
            why = []
            if flags[u]["status"] == "RED":
                why.append("red")
            if u in slipped:
                why.append("slipped")
            if why:
                issues.append({"program_id": u, "why": " and ".join(why), "direct": u in data["ups"].get(pid, [])})
        out[pid] = issues
    return out


def capacity_grid(data: dict) -> list:
    """Demand against supply for every team and quarter."""
    need = defaultdict(float)
    for r in data["demand"]:
        need[(r["team"], r["quarter"])] += r["need_fte"]
    cells = []
    for team in TEAMS:
        for q in data["quarters"]:
            supply = data["capacity"][(team, q)]
            d = round(need[(team, q)], 2)
            cells.append({"team": team, "quarter": q, "supply": supply, "demand": d,
                          "ratio": round(d / supply, 3), "over": d > supply,
                          "gap": round(max(0.0, d - supply), 2)})
    return cells


def wip_table(data: dict, window: int = WINDOW_WEEKS) -> list:
    """Work in progress, throughput and average time in stage, all from stage_history.csv."""
    as_of = data["as_of_week"]
    rows = []
    for s in STAGES:
        visits = [h for h in data["history"] if h["stage"] == s]
        wip = sum(1 for h in visits if h["exited"] is None)
        done = [h for h in visits if h["exited"] is not None and as_of - window < h["exited"] <= as_of]
        thr = len(done) / window
        mean_done = (sum(h["exited"] - h["entered"] for h in done) / len(done)) if done else None
        little = (wip / thr) if thr > 0 else None
        limit = data["limits"][s]
        rows.append({"stage": s, "wip": wip, "limit": limit, "over_by": max(0, wip - limit),
                     "over": wip > limit, "exits": len(done), "throughput": round(thr, 4),
                     "little_weeks": round(little, 1) if little is not None else None,
                     "mean_completed_weeks": round(mean_done, 1) if mean_done is not None else None,
                     "gap_pct": round(100.0 * (little - mean_done) / mean_done, 1) if (little and mean_done) else None,
                     "weeks_at_limit": round(limit / thr, 1) if thr > 0 else None})
    return rows


def review_waits(data: dict) -> list:
    """Weeks of work versus weeks waiting at the exit review gate, per stage (completed visits),
    plus programs waiting at the gate right now."""
    as_of = data["as_of_week"]
    rows = []
    for s in STAGES[:-1]:                       # scale has no exit gate
        visits = [h for h in data["history"] if h["stage"] == s]
        done = [h for h in visits if h["exited"] is not None]
        waiting = [h for h in visits if h["exited"] is None and h["requested"] is not None]
        not_yet = [h for h in visits if h["exited"] is None and h["requested"] is None]
        wait = [h["exited"] - h["requested"] for h in done]
        work = [h["requested"] - h["entered"] for h in done]
        total = sum(wait) + sum(work)
        rows.append({"stage": s, "visits": len(done),
                     "mean_work": round(sum(work) / len(work), 1) if work else None,
                     "mean_wait": round(sum(wait) / len(wait), 1) if wait else None,
                     "wait_share": round(100.0 * sum(wait) / total, 1) if total else None,
                     "waiting_now": len(waiting),
                     "mean_wait_so_far": round(sum(as_of - h["requested"] for h in waiting) / len(waiting), 1)
                     if waiting else None,
                     "not_yet_requested": len(not_yet), "wait_sum": sum(wait), "wait_n": len(wait)})
    return rows


# ---------------------------------------------------------------------------
# The six deficiencies
# ---------------------------------------------------------------------------
def deficiencies(data: dict) -> dict:
    flags = evidence_flags(data)
    slipped = slipped_programs(data)
    issues = upstream_issues(data, flags, slipped)
    prog = data["prog"]
    green = [p for p in data["programs"] if p["self_reported_rag"] == "green"]

    # (a) green but failing gate criteria
    a_fail = [p for p in green if flags[p["program_id"]]["status"] == "RED"]
    a_stale = [p for p in green if flags[p["program_id"]]["status"] == "AMBER"]
    a_unmet_total = sum(len(flags[p["program_id"]]["unmet"]) for p in a_fail)
    unmet_count = defaultdict(int)
    for p in a_fail:
        for c in flags[p["program_id"]]["unmet"]:
            unmet_count[c] += 1

    # (b) capacity
    cells = capacity_grid(data)
    over = [c for c in cells if c["over"]]
    mr = [c for c in cells if c["team"] == "model_risk_review"]
    mr_over = [c for c in mr if c["over"]]
    worst = max(cells, key=lambda c: c["ratio"])

    # (c) green programs behind a red or slipped upstream
    c_blocked = [p for p in green if issues[p["program_id"]]]
    c_direct = [p for p in c_blocked if any(i["direct"] for i in issues[p["program_id"]])]
    c_chain_only = [p for p in c_blocked if p not in c_direct]

    # (d) WIP
    wip = wip_table(data)
    over_stages = [w for w in wip if w["over"]]
    wip_from_history = {w["stage"]: w["wip"] for w in wip}
    wip_matches = sum(1 for p in data["programs"] if wip_from_history.get(p["stage"]) is not None) and \
        all(wip_from_history[s] == sum(1 for p in data["programs"] if p["stage"] == s) for s in STAGES)

    # (e) benefit at risk
    red_ev = [p for p in data["programs"] if flags[p["program_id"]]["status"] == "RED"]
    benefit_total = sum(p["est_benefit_usd"] for p in data["programs"])
    benefit_red_ev = sum(p["est_benefit_usd"] for p in red_ev)
    benefit_reported_red = sum(p["est_benefit_usd"] for p in data["programs"] if p["self_reported_rag"] == "red")
    benefit_red_ev_reported_green = sum(p["est_benefit_usd"] for p in red_ev if p["self_reported_rag"] == "green")

    # (f) review queue
    waits = review_waits(data)
    heavy = [w for w in waits if w["stage"] in ("build", "pilot")]
    light = [w for w in waits if w["stage"] in ("idea", "discovery")]
    mean_heavy = sum(w["wait_sum"] for w in heavy) / max(1, sum(w["wait_n"] for w in heavy))
    mean_light = sum(w["wait_sum"] for w in light) / max(1, sum(w["wait_n"] for w in light))
    waiting_heavy = sum(w["waiting_now"] for w in heavy)
    waiting_all = sum(w["waiting_now"] for w in waits)

    return {
        "flags": flags, "slipped": slipped, "issues": issues, "green": green,
        "a": {"fail": a_fail, "stale_only": a_stale, "unmet_total": a_unmet_total, "unmet_count": dict(unmet_count)},
        "b": {"cells": cells, "over": over, "mr": mr, "mr_over": mr_over, "worst": worst},
        "c": {"blocked": c_blocked, "direct": c_direct, "chain_only": c_chain_only},
        "d": {"wip": wip, "over_stages": over_stages, "wip_matches": bool(wip_matches)},
        "e": {"red_ev": red_ev, "benefit_total": benefit_total, "benefit_red_ev": benefit_red_ev,
              "benefit_reported_red": benefit_reported_red,
              "benefit_red_ev_reported_green": benefit_red_ev_reported_green},
        "f": {"waits": waits, "mean_heavy": mean_heavy, "mean_light": mean_light,
              "waiting_heavy": waiting_heavy, "waiting_all": waiting_all},
        "prog": prog,
    }


def summarize(data: dict) -> dict:
    d = deficiencies(data)
    n_green = len(d["green"])
    a, b, c, e, f = d["a"], d["b"], d["c"], d["e"], d["f"]
    over_stage_rows = [{"stage": w["stage"], "wip": w["wip"], "limit": w["limit"],
                        "little_weeks": w["little_weeks"], "mean_completed_weeks": w["mean_completed_weeks"],
                        "weeks_at_limit": w["weeks_at_limit"]} for w in d["d"]["over_stages"]]
    return {
        "green_reported": n_green,
        "a_green_fail": len(a["fail"]), "a_green_stale_only": len(a["stale_only"]),
        "a_unmet_total": a["unmet_total"],
        "b_cells": len(b["cells"]), "b_over": len(b["over"]), "b_mr_cells": len(b["mr"]),
        "b_mr_over": len(b["mr_over"]),
        "b_mr_gap_total": round(sum(x["gap"] for x in b["mr"]), 2),
        "b_worst_team": b["worst"]["team"], "b_worst_quarter": b["worst"]["quarter"],
        "b_worst_ratio_pct": round(100 * b["worst"]["ratio"], 1),
        "c_green_blocked": len(c["blocked"]), "c_direct": len(c["direct"]), "c_chain_only": len(c["chain_only"]),
        "d_stages_over": len(d["d"]["over_stages"]), "d_stages": len(STAGES),
        "d_over": over_stage_rows, "d_wip_matches_programs": d["d"]["wip_matches"],
        "d_wip": d["d"]["wip"],
        "e_benefit_total": e["benefit_total"], "e_benefit_red_ev": e["benefit_red_ev"],
        "e_pct_red_ev": round(100.0 * e["benefit_red_ev"] / e["benefit_total"], 1),
        "e_benefit_reported_red": e["benefit_reported_red"],
        "e_programs_red_ev": len(e["red_ev"]),
        "e_benefit_red_ev_reported_green": e["benefit_red_ev_reported_green"],
        "f_mean_heavy": round(f["mean_heavy"], 1), "f_mean_light": round(f["mean_light"], 1),
        "f_ratio": round(f["mean_heavy"] / f["mean_light"], 1) if f["mean_light"] else None,
        "f_waiting_heavy": f["waiting_heavy"], "f_waiting_all": f["waiting_all"],
        "f_waits": f["waits"],
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    d = deficiencies(data)
    s = summarize(data)
    n_green = s["green_reported"]
    flags = d["flags"]

    print("\n" + "=" * 78)
    print("STEP 03 - Where the red-amber-green report breaks: six named deficiencies")
    print("=" * 78)
    print(f"\nThe report shows {n_green} of {len(data['programs'])} programs green. Each deficiency below is a count "
          "from the evidence, capacity,")
    print("dependency and stage-history files. Data is synthetic; owner benefit figures are estimates.\n")

    # (a)
    print("(a) Green programs that fail their gate criteria")
    print(f"    {s['a_green_fail']} of {n_green} programs reported green have at least one gate criterion not met "
          f"({pct(s['a_green_fail'], n_green)}); {s['a_unmet_total']} unmet criteria in all.")
    print(f"    {s['a_green_stale_only']} more reported green have every criterion met but some evidence older than its freshness rule.")
    worst = sorted(d["a"]["fail"], key=lambda p: -len(flags[p["program_id"]]["unmet"]))[:3]
    for p in worst:
        names = ", ".join(data["crit"][c]["criterion"] for c in flags[p["program_id"]]["unmet"])
        print(f"    e.g. {p['program_id']} {p['name']} ({p['stage']}): not met: {names}")

    # (b)
    print("\n(b) Team-quarters where demand exceeds supply")
    print(f"    {'team':<20}" + "".join(f"{q:>16}" for q in data["quarters"]))
    for team in TEAMS:
        cells = [c for c in d["b"]["cells"] if c["team"] == team]
        print(f"    {TEAM_LABEL[team]:<20}" + "".join(
            f"{c['demand']:>8.1f} /{c['supply']:>5.1f}{'*' if c['over'] else ' '}" for c in cells))
    print("    (demand / supply in FTE; * = demand exceeds supply)")
    print(f"    {s['b_over']} of {s['b_cells']} team-quarters are over. Model risk review is over in "
          f"{s['b_mr_over']} of {s['b_mr_cells']} quarters, short by {s['b_mr_gap_total']} FTE-quarters in total.")
    w = d["b"]["worst"]
    print(f"    Worst cell: {TEAM_LABEL[w['team']]} in {w['quarter']}, demand {w['ratio'] * 100:.1f}% of supply.")

    # (c)
    print("\n(c) Green programs that depend on a red or slipped upstream program")
    print(f"    {s['c_green_blocked']} of {n_green} programs reported green sit behind an upstream program that is red by "
          f"evidence or slipped ({pct(s['c_green_blocked'], n_green)}).")
    print(f"    {s['c_direct']} depend on it directly; {s['c_chain_only']} reach it only through a chain.")
    for p in d["c"]["blocked"][:3]:
        its = "; ".join(f"{i['program_id']} ({i['why']}{'' if i['direct'] else ', through a chain'})"
                        for i in d["issues"][p["program_id"]])
        print(f"    e.g. {p['program_id']} {p['name']}: behind {its}")

    # (d)
    print("\n(d) Stages above their work-in-progress limit")
    print(f"    {'stage':<11}{'WIP':>4}{'limit':>7}{'exits/26wk':>12}{'WIP / exits per wk':>20}{'mean of completed':>19}{'gap':>9}")
    for wv in d["d"]["wip"]:
        lit = f"{wv['little_weeks']:.1f} wk" if wv["little_weeks"] is not None else "n/a"
        mc = f"{wv['mean_completed_weeks']:.1f} wk" if wv["mean_completed_weeks"] is not None else "n/a"
        gap = f"{wv['gap_pct']:+.1f}%" if wv["gap_pct"] is not None else "n/a"
        print(f"    {wv['stage']:<11}{wv['wip']:>4}{wv['limit']:>7}{wv['exits']:>12}{lit:>20}{mc:>19}{gap:>9}")
    print(f"    {s['d_stages_over']} of {s['d_stages']} stages are above their limit: "
          + ", ".join(f"{o['stage']} ({o['wip']} against {o['limit']})" for o in s["d_over"]) + ".")
    for o in s["d_over"]:
        print(f"    {o['stage']}: average time in stage by WIP / throughput is {o['little_weeks']:.1f} weeks; "
              f"the visits that completed in the window took {o['mean_completed_weeks']:.1f} weeks on average.")
    print(f"    WIP counted from stage_history.csv matches the stage in programs.csv for all {len(data['programs'])} programs: "
          f"{'yes' if s['d_wip_matches_programs'] else 'no'}.")

    # (e)
    print("\n(e) Benefit at risk (modeled: owner estimates)")
    print(f"    {s['e_programs_red_ev']} programs are red by evidence. They carry {usd_m(s['e_benefit_red_ev'])} of the "
          f"{usd_m(s['e_benefit_total'])} owner-estimated benefit ({pct(s['e_benefit_red_ev'], s['e_benefit_total'])}).")
    print(f"    The red-amber-green report shows {usd_m(s['e_benefit_reported_red'])} as red. "
          f"{usd_m(s['e_benefit_red_ev_reported_green'])} of the at-risk benefit sits in programs reported green.")

    # (f)
    print("\n(f) The review queue as the bottleneck")
    print(f"    {'exit gate after':<17}{'visits':>7}{'weeks of work':>15}{'weeks at review':>17}{'share waiting':>15}{'waiting now':>13}")
    for wv in d["f"]["waits"]:
        print(f"    {wv['stage']:<17}{wv['visits']:>7}{wv['mean_work']:>15.1f}{wv['mean_wait']:>17.1f}"
              f"{wv['wait_share']:>14.1f}%{wv['waiting_now']:>13}")
    print(f"    Gates after build and pilot (model risk and security review): {s['f_mean_heavy']} weeks waiting on average.")
    print(f"    Gates after idea and discovery: {s['f_mean_light']} weeks. The heavy gates wait {s['f_ratio']} times as long.")
    print(f"    {s['f_waiting_heavy']} of the {s['f_waiting_all']} programs waiting at a gate now are at those two heavy gates.")

    print("\nA status report carries none of this. The product is the layer that computes it.")

    rows = [
        ("a", "Green programs that fail gate criteria", s["a_green_fail"], n_green, "programs"),
        ("b", "Team-quarters where demand exceeds supply", s["b_over"], s["b_cells"], "team-quarters"),
        ("c", "Green programs behind a red or slipped upstream", s["c_green_blocked"], n_green, "programs"),
        ("d", "Stages above their WIP limit", s["d_stages_over"], s["d_stages"], "stages"),
        ("e", "Owner-estimated benefit on red-by-evidence programs", s["e_benefit_red_ev"], s["e_benefit_total"], "USD"),
        ("f", "Mean weeks at heavy review gates against light gates", s["f_mean_heavy"], s["f_mean_light"], "weeks"),
    ]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "deficiency", "value", "compared_to", "unit"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
