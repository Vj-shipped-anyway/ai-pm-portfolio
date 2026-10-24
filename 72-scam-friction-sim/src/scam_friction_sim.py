"""scam_friction_sim: replay a batch of real-time payments against a hold policy and count
what the hold stops and what it costs the customers who were not being scammed. Standard library
only. Python 3.9 or newer.

Command line (from src/):
    python3 scam_friction_sim.py --demo
    python3 scam_friction_sim.py run --payments PAYMENTS.csv --truth TRUTH.csv [--assumptions A.json]
        [--policy none|blanket|score] [--min-amount N] [--hold-score N] [--warn-score N]
        [--legit-weight W] [--max-held-pct X] [--min-stopped-pct Y]

Exit status: 0 when the run is done and inside any budget given, 1 when a budget is broken (the policy
holds more legitimate payments than --max-held-pct allows, or stops less scam value than
--min-stopped-pct asks for), 2 for bad or malformed input.

How it works. Each payment gets a tier from its features alone: PASS, WARN (an in-app warning, no
wait) or HOLD (wait hold_minutes). The truth file is read only to score the outcome. A held scam
payment is stopped when the customer gives up, which is decided by a fixed draw per payment
(u_abandon) against an assumed probability for that scam scenario, unless a scammer who is in touch
with the victim has coached them through the hold (u_evade against coach_rate). A held legitimate
payment is lost when its draw falls under legit_abandon_on_hold. Every probability is an assumption
in the assumptions file, not a measured rate. Because the draws are stored in the data, a run is
exactly repeatable and two policies see the same customers.

Features: amount, usual_amount (the customer's typical payment), payee_age_days (0 = first payment to
this payee), hour (0 to 23), call_active (1 = the customer is on a phone call), device_new (1 = a
device the bank has not seen).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

PAYMENT_COLUMNS = ["payment_id", "amount", "usual_amount", "payee_age_days", "hour", "call_active", "device_new"]
TRUTH_COLUMNS = ["payment_id", "is_scam", "scenario", "u_abandon", "u_evade"]

# Assumption: the author's weights. They are not fitted to anything.
WEIGHTS = {"new_payee": 3, "young_payee": 1, "amount_x3": 2, "amount_x1_5": 1, "call_active": 2, "device_new": 2,
           "night": 1, "large_amount": 1}
LARGE_AMOUNT = 1000

DEFAULT_ASSUMPTIONS = {
    "hold_minutes": 20,
    "warn_minutes": 0.5,
    "legit_abandon_on_hold": 0.03,
    "legit_abandon_on_warn": 0.005,
    "warn_factor": 0.3,
    "coach_rate": 0.2,
    "scam_scenarios": {
        "coached_live": {"p_abandon": 0.4, "human_scammer": True},
        "romance_invest": {"p_abandon": 0.1, "human_scammer": True},
        "takeover": {"p_abandon": 0.35, "human_scammer": False},
        "known_payee": {"p_abandon": 0.15, "human_scammer": True},
    },
}


# ---------------------------------------------------------------- safe text
def clean(text, limit: int = 60) -> str:
    """Escape untrusted text for one-line messages, the way GitHub documents for workflow commands."""
    s = str(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    s = "".join(ch if ch.isprintable() else "?" for ch in s)
    return s if len(s) <= limit else s[:limit] + "..."


# ---------------------------------------------------------------- loading
def _read_csv(path: str, required: list) -> list:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames is None:
                raise ValueError(f"{clean(path)}: the file is empty")
            missing = [c for c in required if c not in reader.fieldnames]
            if missing:
                raise ValueError(f"{clean(path)}: missing column(s) {', '.join(missing)}")
            rows = list(reader)
    except (OSError, csv.Error, UnicodeDecodeError) as e:
        raise ValueError(f"{clean(path)}: cannot read as CSV ({clean(e)})")
    for i, r in enumerate(rows, 2):
        if None in r:
            raise ValueError(f"{clean(path)} line {i}: more values than columns")
        for c in required:
            if r[c] is None:
                raise ValueError(f"{clean(path)} line {i}: truncated row, no value for {c}")
    return rows


def _number(row: dict, key: str, where: str, lo=None, hi=None, integer: bool = False, hi_open: bool = False) -> float:
    raw = row[key].strip()
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{where}: {key} is not a number ({clean(raw)})")
    if not math.isfinite(v):
        raise ValueError(f"{where}: {key} is not a finite number")
    if integer and v != int(v):
        raise ValueError(f"{where}: {key} must be a whole number ({clean(raw)})")
    if (lo is not None and v < lo) or (hi is not None and (v >= hi if hi_open else v > hi)):
        raise ValueError(f"{where}: {key} is out of range ({clean(raw)})")
    return int(v) if integer else v


def load_payments(payments_path: str, truth_path: str) -> list:
    """Payments joined to their truth rows. Raises ValueError with a one-line message on bad input."""
    pay = _read_csv(payments_path, PAYMENT_COLUMNS)
    tru = _read_csv(truth_path, TRUTH_COLUMNS)
    if not pay:
        raise ValueError(f"{clean(payments_path)}: no payments in the file")
    truth = {}
    for r in tru:
        if r["payment_id"] in truth:
            raise ValueError(f"{clean(truth_path)}: duplicate payment_id {clean(r['payment_id'])}")
        truth[r["payment_id"]] = r
    out, seen = [], set()
    for r in pay:
        pid = r["payment_id"]
        where = f"payment {clean(pid)}"
        if pid == "" or pid in seen:
            raise ValueError(f"{clean(payments_path)}: empty or duplicate payment_id {clean(pid)}")
        seen.add(pid)
        if pid not in truth:
            raise ValueError(f"{where}: no row in the truth file")
        t = truth[pid]
        out.append({
            "payment_id": pid,
            "amount": _number(r, "amount", where, lo=0.01, hi=1e12),
            "usual_amount": _number(r, "usual_amount", where, lo=0.01, hi=1e12),
            "payee_age_days": _number(r, "payee_age_days", where, lo=0, integer=True),
            "hour": _number(r, "hour", where, lo=0, hi=23, integer=True),
            "call_active": _number(r, "call_active", where, lo=0, hi=1, integer=True),
            "device_new": _number(r, "device_new", where, lo=0, hi=1, integer=True),
            "is_scam": _number(t, "is_scam", where, lo=0, hi=1, integer=True),
            "scenario": t["scenario"].strip(),
            "u_abandon": _number(t, "u_abandon", where, lo=0, hi=1, hi_open=True),
            "u_evade": _number(t, "u_evade", where, lo=0, hi=1, hi_open=True),
        })
        if out[-1]["scenario"] == "":
            raise ValueError(f"{where}: scenario is empty")
    extra = sorted(set(truth) - seen)
    if extra:
        raise ValueError(f"{clean(truth_path)}: {len(extra)} truth row(s) with no payment, first {clean(extra[0])}")
    return out


def _check_prob(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
        raise ValueError(f"assumptions: {name} must be a number from 0 to 1")
    return float(v)


def _check_minutes(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
        raise ValueError(f"assumptions: {name} must be a number of minutes, 0 or more")
    return float(v)


def check_assumptions(a) -> dict:
    """Validate an assumptions object and return a clean copy. Unknown keys are an error, so a typo cannot pass silently."""
    if not isinstance(a, dict):
        raise ValueError("assumptions: expected a JSON object")
    unknown = sorted(set(a) - set(DEFAULT_ASSUMPTIONS))
    if unknown:
        raise ValueError(f"assumptions: unknown key(s) {', '.join(clean(k) for k in unknown)}")
    out = json.loads(json.dumps(DEFAULT_ASSUMPTIONS))
    out.update(a)
    for k in ("hold_minutes", "warn_minutes"):
        out[k] = _check_minutes(out[k], k)
    for k in ("legit_abandon_on_hold", "legit_abandon_on_warn", "warn_factor", "coach_rate"):
        out[k] = _check_prob(out[k], k)
    sc = out["scam_scenarios"]
    if not isinstance(sc, dict) or not sc:
        raise ValueError("assumptions: scam_scenarios must be an object with at least one scenario")
    clean_sc = {}
    for name, spec in sc.items():
        if not isinstance(spec, dict) or set(spec) != {"p_abandon", "human_scammer"} or not isinstance(spec["human_scammer"], bool):
            raise ValueError(f"assumptions: scenario {clean(name)} needs exactly p_abandon (0 to 1) and human_scammer (true or false)")
        clean_sc[name] = {"p_abandon": _check_prob(spec["p_abandon"], f"{clean(name)}.p_abandon"), "human_scammer": spec["human_scammer"]}
    out["scam_scenarios"] = clean_sc
    return out


def load_assumptions(path: str | None) -> dict:
    if path is None:
        return check_assumptions({})
    try:
        with open(path, encoding="utf-8") as fh:
            return check_assumptions(json.load(fh))
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"{clean(path)}: cannot read ({clean(e)})")
    except json.JSONDecodeError as e:
        raise ValueError(f"{clean(path)}: not valid JSON ({clean(e)})")
    except RecursionError:
        raise ValueError(f"{clean(path)}: JSON is nested too deeply")


# ---------------------------------------------------------------- policy
def risk_score(p: dict) -> int:
    """Points from the features a bank could see at the moment of payment. The labels are never read here."""
    s = 0
    if p["payee_age_days"] == 0:
        s += WEIGHTS["new_payee"]
    elif p["payee_age_days"] <= 7:
        s += WEIGHTS["young_payee"]
    ratio = p["amount"] / p["usual_amount"]
    if ratio >= 3:
        s += WEIGHTS["amount_x3"]
    elif ratio >= 1.5:
        s += WEIGHTS["amount_x1_5"]
    if p["amount"] >= LARGE_AMOUNT:
        s += WEIGHTS["large_amount"]
    if p["call_active"]:
        s += WEIGHTS["call_active"]
    if p["device_new"]:
        s += WEIGHTS["device_new"]
    if p["hour"] <= 5:
        s += WEIGHTS["night"]
    return s


def policy_none() -> dict:
    return {"kind": "none"}


def policy_blanket(min_amount: float = 500) -> dict:
    """Hold every first payment to a new payee at or above min_amount."""
    return {"kind": "blanket", "min_amount": min_amount}


def policy_score(hold_score: int, warn_score: int | None = None) -> dict:
    if warn_score is not None and warn_score >= hold_score:
        raise ValueError("policy: warn-score must be below hold-score")
    return {"kind": "score", "hold_score": hold_score, "warn_score": warn_score}


def describe(policy: dict) -> str:
    if policy["kind"] == "none":
        return "none (no hold)"
    if policy["kind"] == "blanket":
        return f"blanket (new payee, amount >= {policy['min_amount']:g})"
    warn = f", warn >= {policy['warn_score']}" if policy["warn_score"] is not None else ""
    return f"score (hold >= {policy['hold_score']}{warn})"


def tier(p: dict, policy: dict) -> str:
    """PASS, WARN or HOLD from the payment's features alone."""
    kind = policy["kind"]
    if kind == "none":
        return "PASS"
    if kind == "blanket":
        return "HOLD" if p["payee_age_days"] == 0 and p["amount"] >= policy["min_amount"] else "PASS"
    s = risk_score(p)
    if s >= policy["hold_score"]:
        return "HOLD"
    if policy["warn_score"] is not None and s >= policy["warn_score"]:
        return "WARN"
    return "PASS"


