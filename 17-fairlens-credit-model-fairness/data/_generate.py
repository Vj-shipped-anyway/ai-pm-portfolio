"""Generates the FairLens synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes three CSVs next to this file)

What it builds
  applicants.csv       6,000 synthetic credit applicants in three synthetic groups
                       (Group A 3,600, Group B 1,950, Group C 450). Columns: applicant_id,
                       group, income, dti, history_months, utilization, prior_delinq,
                       postcode_band, defaulted.
  scorecard_points.csv The points of the stand-in "model": a hand-written points scorecard.
                       It is a stub, not a trained model. It gives points for postcode_band,
                       and that is the planted flaw.
  reason_codes.csv     Maps each scorecard component to a plain-language reason code.

How the truth is decided (this is why the truth is known)
  * "defaulted" is drawn from a logistic function of income, dti, history_months,
    utilization and prior_delinq only. Group and postcode_band are NOT inputs to it. The
    generator decides who defaulted, so the outcome is known, not estimated.
  * postcode_band (P1 best to P5 worst) is correlated with group BY CONSTRUCTION: each group
    has its own postcode mix. It has no effect on default in this generator.
  * The groups also differ mildly in income, dti, history and utilization, so part of any
    approval gap comes from legitimate inputs and part from the postcode points.
  * Group labels are synthetic. No real protected class is encoded and nothing here is a
    real bank, applicant, postcode or model.

The group parameters below were set by hand over several trial runs so that the approval
gap, the proxy effect and the small-group uncertainty all appear often enough to count. They
are not estimates of anything real. See data/README.md.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path

SEED = 20261018
OUT = Path(__file__).parent

GROUP_SIZES = [("Group A", 3600), ("Group B", 1950), ("Group C", 450)]

# Per-group input distributions. dq = probabilities of 0, 1, 2, 3 prior delinquencies.
# pb = probabilities of postcode bands P1..P5 (P1 is the best band).
GROUP_PARAMS = {
    "Group A": {"income_median": 64000, "dti_mean": 0.310, "hist_mean": 96, "util_mean": 0.380,
                "dq": [0.80, 0.14, 0.04, 0.02], "pb": [0.34, 0.30, 0.20, 0.11, 0.05]},
    "Group B": {"income_median": 58000, "dti_mean": 0.325, "hist_mean": 88, "util_mean": 0.410,
                "dq": [0.77, 0.15, 0.05, 0.03], "pb": [0.04, 0.11, 0.25, 0.36, 0.24]},
    "Group C": {"income_median": 59000, "dti_mean": 0.325, "hist_mean": 90, "util_mean": 0.410,
                "dq": [0.77, 0.15, 0.05, 0.03], "pb": [0.08, 0.18, 0.28, 0.28, 0.18]},
}
INCOME_SIGMA = 0.45     # log-normal spread of income
DTI_SD = 0.10
HIST_SD = 52.0
UTIL_SD = 0.22

# True default process: logit = INTERCEPT + SCALE * risk, risk built from five inputs only.
INTERCEPT = -3.2
SCALE = 5.0


def true_default_probability(income: int, dti: float, hist: int, util: float, dq: int) -> float:
    risk = (-1.0 * math.log(income / 60000.0) + 3.5 * (dti - 0.32) - 0.007 * (hist - 80)
            + 1.8 * (util - 0.40) + 0.5 * dq)
    z = INTERCEPT + SCALE * risk
    return 1.0 / (1.0 + math.exp(-z))


def draw_index(rng: random.Random, probs: list) -> int:
    r, acc = rng.random(), 0.0
    for k, p in enumerate(probs):
        acc += p
        if r < acc:
            return k
    return len(probs) - 1


def make_applicant(rng: random.Random, group: str) -> dict:
    p = GROUP_PARAMS[group]
    income = math.exp(math.log(p["income_median"]) + INCOME_SIGMA * rng.gauss(0, 1))
    income = int(round(min(max(income, 12000.0), 400000.0) / 100.0) * 100)
    dti = round(min(max(rng.gauss(p["dti_mean"], DTI_SD), 0.05), 0.70), 2)
    hist = int(min(max(round(rng.gauss(p["hist_mean"], HIST_SD)), 3), 360))
    util = round(min(max(rng.gauss(p["util_mean"], UTIL_SD), 0.0), 1.0), 2)
    dq = draw_index(rng, p["dq"])
    band = "P%d" % (draw_index(rng, p["pb"]) + 1)
    default = 1 if rng.random() < true_default_probability(income, dti, hist, util, dq) else 0
    return {"group": group, "income": income, "dti": dti, "history_months": hist,
            "utilization": util, "prior_delinq": dq, "postcode_band": band, "defaulted": default}


# ---------------------------------------------------------------------------
# The stub scorecard (hand-written points; never fitted to this data)
# ---------------------------------------------------------------------------
def band_rows(component: str, cuts: list) -> list:
    """cuts = [(low, high_or_None, points, label)] -> scorecard rows."""
    rows = []
    for low, high, pts, label in cuts:
        rows.append({"component": component, "bucket": label, "low": low,
                     "high": "" if high is None else high, "points": pts})
    return rows


def scorecard_rows() -> list:
    rows = []
    rows += band_rows("income", [(0, 25000, 0, "under 25k"), (25000, 35000, 12, "25k to 35k"),
                                 (35000, 50000, 26, "35k to 50k"), (50000, 70000, 40, "50k to 70k"),
                                 (70000, 100000, 54, "70k to 100k"), (100000, 150000, 64, "100k to 150k"),
                                 (150000, None, 70, "150k and over")])
    rows += band_rows("dti", [(0, 0.15, 65, "under 0.15"), (0.15, 0.25, 54, "0.15 to 0.25"),
                              (0.25, 0.35, 38, "0.25 to 0.35"), (0.35, 0.45, 20, "0.35 to 0.45"),
                              (0.45, 0.55, 7, "0.45 to 0.55"), (0.55, None, 0, "0.55 and over")])
    rows += band_rows("history_months", [(0, 12, 0, "under 12"), (12, 36, 14, "12 to 35"),
                                         (36, 72, 28, "36 to 71"), (72, 120, 40, "72 to 119"),
                                         (120, 180, 52, "120 to 179"), (180, None, 60, "180 and over")])
    rows += band_rows("utilization", [(0, 0.15, 60, "under 0.15"), (0.15, 0.30, 50, "0.15 to 0.30"),
                                      (0.30, 0.50, 36, "0.30 to 0.50"), (0.50, 0.70, 20, "0.50 to 0.70"),
                                      (0.70, 0.85, 6, "0.70 to 0.85"), (0.85, None, 0, "0.85 and over")])
    rows += band_rows("prior_delinq", [(0, 1, 60, "0"), (1, 2, 28, "1"), (2, 3, 8, "2"),
                                       (3, None, 0, "3 or more")])
    # The planted flaw: points for the postcode band. It has no effect on default in this data.
    for band, pts in (("P1", 35), ("P2", 25), ("P3", 15), ("P4", 5), ("P5", 0)):
        rows.append({"component": "postcode_band", "bucket": band, "low": "", "high": "", "points": pts})
    return rows


REASON_ROWS = [
    {"component": "income", "reason_code": "R01", "plain_language": "Income is low for the credit requested"},
    {"component": "dti", "reason_code": "R02", "plain_language": "Debt payments are high compared with income"},
    {"component": "history_months", "reason_code": "R03", "plain_language": "Length of credit history is short"},
    {"component": "utilization", "reason_code": "R04", "plain_language": "Balances are high compared with credit limits"},
    {"component": "prior_delinq", "reason_code": "R05", "plain_language": "Late payments are on record"},
    {"component": "postcode_band", "reason_code": "R06", "plain_language": "Postcode band of the home address"},
]


def write_csv(path: Path, fields: list, rows: list) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    people = []
    for group, n in GROUP_SIZES:
        for _ in range(n):
            people.append(make_applicant(rng, group))
    # Fisher-Yates shuffle with the seeded generator, so ids interleave the groups.
    for i in range(len(people) - 1, 0, -1):
        j = int(rng.random() * (i + 1))
        people[i], people[j] = people[j], people[i]
    for i, a in enumerate(people, start=1):
        a["applicant_id"] = "AP-%05d" % i

    fields = ["applicant_id", "group", "income", "dti", "history_months", "utilization",
              "prior_delinq", "postcode_band", "defaulted"]
    write_csv(OUT / "applicants.csv", fields, people)
    write_csv(OUT / "scorecard_points.csv", ["component", "bucket", "low", "high", "points"], scorecard_rows())
    write_csv(OUT / "reason_codes.csv", ["component", "reason_code", "plain_language"], REASON_ROWS)

    print(f"Wrote {len(people):,} applicants -> applicants.csv")
    for group, n in GROUP_SIZES:
        g = [a for a in people if a["group"] == group]
        d = sum(a["defaulted"] for a in g)
        print(f"  {group}: {len(g):,} applicants, {d} defaulted ({100 * d / len(g):.1f}%)")
    print("Postcode band mix (share of each group's applicants; P1 is the best band):")
    for group, _ in GROUP_SIZES:
        g = [a for a in people if a["group"] == group]
        mix = ", ".join(f"P{k} {100 * sum(1 for a in g if a['postcode_band'] == 'P%d' % k) / len(g):.1f}%" for k in range(1, 6))
        print(f"  {group}: {mix}")
    print(f"Wrote {len(scorecard_rows())} scorecard point rows -> scorecard_points.csv")
    print(f"Wrote {len(REASON_ROWS)} reason codes -> reason_codes.csv")


if __name__ == "__main__":
    main()
