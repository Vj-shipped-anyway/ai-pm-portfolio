"""Step 4 - The fix: AdoptionPulse.

AdoptionPulse reads the weekly AI usage that the login view never held and does five things:

  1. Stages every licensed user: licensed, activated, habitual, proficient (rules in
     data/funnel_policy.csv, assumptions of a modeled bank).
  2. Shows the funnel overall and by org unit, and where each unit leaks users between stages.
  3. Reads training and champion coverage against usage (training-to-usage conversion).
  4. Draws the retention curve: the share of activated users active in each week.
  5. Ranks the units to act on and attaches a rule-based action to each.

It is then scored against the stage the generator decided for each user (user_truth.csv).
The truth is known because the data is synthetic. There is no model in this step: the rules are
plain thresholds you can read. The recommended actions are rules, not tested interventions.

KNOWN LIMITS, left in on purpose and printed below:
  * Telemetry counts use, not value. Some users the rules call proficient produce poor work, and
    nothing in the weekly counts can show it.
  * "Proficient" is a proxy (advanced-feature use plus accepted-output rate).
  * The champion and training effects are true here only by construction: the generator planted
    them. The planted size is printed next to the measured one.

Run (from src/):
    python3 step_04_with_adoptionpulse.py

Output: a readable report, plus CSVs and out/step_04_summary.json in src/out/.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter

from step_01_license_counts_status_quo import (OUT_DIR, STAGE_RANK, STAGES, WEEKS, ever_logged_in, load_all,
                                               stage_of)
from step_02_login_adoption_baseline import summarize as summarize_step2

MODELED_POPULATION = 800                      # MODELED: licensed staff in the modeled bank
POPULATION_SENSITIVITY = [800, 2000, 5000]    # MODELED: alternative licensed populations
RETENTION_FROM_WEEK = 4                       # first week in which every user is licensed
TRANSITIONS = [("licensed to activated", "activated", "licensed"),
               ("activated to habitual", "habitual", "activated"),
               ("habitual to proficient", "proficient", "habitual")]
TYPE_ORDER = ["never", "one_time", "casual", "lapsed", "habitual", "proficient"]
TYPE_LABEL = {"never": "never used", "one_time": "tried once", "casual": "casual",
              "lapsed": "lapsed", "habitual": "habitual", "proficient": "proficient"}


def pct(a: float, b: float) -> float:
    return round(100 * a / b, 1) if b else 0.0


def rank(stage: str) -> int:
    return STAGE_RANK[stage]


def reached(stage_list: list, stage: str) -> int:
    return sum(1 for s in stage_list if rank(s) >= rank(stage))


def action_text(leak: str, champion: bool, users_lost: int) -> str:
    if leak == "licensed to activated":
        return (f"First-use gap: {users_lost} licensed users never started. "
                "Check access and run a first-week session.")
    if leak == "activated to habitual":
        if not champion:
            return (f"Users start and stop: {users_lost} activated users are not habitual and the unit has "
                    "no champion. Assign one (a hypothesis: the champion effect in this data is planted, not observed).")
        return (f"Users start and stop despite a champion: {users_lost} activated users are not habitual. "
                "Review what the champion runs and add coaching.")
    if leak == "habitual to proficient":
        return f"Weekly users without depth: coach advanced features for {users_lost} habitual users."
    return "No action: at or above the estate rate at every stage."


def analyze(data: dict | None = None) -> dict:
    data = data or load_all()
    users, use, policy, truth = data["users"], data["use"], data["policy"], data["truth"]
    n = len(users)
    min_gap = policy["leak_min_gap_points"]
    min_users = int(policy["leak_min_users"])
    stage = {u["user_id"]: stage_of(u, use[u["user_id"]], policy) for u in users}
    s2 = summarize_step2(data)
    login_by_unit = {r["unit"]: r for r in s2["units"]}

    # --- estate funnel ---
    stage_list = list(stage.values())
    funnel = {s: reached(stage_list, s) for s in STAGES}
    est_conv = {"activated": pct(funnel["activated"], funnel["licensed"]),
                "habitual": pct(funnel["habitual"], funnel["activated"]),
                "proficient": pct(funnel["proficient"], funnel["habitual"])}
    est_hab_rate = funnel["habitual"] / n

    # --- per-unit rows ---
    champs_by_unit = Counter(c["org_unit"] for c in data["champions"])
    rows = []
    for unit in data["units"]:
        us = data["by_unit"][unit]
        sl = [stage[u["user_id"]] for u in us]
        f = {s: reached(sl, s) for s in STAGES}
        conv = {"activated": pct(f["activated"], f["licensed"]), "habitual": pct(f["habitual"], f["activated"]),
                "proficient": pct(f["proficient"], f["habitual"])}
        entered = {"activated": f["licensed"], "habitual": f["activated"], "proficient": f["habitual"]}
        lost = {"activated": f["licensed"] - f["activated"], "habitual": f["activated"] - f["habitual"],
                "proficient": f["habitual"] - f["proficient"]}
        best_gap, leak, leak_to = 0.0, "", ""
        for label, to_stage, _from in TRANSITIONS:
            if entered[to_stage] < min_users:
                continue
            gap = conv[to_stage] - est_conv[to_stage]
            if gap < best_gap:
                best_gap, leak, leak_to = gap, label, to_stage
        if best_gap > -min_gap:
            leak, leak_to, best_gap = "", "", 0.0
        champion = us[0]["champion"]
        t_types = Counter(truth[u["user_id"]]["latent_type"] for u in us)
        t_stages = Counter(truth[u["user_id"]]["true_stage"] for u in us)
        correct = sum(1 for u in us if stage[u["user_id"]] == truth[u["user_id"]]["true_stage"])
        gain = max(0.0, est_hab_rate * len(us) - f["habitual"])
        login_cum, active_share = [], []
        for w in range(1, WEEKS + 1):
            lic_w = [u for u in us if u["licensed_week"] <= w]
            logged_w = [u for u in lic_w if sum(use[u["user_id"]]["logins"][:w]) > 0]
            act_w = [u for u in lic_w if use[u["user_id"]]["sessions"][w - 1] > 0]
            login_cum.append(pct(len(logged_w), len(lic_w)))
            active_share.append(pct(len(act_w), len(lic_w)))
        rows.append({
            "login_cum": login_cum, "active_share": active_share,
            "unit": unit, "licensed": f["licensed"], "activated": f["activated"], "habitual": f["habitual"],
            "proficient": f["proficient"], "activated_pct": pct(f["activated"], f["licensed"]),
            "habitual_pct": pct(f["habitual"], f["licensed"]), "conv_habitual_pct": conv["habitual"],
            "conv_proficient_pct": conv["proficient"], "champion": champion, "champions": champs_by_unit.get(unit, 0),
            "trained_pct": pct(sum(1 for u in us if u["trained_week"] is not None), len(us)),
            "logged_in": login_by_unit[unit]["logged_in"], "login_pct": login_by_unit[unit]["adoption_pct"],
            "gain": round(gain, 1), "leak": leak, "leak_gap_points": round(best_gap, 1),
            "leak_users": lost[leak_to] if leak else 0,
            "action": action_text(leak, champion, lost[leak_to] if leak else 0),
            "truth_types": {t: t_types.get(t, 0) for t in TYPE_ORDER},
            "truth_stages": {s: t_stages.get(s, 0) for s in STAGES},
            "correct": correct,
        })
    ranked = sorted(rows, key=lambda r: (-r["gain"], r["unit"]))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i if r["gain"] > 0 else None        # units with no users to gain are not ranked
    units_to_act = sum(1 for r in rows if r["gain"] > 0)

    # --- training to usage ---
    trained = [u for u in users if u["trained_week"] is not None]
    untrained = [u for u in users if u["trained_week"] is None]

    def group(g: list) -> dict:
        sl = [stage[u["user_id"]] for u in g]
        idle = sum(1 for u in g if sum(use[u["user_id"]]["sessions"]) == 0)
        return {"n": len(g), "activated": reached(sl, "activated"), "habitual": reached(sl, "habitual"),
                "proficient": reached(sl, "proficient"), "never_active": idle,
                "activated_pct": pct(reached(sl, "activated"), len(g)),
                "habitual_pct": pct(reached(sl, "habitual"), len(g)),
                "never_active_pct": pct(idle, len(g))}
    tr, un = group(trained), group(untrained)
    training = {"trained": tr, "untrained": un,
                "measured_gap_points": round(tr["habitual_pct"] - un["habitual_pct"], 1),
                "planted_gap_points": float(data["planted"]["training_completed"]["planted_gap_points"]),
                "planted_logit": float(data["planted"]["training_completed"]["planted_logit_shift"])}

    # --- champion coverage ---
    wc = group([u for u in users if u["champion"]])
    nc = group([u for u in users if not u["champion"]])
    ch_weeks = [c["active_weeks"] for c in data["champions"]]
    ut_rows = data["unit_truth"]

    def appetite(champ_flag: bool) -> float:
        sel = [r for r in ut_rows.values() if (r["champion_in_unit"] == "yes") == champ_flag]
        return round(sum(float(r["appetite_logit"]) * int(r["licensed"]) for r in sel)
                     / sum(int(r["licensed"]) for r in sel), 2)

    champion = {"appetite_champion": appetite(True), "appetite_other": appetite(False),
                "units_with": sum(1 for r in rows if r["champion"]), "units": len(rows),
                "champions": len(data["champions"]), "with": wc, "without": nc,
                "median_active_weeks": statistics.median(ch_weeks),
                "per_100_users": round(100 * len(data["champions"]) / wc["n"], 1),
                "measured_gap_points": round(wc["habitual_pct"] - nc["habitual_pct"], 1),
                "planted_gap_points": float(data["planted"]["champion_in_unit"]["planted_gap_points"]),
                "planted_logit": float(data["planted"]["champion_in_unit"]["planted_logit_shift"])}

    # --- retention curve among the activated ---
    act_users = [u for u in users if rank(stage[u["user_id"]]) >= rank("activated")]
    base = {r["week"]: r for r in s2["weekly"]}
    free_week = max(u["licensed_week"] for u in users) + int(policy["activation_window_weeks"])
    retention = []
    for w in range(RETENTION_FROM_WEEK, WEEKS + 1):
        a = sum(1 for u in act_users if use[u["user_id"]]["sessions"][w - 1] > 0)
        retention.append({"week": w, "activated_active": a, "activated_pct": pct(a, len(act_users)),
                          "login_view_pct": base[w]["adoption_pct"]})

    # --- scored against the generator's truth ---
    true_stage = {u["user_id"]: truth[u["user_id"]]["true_stage"] for u in users}
    ap_correct = sum(1 for uid in stage if stage[uid] == true_stage[uid])
    confusion = {t: {s: 0 for s in STAGES} for t in STAGES}
    for uid in stage:
        confusion[true_stage[uid]][stage[uid]] += 1
    adopter = {uid: rank(true_stage[uid]) >= rank("habitual") for uid in stage}
    base_as_reported = sum(1 for u in users if ever_logged_in(use[u["user_id"]]) == adopter[u["user_id"]])
    ap_binary = sum(1 for uid in stage if (rank(stage[uid]) >= rank("habitual")) == adopter[uid])
    best_case, mapping = 0, {}
    for flag in (True, False):
        grp = Counter(true_stage[u["user_id"]] for u in users if ever_logged_in(use[u["user_id"]]) == flag)
        top = max(STAGES, key=lambda s: (grp.get(s, 0), -rank(s)))
        mapping[flag] = {"stage": top, "correct": grp.get(top, 0), "n": sum(grp.values())}
        best_case += grp.get(top, 0)
    under = sum(1 for uid in stage if rank(stage[uid]) < rank(true_stage[uid]))
    over = sum(1 for uid in stage if rank(stage[uid]) > rank(true_stage[uid]))
    by_type = []
    for t in TYPE_ORDER:
        ids = [uid for uid in stage if truth[uid]["latent_type"] == t]
        ok = sum(1 for uid in ids if stage[uid] == true_stage[uid])
        by_type.append({"type": t, "n": len(ids), "correct": ok, "correct_pct": pct(ok, len(ids))})
    nest_violations = sum(1 for u in users if rank(stage[u["user_id"]]) >= rank("habitual")
                          and not any(use[u["user_id"]]["sessions"][w - 1] > 0
                                      for w in range(u["licensed_week"],
                                                     min(WEEKS, u["licensed_week"] + int(policy["activation_window_weeks"]) - 1) + 1)))

    # --- known limit: telemetry counts use, not value ---
    prof_ids = [uid for uid in stage if stage[uid] == "proficient"]
    poor = [uid for uid in prof_ids if truth[uid]["work_quality"] == "poor"]
    true_prof = [uid for uid in stage if true_stage[uid] == "proficient"]
    true_hab = [uid for uid in stage if true_stage[uid] == "habitual"]
    limit = {"rule_proficient": len(prof_ids), "rule_proficient_poor": len(poor),
             "rule_proficient_poor_pct": pct(len(poor), len(prof_ids)),
             "true_proficient": len(true_prof),
             "true_proficient_staged_proficient": sum(1 for uid in true_prof if stage[uid] == "proficient"),
             "true_proficient_staged_habitual": sum(1 for uid in true_prof if stage[uid] == "habitual"),
             "true_proficient_staged_lower": sum(1 for uid in true_prof if rank(stage[uid]) < rank("habitual")),
             "true_habitual": len(true_hab),
             "true_habitual_staged_proficient": sum(1 for uid in true_hab if stage[uid] == "proficient"),
             "true_habitual_staged_activated": sum(1 for uid in true_hab if stage[uid] == "activated")}

    # --- utility ---
    ap_share, base_share = ap_correct / n, best_case / n
    utility = {"ap_share_pct": pct(ap_correct, n), "baseline_share_pct": pct(best_case, n),
               "delta_points": round(100 * (ap_share - base_share), 1),
               "modeled_population": MODELED_POPULATION,
               "utility_users": round((ap_share - base_share) * MODELED_POPULATION),
               "sensitivity": {str(p): round((ap_share - base_share) * p) for p in POPULATION_SENSITIVITY}}

    summary = {
        "licensed": n, "units": len(rows), "funnel": funnel, "est_conv": est_conv,
        "habitual_pct": pct(funnel["habitual"], n), "proficient_pct": pct(funnel["proficient"], n),
        "activated_pct": pct(funnel["activated"], n),
        "reported_pct": s2["overall_pct"], "reported_logged": s2["overall_logged"],
        "best_unit": ranked[0]["unit"],
        "units_to_act": units_to_act, "nest_violations": nest_violations,
        "ap_correct": ap_correct, "ap_correct_pct": pct(ap_correct, n),
        "ap_binary": ap_binary, "ap_binary_pct": pct(ap_binary, n),
        "base_as_reported": base_as_reported, "base_as_reported_pct": pct(base_as_reported, n),
        "base_best": best_case, "base_best_pct": pct(best_case, n),
        "base_mapping": {("logged in" if k else "never logged in"): v for k, v in mapping.items()},
        "understaged": under, "overstaged": over,
        "training": training, "champion": champion, "limit": limit, "utility": utility,
        "retention_wk_from": retention[0], "retention_wk_last": retention[-1],
        "retention_free_week": next(r for r in retention if r["week"] == free_week),
        "retention_activated": len(act_users),
    }
    return {"data": data, "stage": stage, "rows": rows, "ranked": ranked, "retention": retention,
            "confusion": confusion, "by_type": by_type, "summary": summary,
            "hab_rates": sorted(r["habitual_pct"] for r in rows)}


def write_outputs(a: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "step_04_funnel_by_unit.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["unit", "licensed", "activated", "habitual", "proficient", "habitual_pct", "champion",
                    "trained_pct", "login_pct", "gain", "leak", "leak_users", "leak_gap_points", "action"])
        for r in a["ranked"]:
            w.writerow([r["unit"], r["licensed"], r["activated"], r["habitual"], r["proficient"],
                        r["habitual_pct"], "yes" if r["champion"] else "no", r["trained_pct"], r["login_pct"],
                        r["gain"], r["leak"], r["leak_users"], r["leak_gap_points"], r["action"]])
    with open(OUT_DIR / "step_04_unit_weekly.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["unit", "week", "login_view_cumulative_pct", "licensed_with_ai_session_pct"])
        for r in a["rows"]:
            for i in range(WEEKS):
                w.writerow([r["unit"], i + 1, r["login_cum"][i], r["active_share"][i]])
    with open(OUT_DIR / "step_04_retention.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["week", "activated_active", "activated_pct", "login_view_pct"])
        for r in a["retention"]:
            w.writerow([r["week"], r["activated_active"], r["activated_pct"], r["login_view_pct"]])
    with open(OUT_DIR / "step_04_confusion.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["true_stage"] + STAGES)
        for t in STAGES:
            w.writerow([t] + [a["confusion"][t][s] for s in STAGES])
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(a["summary"], f, indent=2, default=str)


def main() -> None:
    a = analyze()
    s = a["summary"]
    write_outputs(a)
    fn, ec = s["funnel"], s["est_conv"]
    tr, ch, lim, ut = s["training"], s["champion"], s["limit"], s["utility"]

    print("\n" + "=" * 78)
    print("Step 4 - AdoptionPulse: stage, unit, week")
    print("=" * 78)
    print(f"\nNo model is used in this step. Stages come from the rules in data/funnel_policy.csv.")
    print(f"Users habitual by the rules but not activated (should be 0): {s['nest_violations']}.\n")

    print("THE FUNNEL (all licensed users)")
    print(f"  {'stage':<11} {'users':>6} {'share of licensed':>18} {'conversion from previous':>26}")
    prev = None
    for st in STAGES:
        conv = "" if prev is None else f"{pct(fn[st], fn[prev])}%"
        print(f"  {st:<11} {fn[st]:>6} {pct(fn[st], s['licensed']):>17.1f}% {conv:>26}".rstrip())
        prev = st

    print("\nFUNNEL BY ORG UNIT (ranked: habitual users gained if the unit matched the estate rate)")
    print(f"  {'#':>2} {'unit':<22} {'lic':>4} {'act':>4} {'hab':>4} {'prof':>4} {'hab%':>6} {'champ':>5} {'train%':>6} {'gain':>5}")
    for r in a["ranked"]:
        print(f"  {(str(r['rank']) if r['rank'] else '-'):>2} {r['unit']:<22} {r['licensed']:>4} {r['activated']:>4} {r['habitual']:>4} "
              f"{r['proficient']:>4} {r['habitual_pct']:>5.1f}% {'yes' if r['champion'] else 'no':>5} "
              f"{r['trained_pct']:>5.1f}% {r['gain']:>5.1f}")

    print(f"\n  Units with habitual users to gain: {s['units_to_act']} of {s['units']}")

    print("\nUNITS TO ACT ON (leak = the stage conversion furthest below the estate rate, at least "
          f"{a['data']['policy']['leak_min_gap_points']:.0f} points)")
    for r in a["ranked"][:6]:
        print(f"  {r['rank']}. {r['unit']} ({r['licensed']} users, {r['habitual_pct']}% habitual, gain {r['gain']} users)")
        print(f"     leak: {r['leak'] or 'none'}" + (f" ({r['leak_gap_points']} points)" if r['leak'] else ""))
        print(f"     action: {r['action']}")

    print("\nTRAINING TO USAGE")
    print(f"  Trained   {tr['trained']['n']:>3}: activated {tr['trained']['activated_pct']}%, habitual {tr['trained']['habitual_pct']}%, "
          f"never active {tr['trained']['never_active']} ({tr['trained']['never_active_pct']}%)")
    print(f"  Untrained {tr['untrained']['n']:>3}: activated {tr['untrained']['activated_pct']}%, habitual {tr['untrained']['habitual_pct']}%, "
          f"never active {tr['untrained']['never_active']} ({tr['untrained']['never_active_pct']}%)")
    print(f"  Planted effect (logit +{tr['planted_logit']:.2f}): +{tr['planted_gap_points']} points in the chance of becoming habitual, averaged over trained users.")
    print(f"  Measured gap in habitual rate: {tr['measured_gap_points']} points. True here by construction; real data would be confounded.")

    print("\nCHAMPION COVERAGE")
    print(f"  {ch['units_with']} of {ch['units']} units have a champion; {ch['champions']} champions "
          f"({ch['per_100_users']} per 100 users in those units), median {ch['median_active_weeks']} active weeks of {WEEKS}.")
    print(f"  With a champion {ch['with']['n']:>3}: habitual {ch['with']['habitual_pct']}%   Without {ch['without']['n']:>3}: habitual {ch['without']['habitual_pct']}%")
    print(f"  Planted effect (logit +{ch['planted_logit']:.2f}): +{ch['planted_gap_points']} points in the chance of becoming habitual, averaged over users in champion units.")
    print(f"  Hidden unit appetite the generator drew (logit, size-weighted mean): champion units {ch['appetite_champion']:.2f}, other units {ch['appetite_other']:.2f}.")
    print(f"  Measured gap: {ch['measured_gap_points']} points. It differs from the planted effect because unit appetite is not balanced across the two groups; with 20 units it cannot be.")

    print(f"\nRETENTION CURVE (activated users with an AI session in the week; {s['retention_activated']} activated users)")
    print(f"  {'week':>4} {'active':>7} {'share':>7} {'login view':>11}")
    for r in a["retention"]:
        print(f"  {r['week']:>4} {r['activated_active']:>7} {r['activated_pct']:>6.1f}% {r['login_view_pct']:>10.1f}%")
    fw = s["retention_free_week"]
    print(f"  Weeks before {fw['week']} are partly set by the activation rule (activated means a session in the first two weeks);")
    print(f"  from week {fw['week']} the curve is free of that effect: {fw['activated_pct']}% in week {fw['week']}, "
          f"{s['retention_wk_last']['activated_pct']}% in week {WEEKS}.")

    print("\nMEASURED AGAINST THE GENERATOR'S TRUTH (user_truth.csv; no rule reads it)")
    print(f"  AdoptionPulse stage correct:            {s['ap_correct']} of {s['licensed']} ({s['ap_correct_pct']}%)")
    print(f"  Wrong: {s['understaged']} staged too low, {s['overstaged']} staged too high")
    print(f"  Login view as reported (logged in = adopted), adopter or not: {s['base_as_reported']} of {s['licensed']} ({s['base_as_reported_pct']}%)")
    print(f"  AdoptionPulse, same adopter-or-not question:                  {s['ap_binary']} of {s['licensed']} ({s['ap_binary_pct']}%)")
    print(f"  Login flag mapped to four stages with hindsight (best case):  {s['base_best']} of {s['licensed']} ({s['base_best_pct']}%)")
    for k, v in s["base_mapping"].items():
        print(f"     {k:<16} -> {v['stage']:<10} ({v['correct']} of {v['n']})")
    print("  Confusion matrix (rows: generator's stage, columns: AdoptionPulse stage)")
    print(f"  {'':<11}" + "".join(f"{st:>11}" for st in STAGES))
    for t in STAGES:
        print(f"  {t:<11}" + "".join(f"{a['confusion'][t][st]:>11}" for st in STAGES))
    print("  Accuracy by the generator's latent user type")
    for r in a["by_type"]:
        print(f"     {TYPE_LABEL[r['type']]:<11} {r['n']:>4} users, {r['correct']:>4} staged correctly ({r['correct_pct']}%)")
    print("  Agreement between the rules and the generator's types holds partly by construction: the generator's")
    print("  behavior was written around the same thresholds. Read it as a property of this synthetic set.")

    print("\nKNOWN LIMIT (left in on purpose)")
    print(f"  Telemetry counts use, not value. {lim['rule_proficient_poor']} of {lim['rule_proficient']} users the rules call proficient "
          f"({lim['rule_proficient_poor_pct']}%) produce poor work in the generator,")
    print("  and nothing in the weekly counts can show it. Work quality is independent of the counts by design.")
    print(f"  'Proficient' is a proxy. Of {lim['true_proficient']} proficient-type users, {lim['true_proficient_staged_proficient']} are staged proficient, "
          f"{lim['true_proficient_staged_habitual']} habitual, {lim['true_proficient_staged_lower']} lower.")
    print(f"  Of {lim['true_habitual']} habitual-type users, {lim['true_habitual_staged_proficient']} are staged proficient and "
          f"{lim['true_habitual_staged_activated']} are staged only activated (active in fewer than 4 of the last 6 weeks).")
    print(f"  The champion gap ({ch['measured_gap_points']} measured, {ch['planted_gap_points']} planted) and the training gap "
          f"({tr['measured_gap_points']} measured, {tr['planted_gap_points']} planted) are true by construction.")

    print("\nUTILITY (share of licensed users correctly staged)")
    print(f"  AdoptionPulse: {ut['ap_share_pct']}%   Login view, best case with hindsight: {ut['baseline_share_pct']}%   Delta: {ut['delta_points']} points")
    print(f"  MODELED: {ut['modeled_population']} licensed staff in scope (assumption: the modeled bank's full license count;")
    print("           assumes the staging accuracy measured on this synthetic set holds on real telemetry)")
    print(f"  Utility = ({ut['ap_share_pct']}% - {ut['baseline_share_pct']}%) x {ut['modeled_population']} = about "
          f"{ut['utility_users']} users correctly staged")
    print("  Sensitivity to the licensed population: " +
          ", ".join(f"{int(k):,}: {v:,}" for k, v in ut["sensitivity"].items()))
    print("\nWrote step_04_funnel_by_unit.csv, step_04_unit_weekly.csv, step_04_retention.csv,")
    print("      step_04_confusion.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