# ---------------------------------------------------------------- simulation
def simulate(rows: list, policy: dict, assumptions: dict) -> dict:
    """Counts and values for one policy. Legitimate counts are raw; apply a weight with metrics()."""
    sc = assumptions["scam_scenarios"]
    r = {"payments": len(rows), "scam_n": 0, "scam_value": 0.0, "scam_held_n": 0, "scam_stopped_n": 0, "scam_stopped_value": 0.0,
         "legit_n": 0, "legit_held": 0, "legit_warned": 0, "legit_lost": 0, "legit_minutes": 0.0, "legit_value_delayed": 0.0,
         "stopped_by_scenario": {}, "scam_by_scenario": {}, "legit_held_by_scenario": {}, "legit_by_scenario": {}}
    for p in rows:
        t = tier(p, policy)
        name = p["scenario"]
        if p["is_scam"]:
            if name not in sc:
                raise ValueError(f"payment {clean(p['payment_id'])}: scenario {clean(name)} has no entry in scam_scenarios")
            r["scam_n"] += 1
            r["scam_value"] += p["amount"]
            r["scam_by_scenario"][name] = r["scam_by_scenario"].get(name, 0) + 1
            if t == "PASS":
                continue
            r["scam_held_n"] += 1
            spec = sc[name]
            prob = spec["p_abandon"] * (1.0 if t == "HOLD" else assumptions["warn_factor"])
            coached = spec["human_scammer"] and p["u_evade"] < assumptions["coach_rate"]
            if not coached and p["u_abandon"] < prob:
                r["scam_stopped_n"] += 1
                r["scam_stopped_value"] += p["amount"]
                r["stopped_by_scenario"][name] = r["stopped_by_scenario"].get(name, 0) + 1
        else:
            r["legit_n"] += 1
            r["legit_by_scenario"][name] = r["legit_by_scenario"].get(name, 0) + 1
            if t == "HOLD":
                r["legit_held"] += 1
                r["legit_held_by_scenario"][name] = r["legit_held_by_scenario"].get(name, 0) + 1
                r["legit_minutes"] += assumptions["hold_minutes"]
                r["legit_value_delayed"] += p["amount"]
                if p["u_abandon"] < assumptions["legit_abandon_on_hold"]:
                    r["legit_lost"] += 1
            elif t == "WARN":
                r["legit_warned"] += 1
                r["legit_minutes"] += assumptions["warn_minutes"]
                if p["u_abandon"] < assumptions["legit_abandon_on_warn"]:
                    r["legit_lost"] += 1
    return r


