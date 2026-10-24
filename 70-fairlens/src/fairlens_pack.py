"""fairlens_pack: a six-test fairness pack for a points scorecard, run on a scores file.
Standard library only. Python 3.9 or newer.

Command line (from src/):
    python3 fairlens_pack.py --demo
    python3 fairlens_pack.py check SCORES.csv --cutoff 120 [--proxy-column postcode_points --proxy-code R05]
                                              [--reason-columns reason_1,reason_2,reason_3]
                                              [--fail-on fail|review|never] [--format text|github]
                                              [--resamples 400] [--seed 70] [--sweep-width 30]

Scores file, one row per applicant, UTF-8 CSV with a header:
    group         required, the group label (any text); the tool never infers a group from another field
    score         required, the scorecard total; an applicant is approved when score >= --cutoff
    bad_outcome   required, 1 when the applicant defaulted, else 0
    <proxy col>   optional, the points the suspected proxy contributes to score (named by --proxy-column)
    reason_1..3   optional, the reason codes listed on the decline notice, most important first

Tests (each returns PASS, REVIEW or FAIL, or NOT RUN when the file lacks what it needs):
    T1 approval gap       spread of approval rates across groups, in points (REVIEW at most: a gap in points has no screen)
    T2 AIR by group       adverse impact ratio per group with a 95% bootstrap interval
    T3 cutoff sweep       where the lowest AIR crosses the screen, and what moving the cutoff costs
    T4 proxy ablation     replace the proxy points by their mean and re-run the decisions
    T5 reason pairs       do declined applicants within 5 score points of each other get the same top reason in every group
    T6 reason naming      do the declines that turn on the proxy list the proxy's reason code

Exit status: 0 when the overall verdict is below --fail-on, 1 when it is at or above it, 2 for bad
or malformed input. There is no model in this file: every test is a count, a ratio, a sort or a
seeded resample. AIR is a screening statistic, not a legal finding. Every threshold below is an
assumption of a modeled bank; change it and the verdicts change.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from dataclasses import dataclass
from typing import Optional

AIR_SCREEN = 0.80                 # screening convention for the ratio of approval rates
SPREAD_REVIEW_PTS = 10.0          # T1: REVIEW at or above this spread of approval rates, in points (T1 never fails alone)
SWEEP_WIDTH = 30                  # T3: cutoffs from -30 to +30 score points around the policy cutoff
SWEEP_HEADROOM = 10               # T3: REVIEW when the screen is lost within this many points above the cutoff
PROXY_LIFT_REVIEW = 0.05          # T4: REVIEW when removing the proxy lifts the lowest AIR by this much
ACCURACY_COST_MAX_PTS = 1.0       # T4: FAIL only when the proxy-free scorecard loses at most this many accuracy points
SCORE_BAND = 5                    # T5: declined applicants this close in score are matched
PAIR_EXCESS_REVIEW_PTS = 15.0     # T5: cross-group mismatch above the within-group control, in points
PAIR_EXCESS_FAIL_PTS = 30.0
MIN_PAIRS = 15                    # T5: fewer matched pairs than this is not enough to judge
UNNAMED_REVIEW = 0.10             # T6: share of proxy-caused declines whose listed reasons omit the proxy code
UNNAMED_FAIL = 0.50
MIN_PROXY_DECLINES = 10           # T6: fewer proxy-caused declines than this is not enough to judge
RESAMPLES = 400
SEED = 70
DEFAULT_REASON_COLUMNS = ("reason_1", "reason_2", "reason_3")
RANK = {"PASS": 0, "REVIEW": 1, "FAIL": 2}


class InputError(Exception):
    """Bad or malformed input. The command line turns it into exit status 2."""


@dataclass
class Data:
    names: list          # sorted group labels
    groups: list         # group label per row
    scores: list
    bad: list
    proxy: list          # proxy points per row; empty when no proxy column was named
    proxy_name: str
    reasons: list        # tuple of non-empty reason codes per row; empty when the file has no reason columns


@dataclass
class Params:
    cutoff: float
    proxy_code: Optional[str] = None
    resamples: int = RESAMPLES
    seed: int = SEED
    sweep_width: int = SWEEP_WIDTH


def clean(text) -> str:
    """Make untrusted text safe to print: control and other unprintable characters become escapes."""
    out = "".join(c if c.isprintable() else ("\\x%02x" % ord(c) if ord(c) < 256 else "\\u%04x" % ord(c)) for c in str(text))
    return out if len(out) <= 60 else out[:57] + "..."


def gh_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def gh_prop(text: str) -> str:
    return gh_data(text).replace(":", "%3A").replace(",", "%2C")


def num(x) -> str:
    return "%g" % x


# ---------------------------------------------------------------- loading
def _number(text: str, what: str, line: int) -> float:
    try:
        v = float(text)
    except ValueError:
        raise InputError("line %d: %s is not a number" % (line, what))
    if not math.isfinite(v):
        raise InputError("line %d: %s is not a finite number" % (line, what))
    return v


def load_scores(path: str, proxy_column: Optional[str] = None, reason_columns: Optional[list] = None) -> Data:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            table = list(csv.reader(fh))
    except OSError as e:
        raise InputError("cannot read %s: %s" % (clean(path), e.strerror or "error"))
    except UnicodeDecodeError:
        raise InputError("%s is not UTF-8 text" % clean(path))
    except csv.Error as e:
        raise InputError("%s is not readable CSV: %s" % (clean(path), e))
    if not table or not any(table[0]):
        raise InputError("the scores file is empty")
    header = [h.strip() for h in table[0]]
    if len(set(header)) != len(header):
        raise InputError("the header repeats a column name")
    missing = [c for c in ("group", "score", "bad_outcome") if c not in header]
    if missing:
        raise InputError("missing required column(s): " + ", ".join(missing))
    if proxy_column is not None and proxy_column not in header:
        raise InputError("proxy column %s is not in the file" % clean(proxy_column))
    if reason_columns is None:
        reason_columns = list(DEFAULT_REASON_COLUMNS) if all(c in header for c in DEFAULT_REASON_COLUMNS) else []
    for c in reason_columns:
        if c not in header:
            raise InputError("reason column %s is not in the file" % clean(c))
    ix = {c: header.index(c) for c in header}
    groups, scores, bad, proxy, reasons = [], [], [], [], []
    for line, row in enumerate(table[1:], start=2):
        if not row:
            continue
        if len(row) != len(header):
            raise InputError("line %d: expected %d fields, found %d" % (line, len(header), len(row)))
        g = row[ix["group"]].strip()
        if not g:
            raise InputError("line %d: group is empty" % line)
        if row[ix["bad_outcome"]].strip() not in ("0", "1"):
            raise InputError("line %d: bad_outcome must be 0 or 1" % line)
        groups.append(g)
        scores.append(_number(row[ix["score"]], "score", line))
        bad.append(int(row[ix["bad_outcome"]]))
        if proxy_column is not None:
            proxy.append(_number(row[ix[proxy_column]], proxy_column, line))
        if reason_columns:
            reasons.append(tuple(row[ix[c]].strip() for c in reason_columns if row[ix[c]].strip()))
    if not groups:
        raise InputError("the scores file has a header and no rows")
    names = sorted(set(groups))
    if len(names) < 2:
        raise InputError("the scores file needs at least two groups")
    return Data(names, groups, scores, bad, proxy, proxy_column or "", reasons)


# ---------------------------------------------------------------- statistics
def group_stats(d: Data, scores: list, cutoff: float) -> Optional[dict]:
    """Approval, accuracy and AIR per group. None when nobody is approved (AIR is undefined)."""
    n = {g: 0 for g in d.names}
    ap = dict(n)
    ok = dict(n)
    bad_ap = 0
    for g, s, b in zip(d.groups, scores, d.bad):
        approved = s >= cutoff
        n[g] += 1
        ap[g] += approved
        ok[g] += (approved and b == 0) or (not approved and b == 1)
        bad_ap += approved and b == 1
    rates = {g: ap[g] / n[g] for g in d.names}
    ref = max(d.names, key=lambda g: rates[g])
    if rates[ref] == 0:
        return None
    air = {g: rates[g] / rates[ref] for g in d.names}
    low = min((g for g in d.names if g != ref), key=lambda g: air[g])
    total, approved_total = len(scores), sum(ap.values())
    return {"ref": ref, "min_air": air[low], "min_group": low, "approval_rate": approved_total / total,
            "accuracy": sum(ok.values()) / total,
            "approved_default_rate": bad_ap / approved_total if approved_total else 0.0,
            "groups": {g: {"n": n[g], "approved": ap[g], "rate": rates[g], "air": air[g], "accuracy": ok[g] / n[g]}
                       for g in d.names}}


def bootstrap(d: Data, cutoff: float, ref: str, resamples: int, seed: int) -> dict:
    """95% interval of each non-reference group's AIR, resampling applicants within each group."""
    rng = random.Random(seed)
    approved = {g: [1 if s >= cutoff else 0 for gg, s in zip(d.groups, d.scores) if gg == g] for g in d.names}
    others = [g for g in d.names if g != ref]
    draws = {g: [] for g in others}
    for _ in range(resamples):
        top = sum(rng.choices(approved[ref], k=len(approved[ref]))) / len(approved[ref])
        if top == 0:
            continue
        for g in others:
            draws[g].append(sum(rng.choices(approved[g], k=len(approved[g]))) / len(approved[g]) / top)
    out = {}
    for g in others:
        s = sorted(draws[g])
        out[g] = (s[int(0.025 * len(s))], s[min(len(s) - 1, int(0.975 * len(s)))]) if s else (0.0, 0.0)
    return {"intervals": out, "resamples": resamples, "seed": seed}


