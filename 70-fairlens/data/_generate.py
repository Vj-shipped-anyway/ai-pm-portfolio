"""Generate the synthetic data for project 70 (fairlens): 36 scored portfolios of about 830
applicants each, three synthetic groups, one points scorecard per portfolio.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth of each portfolio
is the mechanism that was planted, and it comes from the generative process below, not from any
fairness test:

  clean              groups share every distribution; the postcode points are unrelated to group
  legit_gap          groups differ in the legitimate inputs; real default risk differs; no proxy
  small_group_noise  groups share every distribution, but the smallest group has 30 applicants and
                     the portfolio is redrawn until that group's approval rate happens to fall
                     below four fifths of the reference group's (hard negative: no true gap)
  proxy_gap          the postcode points track group and have no effect on default (planted proxy)
  proxy_predictive   the postcode points track group AND predict default (hard negative: a
                     correlated feature that earns its place)
  two_proxies        two group-correlated components, postcode and region (planted; the check is
                     pointed at the postcode column only, a known limit)
  quiet_proxy        a planted proxy worth only 8 to 12 points (a hard case the rules should miss)

Run (from data/):  python3 _generate.py
Writes:  case_scores.csv, case_truth.csv, example_scores.csv, example_params.json
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

SEED = 7020261024
OUT = Path(__file__).parent

# component, reason code, maximum points
LEGIT = [("income", "R01", 70), ("debt_ratio", "R02", 65), ("history", "R03", 60), ("utilization", "R04", 60)]
POSTCODE_CODE = "R05"
REGION_CODE = "R06"
CUTS = (-1.0, -0.35, 0.35, 1.0)          # a quality draw earns 0 to 4 quarters of the component maximum
SHIFT_B = (-0.45, -0.30, -0.25, -0.30)   # legitimate-input shift of Group B, in standard deviations; Group C gets half
BASE_LOGIT = -1.45
RISK_SLOPE = 1.3
APPROVE_QUANTILE = 0.30                  # the policy cutoff is the score at this quantile of the portfolio

MIX_SAME = {g: [0.15, 0.25, 0.30, 0.20, 0.10] for g in ("Group A", "Group B", "Group C")}
MIX_SPLIT = {"Group A": [0.40, 0.30, 0.18, 0.08, 0.04],
             "Group B": [0.02, 0.08, 0.20, 0.38, 0.32],
             "Group C": [0.10, 0.18, 0.28, 0.26, 0.18]}

PLAN = [("clean", 5), ("legit_gap", 6), ("small_group_noise", 6), ("proxy_gap", 8),
        ("proxy_predictive", 5), ("two_proxies", 3), ("quiet_proxy", 3)]
PLANTED = {"proxy_gap", "two_proxies", "quiet_proxy"}


def params_for(mech: str, k: int) -> dict:
    """The planted parameters of the k-th portfolio of a mechanism."""
    p = {"mechanism": mech, "postcode_w": 30, "region_w": 0, "shift": 0.0, "mix": "same", "predictive": 0.0,
         "sizes": {"Group A": 450, "Group B": 280, "Group C": 100}}
    if mech in ("clean", "small_group_noise"):
        p["postcode_w"] = (20, 30, 40)[k % 3]
    if mech == "small_group_noise":
        p["sizes"]["Group C"] = 30
    if mech == "legit_gap":
        p["postcode_w"] = (20, 30, 40)[k % 3]
        p["shift"] = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9)[k]
    if mech == "proxy_gap":
        p.update(mix="split", postcode_w=(40, 45, 50, 55, 60)[k % 5], shift=0.2)
    if mech == "proxy_predictive":
        p.update(mix="split", postcode_w=(35, 40, 45)[k % 3], predictive=(1.2, 1.4, 1.6, 1.3, 1.5)[k])
    if mech == "two_proxies":
        p.update(mix="split", postcode_w=28, region_w=28, shift=0.2)
    if mech == "quiet_proxy":
        p.update(mix="split", postcode_w=(8, 10, 12)[k])
    return p


def draw_band(rng: random.Random, mix: list) -> int:
    r, acc = rng.random(), 0.0
    for i, share in enumerate(mix):
        acc += share
        if r < acc:
            return i + 1
    return len(mix)


def make_applicant(rng: random.Random, group: str, p: dict) -> dict:
    scale = p["shift"] * (0.0 if group == "Group A" else 1.0 if group == "Group B" else 0.5)
    q = [rng.gauss(0, 1) + scale * SHIFT_B[i] for i in range(4)]
    pts = [(LEGIT[i][2] * sum(1 for c in CUTS if q[i] > c)) // 4 for i in range(4)]
    mix = MIX_SPLIT if p["mix"] == "split" else MIX_SAME
    band = draw_band(rng, mix[group])
    region_band = draw_band(rng, mix[group])
    postcode_pts = (p["postcode_w"] * (5 - band)) // 4
    region_pts = (p["region_w"] * (5 - region_band)) // 4
    logit = BASE_LOGIT - RISK_SLOPE * sum(q) / 2.0 + p["predictive"] * (band - 3) / 2.0
    bad = 1 if rng.random() < 1.0 / (1.0 + math.exp(-logit)) else 0
    lost = [(LEGIT[i][2] - pts[i], i, LEGIT[i][1]) for i in range(4)]
    lost.append((p["postcode_w"] - postcode_pts, 4, POSTCODE_CODE))
    if p["region_w"]:
        lost.append((p["region_w"] - region_pts, 5, REGION_CODE))
    lost.sort(key=lambda t: (-t[0], t[1]))
    return {"group": group, "score": sum(pts) + postcode_pts + region_pts, "bad_outcome": bad,
            "postcode_points": postcode_pts, "region_points": region_pts,
            "reasons": [t[2] for t in lost[:3]]}


def build(seed: int, p: dict) -> tuple:
    rng = random.Random(seed)
    people = []
    for group, n in p["sizes"].items():
        people.extend(make_applicant(rng, group, p) for _ in range(n))
    for i in range(len(people) - 1, 0, -1):          # seeded Fisher-Yates shuffle
        j = int(rng.random() * (i + 1))
        people[i], people[j] = people[j], people[i]
    scores = sorted(a["score"] for a in people)
    return people, scores[int(APPROVE_QUANTILE * len(scores))]


def min_air(people: list, cutoff: int) -> float:
    rates = {}
    for g in sorted({a["group"] for a in people}):
        rows = [a for a in people if a["group"] == g]
        rates[g] = sum(1 for a in rows if a["score"] >= cutoff) / len(rows)
    top = max(rates.values())
    return min(r / top for r in rates.values())


def main() -> None:
    cases, truth = [], []
    index = 0
    for mech, count in PLAN:
        for k in range(count):
            index += 1
            cid = "C%02d" % index
            p = params_for(mech, k)
            redraws = 0
            people, cutoff = build(SEED + index * 1000, p)
            if mech == "small_group_noise":
                while min_air(people, cutoff) >= 0.80 and redraws < 400:
                    redraws += 1
                    people, cutoff = build(SEED + index * 1000 + redraws, p)
            for i, a in enumerate(people, start=1):
                cases.append([cid, "AP-%04d" % i, a["group"], a["score"], a["bad_outcome"], a["postcode_points"],
                              a["region_points"]] + a["reasons"])
            truth.append([cid, mech, 1 if mech in PLANTED else 0, 1 if mech == "proxy_predictive" else 0,
                          p["shift"], p["postcode_w"], p["region_w"], p["sizes"]["Group C"], len(people), cutoff, redraws])

    head = ["applicant_id", "group", "score", "bad_outcome", "postcode_points", "region_points",
            "reason_1", "reason_2", "reason_3"]
    with open(OUT / "case_scores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_id"] + head)
        w.writerows(cases)
    with open(OUT / "case_truth.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["case_id", "mechanism", "proxy_planted", "proxy_predictive", "legit_shift_scale", "postcode_max_points",
                    "region_max_points", "smallest_group_size", "applicants", "cutoff", "redraws"])
        w.writerows(truth)

    example = next(t for t in truth if t[1] == "proxy_gap" and t[5] == 45)
    with open(OUT / "example_scores.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(head)
        w.writerows(r[1:] for r in cases if r[0] == example[0])
    with open(OUT / "example_params.json", "w", encoding="utf-8") as fh:
        json.dump({"case_id": example[0], "cutoff": example[9], "proxy_column": "postcode_points", "proxy_code": POSTCODE_CODE},
                  fh, indent=1, sort_keys=True)
        fh.write("\n")

    print("Wrote %d scored rows in %d portfolios -> case_scores.csv, case_truth.csv" % (len(cases), len(truth)))
    for mech, count in PLAN:
        print("  %-18s %2d portfolios" % (mech, count))
    print("Example portfolio %s (%s) -> example_scores.csv, example_params.json" % (example[0], example[1]))


if __name__ == "__main__":
    main()
