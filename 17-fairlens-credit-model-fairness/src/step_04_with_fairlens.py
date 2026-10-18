"""Step 4 - The fix: the FairLens test pack.

Six tests, one for each deficiency in step 3, each returning PASS, REVIEW or FAIL with the
numbers behind it:

  T1  Group approval gap          approval rate by group and the spread in points
  T2  AIR by group                adverse impact ratio per group, with a bootstrap interval
  T3  Cutoff sweep                where the minimum AIR crosses 0.80 and what that costs
  T4  Proxy ablation              AIR and accuracy with the postcode_band points neutralized
  T5  Reason-code consistency     matched pairs, and whether listed reasons name the proxy
  T6  Small-group stability       does the smallest group's interval straddle 0.80

THE SCORECARD IS A STUB, NOT A TRAINED MODEL, and no model is used anywhere in the pack:
every test is a count, a ratio, a sort or a seeded resample. The data is synthetic; the truth
(who defaulted) is known because the generator decided it.

AIR is a screening statistic, not a legal finding. The 0.80 line comes from employment
guidance (29 CFR 1607) and is used here only as a screening convention, not as a credit-law
standard.

ASSUMPTIONS (policy constants of a modeled bank, not legal advice; edit them below):
  every threshold in the VERDICT RULES block, the cutoff in step 1, REASONS_LISTED and
  SCORE_BAND in step 3, and ANNUAL_DECISIONS (a modeled volume, not a statistic).

Run (from src/):
    python3 step_04_with_fairlens.py

Output: a readable summary, plus out/step_04_test_pack.csv, out/step_04_air_by_group.csv and
out/step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter

from step_01_model_card_only import (BASELINE_TESTS_RUN, GROUPS, OUT_DIR, POLICY_CUTOFF, approved, prepare, rate)
from step_02_accuracy_baseline import accuracy_by_group
from step_03_deficiencies_exposed import (AIR_SCREEN, REASONS_LISTED, SCORE_BAND, SWEEP_HIGH, SWEEP_LOW,
                                          ablate_postcode, bootstrap_air, crossing, group_stats,
                                          group_verdict, min_air, overall_at, proxy_decline_report,
                                          reason_pair_report, reasons, sweep, top_reason)

# VERDICT RULES (assumptions of a modeled bank; change them and the verdicts change)
APPROVAL_SPREAD_REVIEW_PTS = 5.0     # T1: REVIEW at or above this spread, in points
APPROVAL_SPREAD_FAIL_PTS = 15.0      # T1: FAIL at or above this spread
AIR_NEAR_MARGIN = 0.05               # T2: REVIEW when the lowest AIR is within this margin above the screen
SWEEP_HEADROOM = 10                  # T3: REVIEW when the screen is lost within this many points above the cutoff
PROXY_LIFT_REVIEW = 0.05             # T4: REVIEW when neutralizing the proxy lifts the lowest AIR by this much
PAIR_EXCESS_REVIEW_PTS = 5.0         # T5: cross-group mismatch above the within-group control, in points
PAIR_EXCESS_FAIL_PTS = 15.0
UNNAMED_REVIEW = 0.10                # T5: share of proxy-caused declines whose listed reasons omit the postcode reason
UNNAMED_FAIL = 0.50

ANNUAL_DECISIONS = 20000             # MODELED volume of credit decisions a year; an assumption, not a statistic
TESTS_BASELINE = BASELINE_TESTS_RUN  # by definition: the model card reports nothing split by group
LABEL_NOISE_SEED = 20261020
LABEL_NOISE_LEVELS = (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
PICK_CUTOFFS_FIXED = (170, 180, 200, 210)

RANK = {"PASS": 0, "REVIEW": 1, "FAIL": 2}


def worst(*verdicts: str) -> str:
    return max(verdicts, key=lambda v: RANK[v])


# ---------------------------------------------------------------------------
# The six tests
# ---------------------------------------------------------------------------
def t1_approval_gap(gs: dict) -> dict:
    rates = {g: gs["groups"][g]["approval_rate"] for g in GROUPS}
    spread = 100 * (max(rates.values()) - min(rates.values()))
    v = "FAIL" if spread >= APPROVAL_SPREAD_FAIL_PTS else "REVIEW" if spread >= APPROVAL_SPREAD_REVIEW_PTS else "PASS"
    return {"id": "T1", "deficiency": 1, "name": "Group approval gap", "verdict": v, "spread_pts": spread, "rates": rates,
            "rule": f"FAIL at {APPROVAL_SPREAD_FAIL_PTS:.0f} points or more, REVIEW at {APPROVAL_SPREAD_REVIEW_PTS:.0f}",
            "numbers": "approval " + " / ".join(f"{100 * rates[g]:.1f}%" for g in GROUPS) + f", spread {spread:.1f} points"}


def t2_air(gs: dict) -> dict:
    m, who = min_air(gs)
    v = "FAIL" if m < AIR_SCREEN else "REVIEW" if m < AIR_SCREEN + AIR_NEAR_MARGIN else "PASS"
    below = sum(1 for g in GROUPS if not gs["groups"][g]["is_reference"] and gs["groups"][g]["air"] < AIR_SCREEN)
    return {"id": "T2", "deficiency": 2, "name": "AIR by group", "verdict": v, "min_air": m, "min_group": who, "below": below,
            "rule": f"FAIL when any group is below {AIR_SCREEN:.2f}, REVIEW within {AIR_NEAR_MARGIN:.2f} above it",
            "numbers": f"lowest AIR {m:.3f} ({who}); {below} of {len(GROUPS) - 1} non-reference groups below {AIR_SCREEN:.2f}"}


def t3_sweep(sw: list, cutoff: int = POLICY_CUTOFF) -> dict:
    cp = crossing(sw)
    row_at = {r["cutoff"]: r for r in sw}
    pol = row_at[cutoff]
    if pol["min_air"] < AIR_SCREEN:
        v = "FAIL"
    elif cp - cutoff < SWEEP_HEADROOM:
        v = "REVIEW"
    else:
        v = "PASS"
    cr = row_at[cp]
    if cutoff > cp:
        nums = (f"screen holds up to cutoff {cp}; cutoff {cutoff} is {cutoff - cp} points above; passing costs "
                f"approval {100 * pol['approval_rate']:.1f}% -> {100 * cr['approval_rate']:.1f}% and approved-book default rate "
                f"{100 * pol['approved_default_rate']:.1f}% -> {100 * cr['approved_default_rate']:.1f}%")
    else:
        nums = (f"screen holds up to cutoff {cp}; cutoff {cutoff} has {cp - cutoff} points of headroom below it; "
                f"approved-book default rate {100 * pol['approved_default_rate']:.1f}% at {cutoff}")
    return {"id": "T3", "deficiency": 3, "name": "Cutoff sweep", "verdict": v, "crossing": cp, "cutoff": cutoff,
            "points_above": cutoff - cp, "policy_row": pol, "crossing_row": cr,
            "rule": f"FAIL when the cutoff fails the screen, REVIEW when it holds with under {SWEEP_HEADROOM} points of headroom",
            "numbers": nums}


def t4_proxy(prep: dict, ab: dict) -> dict:
    b, a = min_air(ab["before"]["groups"]), min_air(ab["after"]["groups"])
    lift = a[0] - b[0]
    if b[0] < AIR_SCREEN <= a[0]:
        v = "FAIL"
    elif lift >= PROXY_LIFT_REVIEW:
        v = "REVIEW"
    else:
        v = "PASS"
    acc_b, acc_a = ab["before"]["overall"]["accuracy"], ab["after"]["overall"]["accuracy"]
    fin, fout = ab["flip_to_approve"], ab["flip_to_decline"]
    return {"id": "T4", "deficiency": 4, "name": "Proxy ablation", "verdict": v, "before": b, "after": a, "lift": lift,
            "acc_before": acc_b, "acc_after": acc_a, "flip_in": len(fin), "flip_out": len(fout),
            "flip_in_default_rate": rate(sum(x["defaulted"] for x in fin), len(fin)),
            "flip_out_default_rate": rate(sum(x["defaulted"] for x in fout), len(fout)),
            "air_before": {g: ab["before"]["groups"]["groups"][g]["air"] for g in GROUPS},
            "air_after": {g: ab["after"]["groups"]["groups"][g]["air"] for g in GROUPS},
            "neutral": ab["neutral"],
            "rule": f"FAIL when neutralizing postcode_band moves the lowest AIR from below {AIR_SCREEN:.2f} to at or above it; "
                    f"REVIEW when it lifts the lowest AIR by {PROXY_LIFT_REVIEW:.2f} or more",
            "numbers": (f"lowest AIR {b[0]:.3f} -> {a[0]:.3f}, accuracy {100 * acc_b:.1f}% -> {100 * acc_a:.1f}%, "
                        f"{len(fin)} decisions turn to approve and {len(fout)} to decline")}


def t5_reasons(prep: dict, ab: dict, cutoff: int = POLICY_CUTOFF) -> dict:
    pr = reason_pair_report(prep, cutoff)
    px = proxy_decline_report(prep, ab, cutoff)
    excess = pr["excess_pts"]
    v_pairs = "FAIL" if excess >= PAIR_EXCESS_FAIL_PTS else "REVIEW" if excess >= PAIR_EXCESS_REVIEW_PTS else "PASS"
    u = px["unnamed_share"]
    v_name = "FAIL" if u >= UNNAMED_FAIL else "REVIEW" if u >= UNNAMED_REVIEW else "PASS"
    return {"id": "T5", "deficiency": 5, "name": "Reason-code consistency", "verdict": worst(v_pairs, v_name),
            "pairs_verdict": v_pairs, "naming_verdict": v_name, "pairs": pr, "proxy": px,
            "rule": (f"worst of: cross-group mismatch above the within-group control (REVIEW at {PAIR_EXCESS_REVIEW_PTS:.0f} points, "
                     f"FAIL at {PAIR_EXCESS_FAIL_PTS:.0f}) and share of proxy-caused declines whose {REASONS_LISTED} listed reasons omit "
                     f"{px['code']} (REVIEW at {100 * UNNAMED_REVIEW:.0f}%, FAIL at {100 * UNNAMED_FAIL:.0f}%)"),
            "numbers": (f"{pr['cross_differ']} of {pr['cross_pairs']} matched pairs differ ({100 * pr['cross_share']:.1f}%) against "
                        f"{100 * pr['control']['share']:.1f}% within Group A ({excess:+.1f} points); {px['unnamed']} of {px['proxy_declines']} "
                        f"proxy-caused declines omit {px['code']} ({100 * u:.1f}%)")}


def t6_small_group(prep: dict, gs: dict, bs: dict) -> dict:
    small = min(GROUPS, key=lambda g: gs["groups"][g]["n"])
    iv = bs["intervals"][small]
    straddles = iv["lo"] < AIR_SCREEN <= iv["hi"]
    return {"id": "T6", "deficiency": 6, "name": "Small-group stability", "verdict": "REVIEW" if straddles else "PASS",
            "group": small, "n": gs["groups"][small]["n"], "air": iv["air"], "lo": iv["lo"], "hi": iv["hi"],
            "width": iv["hi"] - iv["lo"], "straddles": straddles,
            "rule": f"REVIEW when the smallest group's 95% interval straddles {AIR_SCREEN:.2f}",
            "numbers": f"{small} (n {gs['groups'][small]['n']}) AIR {iv['air']:.3f}, interval {iv['lo']:.3f} to {iv['hi']:.3f}, "
                       + ("straddles" if straddles else "entirely below" if iv["hi"] < AIR_SCREEN else "entirely at or above")
                       + f" {AIR_SCREEN:.2f}"}


# ---------------------------------------------------------------------------
# Scenario for the picker (one group at one cutoff) and the whole pack
# ---------------------------------------------------------------------------
def reason_mix(prep: dict, group: str, cutoff: int, top: int = 3) -> dict:
    card = prep["card"]
    dec = [a for a in prep["rows"] if a["group"] == group and not approved(a["score"], cutoff)]
    cnt = Counter(top_reason(a, card) for a in dec)
    text = {v["code"]: v["text"] for v in card["reasons"].values()}
    rows = [{"code": c, "text": text[c], "n": n, "share": rate(n, len(dec))} for c, n in cnt.most_common(top)]
    return {"declined": len(dec), "top": rows,
            "postcode_named": sum(1 for a in dec if "postcode_band" in reasons(a, card)),
            "postcode_top": sum(1 for a in dec if top_reason(a, card) == card["reasons"]["postcode_band"]["code"])}


def scenario(prep: dict, group: str, cutoff: int, boot: dict | None = None) -> dict:
    gs = group_stats(prep, cutoff)
    bs = boot if boot is not None else bootstrap_air(prep, cutoff)
    v = gs["groups"][group]
    iv = bs["intervals"][group]
    m, who = min_air(gs)
    return {"group": group, "cutoff": cutoff, "n": v["n"], "approved": v["approved"], "approval_rate": v["approval_rate"],
            "accuracy": v["accuracy"], "air": v["air"], "lo": iv["lo"], "hi": iv["hi"], "reference": gs["reference"],
            "is_reference": v["is_reference"], "verdict": group_verdict(iv), "min_air": m, "min_group": who,
            "overall": overall_at(prep, cutoff), "reasons": reason_mix(prep, group, cutoff)}


def pick_cutoffs(cp: int) -> list:
    return sorted(set(PICK_CUTOFFS_FIXED) | {cp, POLICY_CUTOFF})


def run_pack(prep: dict, bs: dict | None = None, cutoff: int = POLICY_CUTOFF) -> dict:
    """The six tests at one cutoff. The sweep (T3) always covers the whole range."""
    gs = group_stats(prep, cutoff)
    sw = sweep(prep)
    ab = ablate_postcode(prep, cutoff)
    bs = bs if bs is not None else bootstrap_air(prep, cutoff)
    tests = [t1_approval_gap(gs), t2_air(gs), t3_sweep(sw, cutoff), t4_proxy(prep, ab),
             t5_reasons(prep, ab, cutoff), t6_small_group(prep, gs, bs)]
    return {"cutoff": cutoff, "gs": gs, "sweep": sw, "ablation": ab, "boot": bs, "tests": tests}


# ---------------------------------------------------------------------------
# Known limit: group labels
# ---------------------------------------------------------------------------
def label_noise_stress(prep: dict, levels=LABEL_NOISE_LEVELS, seed: int = LABEL_NOISE_SEED,
                       cutoff: int = POLICY_CUTOFF) -> list:
    """Re-run the AIR screen when a share of group labels is wrong.

    Each applicant, with probability p, is given a different group label drawn from the other
    groups in proportion to their size. This is an optimistic model of label error: real
    inference errors correlate with geography."""
    rows = prep["rows"]
    sizes = {g: sum(1 for a in rows if a["group"] == g) for g in GROUPS}
    out = []
    for p in levels:
        rng = random.Random(seed)
        labels = []
        for a in rows:
            if rng.random() < p:
                others = [g for g in GROUPS if g != a["group"]]
                tot = sum(sizes[g] for g in others)
                r, acc, pick = rng.random() * tot, 0.0, others[-1]
                for g in others:
                    acc += sizes[g]
                    if r < acc:
                        pick = g
                        break
                labels.append(pick)
            else:
                labels.append(a["group"])
        rates = {}
        for g in GROUPS:
            idx = [i for i, lab in enumerate(labels) if lab == g]
            rates[g] = rate(sum(1 for i in idx if approved(rows[i]["score"], cutoff)), len(idx))
        ref = max(GROUPS, key=lambda g: rates[g])
        airs = {g: rate(rates[g], rates[ref]) for g in GROUPS if g != ref}
        low = min(airs.values())
        wrong = sum(1 for i, lab in enumerate(labels) if lab != rows[i]["group"])
        out.append({"p": p, "wrong": wrong, "wrong_share": rate(wrong, len(rows)), "min_air": low,
                    "passes": low >= AIR_SCREEN})
    return out


def utility(pack: dict) -> dict:
    tests = pack["tests"]
    run = len(tests)
    flagged = sum(1 for t in tests if t["verdict"] != "PASS")
    t4 = next(t for t in tests if t["id"] == "T4")
    turn = t4["flip_in"] + t4["flip_out"]
    n = sum(v["n"] for v in pack["gs"]["groups"].values())
    return {"tests_run": run, "tests_baseline": TESTS_BASELINE, "flagged": flagged,
            "delta": rate(run - TESTS_BASELINE, run), "annual_decisions": ANNUAL_DECISIONS,
            "utility": rate(run - TESTS_BASELINE, run) * ANNUAL_DECISIONS,
            "turn_on_proxy": turn, "applicants": n, "turn_share": rate(turn, n),
            "turn_annual": rate(turn, n) * ANNUAL_DECISIONS}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    prep = prepare()
    pack = run_pack(prep)
    tests, gs, bs = pack["tests"], pack["gs"], pack["boot"]
    t = {x["id"]: x for x in tests}
    ref = gs["reference"]
    u = utility(pack)

    print("\n" + "=" * 78)
    print("Step 4 - With FairLens: six tests, each with a verdict and its numbers")
    print("=" * 78)
    print(f"\nSame 6,000 synthetic applicants and stub scorecard at cutoff {POLICY_CUTOFF}. No model is used in the pack.")
    print(f"AIR screen {AIR_SCREEN:.2f} is a screening convention (29 CFR 1607), not a credit-law standard or a legal finding.\n")

    print("TEST PACK")
    print(f"  {'test':<4} {'verdict':<7} {'what it checks':<26} numbers")
    for x in tests:
        print(f"  {x['id']:<4} {x['verdict']:<7} {x['name']:<26} {x['numbers']}")
    counts = Counter(x["verdict"] for x in tests)
    print(f"  Result: {counts['FAIL']} FAIL, {counts['REVIEW']} REVIEW, {counts['PASS']} PASS across {len(tests)} tests")
    print("  Verdict rules are assumptions of a modeled bank, not legal advice:")
    for x in tests:
        print(f"    {x['id']}: {x['rule']}")

    print(f"\nT1/T2/T6  AIR BY GROUP WITH A 95% BOOTSTRAP INTERVAL (cutoff {POLICY_CUTOFF}, {bs['n_boot']:,} resamples, seed {bs['seed']})")
    print(f"  {'group':<9} {'applicants':>10} {'approved':>9} {'rate':>7} {'AIR':>6}  {'interval':<15} verdict")
    for g in GROUPS:
        v, iv = gs["groups"][g], bs["intervals"][g]
        itxt = "reference" if v["is_reference"] else f"{iv['lo']:.3f} to {iv['hi']:.3f}"
        print(f"  {g:<9} {v['n']:>10,} {v['approved']:>9,} {100 * v['approval_rate']:>6.1f}% {v['air']:>6.3f}  {itxt:<15} {group_verdict(iv)}")
    print(f"  Reference group {ref} (highest approval rate). Group verdict: FAIL when the whole interval is below {AIR_SCREEN:.2f},")
    print(f"  PASS when the whole interval is at or above it, REVIEW when the interval straddles it.")

    print(f"\nT3  CUTOFF SWEEP (step 1 across {SWEEP_LOW} to {SWEEP_HIGH}; every 5th shown)")
    print(f"  {'cutoff':>6} {'approval':>9} {'accuracy':>9} {'approved default':>17} {'min AIR':>8}  group  screen")
    for r in pack["sweep"]:
        if (r["cutoff"] % 5 == 0 and 160 <= r["cutoff"] <= 215) or r["cutoff"] == t["T3"]["crossing"] or r["cutoff"] == POLICY_CUTOFF:
            mark = "  <- policy" if r["cutoff"] == POLICY_CUTOFF else "  <- last cutoff that holds" if r["cutoff"] == t["T3"]["crossing"] else ""
            print(f"  {r['cutoff']:>6} {100 * r['approval_rate']:>8.1f}% {100 * r['accuracy']:>8.1f}% {100 * r['approved_default_rate']:>16.1f}% "
                  f"{r['min_air']:>8.3f}  {r['min_group'][-1]:<5}  {'holds' if r['min_air'] >= AIR_SCREEN else 'fails'}{mark}")
    t3 = t["T3"]
    print(f"  Cost of passing: cutoff {POLICY_CUTOFF} -> {t3['crossing']} moves approval {100 * t3['policy_row']['approval_rate']:.1f}% -> "
          f"{100 * t3['crossing_row']['approval_rate']:.1f}% and the approved-book default rate "
          f"{100 * t3['policy_row']['approved_default_rate']:.1f}% -> {100 * t3['crossing_row']['approved_default_rate']:.1f}%.")

    t4 = t["T4"]
    print(f"\nT4  PROXY ABLATION (postcode_band points replaced by the population mean, {t4['neutral']} points)")
    print(f"  {'group':<9} {'AIR before':>11} {'AIR after':>10}")
    for g in GROUPS:
        print(f"  {g:<9} {t4['air_before'][g]:>11.3f} {t4['air_after'][g]:>10.3f}")
    print(f"  Lowest AIR {t4['before'][0]:.3f} -> {t4['after'][0]:.3f} (lift {t4['lift']:+.3f}); accuracy {100 * t4['acc_before']:.1f}% -> {100 * t4['acc_after']:.1f}% "
          f"({100 * (t4['acc_after'] - t4['acc_before']):+.1f} points).")
    print(f"  {t4['flip_in']} decisions turn from decline to approve (default rate {100 * t4['flip_in_default_rate']:.1f}%); "
          f"{t4['flip_out']} turn from approve to decline (default rate {100 * t4['flip_out_default_rate']:.1f}%).")
    print("  The truth is known because the data is synthetic: postcode_band has no effect on default in the generator.")

    t5 = t["T5"]
    pr, px = t5["pairs"], t5["proxy"]
    print(f"\nT5  REASON-CODE CONSISTENCY (principal reason = most points lost against the maximum; {REASONS_LISTED} reasons listed)")
    print(f"  Matched pairs of declined applicants, scores within {SCORE_BAND} points, different groups:")
    for g, p in pr["pairs"].items():
        print(f"    {g} vs {ref}: {p['pairs']} pairs, top reason differs in {p['differ']} ({100 * p['share']:.1f}%)")
    print(f"    Control, {ref} vs {ref}: {pr['control']['pairs']} pairs, differs in {pr['control']['differ']} ({100 * pr['control']['share']:.1f}%)")
    print(f"    Cross-group: {pr['cross_differ']} of {pr['cross_pairs']} pairs differ ({100 * pr['cross_share']:.1f}%), {pr['excess_pts']:+.1f} points against the control -> {t5['pairs_verdict']}")
    print(f"  Declines caused by the postcode points alone: {px['proxy_declines']}. Reason {px['code']} is among the listed reasons for {px['named']}; "
          f"unnamed {px['unnamed']} ({100 * px['unnamed_share']:.1f}%) -> {t5['naming_verdict']}")
    print("  Sensitivity to how many reasons are listed: " + "; ".join(f"{x['listed']} -> {x['named']} of {x['of']} named" for x in px["sensitivity"]) + ".")
    print("  Top principal reason codes among declined applicants, by group (share of declines):")
    for g in GROUPS:
        rm = reason_mix(prep, g, POLICY_CUTOFF)
        print(f"    {g}: " + ", ".join(f"{r['code']} {100 * r['share']:.1f}%" for r in rm["top"])
              + f"  (declined {rm['declined']:,}; {px['code']} is the top reason for {rm['postcode_top']})")

    t6 = t["T6"]
    print(f"\nT6  SMALL-GROUP STABILITY")
    print(f"  {t6['group']} has {t6['n']} applicants. AIR {t6['air']:.3f}, interval {t6['lo']:.3f} to {t6['hi']:.3f} (width {t6['width']:.3f}).")
    print(f"  The interval {'straddles' if t6['straddles'] else 'does not straddle'} {AIR_SCREEN:.2f}: report REVIEW, not PASS or FAIL.")

    ln = label_noise_stress(prep)
    first_pass = next((x for x in ln if x["passes"]), None)
    print("\nWHAT IT STILL GETS WRONG (known limits, left in on purpose)")
    print("  1. AIR is a screening statistic, not a legal finding. 0.80 comes from employment guidance (29 CFR 1607)")
    print("     and is applied here as a screening convention, not as a credit-law standard.")
    print("  2. The search for less discriminatory alternatives is one ablation (postcode_band), not a search. A second")
    print("     proxy, or a re-weighted scorecard, would not be found by this pack.")
    print("  3. Real credit data has no group labels. This prototype reads the group from the file; real use needs a")
    print("     defensible group-inference step that this prototype does not have. The one concrete example, with a share")
    print(f"     of labels made wrong at random (seed {LABEL_NOISE_SEED}; real inference errors correlate with geography):")
    print(f"       {'wrong labels':>14} {'lowest AIR':>11}  AIR screen at cutoff {POLICY_CUTOFF}")
    for x in ln:
        print(f"       {x['wrong']:>7,} ({100 * x['wrong_share']:>4.1f}%) {x['min_air']:>11.3f}  {'passes' if x['passes'] else 'fails'}")
    if first_pass:
        print(f"     With {100 * first_pass['wrong_share']:.1f}% of labels wrong the screen passes (lowest AIR {first_pass['min_air']:.3f}). "
              f"A pass that depends on label quality is not evidence.")
    print(f"  4. A real miss inside the pack: the reason-code pair check passes ({pr['excess_pts']:+.1f} points against its control)")
    print(f"     while {px['proxy_declines']} declines are caused by the postcode points. Only T4 and the naming check see them, and the naming")
    print(f"     check depends on how many reasons are listed: with 2 listed, {next(x for x in px['sensitivity'] if x['listed'] == 2)['named']} of "
          f"{px['proxy_declines']} are named.")

    print("\nUTILITY (per the formula in the README)")
    print(f"  Fairness tests the accuracy-only view runs: {u['tests_baseline']} of {u['tests_run']} (by definition: nothing on the model card is split by group)")
    print(f"  Fairness tests the pack runs:                {u['tests_run']} of {u['tests_run']}; {u['flagged']} of {u['tests_run']} return REVIEW or FAIL")
    print(f"  Delta = {u['tests_run']}/{u['tests_run']} - {u['tests_baseline']}/{u['tests_run']} = {u['delta']:.2f}")
    print(f"  MODELED: {u['annual_decisions']:,} credit decisions a year under this scorecard (an assumption, not a statistic; edit ANNUAL_DECISIONS).")
    print(f"  Utility = {u['delta']:.2f} x {u['annual_decisions']:,} = {u['utility']:,.0f} decisions a year under a model with a full fairness test pack")
    print(f"  MODELED illustration: {u['turn_on_proxy']} of {u['applicants']:,} test-set decisions turn on the postcode points ({100 * u['turn_share']:.2f}%);")
    print(f"  at {u['annual_decisions']:,} a year the same share would be about {u['turn_annual']:,.0f}. The test set is dense on purpose, so this is not a frequency estimate.")

    print("\nPICKER SCENARIOS (the app and the demo read these; each cutoff re-runs the six tests with its own bootstrap)")
    cp = t["T3"]["crossing"]
    for c in pick_cutoffs(cp):
        pk = pack if c == POLICY_CUTOFF else run_pack(prep, None, c)
        tag = " (policy cutoff)" if c == POLICY_CUTOFF else " (last cutoff where the screen holds)" if c == cp else ""
        scn = {g: scenario(prep, g, c, pk["boot"]) for g in GROUPS}
        any_s = scn[GROUPS[0]]
        accs = {b["group"]: b["accuracy"] for b in accuracy_by_group(prep["rows"], c)}
        print(f"  cutoff {c}{tag}: model card accuracy {100 * any_s['overall']['accuracy']:.1f}%, approval {100 * any_s['overall']['approval_rate']:.1f}%")
        for g in GROUPS:
            sc = scn[g]
            itxt = "reference" if sc["is_reference"] else f"{sc['lo']:.3f} to {sc['hi']:.3f}"
            rtxt = ", ".join(f"{r['code']} {100 * r['share']:.1f}%" for r in sc["reasons"]["top"])
            print(f"    {g}: approval {100 * sc['approval_rate']:.1f}%, accuracy {100 * accs[g]:.1f}% "
                  f"({100 * (max(accs.values()) - accs[g]):.1f} points below the best group), AIR {sc['air']:.3f}, interval {itxt}, "
                  f"{sc['verdict']}; top reasons {rtxt}")
        for x in pk["tests"]:
            print(f"    {x['id']} {x['verdict']:<6} {x['numbers']}")

    with open(OUT_DIR / "step_04_test_pack.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["test", "deficiency", "name", "verdict", "numbers", "rule"])
        for x in tests:
            w.writerow([x["id"], x["deficiency"], x["name"], x["verdict"], x["numbers"], x["rule"]])
    with open(OUT_DIR / "step_04_air_by_group.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["group", "applicants", "approved", "approval_rate", "air", "ci_low", "ci_high", "verdict"])
        for g in GROUPS:
            v, iv = gs["groups"][g], bs["intervals"][g]
            w.writerow([g, v["n"], v["approved"], round(v["approval_rate"], 4), round(v["air"], 4),
                        round(iv["lo"], 4), round(iv["hi"], 4), group_verdict(iv)])
    summary = {"verdicts": {x["id"]: x["verdict"] for x in tests}, "numbers": {x["id"]: x["numbers"] for x in tests},
               "utility": u, "label_noise": ln}
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\nWrote step_04_test_pack.csv, step_04_air_by_group.csv and step_04_summary.json in src/out/")


if __name__ == "__main__":
    main()
