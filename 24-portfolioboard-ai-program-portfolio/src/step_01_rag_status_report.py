"""Step 1 - Before PortfolioBoard: the monthly red-amber-green report.

A modeled bank runs 30 AI programs. Once a month each owner picks a red, amber or green status
for their own program and sends it to the head of the AI program office, with an estimate of the
annual benefit. That is the whole report. This script reads it the way the program office reads
it: counts of each color and the benefit total.

Nothing in the report says which green programs fail their gate criteria, where demand for scarce
reviewers exceeds supply, which programs wait on an upstream program that slipped, how much work
is in flight per stage, or how much of the promised benefit is at risk. Step 03 puts a number on
each of those.

Nothing here is a real bank, program, team or model. The data is written by data/_generate.py.
No model is used anywhere in this repo.

Run (from src/):
    python3 step_01_rag_status_report.py

Output: a readable summary, plus out/step_01_rag_report.csv and out/step_01_summary.json.
This module also holds the shared loaders and constants that the later steps and the app import.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

STAGES = ["idea", "discovery", "build", "pilot", "scale"]
TEAMS = ["data_science", "engineering", "model_risk_review", "security_review"]
TEAM_LABEL = {"data_science": "data science", "engineering": "engineering",
              "model_risk_review": "model risk review", "security_review": "security review"}
RAGS = ["green", "amber", "red"]

# Assumption of the modeled bank, not a statistic: one executive sponsor per three programs.
PROGRAMS_PER_SPONSOR = 3


# ---------------------------------------------------------------------------
# Shared loaders (later steps and the app import these)
# ---------------------------------------------------------------------------
def _rd(data_dir: Path, name: str) -> list:
    with open(data_dir / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def quarter_label(idx: int, cal_start: int) -> str:
    return f"{cal_start + idx // 4}Q{idx % 4 + 1}"


def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the ten CSVs into plain dicts and lists. No pandas needed."""
    policy = {r["key"]: r["value"] for r in _rd(data_dir, "policy.csv")}
    as_of_week = int(policy["as_of_week"])
    cal_start = int(policy["calendar_start_year"])
    as_of_q_idx = (as_of_week - 1) // 13

    programs = _rd(data_dir, "programs.csv")
    for p in programs:
        p["est_benefit_usd"] = int(p["est_benefit_usd"])
        p["benefit_confidence"] = float(p["benefit_confidence"])
    prog = {p["program_id"]: p for p in programs}

    criteria = _rd(data_dir, "gate_criteria.csv")
    for c in criteria:
        c["gate"] = int(c["gate"])
        c["max_age_days"] = int(c["max_age_days"])
    crit = {c["criterion_id"]: c for c in criteria}

    evidence = _rd(data_dir, "program_evidence.csv")
    ev_by_prog: dict = defaultdict(list)
    for r in evidence:
        r["met"] = r["met"] == "yes"
        r["age"] = int(r["evidence_age_days"]) if r["evidence_age_days"] != "" else None
        ev_by_prog[r["program_id"]].append(r)

    capacity = {(r["team"], r["quarter"]): float(r["supply_fte"]) for r in _rd(data_dir, "capacity.csv")}
    demand = _rd(data_dir, "demand.csv")
    for r in demand:
        r["need_fte"] = float(r["need_fte"])
    quarters = sorted({q for (_t, q) in capacity})

    deps = _rd(data_dir, "dependencies.csv")
    ups: dict = defaultdict(list)
    for d in deps:
        ups[d["program_id"]].append(d["depends_on"])

    history = _rd(data_dir, "stage_history.csv")
    for h in history:
        h["entered"] = int(h["entered_week"])
        h["requested"] = int(h["review_requested_week"]) if h["review_requested_week"] != "" else None
        h["exited"] = int(h["exited_week"]) if h["exited_week"] != "" else None

    limits = {r["stage"]: int(r["wip_limit"]) for r in _rd(data_dir, "wip_limits.csv")}
    truth = {r["program_id"]: r for r in _rd(data_dir, "program_truth.csv")}

    return {"as_of_week": as_of_week, "as_of_quarter": quarter_label(as_of_q_idx, cal_start),
            "quarters": quarters, "programs": programs, "prog": prog, "criteria": criteria, "crit": crit,
            "evidence": evidence, "ev_by_prog": dict(ev_by_prog), "capacity": capacity, "demand": demand,
            "deps": deps, "ups": dict(ups), "history": history, "limits": limits, "truth": truth}


def usd_m(x: float) -> str:
    """Dollars as $x.xxM. Owner estimates are multiples of $50,000, so two decimals are exact."""
    hundredths = (int(round(x)) + 5_000) // 10_000
    return f"${hundredths / 100:.2f}M"


def pct(a: int, b: int) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


