"""Step 1 - Status quo: "we will switch it off manually".

A modeled bank's AI decision service has a fallback path: a simple rules engine. The plan for
a bad day is that someone will switch the AI off by hand. Nobody has defined the trigger,
drilled the switch, measured how long recovery takes, or asked whether every segment must fall
back when only one is degraded.

This script plays that plan forward on the synthetic 90 days and counts, for each of the 12
degradation events, how long the bad decisions run before a person flips the switch and what
the flip costs.

Everything below the loaders is shared: the later steps and the apps import it.

ASSUMPTIONS (modeled, change them here; they are also listed in data/policy.csv):
  A1. A person notices a problem when complaints, summed over all four segments, reach
      CLUSTER_COMPLAINTS_3H in a rolling 3-hour window.
  A2. Noticing is followed by MANUAL_DECISION_DELAY_H hours before the switch is flipped, and
      the same delay again between the end of the event and flipping it back.
  A3. The switch is all-or-nothing: every segment moves to the rules path.
  A4. Triage is perfect: the person never switches on a false cluster. A real team would do
      worse, so every manual number below is a floor on the harm.
  A5. If the cluster is only noticed after the event has already ended, nothing is switched.

How harm is counted ("bad decisions"). All counts are relative to a healthy model path:
  * on the model path during an event, a share of decisions equal to the event's
    bad_decision_rate is bad;
  * on the rules path, a share equal to that segment's quality gap (data/fallback_rules.csv, a
    stub set by the generator, not a measurement) is worse than a healthy model would have done.
  These are expected counts (decisions x rate), not sampled outcomes. No model is used anywhere
  in this repo.

Run (from src/):
    python3 step_01_manual_switch_off.py

Output: a readable summary, plus out/step_01_events.csv and out/step_01_summary.json.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent / "out"

HOURS = 2160                 # 90 days x 24
TRAIN_END = 1440             # hours 0-1439 are days 1-60; hours 1440-2159 are days 61-90 (held out)
SEGMENTS = ["consumer", "small_business", "affluent", "new_to_bank"]
SEG_SHORT = {"consumer": "cons", "small_business": "smb", "affluent": "aff", "new_to_bank": "ntb"}

CLUSTER_COMPLAINTS_3H = 12   # assumption A1
MANUAL_DECISION_DELAY_H = 4  # assumption A2
JUSTIFY_GRACE_H = 6          # a trip is justified if an event was active in the 6 hours before
RETRIP_H = 6                 # a return that falls back again within 6 hours "re-tripped"
HEALTHY_TAIL_H = 72          # hours after an event ends that are not used as a healthy baseline

PERIODS = ("train", "heldout", "all")
PERIOD_LABEL = {"train": "days 1-60", "heldout": "days 61-90", "all": "days 1-90"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def period_of(hour: int) -> str:
    return "train" if hour < TRAIN_END else "heldout"


def hour_label(h: int) -> str:
    return f"day {h // 24 + 1} {h % 24:02d}:00"


def seg_list(segs) -> str:
    return "all 4" if len(segs) == 4 else "+".join(SEG_SHORT[s] for s in segs)


def seg_long(segs) -> str:
    return "all four segments" if len(segs) == 4 else ", ".join(s.replace("_", " ") for s in segs)


def type_label(t: str) -> str:
    return t.replace("_", " ")


def bad_weight(ev: dict, h: int) -> float:
    """Share of the event's bad_decision_rate in force at hour h (ramps in for drift)."""
    s, e, r = ev["start"], ev["end"], ev["ramp"]
    if s <= h < e:
        return min(1.0, (h - s + 1) / r) if r > 0 else 1.0
    return 0.0


def pct(a, b) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def rnd(x) -> int:
    return int(round(x))


