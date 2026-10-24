"""Generate the synthetic data for project 33: 1,000 card-dispute cases that an agent triaged in shadow
mode, and the outcome a person recorded for most of them.

Everything is seeded, so a rerun reproduces every file byte for byte. The truth of each case (what
should have happened) is drawn first. The agent's proposal and the person's outcome are then drawn
from it by two separate processes, each with its own error rates. The scorecard in src/ never sees
the truth file; the step scripts use it only to say whether a flag was right.

Planted on purpose (see planted_problems.csv):
  real problems     one weak segment, two weeks after a "model change", one outcome class the agent
                    abstains on, one reviewer who disagrees with the agent far more than the rest
  hard negatives    a segment with 8 cases, a holiday week with 10, and a reviewer with 6 cases, each
                    with 3 or 4 planted disagreements that a flag with no minimum group size would
                    raise and a minimum of 30 proposals should not
  hard cases        16 cases where the agent and the person agree and both are wrong against the
                    truth. Two files cannot show these.

Run (from data/):  python3 _generate.py
Writes:  proposals.csv, outcomes.csv, case_truth.csv, planted_problems.csv
"""
from __future__ import annotations

import csv
import random

SEED = 33
rng = random.Random(SEED)

CLASSES = ["REFUND", "DENY", "REQUEST_DOCS", "ESCALATE_FRAUD"]
# (segment, weight, mix over CLASSES, agent error rate)
SEGMENTS = [
    ("card_present", 0.32, (0.66, 0.22, 0.08, 0.04), 0.01),
    ("online", 0.30, (0.55, 0.22, 0.09, 0.14), 0.015),
    ("recurring", 0.20, (0.60, 0.25, 0.10, 0.05), 0.015),
    ("business", 0.11, (0.62, 0.18, 0.17, 0.03), 0.02),
    ("joint_account", 0.07, (0.58, 0.20, 0.18, 0.04), 0.18),
]
TINY_SEGMENT = ("intl_atm", (0.62, 0.22, 0.10, 0.06))
N_MAIN, N_TINY = 992, 8
HOLIDAY_WEEK = 6
WEEK_WEIGHTS = [0.15 if w == HOLIDAY_WEEK else 1 for w in range(14)]
DRIFT_WEEKS = (12, 13)
DRIFT_EXTRA_ERROR = 0.20
ABSTAIN = {"REFUND": 0.02, "DENY": 0.05, "REQUEST_DOCS": 0.08, "ESCALATE_FRAUD": 0.35}
VALUE_ERROR = 0.02
REVIEWERS = [("W01", 1), ("W02", 1), ("W03", 1), ("W04", 1), ("W05", 1), ("W06", 1), ("W07", 0.5), ("W08", 1)]
HUMAN_ERROR = {"W07": 0.20}
HUMAN_ERROR_DEFAULT = 0.005
N_SHARED_WRONG, N_PENDING = 16, 14
AGENT_WRONG = {"REFUND": [("DENY", 0.5), ("REQUEST_DOCS", 0.5)], "DENY": [("REFUND", 0.65), ("REQUEST_DOCS", 0.35)],
               "REQUEST_DOCS": [("REFUND", 0.5), ("DENY", 0.5)], "ESCALATE_FRAUD": [("REFUND", 0.4), ("DENY", 0.6)]}
HUMAN_WRONG = {"REFUND": [("REQUEST_DOCS", 0.5), ("DENY", 0.5)], "DENY": [("REFUND", 0.4), ("REQUEST_DOCS", 0.6)],
               "REQUEST_DOCS": [("REFUND", 0.5), ("DENY", 0.5)], "ESCALATE_FRAUD": [("DENY", 0.6), ("REQUEST_DOCS", 0.4)]}


def pick(pairs, u):
    x = u * sum(w for _, w in pairs)
    for name, w in pairs:
        x -= w
        if x < 0:
            return name
    return pairs[-1][0]


def skeleton():
    weights = [(s, w) for s, w, _, _ in SEGMENTS]
    cases = []
    for i in range(N_MAIN + N_TINY):
        seg = pick(weights, rng.random()) if i < N_MAIN else TINY_SEGMENT[0]
        week = pick(list(enumerate(WEEK_WEIGHTS)), rng.random())
        cases.append({"segment": seg, "week": week, "day": week * 7 + int(rng.random() * 7), "r": rng.random()})
    cases.sort(key=lambda c: (c["day"], c["r"]))
    for n, c in enumerate(cases, 1):
        c["case_id"] = "D-%04d" % n
    return cases


def draw(cases):
    mix = {s: m for s, _, m, _ in SEGMENTS}
    mix[TINY_SEGMENT[0]] = TINY_SEGMENT[1]
    err = {s: e for s, _, _, e in SEGMENTS}
    for c in cases:
        u = [rng.random() for _ in range(9)]
        c["truth"] = pick(list(zip(CLASSES, mix[c["segment"]])), u[0])
        c["amount"] = round(15 + 485 * u[1] * u[1], 2)
        c["reviewer"] = pick(REVIEWERS, u[2])
        c["abstain"] = u[3] < ABSTAIN[c["truth"]]
        rate = err.get(c["segment"], 0.0) + (DRIFT_EXTRA_ERROR if c["week"] in DRIFT_WEEKS else 0.0)
        c["agent_wrong"] = u[4] < rate
        c["agent_pick"] = pick(AGENT_WRONG[c["truth"]], u[5])
        c["conf_u"] = u[6]
        c["value_error"] = u[7] < VALUE_ERROR
        c["human_dev"] = u[8] < HUMAN_ERROR.get(c["reviewer"], HUMAN_ERROR_DEFAULT)
        c["human_pick"] = pick(HUMAN_WRONG[c["truth"]], rng.random())
        c["mode"], c["planted"] = "auto", ""


