"""Generates the PortfolioBoard synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes ten CSVs next to this file)

What it builds (a modeled bank that runs 30 AI programs)
  programs.csv         30 programs: stage, owner, the owner's red-amber-green report, the owner's
                       benefit estimate and confidence, target quarter.
  gate_criteria.csv    17 criteria across 5 stage gates, each with a freshness rule (max age).
  program_evidence.csv Program x criterion: met yes/no and the age of the evidence in days, for
                       every criterion in force at the program's stage (self-attested).
  capacity.csv         Supply in FTE: 4 teams x 4 quarters.
  demand.csv           Owner-planned need in FTE: program x team x quarter.
  dependencies.csv     Which program depends on which (platform, data feed, approval).
  stage_history.csv    Every stage visit: entered, review requested, exited (blank = still there).
  wip_limits.csv       Work-in-progress limit per stage (a policy assumption of the modeled bank).
  policy.csv           The fixed AS_OF week and calendar convention.
  program_truth.csv    What each program's status truly is. Used only to score; no decision reads it.

The truth is known because the data is synthetic: the generator decides which programs have unmet
or stale evidence, which are slipped, and which attestations are false. Nothing here is a real
bank, program, team, vendor or incident, and no model is used anywhere.

Design choices, fixed before the data was inspected
  * Weeks are counted from the first week of 2023Q1 in 13-week quarters. AS_OF_WEEK = 200 is week 5
    of 2026Q4. No clock is read anywhere.
  * Evidence health quota across the 30 programs: 12 GREEN, 8 AMBER, 10 RED (before dependencies).
    The six shared foundations (platforms, data feeds, an approval service) are fixed by hand: two
    RED and two slipped, because shared services are where dependency risk concentrates. The other
    24 programs are shuffled into the remaining quota.
  * Owners report optimistically: GREEN evidence is reported green 85% of the time, AMBER 65%,
    RED 55%. Reporting red is rare (0%, 5%, 15%).
  * Supply is sized to the plan the budget can see: data science, engineering and security review
    are sized close to average demand; model risk review is sized for last year's portfolio.
  * Stage durations are drawn per stage, and each program's history is built backwards from its
    current stage. Mean work and review-wait weeks per stage are set so that the stage counts
    (5, 6, 8, 6, 5) are consistent with Little's law for a flow of about one new program every five
    weeks. There is no simulated arrival process. The review gates after build and pilot wait
    longest because model risk and security review sit there.
  * Exactly three programs get one false attestation: the owner attested "met", the criterion is
    not truly met, and the evidence is fresh, so nothing in the file reveals it. This is the miss
    left in on purpose.

Two changes were made after the first run; both are described in data/README.md.
  1. The first run showed that no program reached a bad upstream program only through a chain, so
     the transitive path of the propagation rule was never exercised. I added one fixed edge: P-17
     (model inventory registration) depends on P-05 (evaluation harness).
  2. A coherence check found evidence older than the program itself (29 of 268 "met" attestations,
     in 13 programs) and scale-stage target quarters earlier than the quarter the program entered
     scale. I capped every evidence age at the program's life, restricted amber (stale) health to
     programs old enough to have stale evidence, and set the target quarter of a scale-stage program
     to the quarter it entered scale. That moved the health shuffle and therefore the owners'
     colors and the evidence rows. No supply, demand, probability, quota or limit was touched, and
     the seed is the first and only one tried.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

SEED = 20261018
OUT = Path(__file__).parent

AS_OF_WEEK = 200            # week 5 of 2026Q4 in the modeled calendar
CAL_START_YEAR = 2023       # week 1 = first week of 2023Q1; 13-week quarters
STAGES = ["idea", "discovery", "build", "pilot", "scale"]
TEAMS = ["data_science", "engineering", "model_risk_review", "security_review"]


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def quarter_index_of_week(w: int) -> int:
    return (w - 1) // 13


def quarter_label(idx: int) -> str:
    return f"{CAL_START_YEAR + idx // 4}Q{idx % 4 + 1}"


Q_NOW = quarter_index_of_week(AS_OF_WEEK)           # 15 -> 2026Q4
PLAN_QUARTERS = [quarter_label(Q_NOW + i) for i in range(4)]


# ---------------------------------------------------------------------------
# The 30 programs (names are invented use-case labels; owners are invented unit codes)
# ---------------------------------------------------------------------------
PROGRAMS = [
    ("P-01", "Complaint triage assistant", "pilot", "CX-01"),
    ("P-02", "Enterprise model gateway", "scale", "TC-01"),
    ("P-03", "Dispute case summarizer", "build", "OP-01"),
    ("P-04", "KYC document extraction", "scale", "OP-02"),
    ("P-05", "Evaluation harness service", "pilot", "DS-01"),
    ("P-06", "Call center agent assist", "pilot", "CX-02"),
    ("P-07", "Credit memo drafting", "build", "CB-01"),
    ("P-08", "Fraud alert narrative writer", "discovery", "RK-02"),
    ("P-09", "Customer master data feed", "scale", "TC-02"),
    ("P-10", "Policy question answering", "build", "OP-03"),
    ("P-11", "Collections outreach drafting", "discovery", "RB-01"),
    ("P-12", "Treasury cash forecast explainer", "idea", "FN-01"),
    ("P-13", "Document corpus ingestion", "build", "TC-03"),
    ("P-14", "Regulatory change digest", "scale", "RK-03"),
    ("P-15", "Onboarding checklist copilot", "build", "RB-02"),
    ("P-16", "Underwriting document check", "pilot", "CB-02"),
    ("P-17", "Model inventory registration", "pilot", "RK-04"),
    ("P-18", "Meeting note summarizer", "scale", "OP-04"),
    ("P-19", "Branch FAQ assistant", "discovery", "RB-03"),
    ("P-20", "Complaint root-cause clustering", "idea", "CX-01"),
    ("P-21", "Payments exception resolver", "build", "OP-02"),
    ("P-22", "Prompt and tool registry", "build", "TC-01"),
    ("P-23", "Trade surveillance alert triage", "discovery", "RK-02"),
    ("P-24", "Vendor contract clause finder", "build", "FN-02"),
    ("P-25", "Wealth client briefing pack", "discovery", "WM-01"),
    ("P-26", "Code review assistant", "discovery", "TC-04"),
    ("P-27", "AML narrative quality checker", "pilot", "RK-03"),
    ("P-28", "Loan servicing email responder", "idea", "RB-04"),
    ("P-29", "HR policy assistant", "idea", "HR-01"),
    ("P-30", "Audit evidence collector", "idea", "AU-01"),
]
STAGE_OF = {p[0]: p[2] for p in PROGRAMS}

# Shared foundations other programs depend on: id -> dependency type
FOUNDATION = {"P-02": "platform", "P-05": "platform", "P-09": "data_feed",
              "P-13": "data_feed", "P-17": "approval", "P-22": "platform"}
FOUNDATION_WEIGHT = {"P-02": 0.30, "P-05": 0.12, "P-09": 0.18, "P-13": 0.12, "P-17": 0.18, "P-22": 0.10}
FIXED_HEALTH = {"P-02": "GREEN", "P-05": "RED", "P-09": "AMBER", "P-13": "GREEN", "P-17": "GREEN", "P-22": "RED"}
FIXED_SLIPPED = ["P-13", "P-22"]
N_RANDOM_SLIPPED = 3
HEALTH_QUOTA_OTHERS = {"GREEN": 9, "AMBER": 7, "RED": 8}
FOUNDATION_EDGES = [("P-05", "P-02", "platform"), ("P-13", "P-09", "data_feed"), ("P-22", "P-02", "platform"),
                    ("P-17", "P-05", "platform")]
CHAIN_EDGES = [("P-06", "P-01", "data_feed"), ("P-20", "P-01", "data_feed")]
EDGE_PROB = {"idea": 0.40, "discovery": 0.60, "build": 0.85, "pilot": 0.90, "scale": 0.50}
SECOND_EDGE_PROB = 0.30

REPORT_PROB = {            # evidence health -> (P green, P amber, P red) as reported by the owner
    "GREEN": (0.85, 0.15, 0.00),
    "AMBER": (0.65, 0.30, 0.05),
    "RED": (0.55, 0.30, 0.15),
}

BENEFIT_RANGE = {          # owner estimate of annual benefit in USD, by stage
    "idea": (300_000, 2_000_000), "discovery": (500_000, 3_000_000), "build": (1_000_000, 4_000_000),
    "pilot": (1_500_000, 5_000_000), "scale": (2_000_000, 6_000_000)}
FOUNDATION_BENEFIT = (800_000, 2_500_000)
CONFIDENCE_VALUES = [0.3, 0.5, 0.7, 0.9]
CONFIDENCE_WEIGHTS = {
    "idea": [0.5, 0.4, 0.1, 0.0], "discovery": [0.3, 0.5, 0.2, 0.0], "build": [0.0, 0.4, 0.4, 0.2],
    "pilot": [0.0, 0.2, 0.5, 0.3], "scale": [0.0, 0.0, 0.4, 0.6]}
TARGET_OFFSET = {          # quarters from now to the committed target (scale or go-live)
    "idea": (5, 7), "discovery": (3, 5), "build": (2, 4), "pilot": (1, 3), "scale": (-3, 0)}

# Gate criteria: (id, gate, gate name, criterion, attested by, max age in days)
CRITERIA = [
    ("K01", 1, "Intake", "Owner named", "owner", 365),
    ("K02", 1, "Intake", "Risk tier assigned", "model_risk_review", 365),
    ("K03", 1, "Intake", "Use case registered in intake", "owner", 365),
    ("K04", 2, "Discovery entry", "Sponsor named", "owner", 365),
    ("K05", 2, "Discovery entry", "Data source approved", "data_governance", 180),
    ("K06", 2, "Discovery entry", "Benefit estimate logged", "owner", 180),
    ("K07", 3, "Build entry", "Evaluation plan attached", "data_science", 180),
    ("K08", 3, "Build entry", "Security design review complete", "security_review", 180),
    ("K09", 3, "Build entry", "Model risk scoping review complete", "model_risk_review", 180),
    ("K10", 4, "Pilot entry", "Eval evidence attached", "data_science", 90),
    ("K11", 4, "Pilot entry", "Risk review complete", "model_risk_review", 120),
    ("K12", 4, "Pilot entry", "Security review complete", "security_review", 120),
    ("K13", 4, "Pilot entry", "Rollback plan documented", "engineering", 180),
    ("K14", 5, "Scale entry", "Pilot results reviewed", "owner", 90),
    ("K15", 5, "Scale entry", "Control evidence complete", "model_risk_review", 90),
    ("K16", 5, "Scale entry", "Rollback plan tested", "engineering", 90),
    ("K17", 5, "Scale entry", "Monitoring in place", "engineering", 60),
]
MAX_AGE = {c[0]: c[5] for c in CRITERIA}
GATE_OF = {c[0]: c[1] for c in CRITERIA}

WIP_LIMITS = {"idea": 8, "discovery": 6, "build": 6, "pilot": 5, "scale": 10}

# Capacity supply (FTE per quarter), sized as described in the module docstring
SUPPLY = {
    "data_science": [27.0, 27.0, 27.0, 27.0],
    "engineering": [38.0, 41.0, 44.0, 46.0],
    "model_risk_review": [7.0, 7.0, 7.5, 8.0],
    "security_review": [9.0, 10.0, 10.5, 11.0],
}
# Planned need per program per quarter at each stage (FTE), before size and noise
BASE_NEED = {
    "idea": {"data_science": 0.3, "engineering": 0.1, "model_risk_review": 0.0, "security_review": 0.0},
    "discovery": {"data_science": 0.8, "engineering": 0.4, "model_risk_review": 0.10, "security_review": 0.10},
    "build": {"data_science": 1.4, "engineering": 2.0, "model_risk_review": 0.25, "security_review": 0.30},
    "pilot": {"data_science": 1.0, "engineering": 1.6, "model_risk_review": 0.45, "security_review": 0.45},
    "scale": {"data_science": 0.5, "engineering": 1.4, "model_risk_review": 0.20, "security_review": 0.25},
}
# Extra reviewer need in the quarter a program passes its exit gate (current stage -> extra FTE)
GATE_SPIKE = {
    "idea": {"model_risk_review": 0.0, "security_review": 0.0},
    "discovery": {"model_risk_review": 0.20, "security_review": 0.10},
    "build": {"model_risk_review": 0.50, "security_review": 0.30},
    "pilot": {"model_risk_review": 0.40, "security_review": 0.30},
}
ADVANCE_PROB = {"idea": 0.60, "discovery": 0.50, "build": 0.40, "pilot": 0.45, "scale": 0.0}
SIZE_VALUES = [0.7, 1.0, 1.3]
SIZE_WEIGHTS = [0.30, 0.45, 0.25]

# Stage history: mean weeks of work before a program asks for the exit gate, and mean weeks it
# then waits at that gate. Scale has no exit gate.
WORK_MEAN = {"idea": 22, "discovery": 25, "build": 24, "pilot": 17}
WAIT_MEAN = {"idea": 2.5, "discovery": 4.0, "build": 15.0, "pilot": 12.0}
SCALE_AGE_MAX = 25         # weeks; the first program reached scale about half a year before AS_OF
N_FALSE_ATTESTATIONS = 3


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def stale_feasible(stage: str, life_days: int) -> list:
    """Criteria in force at a stage whose evidence could be stale given how old the program is."""
    return [c for c in criteria_in_force(stage) if int(1.15 * MAX_AGE[c]) <= life_days]


def build_health(rng: random.Random, life_days: dict) -> dict:
    """Shuffle the remaining quota onto the 24 non-foundation programs. A program can only be AMBER
    (stale evidence) if it is old enough for some criterion to be stale; reshuffle until that holds."""
    others = sorted(p[0] for p in PROGRAMS if p[0] not in FIXED_HEALTH)
    labels = ["GREEN"] * HEALTH_QUOTA_OTHERS["GREEN"] + ["AMBER"] * HEALTH_QUOTA_OTHERS["AMBER"] \
        + ["RED"] * HEALTH_QUOTA_OTHERS["RED"]
    assert len(labels) == len(others)
    for _attempt in range(100000):
        rng.shuffle(labels)
        ok = all(lab != "AMBER" or stale_feasible(STAGE_OF[pid], life_days[pid])
                 for pid, lab in zip(others, labels))
        if ok:
            break
    else:
        raise AssertionError("no feasible health assignment")
    health = dict(FIXED_HEALTH)
    health.update(dict(zip(others, labels)))
    return health


def build_dependencies(rng: random.Random) -> list:
    edges = {}
    for a, b, t in FOUNDATION_EDGES + CHAIN_EDGES:
        edges[(a, b)] = t
    ids = sorted(FOUNDATION)
    for pid, _name, stage, _owner in PROGRAMS:
        if pid in FOUNDATION:
            continue
        if rng.random() >= EDGE_PROB[stage]:
            continue
        w = [FOUNDATION_WEIGHT[f] for f in ids]
        first = rng.choices(ids, w)[0]
        edges[(pid, first)] = FOUNDATION[first]
        if rng.random() < SECOND_EDGE_PROB:
            rest = [f for f in ids if f != first]
            w2 = [FOUNDATION_WEIGHT[f] for f in rest]
            second = rng.choices(rest, w2)[0]
            edges[(pid, second)] = FOUNDATION[second]
    return sorted((a, b, t) for (a, b), t in edges.items())


def build_programs(health: dict, slipped: set, scale_quarter: dict) -> list:
    rng_rag = random.Random(SEED + 12)
    rng_ben = random.Random(SEED + 13)
    rng_tgt = random.Random(SEED + 14)
    rows = []
    for pid, name, stage, owner in PROGRAMS:
        pg, pa, pr = REPORT_PROB[health[pid]]
        rag = rng_rag.choices(["green", "amber", "red"], [pg, pa, pr])[0]
        lo, hi = FOUNDATION_BENEFIT if pid in FOUNDATION else BENEFIT_RANGE[stage]
        benefit = int(round(rng_ben.uniform(lo, hi) / 50_000.0)) * 50_000
        conf = rng_ben.choices(CONFIDENCE_VALUES, CONFIDENCE_WEIGHTS[stage])[0]
        a, b = TARGET_OFFSET[stage]
        tq = Q_NOW + rng_tgt.randint(a, b)
        if pid in slipped:
            tq = Q_NOW - rng_tgt.randint(1, 2)
        if stage == "scale":                     # went live in the quarter it entered scale
            tq = scale_quarter[pid]
        rows.append({"program_id": pid, "name": name, "stage": stage, "owner": owner,
                     "self_reported_rag": rag, "est_benefit_usd": benefit,
                     "benefit_confidence": f"{conf:.1f}", "target_quarter": quarter_label(tq)})
    return rows


def criteria_in_force(stage: str) -> list:
    gate_max = STAGES.index(stage) + 1
    return [c[0] for c in CRITERIA if c[1] <= gate_max]


def build_evidence(health: dict, no_plant: set, life_days: dict) -> tuple:
    rng = random.Random(SEED + 16)
    rows, truly = [], {}
    for pid, _n, stage, _o in PROGRAMS:
        cids = criteria_in_force(stage)
        latest = STAGES.index(stage) + 1
        unmet, stale = set(), set()
        h = health[pid]
        life = life_days[pid]
        feasible = stale_feasible(stage, life)
        if h == "RED":
            k = min(rng.choice([1, 1, 2, 3]), len(cids))
            pool = list(cids)
            for _ in range(k):
                w = [3 if GATE_OF[c] == latest else (2 if GATE_OF[c] == latest - 1 else 1) for c in pool]
                pick = rng.choices(pool, w)[0]
                unmet.add(pick)
                pool.remove(pick)
            rest = [c for c in feasible if c not in unmet]
            if rest and rng.random() < 0.30:
                stale.add(rng.choice(rest))
        elif h == "AMBER":
            k = min(rng.choice([1, 1, 2, 3]), len(feasible))
            stale = set(rng.sample(feasible, k))
        for cid in cids:
            if cid in unmet:
                rows.append({"program_id": pid, "criterion_id": cid, "met": "no", "evidence_age_days": ""})
                truly[(pid, cid)] = "no"
                continue
            m = MAX_AGE[cid]
            if cid in stale:
                age = rng.randint(int(1.15 * m), min(int(2.0 * m), life))
            else:
                age = rng.randint(5, min(int(0.8 * m), life))
            rows.append({"program_id": pid, "criterion_id": cid, "met": "yes", "evidence_age_days": age})
            truly[(pid, cid)] = "yes"
    # Plant the false attestations: attested met, fresh, not truly met
    rng_plant = random.Random(SEED + 19)
    cand = [p[0] for p in PROGRAMS
            if p[0] not in FOUNDATION and p[0] not in no_plant and p[2] in ("build", "pilot", "scale")
            and health[p[0]] in ("GREEN", "AMBER")]
    assert len(cand) >= N_FALSE_ATTESTATIONS, "not enough candidates for the planted misses"
    planted = {}
    for pid in sorted(rng_plant.sample(cand, N_FALSE_ATTESTATIONS)):
        latest = STAGES.index(STAGE_OF[pid]) + 1
        pool = [r["criterion_id"] for r in rows
                if r["program_id"] == pid and r["met"] == "yes"
                and GATE_OF[r["criterion_id"]] >= latest - 1
                and int(r["evidence_age_days"]) <= MAX_AGE[r["criterion_id"]]]
        cid = rng_plant.choice(pool)
        truly[(pid, cid)] = "no"
        planted[pid] = cid
    return rows, truly, planted


def build_demand(rng: random.Random) -> list:
    rows = []
    for pid, _n, stage, _o in PROGRAMS:
        size = rng.choices(SIZE_VALUES, SIZE_WEIGHTS)[0]
        s = STAGES.index(stage)
        path = [s]
        for _q in range(1, 4):
            if rng.random() < ADVANCE_PROB[STAGES[s]]:
                s += 1
            path.append(s)
        for qi in range(4):
            st = STAGES[path[qi]]
            passes_gate = qi < 3 and path[qi + 1] > path[qi]
            for team in TEAMS:
                need = BASE_NEED[st][team]
                if passes_gate:
                    need += GATE_SPIKE.get(st, {}).get(team, 0.0)
                need = need * size * rng.uniform(0.85, 1.15)
                if need >= 0.05:
                    rows.append({"program_id": pid, "team": team, "quarter": PLAN_QUARTERS[qi],
                                 "need_fte": f"{need:.2f}"})
    return rows


def build_history(rng: random.Random) -> list:
    rows = []
    for pid, _n, stage, _o in PROGRAMS:
        k = STAGES.index(stage)
        # current visit
        if stage == "scale":
            age = rng.randint(1, SCALE_AGE_MAX)
            entered, requested = AS_OF_WEEK - age, ""
        else:
            work = max(1, int(round(WORK_MEAN[stage] * rng.uniform(0.6, 1.4))))
            wait = max(1, int(round(WAIT_MEAN[stage] * rng.uniform(0.4, 1.6))))
            age = rng.randint(1, work + wait)
            entered = AS_OF_WEEK - age
            requested = (AS_OF_WEEK - (age - work)) if age > work else ""
        rows.append({"program_id": pid, "stage": stage, "entered_week": entered,
                     "review_requested_week": requested, "exited_week": ""})
        cur_entered = entered
        for j in range(k - 1, -1, -1):
            sj = STAGES[j]
            work = max(1, int(round(WORK_MEAN[sj] * rng.uniform(0.6, 1.4))))
            wait = max(1, int(round(WAIT_MEAN[sj] * rng.uniform(0.4, 1.6))))
            exited = cur_entered
            req = exited - wait
            ent = req - work
            assert ent >= 1, "calendar too short for a stage chain"
            rows.append({"program_id": pid, "stage": sj, "entered_week": ent,
                         "review_requested_week": req, "exited_week": exited})
            cur_entered = ent
    rows.sort(key=lambda r: (r["program_id"], STAGES.index(r["stage"])))
    return rows


def truth_rows(programs: list, evidence: list, truly: dict, deps: list, planted: dict) -> list:
    """What each program's status truly is, from the true criteria states and the rules below.
    RED: a criterion is truly unmet. AMBER: all truly met but some evidence is stale, or the program
    is slipped, or an upstream program (directly or through a chain) is RED or slipped. Else GREEN."""
    age = {(r["program_id"], r["criterion_id"]): r["evidence_age_days"] for r in evidence}
    by_id = {p["program_id"]: p for p in programs}
    ups = {}
    for a, b, _t in deps:
        ups.setdefault(a, []).append(b)

    def ancestors(pid: str) -> set:
        seen, stack = set(), list(ups.get(pid, []))
        while stack:
            u = stack.pop()
            if u not in seen:
                seen.add(u)
                stack.extend(ups.get(u, []))
        return seen

    def slipped(pid: str) -> bool:
        p = by_id[pid]
        return p["stage"] != "scale" and p["target_quarter"] < quarter_label(Q_NOW)

    true_ev = {}
    for p in programs:
        pid = p["program_id"]
        cids = criteria_in_force(p["stage"])
        if any(truly[(pid, c)] == "no" for c in cids):
            true_ev[pid] = "RED"
        elif any(age[(pid, c)] != "" and int(age[(pid, c)]) > MAX_AGE[c] for c in cids):
            true_ev[pid] = "AMBER"
        else:
            true_ev[pid] = "GREEN"
    rows = []
    for p in programs:
        pid = p["program_id"]
        blockers = sorted(u for u in ancestors(pid) if true_ev[u] == "RED" or slipped(u))
        if true_ev[pid] == "RED":
            status = "RED"
        elif true_ev[pid] == "AMBER" or blockers or slipped(pid):
            status = "AMBER"
        else:
            status = "GREEN"
        rows.append({"program_id": pid, "true_evidence_status": true_ev[pid],
                     "true_blocked_by": ";".join(blockers), "true_status": status,
                     "false_attestation": planted.get(pid, "")})
    return rows


def write_csv(path: Path, fields: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    history = build_history(random.Random(SEED + 18))
    first_week, scale_quarter = {}, {}
    for h in history:
        first_week[h["program_id"]] = min(first_week.get(h["program_id"], 10 ** 9), h["entered_week"])
        if h["stage"] == "scale":
            scale_quarter[h["program_id"]] = quarter_index_of_week(h["entered_week"])
    life_days = {pid: (AS_OF_WEEK - w) * 7 for pid, w in first_week.items()}
    health = build_health(random.Random(SEED + 11), life_days)
    slip_rng = random.Random(SEED + 15)
    slip_pool = sorted(p[0] for p in PROGRAMS if p[0] not in FOUNDATION and p[2] in ("discovery", "build", "pilot"))
    slipped = set(FIXED_SLIPPED) | set(slip_rng.sample(slip_pool, N_RANDOM_SLIPPED))
    programs = build_programs(health, slipped, scale_quarter)
    deps = build_dependencies(random.Random(SEED + 20))
    has_dependents = {b for _a, b, _t in deps}
    evidence, truly, planted = build_evidence(health, has_dependents, life_days)
    demand = build_demand(random.Random(SEED + 17))
    truth = truth_rows(programs, evidence, truly, deps, planted)

    write_csv(OUT / "programs.csv", ["program_id", "name", "stage", "owner", "self_reported_rag",
                                     "est_benefit_usd", "benefit_confidence", "target_quarter"], programs)
    write_csv(OUT / "gate_criteria.csv", ["criterion_id", "gate", "gate_name", "criterion", "attested_by",
                                          "max_age_days"],
              [dict(zip(["criterion_id", "gate", "gate_name", "criterion", "attested_by", "max_age_days"], c))
               for c in CRITERIA])
    write_csv(OUT / "program_evidence.csv", ["program_id", "criterion_id", "met", "evidence_age_days"], evidence)
    write_csv(OUT / "capacity.csv", ["team", "quarter", "supply_fte"],
              [{"team": t, "quarter": PLAN_QUARTERS[i], "supply_fte": f"{SUPPLY[t][i]:.1f}"}
               for t in TEAMS for i in range(4)])
    write_csv(OUT / "demand.csv", ["program_id", "team", "quarter", "need_fte"], demand)
    write_csv(OUT / "dependencies.csv", ["program_id", "depends_on", "dep_type"],
              [{"program_id": a, "depends_on": b, "dep_type": t} for a, b, t in deps])
    write_csv(OUT / "stage_history.csv", ["program_id", "stage", "entered_week", "review_requested_week",
                                          "exited_week"], history)
    write_csv(OUT / "wip_limits.csv", ["stage", "wip_limit"],
              [{"stage": s, "wip_limit": WIP_LIMITS[s]} for s in STAGES])
    write_csv(OUT / "policy.csv", ["key", "value", "note"], [
        {"key": "as_of_week", "value": AS_OF_WEEK, "note": "fixed week constant; week 5 of 2026Q4 in the modeled calendar"},
        {"key": "calendar_start_year", "value": CAL_START_YEAR, "note": "week 1 is the first week of 2023Q1"},
        {"key": "weeks_per_quarter", "value": 13, "note": "13-week quarters in the modeled calendar"},
    ])
    write_csv(OUT / "program_truth.csv", ["program_id", "true_evidence_status", "true_blocked_by",
                                          "true_status", "false_attestation"], truth)
    print(f"wrote 10 CSVs to {OUT} (seed {SEED}, as-of week {AS_OF_WEEK}, plan quarters {PLAN_QUARTERS[0]} to {PLAN_QUARTERS[-1]})")


if __name__ == "__main__":
    main()