def sweep(d: Data, cutoff: float, width: int) -> list:
    return [{"cutoff": cutoff + k, "gs": group_stats(d, d.scores, cutoff + k)} for k in range(-width, width + 1)]


def ablate(d: Data, cutoff: float) -> dict:
    """Replace the proxy points by their mean and re-run the decisions."""
    neutral = sum(d.proxy) / len(d.proxy)
    new = [s - p + neutral for s, p in zip(d.scores, d.proxy)]
    flip_in = [i for i, (s, t) in enumerate(zip(d.scores, new)) if s < cutoff <= t]
    flip_out = [i for i, (s, t) in enumerate(zip(d.scores, new)) if t < cutoff <= s]
    return {"before": group_stats(d, d.scores, cutoff), "after": group_stats(d, new, cutoff),
            "flip_in": flip_in, "flip_out": flip_out}


def _nearest(scores: list, i: int, pool: list, skip_self: bool) -> Optional[int]:
    best, best_diff = None, SCORE_BAND + 1
    for j in pool:
        if skip_self and j == i:
            continue
        diff = abs(scores[j] - scores[i])
        if diff < best_diff:
            best, best_diff = j, diff
    return best


def reason_pairs(d: Data, cutoff: float, ref: str) -> dict:
    declined = [i for i, s in enumerate(d.scores) if s < cutoff and d.reasons[i]]
    no_reason = sum(1 for i, s in enumerate(d.scores) if s < cutoff and not d.reasons[i])
    pool = sorted((i for i in declined if d.groups[i] == ref), key=lambda i: (d.scores[i], i))
    other = [i for i in declined if d.groups[i] != ref]
    cross = [(i, _nearest(d.scores, i, pool, False)) for i in other]
    control = [(i, _nearest(d.scores, i, pool, True)) for i in pool]
    cross = [(i, j) for i, j in cross if j is not None]
    control = [(i, j) for i, j in control if j is not None]
    c_diff = sum(1 for i, j in cross if d.reasons[i][0] != d.reasons[j][0])
    k_diff = sum(1 for i, j in control if d.reasons[i][0] != d.reasons[j][0])
    return {"cross_pairs": len(cross), "cross_differ": c_diff, "control_pairs": len(control), "control_differ": k_diff,
            "cross_share": c_diff / len(cross) if cross else 0.0,
            "control_share": k_diff / len(control) if control else 0.0, "no_reason": no_reason}


