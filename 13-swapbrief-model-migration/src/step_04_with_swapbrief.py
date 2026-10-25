"""
Step 4 - The fix: SwapBrief.

A go or no-go decision brief for moving a production GenAI feature to a new
model version. It replaces "the average went up" with:

  1. per-slice paired bootstrap intervals (item pairs resampled within each slice)
  2. cost per correct answer, with an interval
  3. p50 and p95 latency, with intervals
  4. a prompt-fair comparison (model B with A's old prompt and with its retuned prompt)
  5. a decision rule: GO, GO WITH GUARDRAILS or NO-GO
  6. explicit rollback triggers: metric, threshold, window

It then scores the rule against the generator's injected truth on 200 seeded
simulated migration scenarios, next to the headline-average rule (step 1) and
the aggregate significance rule (step 2).

All results are SIMULATED (data/_generate.py is a seeded stub). No model was
called, and nothing here measures any real model, vendor or bank.

KNOWN LIMIT, left in on purpose: a slice with too few items cannot be resolved.
SwapBrief marks it INCONCLUSIVE and lists it. A real regression inside such a
slice can still pass. The script prints the slices and counts the misses.

Run (standard library only, Python 3.9; about 40 seconds):
    python step_04_with_swapbrief.py

Output: prints the brief and the decision-quality table; writes
src/out/step_04_results.json, step_04_scenarios.csv and step_04_triggers.csv.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from operator import itemgetter

from step_01_headline_average import CANDIDATE, DATA_DIR, OUT_DIR, headline_rule, load_dataset
from step_02_aggregate_significance import BOOT_SEED as AGG_SEED
from step_02_aggregate_significance import aggregate_rule, mcnemar_exact, percentile
from step_03_deficiencies_exposed import (REPLAY_SLIP_SLICE, REPLAY_SLIP_WEEK, cost_per_correct, item_costs,
                                          latency_stats, replay_production)

sys.path.insert(0, str(DATA_DIR))
import _generate as gen  # noqa: E402

B_MAIN = 2000          # bootstrap resamples for the committed dataset
B_SIM = 200            # bootstrap resamples per simulated scenario
BOOT_SEED = 20261019
SIM_BOOT_SEED = 71000000
SIM_DATA_SEED = 91000000
MIGRATIONS_PER_YEAR = 6   # modeled assumption: 9 production GenAI features, each forced onto a successor about every 18 months

# Curated simulated scenarios shown in the app and the demo. Each id is a scenario of the
# 200 below; verify_curated() checks that it still matches its label.
CURATED = [
    (11, "Headline GO, SwapBrief NO-GO: a critical slice regressed"),
    (3, "A verbose successor: cost per correct answer rises, accuracy does not fall"),
    (4, "A clean migration: SwapBrief says GO"),
    (107, "Known limit: a regression hides in a slice with too few items"),
    (22, "A miss: the regression is real and the intervals did not show it"),
    (1, "Over-guarded: the migration was fine and SwapBrief still asks for a trigger"),
]


# ---------------------------------------------------------------------------
# The analysis
# ---------------------------------------------------------------------------
def dataset_from_sim(sim: dict, policy: dict) -> dict:
    spec = sim["spec"]
    return {
        "slices": [{"slice": s["name"], "severity": s["severity"], "tol": s["tol_pp"] / 100.0,
                    "n_items": s["n"], "description": s["desc"]} for s in spec["slices"]],
        "slice_idx": sim["slice_idx"],
        "should_refuse": sim["should_refuse"],
        "cols": sim["cols"],
        "prices": {m: {"in": p["in"], "out": p["out"]} for m, p in gen.PRICES.items()},
        "model_of": {"A": "model-a", "B_old_prompt": "model-b", "B_new_prompt": "model-b"},
        "policy": policy,
    }


def slice_status(delta: float, lo: float, hi: float, tol: float, half_width_limit: float) -> str:
    if hi < 0 and delta <= -tol:
        return "REGRESSED"          # confirmed, and beyond the tolerance
    if hi < 0 or delta <= -tol:
        return "WATCH"              # confirmed but small, or large but unconfirmed
    if lo > 0:
        return "IMPROVED"           # the whole interval is above zero: no regression is hiding here
    if (hi - lo) / 2.0 > half_width_limit and lo < -tol:
        return "INCONCLUSIVE"       # wide, and it still reaches past the tolerance: too few items to rule a regression out
    return "OK"


def ratio_status(point: float, lo: float, watch: float, block: float) -> str:
    if lo >= block:
        return "BLOCK"
    if point >= watch and lo > 1.0:
        return "WATCH"
    return "OK"


def bootstrap_all(ds: dict, system: str, B: int, seed: int) -> dict:
    """One stratified paired bootstrap that feeds every interval in the brief."""
    n = len(ds["slice_idx"])
    members = [[] for _ in ds["slices"]]
    for i, s in enumerate(ds["slice_idx"]):
        members[s].append(i)
    ca = ds["cols"]["A"]
    cb = ds["cols"][system]
    diff = [y - x for x, y in zip(ca["correct"], cb["correct"])]
    cost_a, cost_b = item_costs(ds, "A"), item_costs(ds, system)
    ok_a, ok_b = ca["correct"], cb["correct"]
    lat_a, lat_b = ca["lat"], cb["lat"]
    sizes = [len(m) for m in members]
    rng = random.Random(seed)
    choices = rng.choices
    slice_reps = [[] for _ in members]
    cost_reps, p50_reps, p95_reps = [], [], []
    for _ in range(B):
        all_idx = []
        for k, m in enumerate(members):
            samp = choices(m, k=sizes[k])
            all_idx.extend(samp)
            slice_reps[k].append(sum(itemgetter(*samp)(diff)) / sizes[k])
        g = itemgetter(*all_idx)
        cost_reps.append((sum(g(cost_b)) / sum(g(ok_b))) / (sum(g(cost_a)) / sum(g(ok_a))))
        la, lb = sorted(g(lat_a)), sorted(g(lat_b))
        p50_reps.append(percentile(lb, 0.50) / percentile(la, 0.50))
        p95_reps.append(percentile(lb, 0.95) / percentile(la, 0.95))
    conf = float(ds["policy"].get("bootstrap_confidence", 0.95))
    tail = (1.0 - conf) / 2.0

    def ci(reps: list) -> tuple:
        s = sorted(reps)
        return percentile(s, tail), percentile(s, 1.0 - tail)

    return {"slice_ci": [ci(r) for r in slice_reps], "cost_ci": ci(cost_reps),
            "p50_ci": ci(p50_reps), "p95_ci": ci(p95_reps)}


def analyze(ds: dict, system: str = CANDIDATE, B: int = B_MAIN, seed: int = BOOT_SEED) -> dict:
    """The SwapBrief analysis of model B (under `system`) against model A."""
    pol = ds["policy"]
    hw_limit = float(pol["inconclusive_half_width"])
    cost_watch, cost_block = float(pol["cost_ratio_watch"]), float(pol["cost_ratio_block"])
    p95_watch, p95_block = float(pol["p95_ratio_watch"]), float(pol["p95_ratio_block"])
    boot = bootstrap_all(ds, system, B, seed)

    ca, cb = ds["cols"]["A"], ds["cols"][system]
    n_sl = len(ds["slices"])
    rows = []
    for k, sl in enumerate(ds["slices"]):
        idx = [i for i, s in enumerate(ds["slice_idx"]) if s == k]
        n = len(idx)
        acc_a = sum(ca["correct"][i] for i in idx) / n
        acc_b = sum(cb["correct"][i] for i in idx) / n
        delta = acc_b - acc_a
        lo, hi = boot["slice_ci"][k]
        status = slice_status(delta, lo, hi, sl["tol"], hw_limit)
        rows.append({
            "slice": sl["slice"], "severity": sl["severity"], "tol": sl["tol"], "n": n,
            "acc_a": acc_a, "acc_b": acc_b, "delta": delta, "lo": lo, "hi": hi, "status": status,
            "refusal_a": sum(ca["ref"][i] for i in idx) / n, "refusal_b": sum(cb["ref"][i] for i in idx) / n,
        })

    n_all = len(ds["slice_idx"])
    cpc_a = cost_per_correct(ds, "A")
    cpc_b = cost_per_correct(ds, system)
    c_ratio = cpc_b / cpc_a
    c_lo, c_hi = boot["cost_ci"]
    lat_a, lat_b = latency_stats(ds, "A"), latency_stats(ds, system)
    p50_ratio, p95_ratio = lat_b["p50"] / lat_a["p50"], lat_b["p95"] / lat_a["p95"]
    cost = {"cpc_a": cpc_a, "cpc_b": cpc_b, "ratio": c_ratio, "lo": c_lo, "hi": c_hi,
            "status": ratio_status(c_ratio, c_lo, cost_watch, cost_block)}
    latency = {"p50_a": lat_a["p50"], "p50_b": lat_b["p50"], "p50_ratio": p50_ratio,
               "p50_lo": boot["p50_ci"][0], "p50_hi": boot["p50_ci"][1],
               "p95_a": lat_a["p95"], "p95_b": lat_b["p95"], "p95_ratio": p95_ratio,
               "p95_lo": boot["p95_ci"][0], "p95_hi": boot["p95_ci"][1],
               "status": ratio_status(p95_ratio, boot["p95_ci"][0], p95_watch, p95_block)}
    overall = {"acc_a": sum(ca["correct"]) / n_all, "acc_b": sum(cb["correct"]) / n_all}
    overall["delta"] = overall["acc_b"] - overall["acc_a"]

    # Decision rule -------------------------------------------------------
    block_reasons, guard_reasons = [], []
    blocking = [r for r in rows if r["status"] == "REGRESSED" and r["severity"] == "critical"]
    for r in blocking:
        block_reasons.append("%s (critical) fell %.1f pp, interval %+.1f to %+.1f pp, beyond its %.0f pp tolerance" % (
            r["slice"], -r["delta"] * 100, r["lo"] * 100, r["hi"] * 100, r["tol"] * 100))
    if cost["status"] == "BLOCK":
        block_reasons.append("cost per correct answer is at least %.2fx A at the interval's lower bound" % cost_block)
    if latency["status"] == "BLOCK":
        block_reasons.append("p95 latency is at least %.2fx A at the interval's lower bound" % p95_block)
    guard_rows = [r for r in rows if r["status"] in ("REGRESSED", "WATCH")
                  or (r["status"] == "INCONCLUSIVE" and r["severity"] == "critical")]
    for r in rows:
        if r["status"] == "REGRESSED" and r["severity"] == "standard":
            guard_reasons.append("%s (standard) fell %.1f pp, interval %+.1f to %+.1f pp: ship only with a trigger and an owner" % (
                r["slice"], -r["delta"] * 100, r["lo"] * 100, r["hi"] * 100))
        elif r["status"] == "WATCH":
            guard_reasons.append("%s change %+.1f pp, interval %+.1f to %+.1f pp: not settled, watch" % (
                r["slice"], r["delta"] * 100, r["lo"] * 100, r["hi"] * 100))
        elif r["status"] == "INCONCLUSIVE" and r["severity"] == "critical":
            guard_reasons.append("%s (critical) is inconclusive on %d items: trigger required" % (r["slice"], r["n"]))
    if cost["status"] == "WATCH":
        guard_reasons.append("cost per correct answer %+.1f%% vs A, interval %+.1f%% to %+.1f%%" % (
            (c_ratio - 1) * 100, (c_lo - 1) * 100, (c_hi - 1) * 100))
    if latency["status"] == "WATCH":
        guard_reasons.append("p95 latency %+.1f%% vs A, interval %+.1f%% to %+.1f%%" % (
            (p95_ratio - 1) * 100, (latency["p95_lo"] - 1) * 100, (latency["p95_hi"] - 1) * 100))
    if block_reasons:
        decision = "NO-GO"
        reasons = block_reasons + ["also flagged: " + x for x in guard_reasons]
    elif guard_reasons:
        decision = "GO WITH GUARDRAILS"
        reasons = guard_reasons
    else:
        decision = "GO"
        reasons = ["no slice is regressed or watched, and cost and p95 are inside the watch levels"]
    advisory = [r for r in rows if r["status"] == "INCONCLUSIVE" and r["severity"] == "standard"]
    for r in advisory:
        reasons.append("advisory: %s (standard) is inconclusive on %d items; listed with a trigger" % (r["slice"], r["n"]))

    inconclusive = [r for r in rows if r["status"] == "INCONCLUSIVE"]
    result = {
        "system": system, "decision": decision, "reasons": reasons, "overall": overall, "slices": rows,
        "cost": cost, "latency": latency, "inconclusive": inconclusive, "n_items": n_all, "bootstrap_resamples": B,
    }
    result["triggers"] = build_triggers(result, ds)
    return result


def build_triggers(res: dict, ds: dict) -> list:
    """Rollback triggers: metric, threshold, window. Derived from the evaluation and the policy."""
    pol = ds["policy"]
    triggers = []
    for r in res["slices"]:
        standing = r["severity"] == "critical"
        flagged = r["status"] in ("REGRESSED", "WATCH", "INCONCLUSIVE")
        if not (standing or flagged):
            continue
        ref = min(r["acc_a"], r["acc_b"])
        floor = ref - r["tol"]
        p = max(0.05, min(0.95, ref))
        n_min = int(math.ceil(4.0 * p * (1.0 - p) / (r["tol"] ** 2)))
        if r["status"] == "REGRESSED":
            why = "regression accepted with an owner; floor is B's evaluated accuracy minus the tolerance"
        elif r["status"] == "WATCH":
            why = "change not settled; floor is the lower of A and B minus the tolerance"
        elif r["status"] == "INCONCLUSIVE":
            why = "inconclusive on %d items; floor is the lower of A and B minus the tolerance" % r["n"]
        else:
            why = "standing trigger on a critical slice"
        triggers.append({
            "metric": "accuracy[%s]" % r["slice"], "comparison": "<", "threshold": floor,
            "threshold_text": "< %.3f" % floor, "window": str(pol["window_slice"]), "min_sample": n_min,
            "action": "roll back to model A", "why": why, "kind": "slice", "slice": r["slice"],
        })
    cost = res["cost"]
    cost_line = cost["cpc_a"] * float(pol["cost_ratio_block"])
    triggers.append({
        "metric": "cost per correct answer (USD)", "comparison": ">", "threshold": cost_line,
        "threshold_text": "> $%.5f (%.2fx A)" % (cost_line, float(pol["cost_ratio_block"])),
        "window": str(pol["window_cost"]), "min_sample": 0, "action": "roll back to model A",
        "why": "the line that blocks at evaluation is the line that rolls back in production", "kind": "cost", "slice": "",
    })
    lat = res["latency"]
    p95_line = lat["p95_a"] * float(pol["p95_ratio_block"])
    triggers.append({
        "metric": "p95 latency (ms)", "comparison": ">", "threshold": p95_line,
        "threshold_text": "> %.0f ms (%.2fx A)" % (p95_line, float(pol["p95_ratio_block"])),
        "window": str(pol["window_p95"]), "min_sample": 0, "action": "roll back to model A",
        "why": "the line that blocks at evaluation is the line that rolls back in production", "kind": "p95", "slice": "",
    })
    return triggers


def flagged_names(res: dict) -> set:
    """Problems SwapBrief called out with a status or a trigger (used to score it)."""
    out = set()
    for r in res["slices"]:
        if r["status"] in ("REGRESSED", "WATCH", "INCONCLUSIVE"):
            out.add("slice:" + r["slice"])
    if res["cost"]["status"] in ("WATCH", "BLOCK"):
        out.add("cost")
    if res["latency"]["status"] in ("WATCH", "BLOCK"):
        out.add("p95")
    return out


# ---------------------------------------------------------------------------
# Triggers against the production replay
# ---------------------------------------------------------------------------
def first_firing_week(triggers: list, replay: list) -> dict:
    """First week a slice trigger fires on the simulated production replay."""
    out = {}
    for t in triggers:
        if t["kind"] != "slice":
            continue
        for rec in replay:
            s = rec["slices"][t["slice"]]
            if s["acc"] < t["threshold"] and s["n"] >= t["min_sample"]:
                out[t["slice"]] = rec["week"]
                break
    return out


# ---------------------------------------------------------------------------
# 200 simulated migration scenarios, scored against the generator's truth
# ---------------------------------------------------------------------------
def scenario_record(i: int, policy: dict, B: int = B_SIM, mix: float = 1.0) -> dict:
    spec = gen.scenario_spec(i, mix)
    truth = gen.scenario_truth(spec)
    sim = gen.simulate(spec, SIM_DATA_SEED + i)
    ds = dataset_from_sim(sim, policy)
    n = len(ds["slice_idx"])
    a, b = ds["cols"]["A"]["correct"], ds["cols"][CANDIDATE]["correct"]
    diff = [y - x for x, y in zip(a, b)]
    delta = sum(diff) / n
    nb = sum(1 for x in diff if x == -1)
    nc = sum(1 for x in diff if x == 1)
    p = mcnemar_exact(nb, nc)
    alpha = float(policy["aggregate_alpha"])
    headline = "GO" if delta > 0 else "NO-GO"
    basic = "GO" if (p < alpha and delta > 0) else ("NO-GO" if (p < alpha and delta < 0) else "HOLD")
    res = analyze(ds, CANDIDATE, B, SIM_BOOT_SEED + i)
    flagged = flagged_names(res)
    return {
        "id": i, "scale": spec["scale"], "n_items": n, "v_out": spec["v_out"], "spike_b": spec["spike_b"],
        "truth_bad": truth["bad"], "problems": truth["problems"], "regressed_slices": truth["regressed_slices"],
        "true_cost_ratio": truth["cost_ratio"], "true_p95_ratio": truth["p95_ratio"],
        "headline_delta": delta, "mcnemar_p": p,
        "headline": headline, "basic": basic, "swapbrief": res["decision"],
        "flagged": sorted(flagged),
        "inconclusive": [r["slice"] for r in res["inconclusive"]],
        "slice_status": {r["slice"]: r["status"] for r in res["slices"]},
        "cost_status": res["cost"]["status"], "p95_status": res["latency"]["status"],
    }


def score_rules(records: list) -> dict:
    """False-GO, missed-regression and bad-migration rates for the three rules.

    Definitions (all against the generator's injected truth):
      false-GO          the rule said plain GO and the migration had at least one real problem
      bad migration     shipped with a real problem the rule did not flag: a plain GO on a bad
                        migration, or GO WITH GUARDRAILS that left a real problem unflagged
      missed regression a truly regressed slice that shipped while the rule called it fine
                        (OK or IMPROVED). Slices SwapBrief marked inconclusive are counted
                        separately as unresolved: the known limit.
    """
    n = len(records)
    bad = [r for r in records if r["truth_bad"]]
    good = [r for r in records if not r["truth_bad"]]
    total_reg = sum(len(r["regressed_slices"]) for r in records)
    out = {}
    for rule in ("headline", "basic", "swapbrief"):
        false_go = bad_shipped = 0
        missed = unresolved = flagged_reg = blocked_reg = 0
        missed_cost = missed_p95 = 0
        good_blocked = good_guarded = good_go = 0
        for r in records:
            d = r[rule]
            shipped = d in ("GO", "GO WITH GUARDRAILS")
            flagged = set(r["flagged"]) if rule == "swapbrief" else set()
            uncovered = [p for p in r["problems"] if p not in flagged]
            if r["truth_bad"] and d == "GO":
                false_go += 1
            if r["truth_bad"] and (d == "GO" or (d == "GO WITH GUARDRAILS" and uncovered)):
                bad_shipped += 1
            for sl in r["regressed_slices"]:
                if not shipped:
                    blocked_reg += 1
                elif rule != "swapbrief":
                    missed += 1
                else:
                    st = r["slice_status"][sl]
                    if st in ("OK", "IMPROVED"):
                        missed += 1
                    elif st == "INCONCLUSIVE":
                        unresolved += 1
                    else:
                        flagged_reg += 1
            if shipped and "cost" in r["problems"] and "cost" not in flagged:
                missed_cost += 1
            if shipped and "p95" in r["problems"] and "p95" not in flagged:
                missed_p95 += 1
            if not r["truth_bad"]:
                if not shipped:
                    good_blocked += 1
                elif d == "GO WITH GUARDRAILS":
                    good_guarded += 1
                else:
                    good_go += 1
        out[rule] = {
            "false_go": false_go, "false_go_rate": false_go / len(bad) if bad else 0.0,
            "bad_shipped": bad_shipped, "bad_migration_rate": bad_shipped / n,
            "missed_regressions": missed, "missed_regression_rate": missed / total_reg if total_reg else 0.0,
            "unresolved_regressions": unresolved, "unresolved_rate": unresolved / total_reg if total_reg else 0.0,
            "flagged_regressions": flagged_reg, "blocked_regressions": blocked_reg,
            "missed_cost_problems": missed_cost, "missed_p95_problems": missed_p95,
            "good_blocked": good_blocked, "good_blocked_rate": good_blocked / len(good) if good else 0.0,
            "good_guarded": good_guarded, "good_guarded_rate": good_guarded / len(good) if good else 0.0,
            "good_go": good_go, "good_go_rate": good_go / len(good) if good else 0.0,
            "decisions": {k: sum(1 for r in records if r[rule] == k)
                          for k in ("GO", "GO WITH GUARDRAILS", "NO-GO", "HOLD")},
        }
    by_scale = []
    for k in sorted({r["scale"] for r in records}):
        rs = [r for r in records if r["scale"] == k]
        regs = sum(len(r["regressed_slices"]) for r in rs)
        sw_missed = sw_unres = 0
        for r in rs:
            if r["swapbrief"] == "NO-GO":
                continue
            for sl in r["regressed_slices"]:
                st = r["slice_status"][sl]
                if st in ("OK", "IMPROVED"):
                    sw_missed += 1
                elif st == "INCONCLUSIVE":
                    sw_unres += 1
        by_scale.append({
            "scale": k, "n_items": rs[0]["n_items"], "n_scenarios": len(rs),
            "swapbrief_go": sum(1 for r in rs if r["swapbrief"] == "GO"),
            "swapbrief_guardrails": sum(1 for r in rs if r["swapbrief"] == "GO WITH GUARDRAILS"),
            "swapbrief_nogo": sum(1 for r in rs if r["swapbrief"] == "NO-GO"),
            "true_regressed_slices": regs, "missed": sw_missed, "unresolved": sw_unres,
            "false_go": sum(1 for r in rs if r["truth_bad"] and r["swapbrief"] == "GO"),
            "bad": sum(1 for r in rs if r["truth_bad"]),
        })
    return {"n_scenarios": n, "n_bad": len(bad), "n_good": len(good), "total_true_regressed_slices": total_reg,
            "rules": out, "by_scale": by_scale}


def run_scenarios(n: int = gen.N_SCENARIOS, policy: dict | None = None, progress: bool = False,
                  mix: float = 1.0) -> list:
    if policy is None:
        policy = load_dataset()["policy"]
    records = []
    for i in range(1, n + 1):
        records.append(scenario_record(i, policy, B_SIM, mix))
        if progress and i % 50 == 0:
            print("  ... %d / %d scenarios" % (i, n))
    return records


def scenario_dataset(i: int, policy: dict, mix: float = 1.0) -> tuple:
    """(dataset, truth) for simulated scenario i; the same draw the 200-scenario test used."""
    spec = gen.scenario_spec(i, mix)
    sim = gen.simulate(spec, SIM_DATA_SEED + i)
    return dataset_from_sim(sim, policy), gen.scenario_truth(spec)


def build_view(ds: dict, B: int, seed: int, truth: dict | None, basic_seed: int | None = None) -> dict:
    """Everything the app and the demo show for one scenario."""
    basic_seed = seed if basic_seed is None else basic_seed
    return {
        "n_items": len(ds["slice_idx"]),
        "headline": headline_rule(ds, CANDIDATE),
        "headline_old": headline_rule(ds, "B_old_prompt"),
        "basic": aggregate_rule(ds, CANDIDATE, B, basic_seed),
        "basic_old": aggregate_rule(ds, "B_old_prompt", B, basic_seed),
        "fair": prompt_fair(ds, B, seed),
        "truth": truth,
    }


def committed_truth() -> dict:
    spec = gen.committed_spec()
    return {
        "regressed_slices": [s["name"] for s in spec["slices"] if s["d_new"] <= -gen.TRUE_REGRESSION_PP],
        "old_prompt_only": [s["name"] for s in spec["slices"] if s["d_old"] < 0 <= s["d_new"]],
        "cost_ratio": gen.true_cost_ratio(spec), "p95_ratio": gen.true_p95_ratio(spec),
    }


def committed_view(ds: dict | None = None) -> dict:
    ds = ds or load_dataset()
    return build_view(ds, B_MAIN, BOOT_SEED, committed_truth(), AGG_SEED)


def scenario_view(i: int, policy: dict) -> dict:
    ds, truth = scenario_dataset(i, policy)
    return build_view(ds, B_SIM, SIM_BOOT_SEED + i, truth)


def verify_curated(records: list) -> list:
    """True for each curated scenario whose record still matches its label."""
    by_id = {r["id"]: r for r in records}
    out = []
    for i, _ in CURATED:
        r = by_id[i]
        unc = [p for p in r["problems"] if p not in r["flagged"]]
        checks = {
            11: r["headline"] == "GO" and r["swapbrief"] == "NO-GO" and r["truth_bad"],
            3: r["swapbrief"] == "GO WITH GUARDRAILS" and r["problems"] == ["cost"] and "cost" in r["flagged"],
            4: r["swapbrief"] == "GO" and not r["truth_bad"],
            107: (r["swapbrief"] == "GO" and "slice:long_answers" in r["problems"]
                  and r["slice_status"]["long_answers"] == "INCONCLUSIVE"),
            22: r["swapbrief"] == "GO" and r["truth_bad"] and len(unc) > 0,
            1: r["swapbrief"] == "GO WITH GUARDRAILS" and not r["truth_bad"],
        }
        out.append(bool(checks[i]))
    return out


def inconclusive_counts(records: list) -> dict:
    """How often each slice was inconclusive across the scenarios (the known limit, by slice)."""
    counts = {}
    for r in records:
        for sl, st in r["slice_status"].items():
            if st == "INCONCLUSIVE":
                counts[sl] = counts.get(sl, 0) + 1
    return counts


def utility(scores: dict) -> dict:
    head = scores["rules"]["headline"]["bad_migration_rate"]
    swap = scores["rules"]["swapbrief"]["bad_migration_rate"]
    return {"headline_rate": head, "swapbrief_rate": swap, "gap": head - swap,
            "migrations_per_year": MIGRATIONS_PER_YEAR, "avoided_per_year": (head - swap) * MIGRATIONS_PER_YEAR}


SENS_MIX = (0.5, 2.0)   # how often real problems occur, relative to the base mix: half and double
SENS_N = 100


def run_sensitivity(policy: dict) -> list:
    """Same rules, same seeds, real problems half as common and twice as common."""
    rows = []
    for m in SENS_MIX:
        recs = run_scenarios(SENS_N, policy, False, m)
        sc = score_rules(recs)
        rules = sc["rules"]
        rows.append({
            "mix": m, "p_regress": gen.P_REGRESS * m, "n_scenarios": SENS_N, "n_bad": sc["n_bad"],
            "headline_rate": rules["headline"]["bad_migration_rate"],
            "swapbrief_rate": rules["swapbrief"]["bad_migration_rate"],
            "headline_false_go": rules["headline"]["false_go_rate"],
            "swapbrief_false_go": rules["swapbrief"]["false_go_rate"],
            "avoided_per_year": (rules["headline"]["bad_migration_rate"] - rules["swapbrief"]["bad_migration_rate"])
            * MIGRATIONS_PER_YEAR,
        })
    return rows


# ---------------------------------------------------------------------------
# The brief as text (printed here, downloadable from the app)
# ---------------------------------------------------------------------------
def brief_markdown(fair: dict, title: str = "SwapBrief decision brief") -> str:
    res = fair["retuned"]
    old = fair["old"]
    lines = ["# %s" % title, "",
             "Simulated evaluation results. No real model was measured.", "",
             "**Decision, model B with the retuned prompt: %s**" % res["decision"],
             "**Decision, model B with A's old prompt: %s**" % old["decision"], ""]
    lines.append("## Why")
    lines += ["- " + x for x in res["reasons"]]
    lines += ["", "## Slices (paired bootstrap 95% interval, B retuned minus A)", "",
              "| slice | severity | n | A | B | change | interval | status |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in res["slices"]:
        lines.append("| %s | %s | %d | %.1f%% | %.1f%% | %+.1f pp | %+.1f to %+.1f | %s |" % (
            r["slice"], r["severity"], r["n"], r["acc_a"] * 100, r["acc_b"] * 100, r["delta"] * 100,
            r["lo"] * 100, r["hi"] * 100, r["status"]))
    c, l = res["cost"], res["latency"]
    lines += ["", "## Cost and latency", "",
              "- Cost per correct answer: $%.5f (A) to $%.5f (B), %+.1f%%, interval %+.1f%% to %+.1f%%" % (
                  c["cpc_a"], c["cpc_b"], (c["ratio"] - 1) * 100, (c["lo"] - 1) * 100, (c["hi"] - 1) * 100),
              "- p50 latency: %.0f ms to %.0f ms, %+.1f%%, interval %+.1f%% to %+.1f%%" % (
                  l["p50_a"], l["p50_b"], (l["p50_ratio"] - 1) * 100, (l["p50_lo"] - 1) * 100, (l["p50_hi"] - 1) * 100),
              "- p95 latency: %.0f ms to %.0f ms, %+.1f%%, interval %+.1f%% to %+.1f%%" % (
                  l["p95_a"], l["p95_b"], (l["p95_ratio"] - 1) * 100, (l["p95_lo"] - 1) * 100, (l["p95_hi"] - 1) * 100)]
    lines += ["", "## Rollback triggers", "", "| metric | threshold | window | min scored responses | action |",
              "| --- | --- | --- | --- | --- |"]
    for t in res["triggers"]:
        lines.append("| %s | %s | %s | %s | %s |" % (t["metric"], t["threshold_text"], t["window"],
                                                      t["min_sample"] or "n/a", t["action"]))
    lines += ["", "## Known limit", ""]
    if res["inconclusive"]:
        lines.append("Slices with too few items to resolve (inconclusive): " + ", ".join(
            "%s (%d items)" % (r["slice"], r["n"]) for r in res["inconclusive"]) + ".")
    else:
        lines.append("No slice is inconclusive in this scenario.")
    return "\n".join(lines) + "\n"


def prompt_fair(ds: dict, B: int = B_MAIN, seed: int = BOOT_SEED) -> dict:
    return {"old": analyze(ds, "B_old_prompt", B, seed), "retuned": analyze(ds, CANDIDATE, B, seed)}


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------
def run(progress: bool = False, sensitivity: bool = False) -> dict:
    ds = load_dataset()
    fair = prompt_fair(ds)
    replay = replay_production(ds)
    fired = first_firing_week(fair["retuned"]["triggers"], replay)
    records = run_scenarios(policy=ds["policy"], progress=progress)
    scores = score_rules(records)
    out = {"fair": fair, "replay": replay, "fired": fired, "records": records, "scores": scores,
           "utility": utility(scores), "inconclusive_counts": inconclusive_counts(records),
           "curated_ok": verify_curated(records)}
    if sensitivity:
        out["sensitivity"] = run_sensitivity(ds["policy"])
    return out


def _pp(x: float) -> str:
    return "%+.1f pp" % (x * 100)


def print_brief(res: dict, old: dict) -> None:
    print("DECISION (model B, retuned prompt):   %s" % res["decision"])
    print("DECISION (model B, A's old prompt):   %s" % old["decision"])
    print("\nWhy, retuned prompt:")
    for x in res["reasons"]:
        print("  - " + x)
    print("Why, A's old prompt:")
    for x in old["reasons"]:
        print("  - " + x)

    print("\nSlices, B retuned minus A, paired bootstrap 95%% interval (%d resamples, stratified by slice):" % res["bootstrap_resamples"])
    print("  %-22s %-8s %4s %6s %6s %9s   %-17s %s" % ("slice", "severity", "n", "A", "B", "change", "interval (pp)", "status"))
    for r in res["slices"]:
        print("  %-22s %-8s %4d %5.1f%% %5.1f%% %9s   %+6.1f to %+6.1f    %s" % (
            r["slice"], r["severity"], r["n"], r["acc_a"] * 100, r["acc_b"] * 100, _pp(r["delta"]),
            r["lo"] * 100, r["hi"] * 100, r["status"]))
    print("\nSame slices with A's old prompt on model B:")
    for r in old["slices"]:
        print("  %-22s change %9s   interval %+6.1f to %+6.1f    %s" % (
            r["slice"], _pp(r["delta"]), r["lo"] * 100, r["hi"] * 100, r["status"]))

    c, l = res["cost"], res["latency"]
    print("\nCost per correct answer:  $%.5f -> $%.5f   %+.1f%%   interval %+.1f%% to %+.1f%%   %s" % (
        c["cpc_a"], c["cpc_b"], (c["ratio"] - 1) * 100, (c["lo"] - 1) * 100, (c["hi"] - 1) * 100, c["status"]))
    print("p50 latency:              %5.0f ms -> %5.0f ms   %+.1f%%   interval %+.1f%% to %+.1f%%" % (
        l["p50_a"], l["p50_b"], (l["p50_ratio"] - 1) * 100, (l["p50_lo"] - 1) * 100, (l["p50_hi"] - 1) * 100))
    print("p95 latency:              %5.0f ms -> %5.0f ms   %+.1f%%   interval %+.1f%% to %+.1f%%   %s" % (
        l["p95_a"], l["p95_b"], (l["p95_ratio"] - 1) * 100, (l["p95_lo"] - 1) * 100, (l["p95_hi"] - 1) * 100, l["status"]))

    print("\nRollback triggers for the retuned prompt (metric | threshold | window | min scored responses):")
    for t in res["triggers"]:
        print("  - %-34s %-24s %-28s %s" % (t["metric"], t["threshold_text"], t["window"], t["min_sample"] or "n/a"))
        print("      %s" % t["why"])


def main() -> None:
    print("\n" + "=" * 80)
    print("Step 4 - The fix: SwapBrief")
    print("=" * 80)
    print("SIMULATED results from a seeded generator (data/_generate.py). No model was called.\n")
    print("Running 200 simulated migration scenarios (about 40 seconds) ...")
    out = run(progress=True, sensitivity=True)
    fair, scores, util = out["fair"], out["scores"], out["utility"]
    res = fair["retuned"]
    print()
    print_brief(res, fair["old"])

    print("\nProduction replay (the same %d-week simulated traffic as step 3; slip at week %d in %s):" % (
        len(out["replay"]), REPLAY_SLIP_WEEK, REPLAY_SLIP_SLICE))
    if out["fired"]:
        for sl, wk in sorted(out["fired"].items(), key=lambda kv: kv[1]):
            print("  trigger accuracy[%s] first fires in week %d" % (sl, wk))
    else:
        print("  no slice trigger fired")

    print("\nKNOWN LIMIT - slices with too few items stay inconclusive (committed set, retuned prompt):")
    if res["inconclusive"]:
        for r in res["inconclusive"]:
            truth = [t for t in gen.SLICES if t["name"] == r["slice"]][0]
            print("  %-22s %3d items  interval %+.1f to %+.1f pp  generator's true change %+.1f pp" % (
                r["slice"], r["n"], r["lo"] * 100, r["hi"] * 100, truth["d_new"] * 100))
    else:
        print("  none on this draw")
    print("  Across the %d scenarios, slices marked inconclusive (count of scenario-slices):" % scores["n_scenarios"])
    for sl, c in sorted(out["inconclusive_counts"].items(), key=lambda kv: -kv[1]):
        print("    %-22s %3d" % (sl, c))
    print("  Curated scenarios matching their labels: %d of %d" % (sum(out["curated_ok"]), len(out["curated_ok"])))

    print("\nDecision quality over %d seeded scenarios (%d with a real problem, %d without; %d truly regressed slices):" % (
        scores["n_scenarios"], scores["n_bad"], scores["n_good"], scores["total_true_regressed_slices"]))
    rules = scores["rules"]
    print("  %-40s %-17s %-17s %-10s" % ("", "headline average", "aggregate test", "SwapBrief"))

    def row(label, key):
        print("  %-40s %-17s %-17s %-10s" % (label, "%.1f%%" % (rules["headline"][key] * 100),
                                            "%.1f%%" % (rules["basic"][key] * 100), "%.1f%%" % (rules["swapbrief"][key] * 100)))
    row("false-GO rate (bad migration got GO)", "false_go_rate")
    row("missed-regression rate (slices)", "missed_regression_rate")
    row("bad-migration rate (all scenarios)", "bad_migration_rate")
    row("good migrations blocked or held", "good_blocked_rate")
    row("good migrations given guardrails", "good_guarded_rate")
    for label, key in (("headline", "headline"), ("aggregate", "basic"), ("SwapBrief", "swapbrief")):
        print("  decisions, %-10s %s" % (label + ":", rules[key]["decisions"]))
    sw = rules["swapbrief"]
    print("  SwapBrief on true slice regressions (%d): blocked %d, flagged %d, unresolved (inconclusive) %d, missed %d." % (
        scores["total_true_regressed_slices"], sw["blocked_regressions"], sw["flagged_regressions"],
        sw["unresolved_regressions"], sw["missed_regressions"]))
    print("  SwapBrief missed cost problems: %d, missed p95 problems: %d." % (sw["missed_cost_problems"], sw["missed_p95_problems"]))
    print("  By evaluation size (items, scenarios, GO / GUARDRAILS / NO-GO, true regressed slices, unresolved, missed):")
    for b in scores["by_scale"]:
        print("    %5d items  %3d scenarios   %3d / %3d / %3d   %3d   %3d   %3d" % (
            b["n_items"], b["n_scenarios"], b["swapbrief_go"], b["swapbrief_guardrails"], b["swapbrief_nogo"],
            b["true_regressed_slices"], b["unresolved"], b["missed"]))

    print("\nSensitivity to the scenario mix (how often real problems occur is an assumption of the simulation):")
    print("  %-34s %9s %12s %10s %10s %12s" % ("mix of problems", "scenarios", "with problem", "headline", "SwapBrief", "avoided/yr"))
    print("  %-34s %9d %12d %10s %10s %12.1f" % (
        "base (slice chance %.1f%%)" % (gen.P_REGRESS * 100), scores["n_scenarios"], scores["n_bad"],
        "%.1f%%" % (util["headline_rate"] * 100), "%.1f%%" % (util["swapbrief_rate"] * 100), util["avoided_per_year"]))
    for row_ in out["sensitivity"]:
        print("  %-34s %9d %12d %10s %10s %12.1f" % (
            "%.1fx base (slice chance %.1f%%)" % (row_["mix"], row_["p_regress"] * 100), row_["n_scenarios"], row_["n_bad"],
            "%.1f%%" % (row_["headline_rate"] * 100), "%.1f%%" % (row_["swapbrief_rate"] * 100), row_["avoided_per_year"]))
    print("  (headline and SwapBrief columns are bad-migration rates)")

    print("\nUtility = (headline bad-migration rate - SwapBrief bad-migration rate) x migrations per year")
    print("  headline bad-migration rate:  %.1f%%   (measured on the %d simulated scenarios)" % (util["headline_rate"] * 100, scores["n_scenarios"]))
    print("  SwapBrief bad-migration rate: %.1f%%   (measured on the same scenarios)" % (util["swapbrief_rate"] * 100))
    print("  migrations per year:          %d      (modeled assumption: 9 production GenAI features, each forced onto a successor about every 18 months)" % util["migrations_per_year"])
    print("  bad migrations avoided / yr:  %.1f" % util["avoided_per_year"])

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_results.json", "w") as f:
        json.dump({k: out[k] for k in ("fair", "fired", "scores", "utility", "sensitivity", "inconclusive_counts")}, f, indent=2)
    with open(OUT_DIR / "step_04_scenarios.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["scenario", "eval_items", "truth_bad", "problems", "headline", "aggregate_test", "swapbrief", "flagged"])
        for r in out["records"]:
            w.writerow([r["id"], r["n_items"], int(r["truth_bad"]), ";".join(r["problems"]), r["headline"], r["basic"],
                        r["swapbrief"], ";".join(r["flagged"])])
    with open(OUT_DIR / "step_04_triggers.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["metric", "threshold", "window", "min_sample", "action", "why"])
        for t in res["triggers"]:
            w.writerow([t["metric"], t["threshold_text"], t["window"], t["min_sample"], t["action"], t["why"]])
    print("\nwrote src/out/step_04_results.json, step_04_scenarios.csv, step_04_triggers.csv")


if __name__ == "__main__":
    main()
