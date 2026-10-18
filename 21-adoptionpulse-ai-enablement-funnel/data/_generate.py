"""Generates the AdoptionPulse synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes seven CSVs next to this file)

What it builds
  users.csv            800 licensed staff in 20 org units: role, licensing week, whether the
                       unit has a champion, and the week the person completed training.
  usage_weekly.csv     800 users x 12 weeks = 9,600 rows of logins, AI sessions, prompts,
                       accepted outputs and advanced-feature uses.
  champions.csv        60 champions spread over the units that have one.
  funnel_policy.csv    The stage definitions and thresholds (assumptions of a modeled bank).
  user_truth.csv       The truth the generator decided for each user: latent type, true stage
                       and work quality. Used only to score the staging; no decision reads it.
  unit_truth.csv       Per org unit: size, rollout week, champion flag, the hidden appetite the
                       generator drew for the unit and its training completion rate.
  planted_effects.csv  The champion and training effects the generator planted, and the average
                       change in the probability of becoming a habitual user that each implies.

The truth is known because the data is synthetic. A latent user type (never, one_time, casual,
habitual, proficient, lapsed) drives the weekly counts. The champion effect and the training
effect are planted by construction: the generator raises the probability that a user is a
habitual or proficient type when the unit has a champion and when the person was trained.
Training and champion assignment are random with respect to propensity here; in real data both
would be confounded (motivated people choose training, motivated units get champions).

Nothing here comes from a real bank, vendor, product, model or person. No model wrote the data.

Parameters below were fixed from design reasoning before any output was looked at. One seed was
used and no other seed was tried.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

SEED = 20261018
HERE = Path(__file__).parent

WEEKS = 12
WEEK_ONE_MONDAY = "2026-07-06"        # constant; week 12 ends 2026-09-27
CHAMPION_TOTAL = 60
CHAMPION_UNITS = 12                   # units with an assigned champion

# Adopter probability = sigmoid(BASE_LOGIT + unit effect + role effect + planted effects).
BASE_LOGIT = -1.30
UNIT_SD = 0.55
CHAMPION_SHIFT = 0.70                 # PLANTED: logit shift when the unit has a champion
TRAINING_SHIFT = 0.55                 # PLANTED: logit shift when the person completed training
PROF_BASE_LOGIT = -0.85               # among adopters, chance of the proficient type

ROLE_ADOPT = {"engineer": 0.45, "analyst": 0.25, "manager": 0.05,
              "relationship manager": -0.10, "specialist": -0.15, "associate": -0.25}
ROLE_PROF = {"engineer": 0.60, "analyst": 0.30, "manager": 0.0,
             "relationship manager": 0.0, "specialist": 0.0, "associate": 0.0}

# Among people who are not adopters: cumulative split into the four lower types.
NONADOPTER_SPLIT = [("never", 0.45), ("one_time", 0.22), ("casual", 0.20), ("lapsed", 0.13)]

SESS_LAMBDA = {"one_time": 0.5, "casual": 0.8, "lapsed": 1.2, "habitual": 2.4, "proficient": 3.8}
PROMPT_LAMBDA = {"one_time": 1.5, "casual": 2.0, "lapsed": 2.0, "habitual": 3.0, "proficient": 4.5}
ACCEPT_MEAN_SD = {"one_time": (0.30, 0.10), "casual": (0.35, 0.10), "lapsed": (0.35, 0.10),
                  "habitual": (0.45, 0.08), "proficient": (0.72, 0.07)}
ADV_LAMBDA = {"one_time": 0.02, "casual": 0.03, "lapsed": 0.03, "habitual": 0.15, "proficient": 2.0}
POOR_QUALITY_RATE = 0.15              # independent of everything else: telemetry cannot see it

# (name, size, rollout week, role mix). Sizes sum to 800.
UNITS = [
    ("Customer Service", 100, 1, {"associate": 0.70, "specialist": 0.22, "manager": 0.08}),
    ("Technology Delivery", 90, 1, {"engineer": 0.72, "analyst": 0.15, "manager": 0.13}),
    ("Payments Operations", 75, 2, {"specialist": 0.50, "associate": 0.35, "analyst": 0.08, "manager": 0.07}),
    ("Branch Network", 70, 3, {"associate": 0.55, "relationship manager": 0.35, "manager": 0.10}),
    ("Commercial Lending", 58, 2, {"relationship manager": 0.45, "analyst": 0.35, "manager": 0.12, "associate": 0.08}),
    ("Retail Operations", 52, 2, {"associate": 0.50, "specialist": 0.35, "manager": 0.15}),
    ("Credit Risk", 46, 1, {"analyst": 0.65, "manager": 0.15, "specialist": 0.20}),
    ("Finance", 42, 1, {"analyst": 0.60, "specialist": 0.20, "manager": 0.20}),
    ("Mortgage Servicing", 38, 3, {"specialist": 0.50, "associate": 0.40, "manager": 0.10}),
    ("Collections", 35, 3, {"associate": 0.65, "specialist": 0.25, "manager": 0.10}),
    ("Fraud Operations", 30, 1, {"analyst": 0.45, "specialist": 0.45, "manager": 0.10}),
    ("Data and Analytics", 28, 1, {"analyst": 0.50, "engineer": 0.40, "manager": 0.10}),
    ("Compliance", 26, 1, {"analyst": 0.50, "specialist": 0.35, "manager": 0.15}),
    ("Wealth Advisory", 24, 3, {"relationship manager": 0.60, "analyst": 0.25, "associate": 0.15}),
    ("Treasury", 20, 1, {"analyst": 0.55, "specialist": 0.25, "manager": 0.20}),
    ("Marketing", 18, 2, {"specialist": 0.50, "analyst": 0.30, "manager": 0.20}),
    ("Legal", 15, 2, {"specialist": 0.70, "manager": 0.30}),
    ("Human Resources", 14, 4, {"specialist": 0.60, "associate": 0.25, "manager": 0.15}),
    ("Procurement", 10, 4, {"specialist": 0.55, "analyst": 0.30, "manager": 0.15}),
    ("Internal Audit", 9, 2, {"analyst": 0.70, "manager": 0.30}),
]

POLICY_ROWS = [
    ("activation_window_weeks", 2, "activated",
     "Activated = at least 1 AI session in the first 14 days after licensing. Weekly data, so the licensing week and the next week."),
    ("habit_window_weeks", 6, "habitual",
     "Look-back window for habit and proficiency: the last 6 weeks of the data (weeks 7 to 12)."),
    ("habit_min_active_weeks", 4, "habitual",
     "Habitual = AI sessions in at least 4 of the last 6 weeks."),
    ("proficient_min_advanced_weeks", 2, "proficient",
     "Proficient also needs advanced-feature use in at least 2 of the last 6 weeks."),
    ("proficient_min_accept_rate", 0.60, "proficient",
     "Proficient also needs accepted outputs divided by prompts over the last 6 weeks at or above this value. A proxy for skill, not a measure of it."),
    ("leak_min_gap_points", 5, "action",
     "A stage conversion counts as a leak when a unit is at least this many points below the estate rate."),
    ("leak_min_users", 5, "action",
     "A stage conversion is judged for a unit only when at least this many users entered the stage before it."),
]


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def binomial(rng: random.Random, n: int, p: float) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


def allocate(total: int, weights: list, minimum: int) -> list:
    """Largest-remainder split of `total` with a floor of `minimum` each."""
    n = len(weights)
    rest = total - minimum * n
    raw = [rest * w / sum(weights) for w in weights]
    out = [minimum + int(r) for r in raw]
    order = sorted(range(n), key=lambda i: (-(raw[i] - int(raw[i])), i))
    for i in order[: total - sum(out)]:
        out[i] += 1
    return out


def pick(rng_value: float, mix: dict) -> str:
    acc = 0.0
    last = None
    for name in sorted(mix):
        acc += mix[name]
        last = name
        if rng_value < acc:
            return name
    return last


def main() -> None:
    assert sum(u[1] for u in UNITS) == 800, "unit sizes must sum to 800"

    # ---- units: hidden appetite, training completion rate, champion assignment ----
    r_units = random.Random(SEED + 1)
    unit_effect = {}
    train_rate = {}
    for name, _size, _wave, _mix in UNITS:
        unit_effect[name] = r_units.gauss(0.0, UNIT_SD)
        train_rate[name] = 0.25 + 0.65 * r_units.random()
    names = [u[0] for u in UNITS]
    r_champ = random.Random(SEED + 2)
    shuffled = names[:]
    for i in range(len(shuffled) - 1, 0, -1):          # Fisher-Yates with random()
        j = int(r_champ.random() * (i + 1))
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    champion_units = set(shuffled[:CHAMPION_UNITS])

    # ---- champions.csv ----
    sizes = {u[0]: u[1] for u in UNITS}
    ch_units = [n for n in names if n in champion_units]
    counts = allocate(CHAMPION_TOTAL, [sizes[n] for n in ch_units], 2)
    r_ch = random.Random(SEED + 3)
    champions = []
    for n, k in zip(ch_units, counts):
        for _ in range(k):
            champions.append((f"CH-{len(champions) + 1:03d}", n, 4 + int(r_ch.random() * 9)))

    # ---- users: slots shuffled so ids do not reveal the unit ----
    slots = [u[0] for u in UNITS for _ in range(u[1])]
    r_slots = random.Random(SEED + 4)
    for i in range(len(slots) - 1, 0, -1):
        j = int(r_slots.random() * (i + 1))
        slots[i], slots[j] = slots[j], slots[i]

    unit_info = {u[0]: u for u in UNITS}
    r_user = random.Random(SEED + 5)
    users, truth_params = [], {}
    train_offsets = [(0, 0.15), (1, 0.25), (2, 0.25), (3, 0.15), (4, 0.10), (5, 0.10)]
    for idx, unit in enumerate(slots, start=1):
        uid = f"U{idx:04d}"
        # Fixed draw order: every uniform is drawn for every user.
        r_role, r_jit, r_train, r_tweek, r_adopt, r_prof, r_split, r_p1, r_fw, r_q = (
            r_user.random() for _ in range(10))
        _, _, wave, mix = unit_info[unit]
        role = pick(r_role, mix)
        lic = min(4, wave + (1 if r_jit < 0.20 else 0))
        champ = unit in champion_units
        trained = r_train < train_rate[unit]
        tweek = ""
        if trained:
            acc, off = 0.0, 0
            for o, w in train_offsets:
                acc += w
                off = o
                if r_tweek < acc:
                    break
            tweek = lic + off
        logit_wo = BASE_LOGIT + unit_effect[unit] + ROLE_ADOPT[role]
        p_adopt = sigmoid(logit_wo + (CHAMPION_SHIFT if champ else 0.0) + (TRAINING_SHIFT if trained else 0.0))
        if r_adopt < p_adopt:
            p_prof = sigmoid(PROF_BASE_LOGIT + ROLE_PROF[role])
            ltype = "proficient" if r_prof < p_prof else "habitual"
        else:
            acc, ltype = 0.0, "lapsed"
            for name, w in NONADOPTER_SPLIT:
                acc += w
                if r_split < acc:
                    ltype = name
                    break
        users.append({"user_id": uid, "org_unit": unit, "role": role, "licensed_week": lic,
                      "champion_in_unit": "yes" if champ else "no", "trained_week": tweek})
        truth_params[uid] = {"type": ltype, "p1": r_p1, "fw": lic + (0 if r_fw < 0.70 else 1),
                             "quality_draw": r_q, "logit_wo": logit_wo, "champ": champ,
                             "trained": trained}

    # ---- usage_weekly.csv ----
    r_use = random.Random(SEED + 6)
    usage_rows = []
    truth_rows = []
    stage_of_type = {"never": "licensed", "one_time": "activated", "casual": "activated",
                     "lapsed": "activated", "habitual": "habitual", "proficient": "proficient"}
    for u in users:
        uid, lic = u["user_id"], u["licensed_week"]
        tp = truth_params[uid]
        ltype, fw = tp["type"], tp["fw"]
        # Per-user parameters
        p_week = 0.0
        if ltype == "habitual":
            p_week = 0.62 + 0.33 * tp["p1"]
        elif ltype == "proficient":
            p_week = 0.70 + 0.27 * tp["p1"]
        elif ltype == "casual":
            p_week = 0.10 + 0.24 * tp["p1"]
        run_len = 2 + int(tp["p1"] * 3) if ltype == "lapsed" else 0     # 2, 3 or 4 weeks
        if ltype != "never":
            mu, sd = ACCEPT_MEAN_SD[ltype]
            accept = min(0.95, max(0.05, r_use.gauss(mu, sd)))
        else:
            accept = 0.0
        for w in range(1, WEEKS + 1):
            logins = sessions = prompts = accepted = adv = 0
            if w >= lic:
                if ltype == "never":
                    active = False
                elif ltype == "one_time":
                    active = (w == fw)
                elif ltype == "casual":
                    if w < fw:
                        active = False
                    elif w == fw:
                        active = True
                    else:
                        p = p_week + (0.30 if (w - lic) <= 2 else 0.0)
                        active = r_use.random() < min(0.95, p)
                elif ltype == "lapsed":
                    if w < fw or w >= fw + run_len:
                        active = False
                    elif w == fw:
                        active = True
                    else:
                        active = r_use.random() < 0.80
                else:                                                   # habitual, proficient
                    if w < fw:
                        active = False
                    elif w == fw:
                        active = True
                    else:
                        active = r_use.random() < p_week
                if active:
                    sessions = 1 + poisson(r_use, SESS_LAMBDA[ltype])
                    prompts = sum(1 + poisson(r_use, PROMPT_LAMBDA[ltype]) for _ in range(sessions))
                    accepted = binomial(r_use, prompts, accept)
                    adv = poisson(r_use, ADV_LAMBDA[ltype])
                    logins = min(sessions, 1 + (1 if r_use.random() < 0.35 else 0))
                else:
                    if ltype == "never":
                        p_login = 0.25 if (w - lic) <= 1 else 0.04
                    else:
                        p_login = 0.08
                    logins = 1 if r_use.random() < p_login else 0
            usage_rows.append((uid, w, logins, sessions, prompts, accepted, adv))
        quality = "none" if ltype == "never" else ("poor" if tp["quality_draw"] < POOR_QUALITY_RATE else "good")
        truth_rows.append((uid, ltype, stage_of_type[ltype], quality))

    # ---- planted_effects.csv: average implied change in adopter probability ----
    def mean(xs: list) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    planted = []
    for label, shift, key in (("champion_in_unit", CHAMPION_SHIFT, "champ"),
                              ("training_completed", TRAINING_SHIFT, "trained")):
        w_out, w_with = [], []
        for u in users:
            tp = truth_params[u["user_id"]]
            if not tp[key]:
                continue
            other = 0.0
            if key == "champ" and tp["trained"]:
                other = TRAINING_SHIFT
            if key == "trained" and tp["champ"]:
                other = CHAMPION_SHIFT
            w_out.append(sigmoid(tp["logit_wo"] + other))
            w_with.append(sigmoid(tp["logit_wo"] + other + shift))
        planted.append((label, shift, len(w_out), round(mean(w_out), 4), round(mean(w_with), 4),
                        round(100 * (mean(w_with) - mean(w_out)), 1)))

    # ---- write ----
    def write(name: str, header: list, rows: list) -> None:
        with open(HERE / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    write("users.csv", ["user_id", "org_unit", "role", "licensed_week", "champion_in_unit", "trained_week"],
          [[u["user_id"], u["org_unit"], u["role"], u["licensed_week"], u["champion_in_unit"], u["trained_week"]]
           for u in users])
    write("usage_weekly.csv", ["user_id", "week", "logins", "ai_sessions", "prompts", "outputs_accepted",
                               "advanced_feature_uses"], usage_rows)
    write("champions.csv", ["champion_id", "org_unit", "active_weeks"], champions)
    write("funnel_policy.csv", ["parameter", "value", "applies_to", "definition"], POLICY_ROWS)
    write("user_truth.csv", ["user_id", "latent_type", "true_stage", "work_quality"], truth_rows)
    write("unit_truth.csv", ["org_unit", "licensed", "rollout_week", "champion_in_unit", "appetite_logit",
                             "training_rate"],
          [[n, sizes[n], unit_info[n][2], "yes" if n in champion_units else "no",
            round(unit_effect[n], 3), round(train_rate[n], 3)] for n in sorted(names)])
    write("planted_effects.csv", ["effect", "planted_logit_shift", "users_affected",
                                  "avg_p_habitual_or_better_without", "avg_p_habitual_or_better_with",
                                  "planted_gap_points"],
          planted)
    print(f"Wrote {len(users)} users, {len(usage_rows):,} weekly rows, {len(champions)} champions, "
          f"{len(POLICY_ROWS)} policy rows, {len(truth_rows)} truth rows, {len(planted)} planted effects.")


if __name__ == "__main__":
    main()