# ---------------------------------------------------------------- the six tests
def _test(tid: str, name: str, verdict: str, numbers: str, rule: str, **extra) -> dict:
    t = {"id": tid, "name": name, "verdict": verdict, "numbers": numbers, "rule": rule}
    t.update(extra)
    return t


def _not_run(tid: str, name: str, why: str) -> dict:
    return _test(tid, name, "NOT RUN", why, "needs more columns than the file has")


def t1_gap(gs: dict) -> dict:
    rates = {g: v["rate"] for g, v in gs["groups"].items()}
    spread = 100 * (max(rates.values()) - min(rates.values()))
    v = "REVIEW" if spread >= SPREAD_REVIEW_PTS else "PASS"
    return _test("T1", "approval gap", v,
                 "approval " + ", ".join("%s %.1f%%" % (clean(g), 100 * r) for g, r in rates.items()) + ", spread %.1f points" % spread,
                 "REVIEW at %g points or more; never FAIL, because a gap in points has no screen of its own" % SPREAD_REVIEW_PTS)


def interval_verdict(lo: float, hi: float) -> str:
    return "FAIL" if hi < AIR_SCREEN else "PASS" if lo >= AIR_SCREEN else "REVIEW"


def t2_air(gs: dict, bs: dict) -> dict:
    verdicts = {g: interval_verdict(*iv) for g, iv in bs["intervals"].items()}
    worst = max(verdicts.values(), key=lambda v: RANK[v])
    parts = ["%s %.3f (%.3f to %.3f) %s" % (clean(g), gs["groups"][g]["air"], iv[0], iv[1], verdicts[g])
             for g, iv in bs["intervals"].items()]
    return _test("T2", "AIR by group", worst, "AIR " + "; ".join(parts),
                 "per group: FAIL when the whole 95%% interval is below %.2f, PASS when it is all at or above, else REVIEW" % AIR_SCREEN,
                 verdicts=verdicts)


