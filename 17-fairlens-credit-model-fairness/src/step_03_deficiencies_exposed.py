"""Step 3 - Where the accuracy-only approach breaks: six named deficiencies, each with a number.

Step 2 showed that accuracy by group looks fine. This step asks what an accuracy-only view
cannot see, using the same 6,000 synthetic applicants and the generator's own outcome.

  (1) Overall accuracy hides group approval gaps.
  (2) The adverse impact ratio (AIR) by group is below 0.80 for a group and is reported
      nowhere.
  (3) One cutoff is a snapshot: sweep the cutoff and see where the minimum AIR crosses 0.80
      and what that costs.
  (4) A proxy: ablate the postcode_band points and compare AIR and accuracy.
  (5) Reason codes: matched pairs of declined applicants from different groups, and the
      declines that only the postcode points cause.
  (6) Small-group instability: a seeded bootstrap interval on AIR for the smallest group.

AIR = a group's approval rate divided by the approval rate of the group with the highest
approval rate (the reference group). 0.80 is the "four-fifths" convention from employment
guidance (29 CFR 1607). It is used here only as a screening convention, not as a credit-law
standard and not as a legal finding.

This module also holds the measurement functions that step 4 and the app import.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_cutoff_sweep.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict

from step_01_model_card_only import (GROUPS, OUT_DIR, POLICY_CUTOFF, approved, correct, prepare, rate)
from step_02_accuracy_baseline import accuracy_by_group

AIR_SCREEN = 0.80            # screening convention, not a legal standard
SWEEP_LOW, SWEEP_HIGH = 120, 250
SHOW_EVERY = 10              # the printed sweep table shows every 10th cutoff
SCORE_BAND = 3               # matched pairs: scores within this many points
REASONS_LISTED = 4           # principal reasons listed for a declined applicant (modeled bank policy)
BOOT_N = 1000
BOOT_SEED = 20261019


# ---------------------------------------------------------------------------
# Group statistics, AIR, sweep
# ---------------------------------------------------------------------------
def score_of(a: dict, neutral_postcode: int | None = None) -> int:
    """The scorecard score; with neutral_postcode set, the postcode points are replaced by it."""
    if neutral_postcode is None:
        return a["score"]
    return a["score"] - a["points"]["postcode_band"] + neutral_postcode


def group_stats(prep: dict, cutoff: int, neutral_postcode: int | None = None) -> dict:
    rows = prep["rows"]
    out = {}
    for g in GROUPS:
        gr = [a for a in rows if a["group"] == g]
        apr = [a for a in gr if approved(score_of(a, neutral_postcode), cutoff)]
        ok = sum(1 for a in gr if correct(a, approved(score_of(a, neutral_postcode), cutoff)))
        out[g] = {"group": g, "n": len(gr), "approved": len(apr), "approval_rate": rate(len(apr), len(gr)),
                  "accuracy": rate(ok, len(gr)),
                  "approved_defaults": sum(a["defaulted"] for a in apr)}
    ref = max(GROUPS, key=lambda g: out[g]["approval_rate"])
    for g in GROUPS:
        out[g]["air"] = rate(out[g]["approval_rate"], out[ref]["approval_rate"])
        out[g]["is_reference"] = g == ref
    return {"groups": out, "reference": ref}


def overall_at(prep: dict, cutoff: int, neutral_postcode: int | None = None) -> dict:
    rows = prep["rows"]
    n = len(rows)
    apr = [a for a in rows if approved(score_of(a, neutral_postcode), cutoff)]
    ok = sum(1 for a in rows if correct(a, approved(score_of(a, neutral_postcode), cutoff)))
    return {"approved": len(apr), "approval_rate": rate(len(apr), n), "accuracy": rate(ok, n),
            "approved_default_rate": rate(sum(a["defaulted"] for a in apr), len(apr)),
            "approved_defaults": sum(a["defaulted"] for a in apr)}


def min_air(gs: dict) -> tuple:
    """(lowest AIR among non-reference groups, that group)."""
    cands = [(v["air"], g) for g, v in gs["groups"].items() if not v["is_reference"]]
    return min(cands)


def sweep(prep: dict, lo: int = SWEEP_LOW, hi: int = SWEEP_HIGH, neutral_postcode: int | None = None) -> list:
    out = []
    for c in range(lo, hi + 1):
        gs = group_stats(prep, c, neutral_postcode)
        ov = overall_at(prep, c, neutral_postcode)
        m, who = min_air(gs)
        out.append({"cutoff": c, "approval_rate": ov["approval_rate"], "accuracy": ov["accuracy"],
                    "approved_default_rate": ov["approved_default_rate"], "min_air": m, "min_group": who,
                    "reference": gs["reference"],
                    "air": {g: gs["groups"][g]["air"] for g in GROUPS},
                    "rate": {g: gs["groups"][g]["approval_rate"] for g in GROUPS}})
    return out


def crossing(sw: list) -> int | None:
    """Highest swept cutoff from which the minimum AIR stays at or above the screen all the way down.

    Scan upward from the lowest swept cutoff; stop at the first cutoff where it falls below.
    None when it is below the screen at the lowest swept cutoff."""
    last = None
    for row in sw:
        if row["min_air"] >= AIR_SCREEN:
            last = row["cutoff"]
        else:
            break
    return last


# ---------------------------------------------------------------------------
# Proxy ablation
# ---------------------------------------------------------------------------
def ablate_postcode(prep: dict, cutoff: int = POLICY_CUTOFF) -> dict:
    """Replace every applicant's postcode points with the population mean (rounded)."""
    neutral = prep["mean_postcode_points"]
    before = {"groups": group_stats(prep, cutoff), "overall": overall_at(prep, cutoff)}
    after = {"groups": group_stats(prep, cutoff, neutral), "overall": overall_at(prep, cutoff, neutral)}
    to_approve, to_decline = [], []
    for a in prep["rows"]:
        was, now = approved(a["score"], cutoff), approved(score_of(a, neutral), cutoff)
        if now and not was:
            to_approve.append(a)
        elif was and not now:
            to_decline.append(a)
    return {"neutral": neutral, "before": before, "after": after,
            "flip_to_approve": to_approve, "flip_to_decline": to_decline}


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------
def reasons(a: dict, card: dict, k: int = REASONS_LISTED) -> list:
    """Components ranked by points lost against the maximum; ties break by scorecard order."""
    lost = [(card["max"][c] - a["points"][c], i, c) for i, c in enumerate(card["components"])]
    lost = [x for x in sorted(lost, key=lambda x: (-x[0], x[1])) if x[0] > 0]
    return [c for _, _, c in lost[:k]]


