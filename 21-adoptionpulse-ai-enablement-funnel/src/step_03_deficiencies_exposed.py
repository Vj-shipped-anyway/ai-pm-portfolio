"""Step 3 - Where the basic approach breaks: six named deficiencies, each with a count.

Step 2 showed that a login count gives one high, rising adoption percentage. This step asks what
that percentage hides, using the same 800 users, their 12 weeks of AI usage and the stage rules in
data/funnel_policy.csv.

  (1) Logins that never became an AI session.
  (2) One-time activation counted as adoption (activated, never habitual).
  (3) The average hides the spread between units.
  (4) Training completion is not usage: trained but never active, and trained versus untrained.
  (5) Champion coverage: habitual rate in units with and without a champion (true by construction).
  (6) Weekly decay: the active share among the activated falls while the login share rises.

All counts come from usage_weekly.csv, users.csv and the stage rules. The champion and training
gaps are planted by construction in the generator; real data would be confounded, because motivated
people choose training and motivated units get champions. Nothing here reads user_truth.csv.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_license_counts_status_quo import (OUT_DIR, STAGE_RANK, WEEKS, ever_logged_in, load_all,
                                               stage_of)
from step_02_login_adoption_baseline import ADOPTION_OK_PCT, summarize as summarize_step2

LOW_HABIT_PCT = 25.0          # assumption: a unit below this habitual rate is not "adopted" in any useful sense
COMPARE_WEEK = 4              # the first week in which every user is licensed


def pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def habitual_or_better(stage: str) -> bool:
    return STAGE_RANK[stage] >= STAGE_RANK["habitual"]


def summarize(data: dict) -> dict:
    users, use, policy = data["users"], data["use"], data["policy"]
    stages = {u["user_id"]: stage_of(u, use[u["user_id"]], policy) for u in users}
    n = len(users)
    s2 = summarize_step2(data)

    # (1) logins that never became an AI session
    logged = [u for u in users if ever_logged_in(use[u["user_id"]])]
    logged_no_ai = [u for u in logged if sum(use[u["user_id"]]["sessions"]) == 0]
    login_events = sum(sum(use[u["user_id"]]["logins"]) for u in users)
    idle_logins = sum(use[u["user_id"]]["logins"][w] for u in users for w in range(WEEKS)
                      if use[u["user_id"]]["sessions"][w] == 0)
    d1 = {"logged_in": len(logged), "logged_no_ai": len(logged_no_ai),
          "logged_no_ai_pct": pct(len(logged_no_ai), len(logged)),
          "login_events": login_events, "idle_logins": idle_logins,
          "idle_logins_pct": pct(idle_logins, login_events)}

    # (2) one-time activation counted as adoption
    activated = [u for u in users if STAGE_RANK[stages[u["user_id"]]] >= STAGE_RANK["activated"]]
    act_not_hab = [u for u in activated if not habitual_or_better(stages[u["user_id"]])]
    counted_adopted = sum(1 for u in act_not_hab if ever_logged_in(use[u["user_id"]]))
    one_week = [u for u in users if sum(1 for w in range(WEEKS) if use[u["user_id"]]["sessions"][w] > 0) == 1]
    d2 = {"activated": len(activated), "act_not_hab": len(act_not_hab),
          "act_not_hab_pct": pct(len(act_not_hab), len(activated)),
          "counted_adopted": counted_adopted, "one_week_only": len(one_week)}

    # (3) the average hides unit spread
    unit_rows = []
    for unit in data["units"]:
        us = data["by_unit"][unit]
        hab = sum(1 for u in us if habitual_or_better(stages[u["user_id"]]))
        unit_rows.append({"unit": unit, "licensed": len(us), "habitual": hab, "habitual_pct": pct(hab, len(us))})
    adopt_by_unit = {r["unit"]: r["adoption_pct"] for r in s2["units"]}
    ranked = sorted(unit_rows, key=lambda r: (-r["habitual_pct"], r["unit"]))
    best, worst = ranked[0], ranked[-1]
    overall_hab = sum(1 for u in users if habitual_or_better(stages[u["user_id"]]))
    fooled = [r for r in unit_rows
              if adopt_by_unit[r["unit"]] >= ADOPTION_OK_PCT and r["habitual_pct"] < LOW_HABIT_PCT]
    d3 = {"overall_habitual": overall_hab, "overall_habitual_pct": pct(overall_hab, n),
          "best": best, "worst": worst, "spread_points": round(best["habitual_pct"] - worst["habitual_pct"], 1),
          "login_best_pct": s2["best_unit"]["adoption_pct"], "login_worst_pct": s2["worst_unit"]["adoption_pct"],
          "login_spread_points": s2["spread_points"],
          "fooled_units": len(fooled), "fooled_names": [r["unit"] for r in fooled],
          "units": len(unit_rows), "unit_rows": unit_rows, "low_habit_pct": LOW_HABIT_PCT}

    # (4) training completion versus usage
    trained = [u for u in users if u["trained_week"] is not None]
    untrained = [u for u in users if u["trained_week"] is None]
    trained_idle = [u for u in trained if sum(use[u["user_id"]]["sessions"]) == 0]
    t_hab = sum(1 for u in trained if habitual_or_better(stages[u["user_id"]]))
    u_hab = sum(1 for u in untrained if habitual_or_better(stages[u["user_id"]]))
    d4 = {"trained": len(trained), "trained_pct": pct(len(trained), n),
          "trained_never_active": len(trained_idle),
          "trained_never_active_pct": pct(len(trained_idle), len(trained)),
          "trained_habitual": t_hab, "trained_habitual_pct": pct(t_hab, len(trained)),
          "untrained": len(untrained), "untrained_habitual": u_hab,
          "untrained_habitual_pct": pct(u_hab, len(untrained)),
          "gap_points": round(pct(t_hab, len(trained)) - pct(u_hab, len(untrained)), 1)}

    # (5) champion coverage
    champ_units = sorted({u["org_unit"] for u in users if u["champion"]})
    with_c = [u for u in users if u["champion"]]
    without_c = [u for u in users if not u["champion"]]
    c_hab = sum(1 for u in with_c if habitual_or_better(stages[u["user_id"]]))
    n_hab = sum(1 for u in without_c if habitual_or_better(stages[u["user_id"]]))
    d5 = {"champion_units": len(champ_units), "units": len(data["units"]),
          "with_champion": len(with_c), "with_champion_habitual": c_hab,
          "with_champion_pct": pct(c_hab, len(with_c)),
          "without_champion": len(without_c), "without_champion_habitual": n_hab,
          "without_champion_pct": pct(n_hab, len(without_c)),
          "gap_points": round(pct(c_hab, len(with_c)) - pct(n_hab, len(without_c)), 1),
          "champions": len(data["champions"])}

    # (6) weekly decay among the activated
    def active_in(week: int) -> int:
        return sum(1 for u in activated if use[u["user_id"]]["sessions"][week - 1] > 0)
    a4, a12 = active_in(COMPARE_WEEK), active_in(WEEKS)
    free_week = max(u["licensed_week"] for u in users) + int(data["policy"]["activation_window_weeks"])
    a_free = active_in(free_week)
    base = {r["week"]: r for r in s2["weekly"]}
    d6 = {"activated": len(activated), "active_wk4": a4, "active_wk4_pct": pct(a4, len(activated)),
          "active_wk12": a12, "active_wk12_pct": pct(a12, len(activated)),
          "drop_points": round(pct(a4, len(activated)) - pct(a12, len(activated)), 1),
          "login_share_wk4": base[COMPARE_WEEK]["adoption_pct"], "login_share_wk12": base[WEEKS]["adoption_pct"],
          "compare_week": COMPARE_WEEK, "free_week": free_week, "active_free": a_free,
          "active_free_pct": pct(a_free, len(activated))}
    return {"users": n, "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5, "d6": d6,
            "reported_pct": s2["overall_pct"]}


def unit_deficiencies(data: dict, stages: dict, unit: str) -> dict:
    """The same six measures for one org unit (the app and the demo import this)."""
    us, use = data["by_unit"][unit], data["use"]
    logged = [u for u in us if ever_logged_in(use[u["user_id"]])]
    logged_no_ai = [u for u in logged if sum(use[u["user_id"]]["sessions"]) == 0]
    act = [u for u in us if STAGE_RANK[stages[u["user_id"]]] >= STAGE_RANK["activated"]]
    hab = [u for u in us if habitual_or_better(stages[u["user_id"]])]
    trained = [u for u in us if u["trained_week"] is not None]
    trained_idle = [u for u in trained if sum(use[u["user_id"]]["sessions"]) == 0]
    a4 = sum(1 for u in act if use[u["user_id"]]["sessions"][COMPARE_WEEK - 1] > 0)
    a12 = sum(1 for u in act if use[u["user_id"]]["sessions"][WEEKS - 1] > 0)
    return {"n": len(us), "logged": len(logged), "logged_no_ai": len(logged_no_ai), "activated": len(act),
            "act_not_hab": len(act) - len(hab), "habitual": len(hab), "trained": len(trained),
            "trained_idle": len(trained_idle), "champion": us[0]["champion"],
            "active_wk4": a4, "active_wk12": a12, "compare_week": COMPARE_WEEK}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)
    a, b, c, d, e, f = s["d1"], s["d2"], s["d3"], s["d4"], s["d5"], s["d6"]

    print("\n" + "=" * 78)
    print("Step 3 - Six deficiencies of the basic approach, with counts")
    print("=" * 78)
    print(f"\nReported adoption (step 2): {s['reported_pct']}%. Counts below use the stage rules in funnel_policy.csv.")
    print("Training and champion gaps are planted by construction; real data would be confounded.")

    print("\n(1) Logins that never became an AI session")
    print(f"    {a['logged_no_ai']} of {a['logged_in']} users who logged in ({a['logged_no_ai_pct']}%) never had an AI session in {WEEKS} weeks.")
    print(f"    {a['idle_logins']:,} of {a['login_events']:,} login events ({a['idle_logins_pct']}%) fell in a week with no AI session.")

    print("\n(2) One-time activation counted as adoption")
    print(f"    {b['act_not_hab']} of {b['activated']} activated users ({b['act_not_hab_pct']}%) never became habitual;")
    print(f"    the login view counts {b['counted_adopted']} of them as adopted. {b['one_week_only']} users had AI sessions in exactly one week of {WEEKS}.")

    print("\n(3) The average hides the spread between units")
    print(f"    Login view: {c['login_worst_pct']}% to {c['login_best_pct']}% across units ({c['login_spread_points']} points).")
    print(f"    Habitual rate: {c['worst']['habitual_pct']}% ({c['worst']['unit']}, {c['worst']['licensed']} users) to "
          f"{c['best']['habitual_pct']}% ({c['best']['unit']}, {c['best']['licensed']} users), {c['spread_points']} points.")
    print(f"    {c['fooled_units']} of {c['units']} units read as healthy (at or above {ADOPTION_OK_PCT:.0f}% logged in) "
          f"while under {c['low_habit_pct']:.0f}% of their users are habitual.")

    print("\n(4) Training completion is not usage")
    print(f"    {d['trained']} of {s['users']} users completed training ({d['trained_pct']}%). "
          f"{d['trained_never_active']} of them ({d['trained_never_active_pct']}%) never had an AI session.")
    print(f"    Habitual rate: trained {d['trained_habitual']} of {d['trained']} ({d['trained_habitual_pct']}%), "
          f"untrained {d['untrained_habitual']} of {d['untrained']} ({d['untrained_habitual_pct']}%), a gap of {d['gap_points']} points.")

    print("\n(5) Champion coverage (true by construction)")
    print(f"    {e['champion_units']} of {e['units']} units have a champion ({e['champions']} champions in all), covering {e['with_champion']} of {s['users']} users.")
    print(f"    Habitual rate: with a champion {e['with_champion_habitual']} of {e['with_champion']} ({e['with_champion_pct']}%), "
          f"without {e['without_champion_habitual']} of {e['without_champion']} ({e['without_champion_pct']}%), a gap of {e['gap_points']} points.")

    print("\n(6) Weekly decay")
    print(f"    Among the {f['activated']} activated users, {f['active_wk4']} ({f['active_wk4_pct']}%) had an AI session in week {f['compare_week']} "
          f"and {f['active_wk12']} ({f['active_wk12_pct']}%) in week {WEEKS}, a drop of {f['drop_points']} points.")
    print(f"    Over the same weeks the login view rose from {f['login_share_wk4']}% to {f['login_share_wk12']}%.")
    print(f"    Week {f['compare_week']} is partly set by the activation rule; from week {f['free_week']} the curve is free of it: "
          f"{f['active_free']} ({f['active_free_pct']}%) in week {f['free_week']}.")

    print("\nThe login count measures reach. The product is the stage, the unit and the week.")
    rows = [(1, "Logins that never became an AI session", f"{a['logged_no_ai']} of {a['logged_in']} logged-in users"),
            (2, "One-time activation counted as adoption", f"{b['act_not_hab']} of {b['activated']} activated users"),
            (3, "Average hides unit spread", f"{c['spread_points']} points between best and worst unit"),
            (4, "Training is not usage", f"{d['trained_never_active']} of {d['trained']} trained users never active"),
            (5, "Champion coverage", f"{e['gap_points']} point habitual gap (by construction)"),
            (6, "Weekly decay", f"{f['drop_points']} point drop in active share, week {f['compare_week']} to {WEEKS}")]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["number", "deficiency", "count"])
        w.writerows(rows)
    with open(OUT_DIR / "step_03_summary.json", "w") as fh:
        json.dump({k: v for k, v in s.items()}, fh, indent=2)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
