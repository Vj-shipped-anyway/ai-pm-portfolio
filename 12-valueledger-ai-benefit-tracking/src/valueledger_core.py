"""Shared plumbing for the ValueLedger step scripts, the Streamlit app and the demo builder.

Standard library only. Nothing in here makes a claim; it loads the synthetic
CSVs, builds team-by-week aggregates, and holds the small statistics helpers
(percentile, least squares, the decay-curve fit).

Two kinds of columns come out of the data folder:
  observed   panel.csv, employees.csv, teams.csv, budget.csv, copilots.csv
             what a measurement team in a bank could see
  answer key truth_person_week.csv, truth_parameters.json
             what the generator injected; known only because the data is synthetic

Methods read the observed files. Only the scoring code reads the answer key.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "data"
OUT_DIR = HERE / "out"

N_WEEKS = 26
LAUNCH_WEEK = 13
PRE_WEEKS = list(range(1, LAUNCH_WEEK))                 # 1..12
POST_WEEKS = list(range(LAUNCH_WEEK, N_WEEKS + 1))      # 13..26
WEEKS_PER_MONTH = 52.0 / 12.0

BOOT_SEED = 7712
BOOT_REPS = 1000

# Design thresholds (choices, not measurements)
GUARDRAIL_REWORK_SHARE = 0.40     # rework above 40% of gross time saved holds the booking
PARALLEL_TREND_TOL = 0.15         # minutes per task per week; pre-period gap slope tolerance
BANK_ELIGIBLE_HEADCOUNT = 5000    # modeled assumption, used only for the utility scale-up


def ensure_out() -> Path:
    OUT_DIR.mkdir(exist_ok=True)
    return OUT_DIR


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _read(name: str) -> list:
    with open(DATA_DIR / name, newline="") as f:
        return list(csv.DictReader(f))


class Data:
    """The synthetic data folder, loaded once."""

    def __init__(self) -> None:
        self.employees = {}
        for r in _read("employees.csv"):
            self.employees[r["employee_id"]] = r
        self.teams = {}
        for r in _read("teams.csv"):
            r["headcount"] = int(r["headcount"])
            r["enthusiasm_score"] = float(r["enthusiasm_score"])
            self.teams[r["team_id"]] = r
        self.budget = {}
        for r in _read("budget.csv"):
            r["headcount"] = int(r["headcount"])
            r["loaded_cost_per_hour_usd"] = float(r["loaded_cost_per_hour_usd"])
            r["addressable_spend_usd_annual"] = float(r["addressable_spend_usd_annual"])
            self.budget[r["cost_center_id"]] = r
        self.copilots = {}
        for r in _read("copilots.csv"):
            r["assumed_minutes_saved_per_use"] = float(r["assumed_minutes_saved_per_use"])
            r["seat_cost_usd_per_month"] = float(r["seat_cost_usd_per_month"])
            self.copilots[r["copilot_id"]] = r
        self.panel = []
        for r in _read("panel.csv"):
            self.panel.append((
                r["employee_id"], int(r["week"]), int(r["tasks_completed"]),
                float(r["minutes_per_task"]), int(r["events_a"]), int(r["events_b"]),
                int(r["events_both"]), float(r["rework_minutes"]),
            ))
        # answer key
        self.truth = []
        for r in _read("truth_person_week.csv"):
            self.truth.append((
                r["employee_id"], int(r["week"]), int(r["true_assisted_tasks"]),
                float(r["true_gross_saved_min"]), float(r["true_rework_min"]),
                float(r["true_net_saved_min"]), float(r["true_hidden_drift_min"]),
            ))
        with open(DATA_DIR / "truth_parameters.json") as f:
            self.params = json.load(f)


_DATA = []


def load_data() -> Data:
    if not _DATA:
        _DATA.append(Data())
    return _DATA[0]


# ---------------------------------------------------------------------------
# Scenarios: a method focus or a cohort slice
# ---------------------------------------------------------------------------
SCENARIOS = [
    {"key": "all", "label": "Whole treated cohort: every method against the answer key",
     "focus": None, "copilots": None, "cash": None, "post": POST_WEEKS},
    {"key": "m_claim", "label": "Method focus: the vendor-style claim (what leadership saw)",
     "focus": "claim", "copilots": None, "cash": None, "post": POST_WEEKS},
    {"key": "m_prepost", "label": "Method focus: pre/post on the treated cohort (the basic approach)",
     "focus": "prepost", "copilots": None, "cash": None, "post": POST_WEEKS},
    {"key": "m_ledger", "label": "Method focus: ValueLedger (difference-in-differences, net, deduplicated)",
     "focus": "ledger", "copilots": None, "cash": None, "post": POST_WEEKS},
    {"key": "two", "label": "Slice: people holding two copilots (overlap)",
     "focus": None, "copilots": ("AB",), "cash": None, "post": POST_WEEKS},
    {"key": "one", "label": "Slice: people holding one copilot",
     "focus": None, "copilots": ("A", "B"), "cash": None, "post": POST_WEEKS},
    {"key": "launch", "label": "Slice: launch month, weeks 13 to 16 (novelty window)",
     "focus": None, "copilots": None, "cash": None, "post": [13, 14, 15, 16]},
    {"key": "steady", "label": "Slice: steady state, weeks 23 to 26",
     "focus": None, "copilots": None, "cash": None, "post": [23, 24, 25, 26]},
    {"key": "cash", "label": "Slice: cost centers where freed time can become cash",
     "focus": None, "copilots": None, "cash": "yes", "post": POST_WEEKS},
    {"key": "capacity", "label": "Slice: cost centers where freed time stays capacity",
     "focus": None, "copilots": None, "cash": "no", "post": POST_WEEKS},
]


def scenario_by_key(key: str) -> dict:
    for s in SCENARIOS:
        if s["key"] == key:
            return s
    raise KeyError(key)


def make_keep(spec: dict, ds: Data):
    """Return a function employee_row -> bool. Holdout people are kept unless the
    slice is a cost-center slice (that slice cuts both arms)."""
    copilots = spec["copilots"]
    cash = spec["cash"]

    def keep(emp: dict) -> bool:
        if cash is not None:
            if ds.budget[emp["cost_center_id"]]["freed_time_can_become_cash"] != cash:
                return False
        if copilots is not None and emp["cohort"] == "treated":
            if emp["copilots"] not in copilots:
                return False
        return True

    return keep


# ---------------------------------------------------------------------------
# Team-by-week aggregates
# ---------------------------------------------------------------------------
OBS_KEYS = ("T", "M", "R", "EA", "EB", "EBOTH")        # tasks, task minutes, rework, events
TRUTH_KEYS = ("G", "AS", "RW", "HID")                  # answer key


class Agg:
    """teams[team_id] = dict with arm, cc and one length-26 list per key."""

    def __init__(self) -> None:
        self.teams = {}
        self.treated = []
        self.holdout = []
        self.n_treated_people = 0
        self.n_holdout_people = 0
        self.seat_cost_per_month = 0.0     # monthly seat cost of the kept treated people
        self.people_by_tools = {}


def build_agg(ds: Data, spec: dict) -> Agg:
    keep = make_keep(spec, ds)
    agg = Agg()
    kept = {}
    for eid, emp in ds.employees.items():
        if keep(emp):
            kept[eid] = emp
            tid = emp["team_id"]
            if tid not in agg.teams:
                agg.teams[tid] = {"arm": "T" if emp["cohort"] == "treated" else "H",
                                  "cc": emp["cost_center_id"]}
                for k in OBS_KEYS + TRUTH_KEYS:
                    agg.teams[tid][k] = [0.0] * N_WEEKS
            if emp["cohort"] == "treated":
                agg.n_treated_people += 1
                tools = emp["copilots"]
                agg.people_by_tools[tools] = agg.people_by_tools.get(tools, 0) + 1
                for cid in tools:
                    agg.seat_cost_per_month += ds.copilots[cid]["seat_cost_usd_per_month"]
            else:
                agg.n_holdout_people += 1
    for (eid, week, tasks, mpt, ea, eb, eboth, rework) in ds.panel:
        if eid not in kept:
            continue
        rec = agg.teams[kept[eid]["team_id"]]
        i = week - 1
        rec["T"][i] += tasks
        rec["M"][i] += tasks * mpt
        rec["R"][i] += rework
        rec["EA"][i] += ea
        rec["EB"][i] += eb
        rec["EBOTH"][i] += eboth
    for (eid, week, assisted, gross, rework, net, hidden) in ds.truth:
        if eid not in kept:
            continue
        rec = agg.teams[kept[eid]["team_id"]]
        i = week - 1
        rec["AS"][i] += assisted
        rec["G"][i] += gross
        rec["RW"][i] += rework
        rec["HID"][i] += hidden
    agg.treated = sorted(t for t, r in agg.teams.items() if r["arm"] == "T")
    agg.holdout = sorted(t for t, r in agg.teams.items() if r["arm"] == "H")
    return agg


def total(agg: Agg, teams: list, key: str, weeks: list) -> float:
    s = 0.0
    idx = [w - 1 for w in weeks]
    for t in teams:
        arr = agg.teams[t][key]
        for i in idx:
            s += arr[i]
    return s


def weekly(agg: Agg, teams: list, key: str) -> list:
    out = [0.0] * N_WEEKS
    for t in teams:
        arr = agg.teams[t][key]
        for i in range(N_WEEKS):
            out[i] += arr[i]
    return out


def blended_rate(ds: Data, agg: Agg, weeks: list) -> float:
    """Loaded cost per hour weighted by the treated cohort's task volume."""
    num = den = 0.0
    for t in agg.treated:
        tasks = total(agg, [t], "T", weeks)
        num += tasks * ds.budget[agg.teams[t]["cc"]]["loaded_cost_per_hour_usd"]
        den += tasks
    return num / den if den else 0.0