def top_reason(a: dict, card: dict) -> str:
    r = reasons(a, card, 1)
    return card["reasons"][r[0]]["code"] if r else ""


def match_pairs(src: list, ref: list, band: int = SCORE_BAND) -> list:
    """Pair each src applicant with the nearest-scoring unused ref applicant within `band` points.

    Deterministic: src is taken in id order; ties go to the lower id. Each ref is used once."""
    pool = defaultdict(list)
    for q in sorted(ref, key=lambda x: x["applicant_id"]):
        pool[q["score"]].append(q)
    used, pairs = set(), []
    for a in sorted(src, key=lambda x: x["applicant_id"]):
        best = None
        for d in range(band + 1):
            cands = []
            for s in {a["score"] - d, a["score"] + d}:
                for q in pool.get(s, []):
                    if q["applicant_id"] not in used and q["applicant_id"] != a["applicant_id"]:
                        cands.append(q)
                        break
            if cands:
                best = min(cands, key=lambda x: x["applicant_id"])
                break
        if best is not None:
            used.add(best["applicant_id"])
            pairs.append((a, best))
    return pairs


def reason_pair_report(prep: dict, cutoff: int = POLICY_CUTOFF) -> dict:
    card = prep["card"]
    dec = {g: [a for a in prep["rows"] if a["group"] == g and not approved(a["score"], cutoff)] for g in GROUPS}
    out = {"band": SCORE_BAND, "declined": {g: len(v) for g, v in dec.items()}}
    pairs = {}
    for g in ("Group B", "Group C"):
        ps = match_pairs(dec[g], dec["Group A"])
        diff = sum(1 for a, b in ps if top_reason(a, card) != top_reason(b, card))
        pairs[g] = {"pairs": len(ps), "differ": diff, "share": rate(diff, len(ps))}
    a_list = sorted(dec["Group A"], key=lambda x: x["applicant_id"])
    ps = match_pairs(a_list[0::2], a_list[1::2])
    diff = sum(1 for a, b in ps if top_reason(a, card) != top_reason(b, card))
    ctrl = {"pairs": len(ps), "differ": diff, "share": rate(diff, len(ps))}
    cross_pairs = sum(p["pairs"] for p in pairs.values())
    cross_diff = sum(p["differ"] for p in pairs.values())
    out.update({"pairs": pairs, "control": ctrl, "cross_pairs": cross_pairs, "cross_differ": cross_diff,
                "cross_share": rate(cross_diff, cross_pairs),
                "excess_pts": 100 * (rate(cross_diff, cross_pairs) - ctrl["share"])})
    return out