def metrics(r: dict, legit_weight: float = 1.0) -> dict:
    """Derived rates. legit_weight w counts every legitimate payment w times, which is the same as scams
    being 1/w as common while everything else stays put."""
    legit_n = r["legit_n"] * legit_weight
    held = r["legit_held"] * legit_weight
    return {
        "stopped_pct": 100.0 * r["scam_stopped_value"] / r["scam_value"] if r["scam_value"] else None,
        "legit_held_pct": 100.0 * held / legit_n if legit_n else None,
        "legit_lost": r["legit_lost"] * legit_weight,
        "holds_per_stopped": held / r["scam_stopped_n"] if r["scam_stopped_n"] else None,
    }


def fmt_money(v: float) -> str:
    return f"${v:,.0f}"


def fmt_pct(v) -> str:
    return "n/a" if v is None else f"{v:.1f}%"


def policy_lines(rows: list, policy: dict, assumptions: dict, legit_weight: float = 1.0) -> tuple:
    """The text block for one policy, and the notes about silent no-ops."""
    r = simulate(rows, policy, assumptions)
    m = metrics(r, legit_weight)
    w = "" if legit_weight == 1 else f" (legitimate payments weighted x{legit_weight:g})"
    per = "n/a" if m["holds_per_stopped"] is None else f"{m['holds_per_stopped']:.1f}"
    lines = [
        f"policy: {describe(policy)}{w}",
        f"  scam value stopped: {fmt_money(r['scam_stopped_value'])} of {fmt_money(r['scam_value'])} ({fmt_pct(m['stopped_pct'])}); "
        f"scam payments stopped: {r['scam_stopped_n']} of {r['scam_n']}",
        f"  legitimate payments held: {r['legit_held']} of {r['legit_n']} ({fmt_pct(m['legit_held_pct'])}); warned: {r['legit_warned']}; "
        f"lost: {r['legit_lost']}; minutes waited: {r['legit_minutes']:g}; value delayed: {fmt_money(r['legit_value_delayed'])}",
        f"  legitimate holds per scam payment stopped: {per}",
    ]
    notes = []
    if r["scam_n"] == 0:
        notes.append("note: the truth file has no scam payments, so nothing could be stopped")
    if r["scam_held_n"] + r["legit_held"] + r["legit_warned"] == 0 and policy["kind"] != "none":
        notes.append("note: this policy held and warned no payments in this file")
    return "\n".join(lines), notes