def median_or_none(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def fmt_h(x, nd: int = 1) -> str:
    return "n/a" if x is None else (f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd else str(int(x)))


# ---------------------------------------------------------------------------
# Loaders (later steps and the apps import these)
# ---------------------------------------------------------------------------
def load_all(data_dir: Path = DATA_DIR) -> dict:
    """Load the CSVs into plain lists and dicts. No pandas needed."""
    m = {s: {"dec": [0] * HOURS, "err": [0.0] * HOURS, "lat": [0.0] * HOURS, "drift": [0.0] * HOURS,
             "ovr": [0.0] * HOURS, "comp": [0] * HOURS} for s in SEGMENTS}
    with open(data_dir / "metrics_hourly.csv", newline="") as f:
        for r in csv.DictReader(f):
            h, s = int(r["hour"]), r["segment"]
            d = m[s]
            d["dec"][h] = int(r["decisions"])
            d["err"][h] = float(r["error_rate"])
            d["lat"][h] = float(r["latency_p95_ms"])
            d["drift"][h] = float(r["drift_score"])
            d["ovr"][h] = float(r["override_rate"])
            d["comp"][h] = int(r["complaints"])

    events = []
    with open(data_dir / "degradation_events.csv", newline="") as f:
        for r in csv.DictReader(f):
            ev = {"event_id": r["event_id"], "start": int(r["start_hour"]), "end": int(r["end_hour"]),
                  "type": r["type"], "segments": r["segments"].split(";"),
                  "bad": float(r["bad_decision_rate"]), "ramp": int(r["ramp_hours"]),
                  "scale": float(r["signal_scale"])}
            ev["period"] = period_of(ev["start"])
            events.append(ev)

    gap, quality = {}, {}
    with open(data_dir / "fallback_rules.csv", newline="") as f:
        for r in csv.DictReader(f):
            gap[r["segment"]] = float(r["quality_gap"])
            quality[r["segment"]] = (float(r["model_path_quality"]), float(r["rules_path_quality"]))

    drills = []
    with open(data_dir / "drills.csv", newline="") as f:
        for r in csv.DictReader(f):
            drills.append({"drill_id": r["drill_id"], "date_hour": int(r["date_hour"]),
                           "scenario": r["scenario"],
                           "minutes": int(r["minutes_to_fallback"]) if r["minutes_to_fallback"] else None,
                           "success": r["success"] == "yes", "reason": r["failure_reason"],
                           "age_days": int(r["rules_version_age_days"])})

    policy = {}
    with open(data_dir / "policy.csv", newline="") as f:
        for r in csv.DictReader(f):
            policy[r["parameter"]] = r

    # The constants at the top of this file must agree with data/policy.csv.
    for key, val in (("manual_cluster_complaints_3h", CLUSTER_COMPLAINTS_3H),
                     ("manual_decision_delay_hours", MANUAL_DECISION_DELAY_H),
                     ("justify_grace_hours", JUSTIFY_GRACE_H), ("re_trip_window_hours", RETRIP_H)):
        if int(policy[key]["value"]) != val:
            raise SystemExit(f"{key} in policy.csv ({policy[key]['value']}) differs from the script ({val})")

    # Which event (if any) is active in each hour. Events must not overlap.
    active_of = [-1] * HOURS
    for i, ev in enumerate(events):
        for h in range(ev["start"], min(HOURS, ev["end"])):
            if active_of[h] != -1:
                raise SystemExit("events overlap")
            active_of[h] = i

    bad_model = {s: [0.0] * HOURS for s in SEGMENTS}
    for ev in events:
        for s in ev["segments"]:
            for h in range(ev["start"], ev["end"]):
                bad_model[s][h] += ev["bad"] * bad_weight(ev, h)
    exposure = []
    for ev in events:
        exposure.append(sum(m[s]["dec"][h] * bad_model[s][h] for s in ev["segments"]
                            for h in range(ev["start"], ev["end"])))
    comp_all = [sum(m[s]["comp"][h] for s in SEGMENTS) for h in range(HOURS)]

    return {"m": m, "events": events, "gap": gap, "quality": quality, "drills": drills, "policy": policy,
            "active_of": active_of, "bad_model": bad_model, "exposure": exposure, "comp_all": comp_all}


def healthy_hours(data: dict) -> list:
    """Hours in days 1-60 that are not inside an event or its signal tail. In a real estate a
    person would have to pick these by hand; here the synthetic truth tells us."""
    bad = [False] * HOURS
    for ev in data["events"]:
        for h in range(ev["start"], min(HOURS, ev["end"] + HEALTHY_TAIL_H)):
            bad[h] = True
    return [h for h in range(TRAIN_END) if not bad[h]]


# ---------------------------------------------------------------------------
# Accounting: what a path-by-hour schedule costs
# ---------------------------------------------------------------------------
def account(data: dict, fb: dict, owner: dict) -> dict:
    """Cost of a path-by-hour schedule.

    fb[segment][hour] is True when that segment is served by the rules path in that hour.
    owner[segment][hour] says why: the index of the event that justified the trip, or None when
    the trip was false (no event touching that scope was active just before it).

    Per event:
      bad_served    bad decisions served by the degraded model path
      protected     rules-path decisions in affected segments while the event was active
      excess        rules-path decisions in affected segments after the event ended
      unneeded      rules-path decisions in segments the event did not touch (all-or-nothing collateral)
      rules_cost    those three times the segment's quality gap
      bad_total     bad_served + rules_cost
    Rules-path decisions that belong to a false trip are counted apart, by period.
    """
    m, gap, events = data["m"], data["gap"], data["events"]
    res = [{"event_id": ev["event_id"], "bad_served": 0.0, "protected": 0, "excess": 0, "unneeded": 0,
            "cost_protected": 0.0, "cost_excess": 0.0, "cost_unneeded": 0.0, "segments_moved": set(),
            "exposure": data["exposure"][i]} for i, ev in enumerate(events)]
    false_trip = {p: {"decisions": 0, "cost": 0.0} for p in ("train", "heldout")}
    for h in range(HOURS):
        act = data["active_of"][h]
        for s in SEGMENTS:
            n = m[s]["dec"][h]
            if fb[s][h]:
                cost = n * gap[s]
                ei = owner[s][h]
                if ei is None:
                    o = false_trip[period_of(h)]
                    o["decisions"] += n
                    o["cost"] += cost
                    continue
                ev, r = events[ei], res[ei]
                r["segments_moved"].add(s)
                if s in ev["segments"] and ev["start"] <= h < ev["end"]:
                    r["protected"] += n
                    r["cost_protected"] += cost
                elif s in ev["segments"]:
                    r["excess"] += n
                    r["cost_excess"] += cost
                else:
                    r["unneeded"] += n
                    r["cost_unneeded"] += cost
            elif act >= 0 and data["bad_model"][s][h] > 0:
                res[act]["bad_served"] += n * data["bad_model"][s][h]
    for r in res:
        r["rules_cost"] = r["cost_protected"] + r["cost_excess"] + r["cost_unneeded"]
        r["bad_total"] = r["bad_served"] + r["rules_cost"]
    return {"events": res, "false_trip": false_trip}


# ---------------------------------------------------------------------------
# Evaluation of any fallback schedule (manual, single threshold, KillSwitch)
# ---------------------------------------------------------------------------
def episodes(arr: list) -> list:
    """Maximal runs of True as (start, end) with end exclusive."""
    out, a = [], None
    for h, v in enumerate(arr):
        if v and a is None:
            a = h
        elif not v and a is not None:
            out.append((a, h))
            a = None
    if a is not None:
        out.append((a, len(arr)))
    return out


def evaluate(data: dict, fb: dict, scope: str) -> dict:
    """Score a fallback schedule against the truth.

    scope "service": the schedule moves every segment together (one stream).
    scope "segment": each segment has its own switch (four streams).
    """
    events = data["events"]
    streams = {"service": (fb[SEGMENTS[0]], list(SEGMENTS))} if scope == "service" else \
        {s: (fb[s], [s]) for s in SEGMENTS}
    trips, transitions = [], []
    owner = {s: [None] * HOURS for s in SEGMENTS}
    for name, (arr, covers) in streams.items():
        eps = episodes(arr)
        touching = [i for i, ev in enumerate(events) if set(ev["segments"]) & set(covers)]
        for k, (a, b) in enumerate(eps):
            just = None
            for i in touching:
                ev = events[i]
                if ev["start"] <= a - 1 and ev["end"] > a - 1 - JUSTIFY_GRACE_H:
                    just = i
                    break
            ret = b if b < HOURS else None
            premature = ret is not None and any(events[i]["start"] <= ret < events[i]["end"] for i in touching)
            retrip = ret is not None and k + 1 < len(eps) and eps[k + 1][0] - ret <= RETRIP_H
            trips.append({"stream": name, "hour": a, "return": ret, "event": None if just is None else events[just]["event_id"],
                          "false": just is None, "premature": premature, "retrip": retrip})
            transitions.append(a)
            if ret is not None:
                transitions.append(ret)
            for s in covers:
                for h in range(a, b):
                    owner[s][h] = just
    acct = account(data, fb, owner)

    ev_out = []
    for i, ev in enumerate(events):
        per_seg, detect = {}, None
        for name, (arr, covers) in streams.items():
            if not (set(ev["segments"]) & set(covers)):
                continue
            first = next((h for h in range(ev["start"], ev["end"]) if arr[h]), None)
            eps = [(a, b) for a, b in episodes(arr) if a < ev["end"] and b > ev["start"]]
            last_ret = None
            if eps:
                a, b = eps[-1]
                last_ret = b if b < HOURS else None
            per_seg[name] = {"first": first, "return": last_ret,
                             "after_end": None if last_ret is None else last_ret - ev["end"]}
            if first is not None and (detect is None or first < detect):
                detect = first
        rets = [v["after_end"] for v in per_seg.values() if v["after_end"] is not None]
        a = acct["events"][i]
        ev_out.append({"event_id": ev["event_id"], "period": ev["period"], "caught": detect is not None,
                       "detect_hour": detect, "delay": None if detect is None else detect - ev["start"],
                       "per_stream": per_seg, "recovery_after_end": max(rets) if rets else None, **a})
    return {"events": ev_out, "trips": trips, "transitions": transitions, "false_trip": acct["false_trip"],
            "scope": scope}


def summarize_period(data: dict, ev: dict, period: str) -> dict:
    """Aggregate an evaluate() result over days 1-60, days 61-90 or both."""
    def inp(h):
        return period == "all" or period_of(h) == period

    evs = [e for e in ev["events"] if period == "all" or e["period"] == period]
    caught = [e for e in evs if e["caught"]]
    trips = [t for t in ev["trips"] if inp(t["hour"])]
    returns = [t for t in trips if t["return"] is not None]
    days = {"train": 60, "heldout": 30, "all": 90}[period]
    per_day = {}
    for h in ev["transitions"]:
        if inp(h):
            per_day[h // 24] = per_day.get(h // 24, 0) + 1
    ft_dec = sum(ev["false_trip"][p]["decisions"] for p in ("train", "heldout") if period in ("all", p))
    ft_cost = sum(ev["false_trip"][p]["cost"] for p in ("train", "heldout") if period in ("all", p))
    bad_events = sum(e["bad_total"] for e in evs)
    n = len(evs)
    return {
        "period": period, "label": PERIOD_LABEL[period], "events": n, "caught": len(caught),
        "missed": n - len(caught),
        "missed_ids": [e["event_id"] for e in evs if not e["caught"]],
        "median_delay_h": median_or_none([e["delay"] for e in caught]),
        "mean_delay_h": (sum(e["delay"] for e in caught) / len(caught)) if caught else None,
        "false_trips": sum(1 for t in trips if t["false"]),
        "trips": len(trips), "switches": sum(per_day.values()),
        "switches_per_day": sum(per_day.values()) / days,
        "worst_day_switches": max(per_day.values()) if per_day else 0,
        "returns": len(returns), "premature_returns": sum(1 for t in returns if t["premature"]),
        "retripped": sum(1 for t in returns if t["retrip"]),
        "median_recovery_after_end_h": median_or_none([e["recovery_after_end"] for e in caught]),
        "bad_served": sum(e["bad_served"] for e in evs), "rules_cost": sum(e["rules_cost"] for e in evs),
        "bad_events": bad_events, "false_trip_decisions": ft_dec, "false_trip_cost": ft_cost,
        "bad_total": bad_events + ft_cost, "bad_per_event": (bad_events + ft_cost) / n if n else 0.0,
        "exposure": sum(e["exposure"] for e in evs),
        "protected": sum(e["protected"] for e in evs), "excess": sum(e["excess"] for e in evs),
        "unneeded": sum(e["unneeded"] for e in evs),
        "unneeded_cost": sum(e["cost_unneeded"] for e in evs),
        "protected_cost": sum(e["cost_protected"] for e in evs),
        "excess_cost": sum(e["cost_excess"] for e in evs),
    }


# ---------------------------------------------------------------------------
# The manual process
# ---------------------------------------------------------------------------
def manual_sim(data: dict, cluster_n: int = CLUSTER_COMPLAINTS_3H, delay: int = MANUAL_DECISION_DELAY_H) -> tuple:
    """Returns (fb, info). fb is the all-segments schedule; info[event_id] has the timeline."""
    comp = data["comp_all"]
    fb = {s: [False] * HOURS for s in SEGMENTS}
    info = {}
    for ev in data["events"]:
        cluster = None
        for h in range(ev["start"], min(HOURS, ev["end"] + 12)):
            if sum(comp[max(0, h - 2):h + 1]) >= cluster_n:
                cluster = h
                break
        switch = None if cluster is None else cluster + delay
        acted = switch is not None and switch < ev["end"]
        back = ev["end"] + delay if acted else None
        if acted:
            for h in range(switch, min(back, HOURS)):
                for s in SEGMENTS:
                    fb[s][h] = True
        info[ev["event_id"]] = {"cluster_hour": cluster, "switch_hour": switch, "acted": acted,
                                "back_hour": back,
                                "complaints_peak_3h": max(sum(comp[max(0, h - 2):h + 1])
                                                          for h in range(ev["start"], min(HOURS, ev["end"] + 12)))}
    return fb, info


def run(data: dict, cluster_n: int = CLUSTER_COMPLAINTS_3H, delay: int = MANUAL_DECISION_DELAY_H) -> dict:
    fb, info = manual_sim(data, cluster_n, delay)
    ev = evaluate(data, fb, "service")
    for e in ev["events"]:
        e.update({"manual": info[e["event_id"]]})
    return {"fb": fb, "info": info, "eval": ev}


def sensitivity(data: dict) -> list:
    """Manual result under other values of the two assumptions (days 1-90)."""
    out = []
    for c in (6, 9, CLUSTER_COMPLAINTS_3H):
        for d in (1, 2, MANUAL_DECISION_DELAY_H):
            q = summarize_period(data, run(data, c, d)["eval"], "all")
            out.append({"cluster": c, "delay": d, "switched": q["caught"], "events": q["events"],
                        "bad_per_event": q["bad_per_event"], "bad_served": q["bad_served"]})
    return out


def summarize(data: dict) -> dict:
    r = run(data)
    s = {p: summarize_period(data, r["eval"], p) for p in PERIODS}
    s["assumptions"] = {"cluster_complaints_3h": CLUSTER_COMPLAINTS_3H,
                        "decision_delay_h": MANUAL_DECISION_DELAY_H}
    s["never_noticed_ids"] = [e["event_id"] for e in r["eval"]["events"] if not e["manual"]["acted"]]
    return s


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    r = run(data)
    ev, info = r["eval"], r["info"]
    s = {p: summarize_period(data, ev, p) for p in PERIODS}
    a = s["all"]
    total_dec = sum(sum(data["m"][x]["dec"]) for x in SEGMENTS)

    print("\n" + "=" * 100)
    print("Step 1 - Status quo: 'we will switch it off manually'")
    print("=" * 100)
    print(f"\n{len(SEGMENTS)} segments, {HOURS // 24} days, {len(data['events'])} degradation events, "
          f"{total_dec:,} decisions. Data is synthetic and seeded; no model is used anywhere.")
    print("Thresholds elsewhere in this walkthrough are set on days 1-60 and scored on days 61-90; "
          "this step has no threshold, so both periods are shown.\n")
    print("ASSUMPTIONS (modeled):")
    print(f"  A1  a person notices when complaints, all segments together, reach "
          f"{CLUSTER_COMPLAINTS_3H} in a rolling 3 hours")
    print(f"  A2  then {MANUAL_DECISION_DELAY_H} hours to decide and flip the switch, and "
          f"{MANUAL_DECISION_DELAY_H} hours after the event ends to flip it back")
    print("  A3  the switch is all-or-nothing: every segment moves to the rules path")
    print("  A4  triage is perfect, so every manual number here is a floor on the harm")
    print("  A5  a cluster noticed after the event has ended triggers no switch\n")

    print(f"{'event':<5} {'starts':<14} {'type':<17} {'segments':<14} {'hrs':>3} "
          f"{'noticed':<14} {'switch':<14} {'delay':>6} {'bad served':>10} {'bad total':>9}")
    print("-" * 112)
    for i, e in enumerate(data["events"]):
        x, mi = ev["events"][i], info[e["event_id"]]
        noticed = hour_label(mi["cluster_hour"]) if mi["cluster_hour"] is not None else "never"
        switch = hour_label(mi["switch_hour"]) if mi["acted"] else "no switch"
        delay = f"{x['delay']} h" if x["caught"] else "n/a"
        print(f"{e['event_id']:<5} {hour_label(e['start']):<14} {type_label(e['type']):<17} "
              f"{seg_list(e['segments']):<14} {e['end'] - e['start']:>3} {noticed:<14} {switch:<14} "
              f"{delay:>6} {rnd(x['bad_served']):>10,} {rnd(x['bad_total']):>9,}")
    print("\n  bad served = bad decisions from the degraded model path; bad total adds the quality gap of "
          "the rules path\n  for every decision the manual switch moved (including healthy segments). "
          "Segments: cons consumer, smb small business, aff affluent, ntb new to bank.")

    print("\nRESULT (by period)")
    for p in ("train", "heldout", "all"):
        q = s[p]
        print(f"  {q['label']:<11} events {q['events']:>2}   switched in time {q['caught']:>2}   "
              f"not switched {q['missed']:>2}   median delay {fmt_h(q['median_delay_h'])} h   "
              f"bad decisions per event {rnd(q['bad_per_event']):,}")
    print(f"\n  Events with a manual switch before they ended:  {a['caught']} of {a['events']}")
    print(f"  Events nobody switched for: {', '.join(a['missed_ids'])}")
    print(f"  Median hours from event start to the switch (those switched): {fmt_h(a['median_delay_h'])} h "
          f"(modeled: built on assumptions A1 and A2)")
    print(f"  Bad decisions served by the degraded model path: {rnd(a['bad_served']):,} of "
          f"{rnd(a['exposure']):,} that doing nothing would have served")
    print(f"  Healthy-segment decisions moved to the rules path by the all-or-nothing switch: "
          f"{a['unneeded']:,} (cost {rnd(a['unneeded_cost']):,} bad-decision equivalents)")

    print("\nSENSITIVITY to the two assumptions (days 1-90; the run above is the last row)")
    print(f"  For reference, doing nothing serves {rnd(a['exposure'] / a['events']):,} bad decisions per event "
          f"({rnd(a['exposure']):,} over {a['events']} events).")
    print(f"  {'complaints to notice':>20} {'decision delay':>15} {'switched in time':>17} {'bad decisions per event':>24}")
    for x in sensitivity(data):
        print(f"  {x['cluster']:>20} {str(x['delay']) + ' h':>15} {str(x['switched']) + ' of ' + str(x['events']):>17} "
              f"{rnd(x['bad_per_event']):>24,}")

    rows = []
    for i, e in enumerate(data["events"]):
        x, mi = ev["events"][i], info[e["event_id"]]
        rows.append([e["event_id"], e["period"], e["type"], ";".join(e["segments"]), e["start"], e["end"],
                     "" if mi["cluster_hour"] is None else mi["cluster_hour"],
                     "" if not mi["acted"] else mi["switch_hour"], "" if x["delay"] is None else x["delay"],
                     rnd(x["bad_served"]), rnd(x["bad_total"]), x["unneeded"]])
    with open(OUT_DIR / "step_01_events.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["event_id", "period", "type", "segments", "start_hour", "end_hour", "cluster_hour",
                    "switch_hour", "delay_h", "bad_served", "bad_total", "healthy_decisions_moved"])
        w.writerows(rows)
    with open(OUT_DIR / "step_01_summary.json", "w") as f:
        json.dump({p: {k: v for k, v in s[p].items()} for p in PERIODS}, f, indent=2, default=str)
    print("\nWrote src/out/step_01_events.csv and step_01_summary.json")


if __name__ == "__main__":
    main()