def proxy_decline_report(prep: dict, ab: dict, cutoff: int = POLICY_CUTOFF) -> dict:
    """Declined applicants who would be approved with neutral postcode points: do the listed
    reasons name the postcode band?"""
    card = prep["card"]
    pcode = card["reasons"]["postcode_band"]["code"]
    out = {"code": pcode, "listed": REASONS_LISTED, "by_group": {}}
    for g in GROUPS:
        decl = [a for a in prep["rows"] if a["group"] == g and not approved(a["score"], cutoff)]
        flips = [a for a in ab["flip_to_approve"] if a["group"] == g]
        named_flips = sum(1 for a in flips if "postcode_band" in reasons(a, card))
        named_all = sum(1 for a in decl if "postcode_band" in reasons(a, card))
        out["by_group"][g] = {"declined": len(decl), "proxy_declines": len(flips),
                              "named_in_flips": named_flips, "named_in_all_declines": named_all}
    tot_flips = sum(v["proxy_declines"] for v in out["by_group"].values())
    tot_named = sum(v["named_in_flips"] for v in out["by_group"].values())
    out.update({"proxy_declines": tot_flips, "named": tot_named, "unnamed": tot_flips - tot_named,
                "unnamed_share": rate(tot_flips - tot_named, tot_flips)})
    sens = []
    for k in (1, 2, 3, 4):
        nm = sum(1 for a in ab["flip_to_approve"] if "postcode_band" in reasons(a, card, k))
        sens.append({"listed": k, "named": nm, "of": tot_flips})
    out["sensitivity"] = sens
    return out


# ---------------------------------------------------------------------------
# Bootstrap interval on AIR
# ---------------------------------------------------------------------------
def bootstrap_air(prep: dict, cutoff: int = POLICY_CUTOFF, neutral_postcode: int | None = None,
                  n_boot: int = BOOT_N, seed: int = BOOT_SEED) -> dict:
    """Seeded percentile bootstrap (2.5th to 97.5th) of each group's AIR.

    Applicants are resampled with replacement inside each group. The reference group is the one
    with the highest approval rate on the real data and stays fixed across resamples."""
    gs = group_stats(prep, cutoff, neutral_postcode)
    ref = gs["reference"]
    flags = {g: [1 if approved(score_of(a, neutral_postcode), cutoff) else 0
                 for a in prep["rows"] if a["group"] == g] for g in GROUPS}
    rng = random.Random(seed)
    rnd = rng.random
    sims = {g: [] for g in GROUPS if g != ref}
    for _ in range(n_boot):
        rates = {}
        for g in GROUPS:
            f = flags[g]
            n = len(f)
            rates[g] = sum([f[int(rnd() * n)] for _ in range(n)]) / n
        for g in sims:
            sims[g].append(rates[g] / rates[ref] if rates[ref] else 0.0)
    out = {}
    for g in GROUPS:
        if g == ref:
            out[g] = {"air": 1.0, "lo": 1.0, "hi": 1.0, "reference": True}
            continue
        s = sorted(sims[g])
        lo, hi = s[int(0.025 * n_boot) - 1], s[int(0.975 * n_boot) - 1]
        out[g] = {"air": gs["groups"][g]["air"], "lo": lo, "hi": hi, "reference": False}
    return {"reference": ref, "intervals": out, "n_boot": n_boot, "seed": seed}