def t3_sweep(sw: list, width: int, group_verdict: str) -> dict:
    """group_verdict is T2's verdict for the group with the lowest AIR at the policy cutoff."""
    pol = sw[width]
    above = []
    for r in sw[width + 1:]:
        if r["gs"] is None:
            break
        above.append(r)
    pgs = pol["gs"]
    rule = ("FAIL when T2 fails the lowest-AIR group at the policy cutoff; REVIEW when its AIR is below the screen but the interval "
            "straddles it, or when the screen holds with under %d points of headroom" % SWEEP_HEADROOM)
    head = "lowest AIR %.3f at cutoff %s; " % (pgs["min_air"], num(pol["cutoff"]))
    if pgs["min_air"] < AIR_SCREEN:
        nxt = next((r for r in above if r["gs"]["min_air"] >= AIR_SCREEN), None)
        if nxt:
            g = nxt["gs"]
            text = head + ("the screen holds from cutoff %s (%s points up): approval %.1f%% -> %.1f%%, approved-book default rate %.1f%% -> %.1f%%"
                           % (num(nxt["cutoff"]), num(nxt["cutoff"] - pol["cutoff"]), 100 * pgs["approval_rate"], 100 * g["approval_rate"],
                              100 * pgs["approved_default_rate"], 100 * g["approved_default_rate"]))
        else:
            text = head + "no cutoff within %d points above clears the screen" % width
        return _test("T3", "cutoff sweep", "FAIL" if group_verdict == "FAIL" else "REVIEW", text, rule)
    nxt = next((r for r in above if r["gs"]["min_air"] < AIR_SCREEN), None)
    if nxt:
        room = nxt["cutoff"] - pol["cutoff"]
        text = head + "the screen is lost at cutoff %s, %s points up" % (num(nxt["cutoff"]), num(room))
        return _test("T3", "cutoff sweep", "REVIEW" if room < SWEEP_HEADROOM else "PASS", text, rule)
    return _test("T3", "cutoff sweep", "PASS", head + "the screen holds across the %d points above" % width, rule)


