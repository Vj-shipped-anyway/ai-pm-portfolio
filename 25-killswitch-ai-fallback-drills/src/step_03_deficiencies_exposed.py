"""Step 3 - Where the status quo and the basic approach break: six named deficiencies, each with a count.

Step 1 showed what "we will switch it off manually" costs. Step 2 showed what one threshold on the
overall error rate does. This step asks six things they cannot do, with the same synthetic 90 days.

  (1) Manual detection is slow, or never happens: delay in hours and bad decisions served.
  (2) A single threshold either misses events or raises false trips: both are counted.
  (3) Without hysteresis the fallback flaps: switches per day.
  (4) The fallback is untested: drills that failed, and how many ran on a stale rules version.
  (5) Recovery is unmanaged: hours until it is safe to return, and returns that re-tripped in 6 hours.
  (6) The switch is all-or-nothing: healthy segments are moved to the weaker rules path.

Counts come from the data files and from steps 1 and 2. "Safe to return" is the synthetic truth
(the hour the event ended); a real service would not know it. Bad-decision counts are expected
values (decisions x rate), and the rules-path quality gap is a stub set by the generator.

Run (from src/):
    python3 step_03_deficiencies_exposed.py

Output: a readable summary, plus out/step_03_deficiencies.csv and out/step_03_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_manual_switch_off import (
    OUT_DIR, RETRIP_H, SEGMENTS, fmt_h, load_all, median_or_none, pct, rnd, type_label,
)
from step_01_manual_switch_off import summarize as summarize_step1
from step_01_manual_switch_off import run as run_manual
from step_02_single_threshold_alert import analyze as analyze_step2


# ---------------------------------------------------------------------------
# Drills (step 4 reuses these)
# ---------------------------------------------------------------------------
def policy_num(data: dict, key: str) -> int:
    return int(data["policy"][key]["value"])


def drill_stats(data: dict) -> dict:
    drills = data["drills"]
    stale_after = policy_num(data, "max_rules_version_age_days")
    target = policy_num(data, "drill_target_minutes")
    failed = [d for d in drills if not d["success"]]
    stale = [d for d in drills if d["age_days"] > stale_after]
    ok = [d for d in drills if d["success"]]
    return {
        "drills": len(drills), "failed": len(failed), "ok": len(ok),
        "stale": len(stale), "failed_stale": sum(1 for d in failed if d["age_days"] > stale_after),
        "ok_stale": sum(1 for d in ok if d["age_days"] > stale_after),
        "median_minutes": median_or_none([d["minutes"] for d in ok]),
        "slowest_minutes": max((d["minutes"] for d in ok), default=None),
        "within_target": sum(1 for d in ok if d["minutes"] <= target),
        "target": target, "stale_after": stale_after,
        "failed_ids": [d["drill_id"] for d in failed],
        "reasons": [(d["drill_id"], d["reason"]) for d in failed],
        "fail_rate": len(failed) / len(drills) if drills else 0.0,
    }


# ---------------------------------------------------------------------------
# Deficiency (6): what an all-or-nothing switch drags along
# ---------------------------------------------------------------------------
def all_or_nothing(data: dict) -> dict:
    """For each single-segment event: suppose a switch fired the hour the event began and was held
    until it ended (an upper bound on any detection, with no delay).
      all-or-nothing  every segment moves; per-segment  only the affected segment moves.
    Net = bad decisions the move avoids minus the quality gap it pays on the rules path."""
    gap, m = data["gap"], data["m"]
    rows = []
    for i, ev in enumerate(data["events"]):
        if len(ev["segments"]) != 1:
            continue
        hrs = range(ev["start"], ev["end"])
        total = sum(m[s]["dec"][h] for s in SEGMENTS for h in hrs)
        aff = sum(m[s]["dec"][h] for s in ev["segments"] for h in hrs)
        cost_all = sum(m[s]["dec"][h] * gap[s] for s in SEGMENTS for h in hrs)
        cost_seg = sum(m[s]["dec"][h] * gap[s] for s in ev["segments"] for h in hrs)
        expo = data["exposure"][i]
        rows.append({"event_id": ev["event_id"], "type": ev["type"], "segment": ev["segments"][0],
                     "decisions_in_window": total, "healthy_moved": total - aff,
                     "healthy_share": (total - aff) / total, "exposure": expo,
                     "cost_all": cost_all, "cost_seg": cost_seg,
                     "net_all": expo - cost_all, "net_seg": expo - cost_seg})
    return {"rows": rows, "events": len(rows),
            "healthy_moved": sum(r["healthy_moved"] for r in rows),
            "decisions": sum(r["decisions_in_window"] for r in rows),
            "worse_than_nothing": sum(1 for r in rows if r["net_all"] < 0),
            "worse_than_nothing_seg": sum(1 for r in rows if r["net_seg"] < 0),
            "net_all": sum(r["net_all"] for r in rows), "net_seg": sum(r["net_seg"] for r in rows)}


# ---------------------------------------------------------------------------
# The six measures
# ---------------------------------------------------------------------------
def summarize(data: dict) -> dict:
    s1 = summarize_step1(data)
    man = run_manual(data)
    s2 = analyze_step2(data)
    tuned, twice = s2["tuned"], s2["twice"]
    a1 = s1["all"]

    noticed_late = [e["event_id"] for e in man["eval"]["events"]
                    if e["manual"]["cluster_hour"] is not None and not e["manual"]["acted"]]
    never = [e["event_id"] for e in man["eval"]["events"] if e["manual"]["cluster_hour"] is None]
    cluster_delays = [e["manual"]["cluster_hour"] - data["events"][i]["start"]
                      for i, e in enumerate(man["eval"]["events"]) if e["manual"]["cluster_hour"] is not None]
    d1 = {"events": a1["events"], "switched": a1["caught"], "not_switched": a1["missed"],
          "noticed_too_late": len(noticed_late), "noticed_too_late_ids": noticed_late,
          "never_clustered": len(never), "never_clustered_ids": never,
          "median_delay_h": a1["median_delay_h"], "median_cluster_h": median_or_none(cluster_delays),
          "bad_served": a1["bad_served"], "exposure": a1["exposure"]}

    d2 = {"events": tuned["all"]["events"], "threshold_tuned": s2["t_tuned"],
          "missed_tuned": tuned["all"]["missed"], "missed_tuned_ids": tuned["all"]["missed_ids"],
          "false_tuned": tuned["all"]["false_trips"],
          "threshold_twice": s2["t_twice"], "caught_twice": twice["all"]["caught"],
          "false_twice": twice["all"]["false_trips"], "sweep": s2["sweep"]}

    d3 = {"tuned_switches": tuned["all"]["switches"], "tuned_per_day": tuned["all"]["switches_per_day"],
          "twice_switches": twice["all"]["switches"], "twice_per_day": twice["all"]["switches_per_day"],
          "twice_worst_day": twice["all"]["worst_day_switches"], "twice_trips": twice["all"]["trips"]}

    d4 = drill_stats(data)

    d5 = {"manual_hours_after_end": data["policy"]["manual_decision_delay_hours"]["value"],
          "tuned_returns": tuned["all"]["returns"], "tuned_retripped": tuned["all"]["retripped"],
          "twice_returns": twice["all"]["returns"], "twice_retripped": twice["all"]["retripped"],
          "twice_premature": twice["all"]["premature_returns"],
          "tuned_median_after_end": tuned["all"]["median_recovery_after_end_h"],
          "twice_median_after_end": twice["all"]["median_recovery_after_end_h"]}

    aon = all_or_nothing(data)
    single = [i for i, e in enumerate(data["events"]) if len(e["segments"]) == 1]

    def single_unneeded(evs):
        return sum(evs[i]["unneeded"] for i in single)

    d6 = {"single_segment_events": aon["events"], "events": len(data["events"]),
          "healthy_moved": aon["healthy_moved"], "window_decisions": aon["decisions"],
          "worse_than_nothing": aon["worse_than_nothing"], "worse_than_nothing_seg": aon["worse_than_nothing_seg"],
          "net_all": aon["net_all"], "net_seg": aon["net_seg"], "rows": aon["rows"],
          "realized_manual": a1["unneeded"], "realized_manual_cost": a1["unneeded_cost"],
          "realized_tuned": tuned["all"]["unneeded"], "realized_twice": twice["all"]["unneeded"],
          "single_manual": single_unneeded(man["eval"]["events"]),
          "single_tuned": single_unneeded(tuned["eval"]["events"]),
          "single_twice": single_unneeded(twice["eval"]["events"])}
    return {"d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5, "d6": d6, "s2": s2}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    S = summarize(data)
    d1, d2, d3, d4, d5, d6 = (S[k] for k in ("d1", "d2", "d3", "d4", "d5", "d6"))

    print("\n" + "=" * 100)
    print("Step 3 - Six deficiencies of the status quo and the basic approach, with counts")
    print("=" * 100)

    print("\n(1) Manual detection is slow, or never happens")
    print(f"    {d1['not_switched']} of {d1['events']} events were not switched off before they ended "
          f"({d1['noticed_too_late']} noticed too late: {', '.join(d1['noticed_too_late_ids'])}; "
          f"{d1['never_clustered']} never produced a complaint cluster).")
    print(f"    Median hours from start to the switch where it happened: {fmt_h(d1['median_delay_h'])} h "
          f"(modeled: assumes a {data['policy']['manual_decision_delay_hours']['value']} h decision delay).")
    print(f"    Bad decisions served by the degraded model path: {rnd(d1['bad_served']):,} of "
          f"{rnd(d1['exposure']):,} ({pct(d1['bad_served'], d1['exposure'])}).")

    print("\n(2) A single threshold either misses events or raises false trips")
    print(f"    Tuned to the budget ({100 * d2['threshold_tuned']:.1f}%): misses {d2['missed_tuned']} of {d2['events']} events "
          f"({', '.join(d2['missed_tuned_ids'])}), {d2['false_tuned']} false trips.")
    print(f"    Twice normal ({100 * d2['threshold_twice']:.1f}%): catches {d2['caught_twice']} of {d2['events']}, "
          f"but raises {d2['false_twice']} false trips in 90 days.")

    print("\n(3) Without hysteresis the fallback flaps")
    print(f"    Twice-normal threshold: {d3['twice_switches']} fallback switches in 90 days "
          f"({d3['twice_per_day']:.2f} a day, worst day {d3['twice_worst_day']}).")
    print(f"    Tuned threshold: {d3['tuned_switches']} switches in 90 days ({d3['tuned_per_day']:.2f} a day).")

    print("\n(4) The fallback is untested")
    print(f"    {d4['failed']} of {d4['drills']} drills failed; {d4['failed_stale']} of those {d4['failed']} ran on a rules version "
          f"older than {d4['stale_after']} days.")
    print(f"    {d4['stale']} of {d4['drills']} drills used a stale rules version, and {d4['ok_stale']} of the {d4['ok']} that worked "
          f"{'was' if d4['ok_stale'] == 1 else 'were'} stale.")
    print(f"    Where it worked, the switch took a median {fmt_h(d4['median_minutes'])} minutes "
          f"(slowest {d4['slowest_minutes']}); {d4['within_target']} of {d4['ok']} met the {d4['target']}-minute target.")
    for did, why in d4["reasons"]:
        print(f"      {did}: {why}")

    print("\n(5) Recovery is unmanaged")
    print(f"    Twice-normal threshold: {d5['twice_retripped']} of {d5['twice_returns']} returns re-tripped within {RETRIP_H} hours; "
          f"{d5['twice_premature']} returns happened while an event was still active.")
    print(f"    Twice-normal: median {fmt_h(d5['twice_median_after_end'])} h from the end of an event to the last return "
          "(events it caught; negative means it came back before the event ended).")
    print(f"    Tuned threshold: {d5['tuned_retripped']} of {d5['tuned_returns']} returns re-tripped; "
          f"median {fmt_h(d5['tuned_median_after_end'])} h from the end of an event to the return (events it caught).")
    print(f"    Manual: the return is {d5['manual_hours_after_end']} h after the event ends by assumption (modeled), "
          f"with no check that the service is healthy.")

    print("\n(6) The switch is all-or-nothing")
    print(f"    {d6['single_segment_events']} of {d6['events']} events hit one segment. In those, the switch moved healthy decisions: "
          f"manual {d6['single_manual']:,}, tuned threshold {d6['single_tuned']:,}, twice-normal {d6['single_twice']:,}.")
    print(f"    Across all {d6['events']} events: manual {d6['realized_manual']:,}, tuned threshold {d6['realized_tuned']:,}, "
          f"twice-normal {d6['realized_twice']:,}.")
    print(f"    If a switch fired the hour each single-segment event began and held until it ended, "
          f"{d6['healthy_moved']:,} of {d6['window_decisions']:,} decisions moved ({pct(d6['healthy_moved'], d6['window_decisions'])}) "
          f"would be healthy.")
    print(f"    {'event':<6} {'type':<17} {'segment':<15} {'bad decisions at stake':>23} {'cost: move all':>15} {'cost: move one':>15}")
    for r in d6["rows"]:
        print(f"    {r['event_id']:<6} {type_label(r['type']):<17} {r['segment']:<15} {rnd(r['exposure']):>23,} "
              f"{rnd(r['cost_all']):>15,} {rnd(r['cost_seg']):>15,}")
    print(f"    Moving every segment costs more than the bad decisions it avoids in {d6['worse_than_nothing']} of "
          f"{d6['single_segment_events']} events; moving only the affected one, in {d6['worse_than_nothing_seg']}.")

    print("\nThe basic approach finds some events and mishandles the rest. The product is the per-segment decision,")
    print("the hysteresis and the drill, not the alarm.")

    rows = [("1", "events not switched before they ended", f"{d1['not_switched']} of {d1['events']}"),
            ("1", "bad decisions served", rnd(d1["bad_served"])),
            ("2", "events missed at the tuned threshold", f"{d2['missed_tuned']} of {d2['events']}"),
            ("2", "false trips at twice normal", d2["false_twice"]),
            ("3", "switches in 90 days at twice normal", d3["twice_switches"]),
            ("4", "drills failed", f"{d4['failed']} of {d4['drills']}"),
            ("4", "failed drills on a stale rules version", f"{d4['failed_stale']} of {d4['failed']}"),
            ("5", f"returns re-tripped within {RETRIP_H} hours at twice normal", f"{d5['twice_retripped']} of {d5['twice_returns']}"),
            ("6", "events where moving every segment costs more than it saves",
             f"{d6['worse_than_nothing']} of {d6['single_segment_events']}")]
    with open(OUT_DIR / "step_03_deficiencies.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["deficiency", "measure", "value"])
        w.writerows(rows)
    keep = {k: v for k, v in S.items() if k != "s2"}
    with open(OUT_DIR / "step_03_summary.json", "w") as f:
        json.dump(keep, f, indent=2, default=str)
    print("\nWrote src/out/step_03_deficiencies.csv and step_03_summary.json")


if __name__ == "__main__":
    main()