# ---------------------------------------------------------------------------
# Small statistics helpers
# ---------------------------------------------------------------------------
def percentile(sorted_vals: list, q: float) -> float:
    if not sorted_vals:
        return float("nan")
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def interval(vals: list, level: float = 0.95) -> tuple:
    s = sorted(vals)
    a = (1.0 - level) / 2.0
    return percentile(s, a), percentile(s, 1.0 - a)


def ols_slope(xs: list, ys: list) -> float:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx


def fit_decay(ts: list, ys: list, ws: list) -> tuple:
    """Fit y = a + b * exp(-k t) by weighted least squares, with a >= 0 and b >= 0.

    k comes from a grid search (0.05 to 1.0 per week); for each k, (a, b) have a
    closed form. The sign limits say a copilot cannot have a negative steady-state
    effect in this fit and novelty cannot subtract. Standard library only.
    """
    sw = sum(ws)
    if sw <= 0:
        return 0.0, 0.0, 0.0
    my = sum(w * y for w, y in zip(ws, ys)) / sw
    best = (sum(w * (y - my) ** 2 for w, y in zip(ws, ys)), my, 0.0, 0.0)
    for step in range(2, 41):
        k = 0.025 * step
        xs = [math.exp(-k * t) for t in ts]
        mx = sum(w * x for w, x in zip(ws, xs)) / sw
        sxx = sum(w * (x - mx) ** 2 for w, x in zip(ws, xs))
        if sxx <= 1e-12:
            continue
        b = sum(w * (x - mx) * (y - my) for w, x, y in zip(ws, xs, ys)) / sxx
        a = my - b * mx
        if b < 0.0:
            b, a = 0.0, my
        elif a < 0.0:
            a = 0.0
            b = sum(w * x * y for w, x, y in zip(ws, xs, ys)) / sum(w * x * x for w, x in zip(ws, xs))
        sse = sum(w * (y - a - b * x) ** 2 for w, x, y in zip(ws, xs, ys))
        if sse < best[0]:
            best = (sse, a, b, k)
    return best[1], best[2], best[3]