def t4_proxy(d: Data, ab: dict) -> dict:
    rule = ("FAIL when removing the proxy lifts the lowest AIR by %.2f or more, from below %.2f to at or above it, and costs at most %g points of accuracy; "
            "REVIEW when it clears the screen at a higher cost or lifts the lowest AIR by %.2f or more" % (PROXY_LIFT_REVIEW, AIR_SCREEN, ACCURACY_COST_MAX_PTS, PROXY_LIFT_REVIEW))
    b, a = ab["before"], ab["after"]
    if a is None:
        return _test("T4", "proxy ablation", "REVIEW", "the proxy-free scorecard approves nobody at this cutoff, so AIR is undefined", rule)
    lift = a["min_air"] - b["min_air"]
    cost = 100 * (b["accuracy"] - a["accuracy"])
    if b["min_air"] < AIR_SCREEN <= a["min_air"] and lift >= PROXY_LIFT_REVIEW:
        v = "FAIL" if cost <= ACCURACY_COST_MAX_PTS else "REVIEW"
    else:
        v = "REVIEW" if lift >= PROXY_LIFT_REVIEW else "PASS"
    return _test("T4", "proxy ablation", v,
                 "lowest AIR %.3f -> %.3f, accuracy %.1f%% -> %.1f%%, %d decisions turn to approve and %d to decline" % (
                     b["min_air"], a["min_air"], 100 * b["accuracy"], 100 * a["accuracy"], len(ab["flip_in"]), len(ab["flip_out"])),
                 rule, lift=lift, cost_pts=cost, before=b["min_air"], after=a["min_air"],
                 flip_in=len(ab["flip_in"]), flip_out=len(ab["flip_out"]))


def t5_pairs(pr: dict, ref: str) -> dict:
    rule = ("declined applicants within %d score points are matched; REVIEW when the cross-group mismatch of top reason is %g points above the "
            "control inside the reference group, FAIL at %g; REVIEW when fewer than %d pairs match" % (SCORE_BAND, PAIR_EXCESS_REVIEW_PTS, PAIR_EXCESS_FAIL_PTS, MIN_PAIRS))
    extra = "; %d declined applicants have no reason on file" % pr["no_reason"] if pr["no_reason"] else ""
    if pr["cross_pairs"] < MIN_PAIRS or pr["control_pairs"] < MIN_PAIRS:
        return _test("T5", "reason pairs", "REVIEW", "only %d cross-group and %d control pairs match, not enough to judge%s" % (
            pr["cross_pairs"], pr["control_pairs"], extra), rule, excess=None)
    excess = 100 * (pr["cross_share"] - pr["control_share"])
    v = "FAIL" if excess >= PAIR_EXCESS_FAIL_PTS else "REVIEW" if excess >= PAIR_EXCESS_REVIEW_PTS else "PASS"
    return _test("T5", "reason pairs", v, "%d of %d cross-group pairs differ in top reason (%.1f%%) against %.1f%% within %s (%+.1f points)%s" % (
        pr["cross_differ"], pr["cross_pairs"], 100 * pr["cross_share"], 100 * pr["control_share"], clean(ref), excess, extra),
        rule, excess=excess)


