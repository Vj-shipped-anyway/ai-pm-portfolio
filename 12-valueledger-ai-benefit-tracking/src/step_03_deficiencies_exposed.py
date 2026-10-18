"""
Step 3 - Six deficiencies exposed, each scored against the answer key.

The synthetic generator injected a known true effect, so for the first time we can
say how wrong the claim and the pre/post comparison are, and why. The answer key
is known only because the data is synthetic. A real bank has no answer key.

  (a) Gross usage is not net time saved
  (b) No counterfactual: the seasonal trend and selection bias inflate the estimate
  (c) Novelty decay ignored: the launch month overstates the steady state
  (d) Rework not netted
  (e) Double counting across overlapping tools
  (f) Benefit not tied to a budget line: how much could become cash

Run (from src/):
    python3 step_03_deficiencies_exposed.py
"""

from __future__ import annotations

import csv
import json

from valueledger_core import (
    POST_WEEKS, PRE_WEEKS, apply_ledger_rule, ensure_out, fmt_int, fmt_usd, load_data, build_agg,
    scenario_by_key, total,
)
from step_01_vendor_claim import claim
from step_02_prepost_basic import prepost


def last_four(weeks: list) -> list:
    return weeks[-4:]


def first_four(weeks: list) -> list:
    return weeks[:4]