# ---------------------------------------------------------------------------
# The report as sent
# ---------------------------------------------------------------------------
def rag_report(data: dict) -> dict:
    """What the program office sees: counts per color and per stage, and the benefit total."""
    by_stage = {s: {"programs": 0, "green": 0, "amber": 0, "red": 0, "benefit": 0} for s in STAGES}
    totals = {"programs": 0, "green": 0, "amber": 0, "red": 0, "benefit": 0}
    benefit_by_rag = {c: 0 for c in RAGS}
    for p in data["programs"]:
        for bucket in (by_stage[p["stage"]], totals):
            bucket["programs"] += 1
            bucket[p["self_reported_rag"]] += 1
            bucket["benefit"] += p["est_benefit_usd"]
        benefit_by_rag[p["self_reported_rag"]] += p["est_benefit_usd"]
    owners = sorted({p["owner"] for p in data["programs"]})
    return {"by_stage": by_stage, "totals": totals, "benefit_by_rag": benefit_by_rag, "owners": owners}


def summarize(data: dict) -> dict:
    r = rag_report(data)
    t = r["totals"]
    return {
        "programs": t["programs"], "green": t["green"], "amber": t["amber"], "red": t["red"],
        "benefit_total": t["benefit"], "benefit_green": r["benefit_by_rag"]["green"],
        "benefit_amber": r["benefit_by_rag"]["amber"], "benefit_red": r["benefit_by_rag"]["red"],
        "pct_green": round(100.0 * t["green"] / t["programs"], 1),
        "pct_benefit_green": round(100.0 * r["benefit_by_rag"]["green"] / t["benefit"], 1),
        "owners": len(r["owners"]), "criteria": len(data["criteria"]), "stages": len(STAGES),
        "evidence_rows": len(data["evidence"]), "dependencies": len(data["deps"]),
        "history_rows": len(data["history"]), "as_of_week": data["as_of_week"],
        "as_of_quarter": data["as_of_quarter"],
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    r = rag_report(data)
    s = summarize(data)
    t = r["totals"]

    print("\n" + "=" * 78)
    print("STEP 01 - Before PortfolioBoard: the monthly red-amber-green report")
    print("=" * 78)
    print(f"\n{s['programs']} programs, {s['stages']} stages, {s['criteria']} gate criteria, "
          f"as of week {s['as_of_week']} ({s['as_of_quarter']}).")
    print("Data is synthetic and seeded. No model is used anywhere in this repo.\n")
    print("THE REPORT AS SENT TO THE HEAD OF THE AI PROGRAM OFFICE")
    print("  Each owner picks the status of their own program. Nothing else is attached but an estimate.\n")
    print(f"{'stage':<11}{'programs':>9}{'green':>7}{'amber':>7}{'red':>5}   {'owner-estimated benefit':>24}")
    print("-" * 10 + " " + "-" * 8 + " " + "-" * 6 + " " + "-" * 6 + " " + "-" * 4 + "   " + "-" * 24)
    for st in STAGES:
        b = r["by_stage"][st]
        print(f"{st:<11}{b['programs']:>9}{b['green']:>7}{b['amber']:>7}{b['red']:>5}   {usd_m(b['benefit']):>24}")
    print(f"{'all':<11}{t['programs']:>9}{t['green']:>7}{t['amber']:>7}{t['red']:>5}   {usd_m(t['benefit']):>24}")

    print("\nRESULT")
    print(f"  Reported status:        green {t['green']}, amber {t['amber']}, red {t['red']}")
    print(f"  Programs reporting green: {t['green']} of {t['programs']} ({pct(t['green'], t['programs'])})")
    print(f"  Benefit total:          {usd_m(t['benefit'])} (owner estimates, not measured)")
    print(f"  Benefit in programs reported green: {usd_m(r['benefit_by_rag']['green'])} "
          f"({pct(r['benefit_by_rag']['green'], t['benefit'])}); amber {usd_m(r['benefit_by_rag']['amber'])}; "
          f"red {usd_m(r['benefit_by_rag']['red'])}")
    print(f"  Owners who report:      {s['owners']} distinct owners for {t['programs']} programs")

    print("\nWHAT THE REPORT CANNOT SHOW")
    for line in (
        "1  Which programs reported green fail their gate criteria",
        "2  Where demand for scarce reviewers exceeds supply",
        "3  Which programs wait on an upstream program that is red or slipped",
        "4  How much work is in flight per stage, against its limit",
        "5  How much of the promised benefit is at risk",
        "6  Whether the review queue is the bottleneck",
    ):
        print(f"  {line}")
    print("  Step 03 puts a number on each.")

    with open(OUT_DIR / "step_01_rag_report.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["program_id", "name", "stage", "owner", "self_reported_rag", "est_benefit_usd"])
        for p in data["programs"]:
            w.writerow([p["program_id"], p["name"], p["stage"], p["owner"], p["self_reported_rag"],
                        p["est_benefit_usd"]])
    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump(s, f, indent=2)
    print("\nWrote src/out/step_01_rag_report.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