def t6_naming(d: Data, ab: dict, code: str, proxy_matters: bool) -> dict:
    """proxy_matters is False when T4 passed: the share is then reported but cannot FAIL on its own."""
    rule = ("of the declines that turn on the proxy, REVIEW when %d%% or more list no reason naming it, FAIL at %d%% (only when T4 did not pass); "
            "REVIEW when fewer than %d such declines exist" % (round(100 * UNNAMED_REVIEW), round(100 * UNNAMED_FAIL), MIN_PROXY_DECLINES))
    flips = ab["flip_in"]
    if not flips:
        return _test("T6", "reason naming", "PASS", "no decline turns on the proxy at this cutoff", rule, count=0, unnamed=0)
    unnamed = sum(1 for i in flips if code not in d.reasons[i])
    share = unnamed / len(flips)
    if len(flips) < MIN_PROXY_DECLINES:
        v = "REVIEW"
    elif share >= UNNAMED_FAIL:
        v = "FAIL" if proxy_matters else "REVIEW"
    else:
        v = "REVIEW" if share >= UNNAMED_REVIEW else "PASS"
    return _test("T6", "reason naming", v, "%d of %d declines that turn on the proxy do not list %s (%.1f%%)%s" % (
        unnamed, len(flips), clean(code), 100 * share, "; too few to judge" if len(flips) < MIN_PROXY_DECLINES else ""),
        rule, count=len(flips), unnamed=unnamed)


def run_pack(d: Data, p: Params) -> dict:
    gs = group_stats(d, d.scores, p.cutoff)
    if gs is None:
        raise InputError("no applicant is approved at cutoff %s, so approval ratios are undefined" % num(p.cutoff))
    bs = bootstrap(d, p.cutoff, gs["ref"], p.resamples, p.seed)
    sw = sweep(d, p.cutoff, p.sweep_width)
    ab = ablate(d, p.cutoff) if d.proxy else None
    pr = reason_pairs(d, p.cutoff, gs["ref"]) if d.reasons else None
    t2 = t2_air(gs, bs)
    tests = [t1_gap(gs), t2, t3_sweep(sw, p.sweep_width, t2["verdicts"][gs["min_group"]])]
    tests.append(t4_proxy(d, ab) if ab else _not_run("T4", "proxy ablation", "no --proxy-column given"))
    tests.append(t5_pairs(pr, gs["ref"]) if pr else _not_run("T5", "reason pairs", "no reason columns in the file"))
    if ab and d.reasons and p.proxy_code:
        tests.append(t6_naming(d, ab, p.proxy_code, tests[3]["verdict"] != "PASS"))
    else:
        tests.append(_not_run("T6", "reason naming", "needs --proxy-column, --proxy-code and reason columns"))
    ran = [t for t in tests if t["verdict"] != "NOT RUN"]
    overall = max((t["verdict"] for t in ran), key=lambda v: RANK[v])
    return {"tests": tests, "overall": overall, "gs": gs, "boot": bs, "sweep": sw, "ablation": ab, "pairs": pr}


# ---------------------------------------------------------------- output
def render_text(d: Data, p: Params, pack: dict) -> str:
    tests = pack["tests"]
    lines = ["fairlens: %d applicants in %d groups, cutoff %s, reference %s" % (len(d.scores), len(d.names), num(p.cutoff), clean(pack["gs"]["ref"]))]
    for t in tests:
        lines.append("  %s %-15s %-7s %s" % (t["id"], t["name"], t["verdict"], t["numbers"]))
    counts = {v: sum(1 for t in tests if t["verdict"] == v) for v in ("FAIL", "REVIEW", "PASS", "NOT RUN")}
    tail = "; not run: " + ", ".join(t["id"] for t in tests if t["verdict"] == "NOT RUN") if counts["NOT RUN"] else ""
    lines.append("overall: %s (%d FAIL, %d REVIEW, %d PASS)%s" % (pack["overall"], counts["FAIL"], counts["REVIEW"], counts["PASS"], tail))
    return "\n".join(lines)