def measure(ds, agg) -> dict:
    tt, th = agg.treated, agg.holdout
    cl = claim(ds, agg, POST_WEEKS)
    pp = prepost(ds, agg, PRE_WEEKS, POST_WEEKS)

    g = total(agg, tt, "G", POST_WEEKS)
    rw = total(agg, tt, "RW", POST_WEEKS)
    ass = total(agg, tt, "AS", POST_WEEKS)
    hid = total(agg, tt, "HID", POST_WEEKS)
    true_gross_h = g / 60.0
    true_rework_h = rw / 60.0
    true_net_h = (g - rw) / 60.0

    # (a) assumed minutes per use against the measured gross minutes per distinct assisted task
    assumed = cl["assumed_min_a"]
    true_gross_per_use = g / ass
    distinct_at_assumed_h = cl["events_distinct"] * assumed / 60.0
    a_error_h = distinct_at_assumed_h - true_gross_h

    # (b) counterfactual
    pre_t = total(agg, tt, "M", PRE_WEEKS) / total(agg, tt, "T", PRE_WEEKS)
    pre_h = total(agg, th, "M", PRE_WEEKS) / total(agg, th, "T", PRE_WEEKS)
    trend_min = 0.0          # holdout's own change, applied to treated tasks
    postonly_min = 0.0       # treated vs holdout after launch, no baseline
    for w in POST_WEEKS:
        t_w = total(agg, tt, "T", [w])
        m_t = total(agg, tt, "M", [w]) / t_w
        m_h = total(agg, th, "M", [w]) / total(agg, th, "T", [w])
        trend_min += (pre_h - m_h) * t_w
        postonly_min += (m_h - m_t) * t_w
    prepost_gross_error_h = pp["hours"] - true_gross_h
    postonly_h = postonly_min / 60.0

    # (c) novelty
    def weekly_net_h(weeks):
        return (total(agg, tt, "G", weeks) - total(agg, tt, "RW", weeks)) / 60.0 / len(weeks)
    early, late = first_four(POST_WEEKS), last_four(POST_WEEKS)
    true_early, true_late = weekly_net_h(early), weekly_net_h(late)
    claim_early = (total(agg, tt, "EA", early) + total(agg, tt, "EB", early)) * assumed / 60.0 / 4.0
    claim_late = (total(agg, tt, "EA", late) + total(agg, tt, "EB", late)) * assumed / 60.0 / 4.0
    def prepost_weekly_h(weeks):
        pre = total(agg, tt, "M", PRE_WEEKS) / total(agg, tt, "T", PRE_WEEKS)
        s = 0.0
        for w in weeks:
            s += (pre - total(agg, tt, "M", [w]) / total(agg, tt, "T", [w])) * total(agg, tt, "T", [w])
        return s / 60.0 / len(weeks)
    pp_early, pp_late = prepost_weekly_h(early), prepost_weekly_h(late)

    # (d) rework
    obs_rework_h = total(agg, tt, "R", POST_WEEKS) / 60.0

    # (e) double counting
    dup_events = cl["events_logged"] - cl["events_distinct"]
    dup_hours = dup_events * assumed / 60.0

    # (f) budget line
    hours_cash_no = 0.0
    hours_cash_yes = 0.0
    for cc, h in cl["claimed_hours_by_cc"].items():
        if ds.budget[cc]["freed_time_can_become_cash"] == "yes":
            hours_cash_yes += h
        else:
            hours_cash_no += h
    # true hard cash: the ledger rule applied to the answer key's gross and rework hours
    gross_cc, rework_cc = {}, {}
    for t in tt:
        cc = agg.teams[t]["cc"]
        gross_cc[cc] = gross_cc.get(cc, 0.0) + total(agg, [t], "G", POST_WEEKS) / 60.0
        rework_cc[cc] = rework_cc.get(cc, 0.0) + total(agg, [t], "RW", POST_WEEKS) / 60.0
    key_ledger = apply_ledger_rule(ds, gross_cc, rework_cc, len(POST_WEEKS))
    hard = key_ledger["hard_usd"]
    value = key_ledger["value_usd"]

    return {
        "n_treated": agg.n_treated_people,
        "claim_hours": cl["claimed_hours"],
        "claim_value_usd": cl["claimed_value_usd"],
        "prepost_hours": pp["hours"],
        "true_gross_hours": true_gross_h,
        "true_rework_hours": true_rework_h,
        "true_net_hours": true_net_h,
        "true_hidden_hours": hid / 60.0,
        "a": {"assumed_min_per_use": assumed, "true_gross_min_per_use": true_gross_per_use,
              "true_net_min_per_use": (g - rw) / ass, "distinct_at_assumed_hours": distinct_at_assumed_h,
              "error_hours": a_error_h},
        "b": {"prepost_gross_hours": pp["hours"], "true_gross_hours": true_gross_h,
              "error_hours": prepost_gross_error_h, "trend_hours": trend_min / 60.0,
              "hidden_hours": hid / 60.0, "postonly_hours": postonly_h,
              "postonly_error_hours": postonly_h - true_gross_h,
              "baseline_gap_min": pre_t - pre_h, "holdout_change_min_per_task": None},
        "c": {"true_early_weekly_hours": true_early, "true_late_weekly_hours": true_late,
              "true_early_over_late": true_early / true_late,
              "claim_early_weekly_hours": claim_early, "claim_late_weekly_hours": claim_late,
              "prepost_early_weekly_hours": pp_early, "prepost_late_weekly_hours": pp_late},
        "d": {"true_rework_hours": true_rework_h, "observed_rework_hours": obs_rework_h,
              "rework_share_of_gross": true_rework_h / true_gross_h},
        "e": {"events_logged": cl["events_logged"], "events_distinct": cl["events_distinct"],
              "truth_distinct": ass, "duplicate_events": dup_events, "duplicate_hours": dup_hours,
              "duplicate_share": dup_events / cl["events_logged"]},
        "f": {"claim_value_usd": cl["claimed_value_usd"], "true_value_usd": value, "true_hard_usd": hard,
              "claim_hours_in_capacity_only": hours_cash_no, "claim_hours_in_cash_lines": hours_cash_yes,
              "capacity_only_share_of_claim": hours_cash_no / cl["claimed_hours"],
              "hard_share_of_claim_value": hard / cl["claimed_value_usd"],
              "hard_share_of_true_value": hard / value},
    }