def demo_table(rows: list, assumptions: dict, hold_score: int, warn_score: int, min_amount: float) -> str:
    out = [f"payments: {len(rows)} ({sum(p['is_scam'] for p in rows)} scam, {sum(1 - p['is_scam'] for p in rows)} legitimate); "
           f"hold {assumptions['hold_minutes']:g} minutes"]
    for pol in (policy_none(), policy_blanket(min_amount), policy_score(hold_score, warn_score)):
        r = simulate(rows, pol, assumptions)
        m = metrics(r)
        out.append(f"  {describe(pol):<42} stopped {fmt_pct(m['stopped_pct']):>6} of scam value, "
                   f"legit held {r['legit_held']:>4} ({fmt_pct(m['legit_held_pct'])}), legit lost {r['legit_lost']}")
    return "\n".join(out)


# ---------------------------------------------------------------- command line
DEMO_HOLD_SCORE = 8
DEMO_WARN_SCORE = 6
DEMO_MIN_AMOUNT = 500


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        print(f"usage error: {clean(message, 200)}", file=sys.stderr)
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    ap = QuietParser(prog="scam_friction_sim")
    ap.add_argument("--demo", action="store_true", help="run three policies on the bundled data (data/payments.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("run", help="score one policy on your own files")
    c.add_argument("--payments", required=True)
    c.add_argument("--truth", required=True)
    c.add_argument("--assumptions", help="JSON file; see data/assumptions.json")
    c.add_argument("--policy", choices=["none", "blanket", "score"], default="score")
    c.add_argument("--min-amount", type=float, default=DEMO_MIN_AMOUNT, help="blanket policy: smallest amount held")
    c.add_argument("--hold-score", type=int, default=DEMO_HOLD_SCORE)
    c.add_argument("--warn-score", type=int, default=None)
    c.add_argument("--legit-weight", type=float, default=1.0, help="count legitimate payments this many times (scams 1/w as common)")
    c.add_argument("--max-held-pct", type=float, default=None, help="exit 1 when more than this percent of legitimate payments are held")
    c.add_argument("--min-stopped-pct", type=float, default=None, help="exit 1 when less than this percent of scam value is stopped")
    return ap


def run_command(a) -> int:
    try:
        if not math.isfinite(a.legit_weight) or a.legit_weight <= 0:
            raise ValueError("--legit-weight must be a number above 0")
        if not math.isfinite(a.min_amount) or a.min_amount <= 0:
            raise ValueError("--min-amount must be a number above 0")
        assumptions = load_assumptions(a.assumptions)
        rows = load_payments(a.payments, a.truth)
        policy = {"none": policy_none, "blanket": lambda: policy_blanket(a.min_amount),
                  "score": lambda: policy_score(a.hold_score, a.warn_score)}[a.policy]()
        text, notes = policy_lines(rows, policy, assumptions, a.legit_weight)
        r = simulate(rows, policy, assumptions)
    except ValueError as e:
        print(f"input error: {e}", file=sys.stderr)
        return 2
    m = metrics(r)
    print(f"payments: {len(rows)} ({r['scam_n']} scam, {r['legit_n']} legitimate)")
    print(text)
    for n in notes:
        print(n)
    broken = []
    if a.max_held_pct is not None and m["legit_held_pct"] is not None and m["legit_held_pct"] > a.max_held_pct:
        broken.append(f"legitimate payments held {m['legit_held_pct']:.1f}% is above the limit {a.max_held_pct:g}%")
    if a.min_stopped_pct is not None and (m["stopped_pct"] is None or m["stopped_pct"] < a.min_stopped_pct):
        broken.append(f"scam value stopped {fmt_pct(m['stopped_pct'])} is below the target {a.min_stopped_pct:g}%")
    for b in broken:
        print(f"budget broken: {b}")
    return 1 if broken else 0


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if a.demo:
        try:
            rows = load_payments(os.path.join(DATA_DIR, "payments.csv"), os.path.join(DATA_DIR, "truth.csv"))
            print(demo_table(rows, load_assumptions(None), DEMO_HOLD_SCORE, DEMO_WARN_SCORE, DEMO_MIN_AMOUNT))
        except ValueError as e:
            print(f"input error: {e}", file=sys.stderr)
            return 2
        return 0
    if a.cmd == "run":
        return run_command(a)
    build_parser().print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
