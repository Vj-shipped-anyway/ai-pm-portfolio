"""Step 1 - Before AdoptionPulse: licenses issued and users who logged in.

A modeled bank licensed an AI assistant to 800 staff and reports adoption as licenses issued
and users who logged in. This script shows what that status quo holds and what it cannot say.
The program lead is asked six questions: who uses it, who uses it every week, who uses it well,
which teams lag, whether training changed anything and whether champions matter. None of them
can be answered from a license date and a login count.

This file also holds the shared loaders and the stage rules that later steps and the app import.
The rules read data/funnel_policy.csv (assumptions of a modeled bank, not advice).

The data is synthetic (data/_generate.py, seeded). No model is used anywhere in this repo.
The user_truth.csv file records what the generator decided for each user; the stage rules
never read it, and only the scoring in step 4 does.

ASSUMPTIONS (modeled, printed with the result):
  A1. The program reports what the license portal and the sign-in log hold: the week a license
      was issued and login counts. It does not hold AI session counts.
  A2. "Adoption" is the share of licensed users who logged in at least once.

Run (from src/):
    python3 step_01_license_counts_status_quo.py

Output: a readable summary, plus out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

WEEKS = 12
STAGES = ["licensed", "activated", "habitual", "proficient"]
STAGE_RANK = {s: i for i, s in enumerate(STAGES)}

# The fields the status quo holds (assumption A1) and the fields each question needs.
STATUS_QUO_FIELDS = {"user_id", "org_unit", "licensed_week", "logins"}
QUESTIONS = [
    ("Who uses it?", {"user_id", "ai_sessions"}),
    ("Who uses it every week?", {"user_id", "week", "ai_sessions"}),
    ("Who uses it well?", {"user_id", "prompts", "outputs_accepted", "advanced_feature_uses"}),
    ("Which teams lag?", {"org_unit", "ai_sessions"}),
    ("Did training change anything?", {"trained_week", "ai_sessions"}),
    ("Do champions matter?", {"champion_in_unit", "ai_sessions"}),
]


# ---------------------------------------------------------------------------
# Shared loaders (later steps and the app import these)
# ---------------------------------------------------------------------------
def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the CSVs into plain dicts. No pandas needed."""
    with open(data_dir / "users.csv", newline="", encoding="utf-8") as f:
        users = list(csv.DictReader(f))
    for u in users:
        u["licensed_week"] = int(u["licensed_week"])
        u["champion"] = u["champion_in_unit"] == "yes"
        u["trained_week"] = int(u["trained_week"]) if u["trained_week"] else None

    use = {u["user_id"]: {k: [0] * WEEKS for k in ("logins", "sessions", "prompts", "accepted", "advanced")}
           for u in users}
    usage_rows = 0
    with open(data_dir / "usage_weekly.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            usage_rows += 1
            w = int(r["week"]) - 1
            d = use[r["user_id"]]
            d["logins"][w] = int(r["logins"])
            d["sessions"][w] = int(r["ai_sessions"])
            d["prompts"][w] = int(r["prompts"])
            d["accepted"][w] = int(r["outputs_accepted"])
            d["advanced"][w] = int(r["advanced_feature_uses"])

    with open(data_dir / "champions.csv", newline="", encoding="utf-8") as f:
        champions = list(csv.DictReader(f))
    for c in champions:
        c["active_weeks"] = int(c["active_weeks"])

    policy = {}
    with open(data_dir / "funnel_policy.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            policy[r["parameter"]] = float(r["value"])

    with open(data_dir / "user_truth.csv", newline="", encoding="utf-8") as f:
        truth = {r["user_id"]: r for r in csv.DictReader(f)}

    with open(data_dir / "planted_effects.csv", newline="", encoding="utf-8") as f:
        planted = {r["effect"]: r for r in csv.DictReader(f)}

    with open(data_dir / "unit_truth.csv", newline="", encoding="utf-8") as f:
        unit_truth = {r["org_unit"]: r for r in csv.DictReader(f)}

    by_unit = defaultdict(list)
    for u in users:
        by_unit[u["org_unit"]].append(u)
    return {"users": users, "use": use, "champions": champions, "policy": policy, "truth": truth,
            "planted": planted, "unit_truth": unit_truth, "units": sorted(by_unit), "by_unit": dict(by_unit), "usage_rows": usage_rows,
            "by_id": {u["user_id"]: u for u in users}}


# ---------------------------------------------------------------------------
# Stage rules, read from funnel_policy.csv
# ---------------------------------------------------------------------------
def last_weeks(policy: dict) -> range:
    n = int(policy["habit_window_weeks"])
    return range(WEEKS - n + 1, WEEKS + 1)            # weeks 7 to 12 with a 6-week window


def active_weeks(use_u: dict, weeks) -> int:
    return sum(1 for w in weeks if use_u["sessions"][w - 1] > 0)


def accept_rate(use_u: dict, weeks) -> float:
    prompts = sum(use_u["prompts"][w - 1] for w in weeks)
    return sum(use_u["accepted"][w - 1] for w in weeks) / prompts if prompts else 0.0


def is_activated(user: dict, use_u: dict, policy: dict) -> bool:
    first = user["licensed_week"]
    last = min(WEEKS, first + int(policy["activation_window_weeks"]) - 1)
    return any(use_u["sessions"][w - 1] > 0 for w in range(first, last + 1))


def is_habitual(use_u: dict, policy: dict) -> bool:
    return active_weeks(use_u, last_weeks(policy)) >= int(policy["habit_min_active_weeks"])


def is_proficient(use_u: dict, policy: dict) -> bool:
    if not is_habitual(use_u, policy):
        return False
    lw = last_weeks(policy)
    adv_weeks = sum(1 for w in lw if use_u["advanced"][w - 1] > 0)
    return (adv_weeks >= int(policy["proficient_min_advanced_weeks"])
            and accept_rate(use_u, lw) >= policy["proficient_min_accept_rate"])


def stage_of(user: dict, use_u: dict, policy: dict) -> str:
    if is_proficient(use_u, policy):
        return "proficient"
    if is_habitual(use_u, policy):
        return "habitual"
    if is_activated(user, use_u, policy):
        return "activated"
    return "licensed"


def ever_logged_in(use_u: dict) -> bool:
    return sum(use_u["logins"]) > 0


# ---------------------------------------------------------------------------
# What the status quo reports
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    users, use = data["users"], data["use"]
    n = len(users)
    cum = []
    for w in range(1, WEEKS + 1):
        cum.append(sum(1 for u in users if u["licensed_week"] <= w))
    logged = sum(1 for u in users if ever_logged_in(use[u["user_id"]]))
    login_events = sum(sum(use[u["user_id"]]["logins"]) for u in users)
    answerable = [q for q, need in QUESTIONS if need <= STATUS_QUO_FIELDS]
    return {
        "licensed": n, "units": len(data["units"]), "licensed_by_week": cum, "usage_rows": data["usage_rows"],
        "champions": len(data["champions"]),
        "first_week": min(u["licensed_week"] for u in users),
        "last_license_week": max(u["licensed_week"] for u in users),
        "logged_in": logged, "adoption_pct": round(100 * logged / n, 1),
        "login_events": login_events,
        "questions": len(QUESTIONS), "answerable": len(answerable),
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    s = summarize(data)

    print("\n" + "=" * 78)
    print("Step 1 - Before AdoptionPulse: licenses issued and users who logged in")
    print("=" * 78)
    print(f"\n{s['licensed']} licenses issued to staff in {s['units']} org units, in weeks "
          f"{s['first_week']} to {s['last_license_week']} of a {WEEKS}-week window.")
    print(f"Usage data: {s['usage_rows']:,} user-weeks. Champions: {s['champions']}.")
    print("Data is synthetic and seeded. The truth is known because the generator decided it.\n")
    print("ASSUMPTIONS (modeled):")
    print("  A1  the program reports what the license portal and the sign-in log hold: the week a")
    print("      license was issued and login counts. It does not hold AI session counts")
    print("  A2  'adoption' is the share of licensed users who logged in at least once\n")

    print("LICENSES ISSUED (cumulative, end of week)")
    for w, c in enumerate(s["licensed_by_week"], start=1):
        if w <= s["last_license_week"]:
            print(f"  week {w:>2}: {c:>3} licenses")

    print("\nWHAT THE STATUS QUO REPORTS")
    print(f"  Licenses issued:                      {s['licensed']}")
    print(f"  Users who logged in at least once:    {s['logged_in']} of {s['licensed']} ({s['adoption_pct']}%)")
    print(f"  Login events in {WEEKS} weeks:               {s['login_events']:,}")
    print(f"  Reported adoption (licensed and logged in): {s['adoption_pct']}%")

    print("\nTHE SIX QUESTIONS THE PROGRAM LEAD GETS ASKED")
    print(f"  {'question':<32} {'needs':<62} answerable")
    for q, need in QUESTIONS:
        ok = need <= STATUS_QUO_FIELDS
        print(f"  {q:<32} {', '.join(sorted(need)):<62} {'yes' if ok else 'no'}")

    print("\nRESULT")
    print(f"  Questions answerable from the fields the status quo holds: {s['answerable']} of {s['questions']} "
          "(by construction of the field list in this script)")
    print(f"  The one number it can give is {s['adoption_pct']}% adoption. It cannot say who uses the tool, how often, or how well.")

    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_01_summary.json")


if __name__ == "__main__":
    main()
