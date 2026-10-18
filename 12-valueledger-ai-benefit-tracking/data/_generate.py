"""Generates the ValueLedger synthetic data.

Seeded and deterministic: running it twice writes byte-identical files.
Standard library only, Python 3.9+. Run once with `python3 _generate.py`.

Files written next to this script:
  teams.csv                 24 teams, enthusiasm score, cohort (the non-random rule)
  employees.csv             320 people, team, cost center, cohort, copilots held
  panel.csv                 320 people x 26 weeks: what a measurement team could observe
  budget.csv                8 cost-center lines with headcount and a cash-conversion flag
  copilots.csv              the two overlapping copilots and their business-case assumption
  truth_person_week.csv     ANSWER KEY. The injected true effect, treated people, post-launch weeks
  truth_parameters.json     ANSWER KEY. The constants the generator injected

Everything here is synthetic. The true effect is known only because this script
injected it. In a real bank nobody has an answer key.

The world in one paragraph
--------------------------
Work is measured in tasks (a case file, a draft, a memo section). Each person
completes about 18 tasks a week at about 46 minutes each. A seasonal workload
curve adds minutes to every task for everyone, peaking early and easing later,
so any before-and-after comparison sees an improvement that no tool caused.
Twelve of the 24 teams get a copilot in week 13. They are the 12 with the
highest enthusiasm score: a non-random rule, so they are also faster at
baseline (selection on a visible trait). The enthusiastic teams also change
how they work after launch in a way the data does not record (a hidden drift
of HIDDEN_DRIFT_MIN minutes per task). That is the known limit ValueLedger
cannot see. Per assisted task the copilot saves STEADY + NOVELTY * exp(-K * t)
minutes, t = weeks since launch, and costs rework minutes when its output has
to be corrected. Some people hold two copilots, and on some tasks both are
used, so two usage logs record the same task.
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent

SEED = 20261012
N_EMPLOYEES = 320
N_TEAMS = 24
N_WEEKS = 26
LAUNCH_WEEK = 13          # weeks 1-12 are pre-launch, 13-26 are post-launch
N_TREATED_TEAMS = 12      # top 12 by enthusiasm score get the copilot first

# --- injected truth ---------------------------------------------------------
STEADY_MIN = 5.5          # minutes saved per assisted task once novelty has worn off
NOVELTY_MIN = 6.0         # extra minutes saved per assisted task in launch week
NOVELTY_DECAY_K = 0.25    # per week; half-life = ln(2)/K = 2.77 weeks
HIDDEN_DRIFT_MIN = 0.45   # minutes per task, treated teams only, post-launch, not caused by the copilot
P_BOTH_GIVEN_AB = 0.60    # for a person holding both copilots: share of assisted tasks that use both

# --- the confounders --------------------------------------------------------
SEASON_AMPLITUDE_MIN = 2.0   # minutes per task, everyone; half-year cosine peaking in week 5
SEASON_PEAK_WEEK = 5
TEAM_WEEK_SHOCK_SD = 1.1     # minutes per task, shared by a team in a week
PERSON_WEEK_NOISE_SD = 2.0   # minutes per task, one person in a week
SELECTION_SLOPE_MIN = 1.8    # minutes per task faster at baseline per +1 sd of team enthusiasm

# --- cost centers -----------------------------------------------------------
# id, name, loaded cost per hour (USD), cash flag, cash lever, addressable annual spend (USD),
# probability copilot output needs correction, mean correction minutes
COST_CENTERS = [
    ("CC-101", "Retail operations processing", 48.0, "yes", "contractor and overtime cover", 70000, 0.18, 8.0),
    ("CC-102", "Client onboarding and KYC", 55.0, "yes", "temporary staffing", 45000, 0.20, 8.0),
    ("CC-103", "Collections and recoveries", 50.0, "yes", "overtime", 60000, 0.18, 8.0),
    ("CC-104", "Credit risk reporting", 82.0, "no", "none, fixed salaried headcount", 0, 0.42, 10.0),
    ("CC-105", "Regulatory compliance", 78.0, "no", "none, fixed salaried headcount", 0, 0.24, 8.0),
    ("CC-106", "Financial control", 74.0, "no", "none, fixed salaried headcount", 0, 0.20, 8.0),
    ("CC-107", "Legal and contracts", 95.0, "no", "none, fixed salaried headcount", 0, 0.26, 8.0),
    ("CC-108", "Product and analytics", 70.0, "no", "none, fixed salaried headcount", 0, 0.16, 8.0),
]

COPILOTS = [
    # id, name, use_case_id, assumed minutes per use, seat cost per month (USD), status
    ("A", "Drafting copilot", "UC-201", 12, 32, "approved"),
    ("B", "Meeting and notes copilot", "UC-202", 12, 24, "approved"),
]


def clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def season(week: int) -> float:
    return SEASON_AMPLITUDE_MIN * math.cos(2.0 * math.pi * (week - SEASON_PEAK_WEEK) / 52.0)


def write_csv(path: Path, header: list, rows: list) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def build_team_sizes(rng: random.Random) -> list:
    sizes = [rng.randint(10, 17) for _ in range(N_TEAMS)]
    while sum(sizes) != N_EMPLOYEES:
        i = rng.randrange(N_TEAMS)
        if sum(sizes) < N_EMPLOYEES and sizes[i] < 17:
            sizes[i] += 1
        elif sum(sizes) > N_EMPLOYEES and sizes[i] > 10:
            sizes[i] -= 1
    return sizes


def main() -> None:
    rng = random.Random(SEED)

    # ---- teams and the non-random selection rule --------------------------
    sizes = build_team_sizes(rng)
    # Enthusiasm scores are redrawn until every cost center holds at least one
    # treated and one holdout team. Without that, the per-cost-center ledger
    # would have nothing to compare against. The redraw is part of the seeded
    # stream, so the result is the same on every run.
    draws = 0
    while True:
        draws += 1
        teams = []
        for t in range(N_TEAMS):
            cc = COST_CENTERS[t // 3][0]                  # three teams per cost center
            enth = round(clip(rng.gauss(3.2, 0.8), 1.0, 5.0), 2)
            teams.append({"team_id": "T%02d" % (t + 1), "cc": cc, "size": sizes[t], "enth": enth})
        ranked = sorted(teams, key=lambda x: (-x["enth"], x["team_id"]))
        treated_ids = set(x["team_id"] for x in ranked[:N_TREATED_TEAMS])
        for x in teams:
            x["cohort"] = "treated" if x["team_id"] in treated_ids else "holdout"
        covered = all(
            set(x["cohort"] for x in teams if x["cc"] == cc[0]) == {"treated", "holdout"}
            for cc in COST_CENTERS
        )
        if covered:
            break
        assert draws < 200, "no enthusiasm draw covers every cost center"
    mean_e = sum(x["enth"] for x in teams) / N_TEAMS
    sd_e = math.sqrt(sum((x["enth"] - mean_e) ** 2 for x in teams) / N_TEAMS)
    for x in teams:
        x["z"] = (x["enth"] - mean_e) / sd_e

    cc_info = {c[0]: c for c in COST_CENTERS}

    # ---- people ---------------------------------------------------------
    people = []
    eid = 0
    for x in teams:
        team_shift = rng.gauss(0.0, 2.0) - SELECTION_SLOPE_MIN * x["z"]
        team_adopt = clip(0.52 + 0.07 * x["z"], 0.25, 0.80)
        for _ in range(x["size"]):
            eid += 1
            if x["cohort"] == "treated":
                u = rng.random()
                tools = "A" if u < 0.45 else ("B" if u < 0.75 else "AB")
            else:
                tools = "none"
            people.append({
                "eid": "E%04d" % eid,
                "team": x["team_id"],
                "cc": x["cc"],
                "cohort": x["cohort"],
                "tools": tools,
                "base": clip(rng.gauss(46.0 + team_shift, 6.5), 28.0, 72.0),
                "tasks": clip(rng.gauss(18.0, 3.0), 8.0, 30.0),
                "skill": clip(rng.gauss(1.0, 0.18), 0.5, 1.6),
                "adopt": clip(rng.gauss(team_adopt, 0.10), 0.15, 0.90),
            })
    assert eid == N_EMPLOYEES

    # team-week shocks, drawn once so every member of a team shares them
    shocks = {}
    for x in teams:
        for w in range(1, N_WEEKS + 1):
            shocks[(x["team_id"], w)] = rng.gauss(0.0, TEAM_WEEK_SHOCK_SD)

    # ---- the panel and the answer key ------------------------------------
    panel_rows = []
    truth_rows = []
    for p in people:
        treated = p["cohort"] == "treated"
        cc = cc_info[p["cc"]]
        p_err, fix_min = cc[6], cc[7]
        for w in range(1, N_WEEKS + 1):
            n_tasks = int(max(5, round(rng.gauss(p["tasks"], 2.2))))
            post = treated and w >= LAUNCH_WEEK
            ea = eb = eboth = 0
            rework = 0.0
            gross = 0.0
            hidden = 0.0
            if post:
                t = w - LAUNCH_WEEK
                for _ in range(n_tasks):
                    if rng.random() >= p["adopt"]:
                        continue
                    if p["tools"] == "A":
                        ea += 1
                    elif p["tools"] == "B":
                        eb += 1
                    else:
                        u = rng.random()
                        if u < P_BOTH_GIVEN_AB:
                            ea += 1
                            eb += 1
                            eboth += 1
                        elif u < P_BOTH_GIVEN_AB + (1.0 - P_BOTH_GIVEN_AB) / 2.0:
                            ea += 1
                        else:
                            eb += 1
                    # one assisted task: maybe the output needs correcting
                    if rng.random() < p_err:
                        rework += max(2.0, rng.gauss(fix_min, 2.0))
                distinct = ea + eb - eboth
                per_task = p["skill"] * (STEADY_MIN + NOVELTY_MIN * math.exp(-NOVELTY_DECAY_K * t))
                gross = distinct * per_task
                hidden = HIDDEN_DRIFT_MIN * n_tasks
                truth_rows.append([
                    p["eid"], w, distinct, "%.2f" % gross, "%.1f" % rework,
                    "%.2f" % (gross - rework), "%.2f" % hidden,
                ])
            minutes = (
                p["base"]
                + season(w)
                + shocks[(p["team"], w)]
                + rng.gauss(0.0, PERSON_WEEK_NOISE_SD)
                - gross / n_tasks
                - hidden / n_tasks
            )
            panel_rows.append([
                p["eid"], w, n_tasks, "%.2f" % minutes, ea, eb, eboth, "%.1f" % rework,
            ])

    # ---- write -----------------------------------------------------------
    write_csv(OUT / "teams.csv",
              ["team_id", "cost_center_id", "headcount", "enthusiasm_score", "cohort"],
              [[x["team_id"], x["cc"], x["size"], "%.2f" % x["enth"], x["cohort"]] for x in teams])

    write_csv(OUT / "employees.csv",
              ["employee_id", "team_id", "cost_center_id", "cohort", "copilots"],
              [[p["eid"], p["team"], p["cc"], p["cohort"], p["tools"]] for p in people])

    write_csv(OUT / "panel.csv",
              ["employee_id", "week", "tasks_completed", "minutes_per_task",
               "events_a", "events_b", "events_both", "rework_minutes"],
              panel_rows)

    heads = {}
    for p in people:
        heads[p["cc"]] = heads.get(p["cc"], 0) + 1
    write_csv(OUT / "budget.csv",
              ["cost_center_id", "cost_center_name", "headcount", "loaded_cost_per_hour_usd",
               "freed_time_can_become_cash", "cash_lever", "addressable_spend_usd_annual"],
              [[c[0], c[1], heads[c[0]], "%.2f" % c[2], c[3], c[4], c[5]] for c in COST_CENTERS])

    write_csv(OUT / "copilots.csv",
              ["copilot_id", "copilot_name", "use_case_id", "assumed_minutes_saved_per_use",
               "seat_cost_usd_per_month", "approval_status"],
              [list(c) for c in COPILOTS])

    write_csv(OUT / "truth_person_week.csv",
              ["employee_id", "week", "true_assisted_tasks", "true_gross_saved_min",
               "true_rework_min", "true_net_saved_min", "true_hidden_drift_min"],
              truth_rows)

    params = {
        "note": "Answer key. Known only because this data is synthetic. No method may read it except to score itself.",
        "seed": SEED,
        "n_employees": N_EMPLOYEES,
        "n_teams": N_TEAMS,
        "n_weeks": N_WEEKS,
        "launch_week": LAUNCH_WEEK,
        "selection_rule": "the %d teams with the highest enthusiasm score get the copilot first; not randomized" % N_TREATED_TEAMS,
        "treated_team_ids": sorted(treated_ids),
        "steady_min_per_assisted_task": STEADY_MIN,
        "novelty_min_per_assisted_task": NOVELTY_MIN,
        "novelty_decay_k_per_week": NOVELTY_DECAY_K,
        "novelty_half_life_weeks": round(math.log(2.0) / NOVELTY_DECAY_K, 2),
        "hidden_drift_min_per_task": HIDDEN_DRIFT_MIN,
        "p_both_given_two_copilots": P_BOTH_GIVEN_AB,
        "season_amplitude_min": SEASON_AMPLITUDE_MIN,
        "season_peak_week": SEASON_PEAK_WEEK,
        "team_week_shock_sd": TEAM_WEEK_SHOCK_SD,
        "person_week_noise_sd": PERSON_WEEK_NOISE_SD,
        "selection_slope_min_per_sd": SELECTION_SLOPE_MIN,
        "rework_by_cost_center": {c[0]: {"p_correction": c[6], "mean_correction_min": c[7]} for c in COST_CENTERS},
    }
    with open(OUT / "truth_parameters.json", "w") as f:
        json.dump(params, f, indent=2, sort_keys=True)
        f.write("\n")

    print("wrote %d employees, %d panel rows, %d truth rows to %s"
          % (len(people), len(panel_rows), len(truth_rows), OUT))


if __name__ == "__main__":
    main()