def main() -> None:
    ds = load_data()
    agg = build_agg(ds, scenario_by_key("all"))
    m = measure(ds, agg)
    n = m["n_treated"]
    a, b, c, d, e, f = m["a"], m["b"], m["c"], m["d"], m["e"], m["f"]

    print("STEP 3 - Six deficiencies exposed, each scored against the answer key")
    print("Synthetic data. The answer key is known only because the generator injected the effect.")
    print("Net hours freed, treated cohort (%d people), 14 post-launch weeks:" % n)
    print("  answer key: gross %s h, rework %s h, net %s h"
          % (fmt_int(m["true_gross_hours"]), fmt_int(m["true_rework_hours"]), fmt_int(m["true_net_hours"])))
    print("  vendor-style claim (step 1): %s h   pre/post (step 2): %s h" % (fmt_int(m["claim_hours"]), fmt_int(m["prepost_hours"])))

    print()
    print("(a) Gross usage is not net time saved")
    print("    assumed minutes saved per use:                    %.1f" % a["assumed_min_per_use"])
    print("    measured gross minutes saved per assisted task:   %.1f   (net of rework: %.1f)"
          % (a["true_gross_min_per_use"], a["true_net_min_per_use"]))
    print("    distinct assisted tasks x assumed minutes:        %s h vs %s h true gross -> overstated by %s h (%+.0f%%)"
          % (fmt_int(a["distinct_at_assumed_hours"]), fmt_int(m["true_gross_hours"]), fmt_int(a["error_hours"]),
             100 * a["error_hours"] / m["true_gross_hours"]))

    print()
    print("(b) No counterfactual: the seasonal trend and selection bias inflate the estimate")
    print("    pre/post gross estimate: %s h vs %s h true gross -> overstated by %s h (%+.0f%%)"
          % (fmt_int(b["prepost_gross_hours"]), fmt_int(b["true_gross_hours"]), fmt_int(b["error_hours"]),
             100 * b["error_hours"] / b["true_gross_hours"]))
    print("    the holdout never got a copilot; its own improvement over the same weeks, applied to the")
    print("    treated cohort's tasks, is %s h. Pre/post credits all of it to the copilot." % fmt_int(b["trend_hours"]))
    print("    treated vs holdout after launch, no baseline: %s h -> overstated by %s h (%+.0f%%)"
          % (fmt_int(b["postonly_hours"]), fmt_int(b["postonly_error_hours"]),
             100 * b["postonly_error_hours"] / b["true_gross_hours"]))
    print("    the treated teams were already %.1f min per task faster before launch (selection by enthusiasm)."
          % (-b["baseline_gap_min"]))

    print()
    print("(c) Novelty decay ignored: the launch month overstates the steady state")
    print("    average weekly net hours, weeks 13-16 vs weeks 23-26")
    print("      answer key:        %5.0f vs %5.0f   (launch month is %.2fx the steady state)"
          % (c["true_early_weekly_hours"], c["true_late_weekly_hours"], c["true_early_over_late"]))
    print("      vendor-style claim: %5.0f vs %5.0f   (flat: usage is flat and 12 minutes does not decay)"
          % (c["claim_early_weekly_hours"], c["claim_late_weekly_hours"]))
    print("      pre/post:           %5.0f vs %5.0f   (the seasonal easing hides the decay)"
          % (c["prepost_early_weekly_hours"], c["prepost_late_weekly_hours"]))
    print("    steady-state run-rate overstated by the claim: %+.0f%%; by pre/post: %+.0f%%"
          % (100 * (c["claim_late_weekly_hours"] / c["true_late_weekly_hours"] - 1),
             100 * (c["prepost_late_weekly_hours"] / c["true_late_weekly_hours"] - 1)))

    print()
    print("(d) Rework not netted")
    print("    rework minutes caused by copilot output: %s h (%.0f%% of gross time saved)"
          % (fmt_int(d["true_rework_hours"]), 100 * d["rework_share_of_gross"]))
    print("    neither the claim nor pre/post subtracts it. Overstated by %s h." % fmt_int(d["true_rework_hours"]))

    print()
    print("(e) Double counting across overlapping tools")
    print("    events logged by the two tools: %s; distinct assisted tasks: %s; answer key: %s"
          % (fmt_int(e["events_logged"]), fmt_int(e["events_distinct"]), fmt_int(e["truth_distinct"])))
    print("    counted twice: %s events (%.1f%% of the log) = %s h at the assumed minutes"
          % (fmt_int(e["duplicate_events"]), 100 * e["duplicate_share"], fmt_int(e["duplicate_hours"])))

    print()
    print("(f) Benefit not tied to a budget line")
    print("    claimed value:                                   %s" % fmt_usd(f["claim_value_usd"]))
    print("    claimed hours sitting in cost centers with no cash lever: %.0f%%" % (100 * f["capacity_only_share_of_claim"]))
    print("    true value of the hours actually freed:          %s" % fmt_usd(f["true_value_usd"]))
    print("    of which cash the budget lines can absorb:       %s  (%.0f%% of the true value, %.0f%% of the claimed value)"
          % (fmt_usd(f["true_hard_usd"]), 100 * f["hard_share_of_true_value"], 100 * f["hard_share_of_claim_value"]))

    print()
    print("Bridge from the claim to the answer key (hours):")
    bridge = [
        ("vendor-style claim", m["claim_hours"]),
        ("(e) remove double-counted events", -e["duplicate_hours"]),
        ("(a) assumed minutes -> measured gross minutes", -a["error_hours"]),
        ("(d) net out rework", -d["true_rework_hours"]),
    ]
    run = 0.0
    for label, v in bridge:
        run += v
        print("    %-48s %9s   running %s" % (label, fmt_int(v) if label.startswith("vendor") else "{:+,}".format(int(round(v))), fmt_int(run)))
    print("    %-48s %9s" % ("answer key (true net)", fmt_int(m["true_net_hours"])))

    out = ensure_out()
    with open(out / "step_03_deficiencies.json", "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(out / "step_03_deficiencies.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["deficiency", "measure", "method_value", "answer_key_value", "error", "error_pct"])
        w.writerow(["a_gross_not_net", "distinct tasks at assumed minutes vs true gross (h)",
                    "%.0f" % a["distinct_at_assumed_hours"], "%.0f" % m["true_gross_hours"], "%.0f" % a["error_hours"],
                    "%.1f" % (100 * a["error_hours"] / m["true_gross_hours"])])
        w.writerow(["b_no_counterfactual", "pre/post gross vs true gross (h)",
                    "%.0f" % b["prepost_gross_hours"], "%.0f" % b["true_gross_hours"], "%.0f" % b["error_hours"],
                    "%.1f" % (100 * b["error_hours"] / b["true_gross_hours"])])
        w.writerow(["c_novelty_decay", "claim weekly net hours in weeks 23-26 vs true (h per week)",
                    "%.0f" % c["claim_late_weekly_hours"], "%.0f" % c["true_late_weekly_hours"],
                    "%.0f" % (c["claim_late_weekly_hours"] - c["true_late_weekly_hours"]),
                    "%.1f" % (100 * (c["claim_late_weekly_hours"] / c["true_late_weekly_hours"] - 1))])
        w.writerow(["d_rework_not_netted", "rework hours not subtracted", "0", "%.0f" % d["true_rework_hours"],
                    "%.0f" % d["true_rework_hours"], "%.1f" % (100 * d["rework_share_of_gross"])])
        w.writerow(["e_double_counting", "duplicate events x assumed minutes (h)", "%.0f" % e["duplicate_hours"], "0",
                    "%.0f" % e["duplicate_hours"], "%.1f" % (100 * e["duplicate_share"])])
        w.writerow(["f_no_budget_line", "claimed value vs hard cash the budget lines can absorb (USD)",
                    "%.0f" % f["claim_value_usd"], "%.0f" % f["true_hard_usd"],
                    "%.0f" % (f["claim_value_usd"] - f["true_hard_usd"]),
                    "%.1f" % (100 * (1 - f["hard_share_of_claim_value"]))])


if __name__ == "__main__":
    main()