def render_github(pack: dict) -> str:
    lines = []
    for t in pack["tests"]:
        if t["verdict"] in ("FAIL", "REVIEW"):
            level = "error" if t["verdict"] == "FAIL" else "warning"
            lines.append("::%s title=%s::%s" % (level, gh_prop("fairlens %s %s" % (t["id"], t["name"])), gh_data(t["numbers"])))
    lines.append("::notice title=fairlens::%s" % gh_data("overall %s" % pack["overall"]))
    return "\n".join(lines)


def run_check(path: str, p: Params, proxy_column: Optional[str], reason_columns: Optional[list], fail_on: str, fmt: str) -> int:
    d = load_scores(path, proxy_column, reason_columns)
    pack = run_pack(d, p)
    print(render_github(pack) if fmt == "github" else render_text(d, p, pack))
    if fail_on == "never":
        return 0
    return 1 if RANK[pack["overall"]] >= RANK[{"fail": "FAIL", "review": "REVIEW"}[fail_on]] else 0


# ---------------------------------------------------------------- command line
class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError(message)


def _int_option(text: str, name: str, lo: int, hi: int) -> int:
    try:
        v = int(text)
    except ValueError:
        raise InputError("%s must be a whole number" % name)
    if not lo <= v <= hi:
        raise InputError("%s must be between %d and %d" % (name, lo, hi))
    return v


def main(argv=None) -> int:
    ap = _Parser(prog="fairlens_pack")
    ap.add_argument("--demo", action="store_true", help="run the bundled example (data/example_scores.csv)")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="run the six tests on a scores file")
    c.add_argument("scores", help="the scores CSV: group, score, bad_outcome, optional proxy points and reason_1 to reason_3")
    c.add_argument("--cutoff", help="approve when score >= cutoff")
    c.add_argument("--proxy-column", help="column holding the suspected proxy's points")
    c.add_argument("--proxy-code", help="reason code that names the proxy on a decline notice")
    c.add_argument("--reason-columns", help="comma-separated reason columns, most important first")
    c.add_argument("--fail-on", choices=["fail", "review", "never"], default="fail", help="exit 1 when the overall verdict is at or above this level (default fail)")
    c.add_argument("--format", choices=["text", "github"], default="text", help="text, or github for workflow annotations")
    c.add_argument("--resamples", default=str(RESAMPLES), help="bootstrap resamples for the T2 interval, 50 to 20000 (default %(default)s)")
    c.add_argument("--seed", default=str(SEED), help="seed for the bootstrap (default %(default)s)")
    c.add_argument("--sweep-width", default=str(SWEEP_WIDTH), help="T3 sweeps cutoffs this many score points either side, 1 to 200 (default %(default)s)")
    try:
        a = ap.parse_args(argv)
        if a.demo:
            here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
            with open(os.path.join(here, "example_params.json"), encoding="utf-8") as fh:
                ex = json.load(fh)
            return run_check(os.path.join(here, "example_scores.csv"),
                             Params(cutoff=ex["cutoff"], proxy_code=ex["proxy_code"]), ex["proxy_column"], None, "never", "text")
        if a.cmd != "check":
            ap.print_help()
            return 2
        if a.cutoff is None:
            raise InputError("--cutoff is required")
        try:
            cutoff = float(a.cutoff)
        except ValueError:
            raise InputError("--cutoff must be a number")
        if not math.isfinite(cutoff):
            raise InputError("--cutoff must be a finite number")
        if a.proxy_code is not None and a.proxy_column is None:
            raise InputError("--proxy-code needs --proxy-column")
        cols = [x.strip() for x in a.reason_columns.split(",")] if a.reason_columns else None
        p = Params(cutoff=cutoff, proxy_code=a.proxy_code, resamples=_int_option(a.resamples, "--resamples", 50, 20000),
                   seed=_int_option(a.seed, "--seed", 0, 2 ** 31), sweep_width=_int_option(a.sweep_width, "--sweep-width", 1, 200))
        return run_check(a.scores, p, a.proxy_column, cols, a.fail_on, a.format)
    except InputError as e:
        print("input error: %s" % clean(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