def group_verdict(iv: dict) -> str:
    """PASS / REVIEW / FAIL for one group from its AIR interval (the picker uses this)."""
    if iv["reference"]:
        return "REFERENCE"
    if iv["hi"] < AIR_SCREEN:
        return "FAIL"
    if iv["lo"] >= AIR_SCREEN:
        return "PASS"
    return "REVIEW"


# ---------------------------------------------------------------------------
# The six measurements
# ---------------------------------------------------------------------------
def summarize(prep: dict, with_bootstrap: bool = True) -> dict:
    rows = prep["rows"]
    gs = group_stats(prep, POLICY_CUTOFF)
    ref = gs["reference"]
    accs = accuracy_by_group(rows)
    acc_vals = [b["accuracy"] for b in accs]
    rates = [gs["groups"][g]["approval_rate"] for g in GROUPS]
    d1 = {"acc_spread_pts": 100 * (max(acc_vals) - min(acc_vals)),
          "approval_spread_pts": 100 * (max(rates) - min(rates)),
          "approval": {g: gs["groups"][g]["approval_rate"] for g in GROUPS},
          "accuracy": {b["group"]: b["accuracy"] for b in accs}}
    below = [g for g in GROUPS if not gs["groups"][g]["is_reference"] and gs["groups"][g]["air"] < AIR_SCREEN]
    d2 = {"reference": ref, "air": {g: gs["groups"][g]["air"] for g in GROUPS},
          "below": below, "non_reference": len(GROUPS) - 1,
          "min_air": min_air(gs)[0], "min_group": min_air(gs)[1]}
    sw = sweep(prep)
    cp = crossing(sw)
    row_at = {r["cutoff"]: r for r in sw}
    d3 = {"crossing": cp, "policy_row": row_at[POLICY_CUTOFF],
          "crossing_row": row_at[cp] if cp is not None else None,
          "points_above": POLICY_CUTOFF - cp if cp is not None else None}
    ab = ablate_postcode(prep)
    pb_before = min_air(ab["before"]["groups"])
    pb_after = min_air(ab["after"]["groups"])
    flips_in = ab["flip_to_approve"]
    d4 = {"neutral": ab["neutral"],
          "before_min_air": pb_before[0], "before_group": pb_before[1],
          "after_min_air": pb_after[0], "after_group": pb_after[1],
          "before_acc": ab["before"]["overall"]["accuracy"], "after_acc": ab["after"]["overall"]["accuracy"],
          "before_apr": ab["before"]["overall"]["approval_rate"], "after_apr": ab["after"]["overall"]["approval_rate"],
          "flip_to_approve": len(flips_in), "flip_to_decline": len(ab["flip_to_decline"]),
          "flip_defaulted": sum(a["defaulted"] for a in flips_in),
          "flip_default_rate": rate(sum(a["defaulted"] for a in flips_in), len(flips_in)),
          "flip_out_defaulted": sum(a["defaulted"] for a in ab["flip_to_decline"]),
          "flip_out_default_rate": rate(sum(a["defaulted"] for a in ab["flip_to_decline"]), len(ab["flip_to_decline"])),
          "flip_by_group": {g: sum(1 for a in flips_in if a["group"] == g) for g in GROUPS},
          "air_before": {g: ab["before"]["groups"]["groups"][g]["air"] for g in GROUPS},
          "air_after": {g: ab["after"]["groups"]["groups"][g]["air"] for g in GROUPS},
          "approved_book_default_before": ab["before"]["overall"]["approved_default_rate"]}
    d5 = reason_pair_report(prep)
    d5["proxy"] = proxy_decline_report(prep, ab)
    summary = {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5}
    if with_bootstrap:
        small = min(GROUPS, key=lambda g: gs["groups"][g]["n"])
        bs = bootstrap_air(prep)
        iv = bs["intervals"][small]
        summary["d6"] = {"group": small, "n": gs["groups"][small]["n"], "air": iv["air"], "lo": iv["lo"],
                         "hi": iv["hi"], "width": iv["hi"] - iv["lo"],
                         "straddles": iv["lo"] < AIR_SCREEN <= iv["hi"], "n_boot": bs["n_boot"], "seed": bs["seed"]}
    return summary


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    prep = prepare()
    s = summarize(prep)
    d1, d2, d3, d4, d5, d6 = s["d1"], s["d2"], s["d3"], s["d4"], s["d5"], s["d6"]
    gs = group_stats(prep, POLICY_CUTOFF)

    print("\n" + "=" * 78)
    print("Step 3 - Where accuracy-only breaks: 6 named deficiencies")
    print("=" * 78)
    print(f"\nSame 6,000 synthetic applicants, stub scorecard, cutoff {POLICY_CUTOFF}. AIR = a group's approval rate")
    print(f"divided by the highest group approval rate. {AIR_SCREEN:.2f} is a screening convention, not a legal finding.\n")

    print("(1) Overall accuracy hides group approval gaps")
    print("    " + " / ".join(f"{g[-1]} {100 * d1['accuracy'][g]:.1f}%" for g in GROUPS)
          + f" accuracy by group: spread {d1['acc_spread_pts']:.1f} points.")
    print("    " + " / ".join(f"{g[-1]} {100 * d1['approval'][g]:.1f}%" for g in GROUPS)
          + f" approval rate by group: spread {d1['approval_spread_pts']:.1f} points.")

    print("\n(2) The AIR by group is below 0.80 for a group and is reported nowhere")
    print(f"    Reference group: {d2['reference']} (highest approval rate).")
    for g in GROUPS:
        if g != d2["reference"]:
            flag = "below 0.80" if d2["air"][g] < AIR_SCREEN else "at or above 0.80"
            print(f"    {g}: AIR {d2['air'][g]:.3f}  {flag}")
    print(f"    {len(d2['below'])} of {d2['non_reference']} non-reference groups are below 0.80. The model card reports none of these.")

    print("\n(3) One cutoff is a snapshot")
    sw = sweep(prep)
    print(f"    {'cutoff':>6} {'approval':>9} {'accuracy':>9} {'approved book default':>22} {'min AIR':>8}  group")
    for r in sw:
        if r["cutoff"] % SHOW_EVERY == 0 and 150 <= r["cutoff"] <= 230 or r["cutoff"] == POLICY_CUTOFF:
            mark = "  <- policy cutoff" if r["cutoff"] == POLICY_CUTOFF else ""
            print(f"    {r['cutoff']:>6} {100 * r['approval_rate']:>8.1f}% {100 * r['accuracy']:>8.1f}% "
                  f"{100 * r['approved_default_rate']:>21.1f}% {r['min_air']:>8.3f}  {r['min_group'][-1]}{mark}")
    pr, cr = d3["policy_row"], d3["crossing_row"]
    print(f"    The minimum AIR stays at or above {AIR_SCREEN:.2f} up to cutoff {d3['crossing']} and is below it at {d3['crossing'] + 1} "
          f"(swept {SWEEP_LOW} to {SWEEP_HIGH}, step 1).")
    print(f"    The policy cutoff {POLICY_CUTOFF} is {d3['points_above']} points above that. Passing the screen means moving the cutoff to {d3['crossing']}:")
    print(f"      overall approval {100 * pr['approval_rate']:.1f}% -> {100 * cr['approval_rate']:.1f}% "
          f"({100 * (cr['approval_rate'] - pr['approval_rate']):+.1f} points)")
    print(f"      default rate in the approved book {100 * pr['approved_default_rate']:.1f}% -> {100 * cr['approved_default_rate']:.1f}% "
          f"({100 * (cr['approved_default_rate'] - pr['approved_default_rate']):+.1f} points)")
    print(f"      accuracy {100 * pr['accuracy']:.1f}% -> {100 * cr['accuracy']:.1f}% ({100 * (cr['accuracy'] - pr['accuracy']):+.1f} points)")

    print("\n(4) A proxy: ablate the postcode_band points")
    print(f"    Postcode points replaced by the population mean ({d4['neutral']} points) for every applicant.")
    print(f"    Minimum AIR {d4['before_min_air']:.3f} ({d4['before_group']}) -> {d4['after_min_air']:.3f} ({d4['after_group']}).")
    print(f"    Accuracy {100 * d4['before_acc']:.1f}% -> {100 * d4['after_acc']:.1f}% ({100 * (d4['after_acc'] - d4['before_acc']):+.1f} points); "
          f"approval {100 * d4['before_apr']:.1f}% -> {100 * d4['after_apr']:.1f}%.")
    print(f"    Decisions that change: {d4['flip_to_approve']} declined -> approved, {d4['flip_to_decline']} approved -> declined.")
    print(f"    Defaulted among the {d4['flip_to_approve']} who flip to approved: {d4['flip_defaulted']} ({100 * d4['flip_default_rate']:.1f}%).")
    print(f"    Defaulted among the {d4['flip_to_decline']} who flip to declined: {d4['flip_out_defaulted']} ({100 * d4['flip_out_default_rate']:.1f}%).")
    print(f"    The postcode points approve applicants who default more often ({100 * d4['flip_out_default_rate']:.1f}%) than the ones they decline ({100 * d4['flip_default_rate']:.1f}%).")

    print("\n(5) Reason codes")
    print(f"    Matched pairs of declined applicants: scores within {d5['band']} points, one in Group A and one in Group B or C.")
    for g, p in d5["pairs"].items():
        print(f"    {g} vs Group A: {p['pairs']} pairs, top reason code differs in {p['differ']} ({100 * p['share']:.1f}%)")
    print(f"    Control, Group A vs Group A: {d5['control']['pairs']} pairs, differs in {d5['control']['differ']} ({100 * d5['control']['share']:.1f}%)")
    print(f"    Cross-group: {d5['cross_differ']} of {d5['cross_pairs']} pairs differ ({100 * d5['cross_share']:.1f}%), "
          f"{d5['excess_pts']:+.1f} points against the control.")
    px = d5["proxy"]
    print(f"    Declines caused by the postcode points alone: {px['proxy_declines']} (approved if the postcode points were neutral).")
    print(f"    Reason {px['code']} (postcode band) is among the {px['listed']} listed reasons for {px['named']} of them; unnamed {px['unnamed']} ({100 * px['unnamed_share']:.1f}%).")
    print("    Sensitivity to how many reasons the bank lists: " + "; ".join(f"{x['listed']} listed -> {x['named']} of {x['of']}" for x in px["sensitivity"]) + ".")

    print("\n(6) Small-group instability")
    print(f"    {d6['group']} has {d6['n']} applicants. AIR {d6['air']:.3f}, 95% bootstrap interval {d6['lo']:.3f} to {d6['hi']:.3f} "
          f"(width {d6['width']:.3f}; {d6['n_boot']:,} resamples, seed {d6['seed']}).")
    print(f"    The interval {'straddles' if d6['straddles'] else 'does not straddle'} {AIR_SCREEN:.2f}: with this many applicants, "
          f"{'the data cannot say which side of the screen the group is on' if d6['straddles'] else 'the group is clearly on one side'}.")

    print("\nThe accuracy-only view reports none of the six. The product is the test pack, not the statistic.")

    with open(OUT_DIR / "step_03_cutoff_sweep.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["cutoff", "approval_rate", "accuracy", "approved_default_rate", "min_air", "min_group"])
        for r in sw:
            w.writerow([r["cutoff"], round(r["approval_rate"], 4), round(r["accuracy"], 4),
                        round(r["approved_default_rate"], 4), round(r["min_air"], 4), r["min_group"]])

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o if not isinstance(v, dict) or "applicant_id" not in v]
        return o
    with open(OUT_DIR / "step_03_summary.json", "w") as f:
        json.dump(clean(s), f, indent=2, default=str)
    print("\nWrote src/out/step_03_cutoff_sweep.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