def fmt_int(x: float) -> str:
    return "{:,.0f}".format(x)


def fmt_signed(x: float) -> str:
    return "{:+,.0f}".format(x)


def fmt_usd(x: float) -> str:
    sign = "-" if x < 0 else ""
    return "{}${:,.0f}".format(sign, abs(x))


def value_by_cc(ds: Data, hours_by_cc: dict) -> float:
    """Dollar value of hours, each at its own cost center's loaded rate."""
    return sum(h * ds.budget[cc]["loaded_cost_per_hour_usd"] for cc, h in hours_by_cc.items())


def cc_of(agg: Agg, team_id: str) -> str:
    return agg.teams[team_id]["cc"]


def round_sig(x: float, digits: int = 3) -> float:
    """Round to a number of significant digits. Used for modeled scale-up figures,
    which should not look more precise than the assumption behind them."""
    if x == 0:
        return 0.0
    return round(x, digits - 1 - int(math.floor(math.log10(abs(x)))))


def apply_ledger_rule(ds: Data, gross_h: dict, rework_h: dict, n_weeks: int) -> dict:
    """The ledger rule, applied per cost center to gross and rework hours.

    value  = net hours x the line's loaded cost per hour
    hard   = value, up to the addressable spend on the line, and only where the line has
             a cash lever; zero if the quality guardrail holds the line
    soft   = the rest (capacity)
    hold   = rework above GUARDRAIL_REWORK_SHARE of gross time saved, or no net saving
    """
    rows = []
    hard = 0.0
    value = 0.0
    for cc in sorted(gross_h):
        b = ds.budget[cc]
        g = gross_h[cc]
        r = rework_h.get(cc, 0.0)
        net = g - r
        share = r / g if g > 0 else float("inf")
        hold = share > GUARDRAIL_REWORK_SHARE or net <= 0
        v = net * b["loaded_cost_per_hour_usd"]
        flag = b["freed_time_can_become_cash"]
        ceiling = b["addressable_spend_usd_annual"] * n_weeks / 52.0 if flag == "yes" else 0.0
        hard_cc = 0.0 if (hold or flag != "yes") else max(0.0, min(v, ceiling))
        rows.append({
            "cost_center_id": cc, "cash_flag": flag, "gross_hours": g, "rework_hours": r,
            "net_hours": net, "rework_share": share, "hold": hold, "value_usd": v,
            "line_ceiling_usd": ceiling, "hard_usd": hard_cc, "soft_usd": v - hard_cc,
        })
        hard += hard_cc
        value += v
    return {"rows": rows, "hard_usd": hard, "soft_usd": value - hard, "value_usd": value}