def plant(cases):
    """Force the hard negatives and the shared-wrong cases. Each case gets one planted role at most."""
    def free(c):
        return c["planted"] == ""

    for c in [c for c in cases if c["segment"] == TINY_SEGMENT[0]][:3]:
        c["mode"], c["planted"] = "agent_wrong", "tiny_segment_miss"
    for c in [c for c in cases if c["week"] == HOLIDAY_WEEK and free(c)][:4]:
        c["mode"], c["planted"] = "agent_wrong", "thin_week_miss"
    shared = [c for c in cases if free(c) and c["segment"] in ("card_present", "online", "recurring")
              and c["week"] not in DRIFT_WEEKS and c["week"] != HOLIDAY_WEEK]
    for c in sorted(shared, key=lambda c: c["r"])[:N_SHARED_WRONG]:
        c["mode"], c["planted"] = "shared_wrong", "shared_wrong"
    tiny_reviewer = [c for c in cases if free(c) and c["segment"] == "card_present" and c["week"] != HOLIDAY_WEEK]
    for k, c in enumerate(sorted(tiny_reviewer, key=lambda c: -c["r"])[:6]):
        c["reviewer"] = "W09"
        c["mode"], c["planted"] = ("human_dev", "tiny_reviewer_miss") if k < 3 else ("agent_right", "")
    pending = [c for c in reversed(cases) if free(c) and c["mode"] == "auto"][:N_PENDING]
    for c in pending:
        c["pending"] = True


def proposal(c):
    """(outcome, value, confidence) the agent wrote; blank outcome means it abstained."""
    if c["mode"] == "shared_wrong":
        wrong = c["agent_pick"]
        return wrong, ("%.2f" % c["amount"] if wrong == "REFUND" else ""), "%.2f" % (0.93 + 0.06 * c["conf_u"])
    forced_right = c["mode"] in ("agent_right", "human_dev")
    if c["abstain"] and c["mode"] == "auto":
        return "", "", ""
    wrong = c["mode"] == "agent_wrong" or (c["mode"] == "auto" and c["agent_wrong"])
    out = c["agent_pick"] if wrong and not forced_right else c["truth"]
    conf = 0.55 + 0.44 * c["conf_u"] if wrong and not forced_right else 0.72 + 0.27 * c["conf_u"] ** 0.5
    value = ""
    if out == "REFUND":
        value = "%.2f" % (c["amount"] + (1.5 if c["value_error"] and c["mode"] == "auto" else 0))
    return out, value, "%.2f" % conf


def human(c):
    if c["mode"] == "shared_wrong":
        out = c["agent_pick"]
    elif c["mode"] == "human_dev" or (c["mode"] == "auto" and c["human_dev"]):
        out = c["human_pick"]
    else:
        out = c["truth"]
    return out, ("%.2f" % c["amount"] if out == "REFUND" else "")


def main():
    cases = skeleton()
    draw(cases)
    plant(cases)
    with open("proposals.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "segment", "day", "proposed_outcome", "proposed_value", "confidence"])
        for c in cases:
            w.writerow([c["case_id"], c["segment"], c["day"], *proposal(c)])
    rows = [[c["case_id"], *human(c), c["reviewer"]] for c in cases if not c.get("pending")]
    rows += [["M-001", "REFUND", "48.20", "W03"], ["M-002", "REFUND", "212.00", "W05"], ["M-003", "DENY", "", "W02"]]
    rows.sort(key=lambda r: outcome_order(r[0]))
    with open("outcomes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "human_outcome", "human_value", "handled_by"])
        w.writerows(rows)
    with open("case_truth.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "true_outcome", "planted"])
        for c in cases:
            w.writerow([c["case_id"], c["truth"], c["planted"]])
    with open("planted_problems.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["problem_id", "kind", "group_type", "group", "real", "note"])
        w.writerows([
            ["P1", "weak_segment", "segment", "joint_account", 1, "agent error rate 0.18 against 0.01 to 0.02 in the other segments"],
            ["P2", "drift", "week", "12", 1, "0.20 added to the agent error rate"],
            ["P3", "drift", "week", "13", 1, "0.20 added to the agent error rate"],
            ["P4", "abstains_on_hard_class", "class", "ESCALATE_FRAUD", 1, "the agent abstains on 35% of these cases"],
            ["P5", "strict_reviewer", "reviewer", "W07", 1, "the person deviates from the truth on 20% of cases against 0.5% for the others"],
            ["N1", "tiny_segment", "segment", "intl_atm", 0, "8 cases, 3 planted agent misses: too few to judge"],
            ["N2", "thin_week", "week", str(HOLIDAY_WEEK), 0, "holiday week with few cases, 4 planted agent misses"],
            ["N3", "tiny_reviewer", "reviewer", "W09", 0, "6 cases, 3 planted deviations by the person"],
        ])
    print("wrote %d proposals and %d outcome rows" % (len(cases), len(rows)))


def outcome_order(case_id):
    """A fixed pseudo-random order for the outcome file that does not depend on Python's hash seed."""
    n = 0
    for ch in case_id:
        n = (n * 131 + ord(ch)) % 1000003
    return (n * 7919) % 1000003, case_id


if __name__ == "__main__":
    main()
