"""Step 4 - The fix: KillSwitch.

KillSwitch turns "we will switch it off manually" into a defined trigger, a per-segment switch, a
way back, and a drill scorecard. Plain rules, no model. The fallback target is a stub rules path
whose quality numbers the generator set (data/fallback_rules.csv); they are not measurements.

  1. Signals. Four per segment and hour: error rate, override rate, latency and drift score. Each
     is scored against the segment's own healthy days-1-60 level over a 3-hour window. Rates are
     scored in standard errors (so a quiet night hour does not shout); a rate is not scored when
     the window holds fewer than 60 decisions.
  2. Tiers. Warn: the worst signal's score is at or above the warn level for 2 hours running; a
     person is told, nothing switches. Trip: the same at the trip level; that segment, and only
     that segment, moves to the rules path.
  3. Hysteresis and cool-off. A tripped segment stays on the rules path for at least 6 hours and
     returns only after its score stays under the clear level (half the trip level) for 4 hours
     running. Nothing flaps in between.
  4. Drill scorecard. Every drill is judged on three things: it worked, it was fast enough, and it
     ran on a fresh rules version. A scenario is ready only if its last drill passed all three.
  5. The trip level is fitted on days 1-60: the lowest candidate whose false trips stay within the
     same budget the single threshold in step 2 was tuned to. Days 61-90 are only scored.

Run (from src/):
    python3 step_04_with_killswitch.py

Output: a readable summary, plus out/step_04_*.csv and out/step_04_summary.json.
"""

from __future__ import annotations

import csv
import json
import math
import statistics

from step_01_manual_switch_off import (
    HOURS, MANUAL_DECISION_DELAY_H, OUT_DIR, PERIODS, PERIOD_LABEL, RETRIP_H, SEGMENTS, TRAIN_END, evaluate, fmt_h, healthy_hours, hour_label,
    load_all, rnd, seg_list, seg_long, summarize_period, type_label,
)
from step_01_manual_switch_off import run as run_manual
from step_01_manual_switch_off import summarize as summarize_step1
from step_02_single_threshold_alert import analyze as analyze_step2
from step_03_deficiencies_exposed import drill_stats, policy_num

SIGNALS = ["error_rate", "override_rate", "latency", "drift"]
EVENTS_PER_QUARTER = 4          # assumption (modeled): degradation events a quarter in a real service
EVENTS_PER_QUARTER_SENS = [2, 4, 8, 12]
REQUIRED_SCENARIOS = ["full_switch_off", "segment_switch_off", "upstream_outage", "model_regression",
                      "tool_failure", "drift", "recovery_return"]
TARGET_SENS = [30, 45, 60]


# ---------------------------------------------------------------------------
# Policy parameters (data/policy.csv is the source of truth)
# ---------------------------------------------------------------------------
def params(data: dict) -> dict:
    p = data["policy"]
    return {"window": int(p["window_hours"]["value"]),
            "min_decisions": int(p["min_window_decisions"]["value"]),
            "persist": int(p["persistence_hours"]["value"]),
            "warn_fraction": float(p["warn_fraction"]["value"]),
            "clear_fraction": float(p["clear_fraction"]["value"]),
            "clear_hours": int(p["clear_hours"]["value"]),
            "cool_off": int(p["cool_off_hours"]["value"]),
            "grid": [float(x) for x in p["trip_level_candidates"]["value"].split(";")],
            "budget": int(p["false_trip_budget_days_1_60"]["value"])}


# ---------------------------------------------------------------------------
# Baselines and scores
# ---------------------------------------------------------------------------
def baselines(data: dict) -> dict:
    """Each segment's normal level, from the healthy hours of days 1-60 only."""
    hh = healthy_hours(data)
    out = {}
    for s in SEGMENTS:
        m = data["m"][s]
        n = sum(m["dec"][h] for h in hh)
        lat = [m["lat"][h] for h in hh]
        drift = [m["drift"][h] for h in hh]
        out[s] = {"p_err": sum(round(m["err"][h] * m["dec"][h]) for h in hh) / n,
                  "p_ovr": sum(round(m["ovr"][h] * m["dec"][h]) for h in hh) / n,
                  "mu_lat": statistics.mean(lat), "sd_lat": statistics.pstdev(lat),
                  "mu_drift": statistics.mean(drift), "sd_drift": statistics.pstdev(drift)}
    return out


def seg_scores(data: dict, base: dict, P: dict) -> dict:
    """Per segment and hour: the score of each signal (in standard errors above normal, never
    negative), the worst of them, and which signal it was."""
    w, min_dec = P["window"], P["min_decisions"]
    out = {}
    for s in SEGMENTS:
        m, b = data["m"][s], base[s]
        z = {k: [0.0] * HOURS for k in SIGNALS}
        for h in range(w - 1, HOURS):
            idx = range(h - w + 1, h + 1)
            n = sum(m["dec"][i] for i in idx)
            if n >= min_dec:
                ke = sum(round(m["err"][i] * m["dec"][i]) for i in idx)
                ko = sum(round(m["ovr"][i] * m["dec"][i]) for i in idx)
                z["error_rate"][h] = max(0.0, (ke / n - b["p_err"]) / math.sqrt(b["p_err"] * (1 - b["p_err"]) / n))
                z["override_rate"][h] = max(0.0, (ko / n - b["p_ovr"]) / math.sqrt(b["p_ovr"] * (1 - b["p_ovr"]) / n))
            lat = sum(m["lat"][i] for i in idx) / w
            dr = sum(m["drift"][i] for i in idx) / w
            z["latency"][h] = max(0.0, (lat - b["mu_lat"]) / (b["sd_lat"] / math.sqrt(w)))
            z["drift"][h] = max(0.0, (dr - b["mu_drift"]) / (b["sd_drift"] / math.sqrt(w)))
        score = [max(z[k][h] for k in SIGNALS) for h in range(HOURS)]
        lead = [max(SIGNALS, key=lambda k: z[k][h]) for h in range(HOURS)]
        out[s] = {"z": z, "score": score, "lead": lead}
    return out


# ---------------------------------------------------------------------------
# The state machine
# ---------------------------------------------------------------------------
def segment_schedule(score: list, trip_z: float, P: dict) -> list:
    """True in the hours a segment is served by the rules path.

    Metrics of hour h decide hour h+1. Trip: score >= trip level for `persist` hours running.
    Return: after the cool-off, once the score has been under the clear level for `clear_hours`."""
    fb = [False] * HOURS
    state, trip_at, below = False, -1, 0
    clear_level = P["clear_fraction"] * trip_z
    for h in range(HOURS):
        fb[h] = state
        if not state:
            if h >= P["persist"] - 1 and all(score[h - i] >= trip_z for i in range(P["persist"])):
                state, trip_at, below = True, h, 0
        else:
            below = below + 1 if score[h] < clear_level else 0
            if h - trip_at >= P["cool_off"] and below >= P["clear_hours"]:
                state = False
    return fb


def warn_condition(score: list, warn_z: float, P: dict) -> list:
    return [h >= P["persist"] - 1 and all(score[h - i] >= warn_z for i in range(P["persist"])) for h in range(HOURS)]


def schedules(scores: dict, trip_z: float, P: dict) -> dict:
    return {s: segment_schedule(scores[s]["score"], trip_z, P) for s in SEGMENTS}


def warn_episodes(cond: list, fb: list, gap: int = 6) -> list:
    """Warn episodes (runs of the warn condition, merged across gaps of up to `gap` hours), as
    (first, last) hours, keeping those that start while the segment is still on the model path."""
    eps, a, last = [], None, None
    for h, v in enumerate(cond):
        if not v:
            continue
        if a is None:
            a, last = h, h
        elif h - last <= gap + 1:
            last = h
        else:
            eps.append((a, last))
            a, last = h, h
    if a is not None:
        eps.append((a, last))
    return [(a, b) for a, b in eps if not fb[a]]


# ---------------------------------------------------------------------------
# Fit on days 1-60, score on both
# ---------------------------------------------------------------------------
def fit_trip_level(data: dict, scores: dict, P: dict) -> tuple:
    """Lowest candidate trip level whose false trips on days 1-60 stay within the budget."""
    table = []
    for z in P["grid"]:
        ev = evaluate(data, schedules(scores, z, P), "segment")
        q = {p: summarize_period(data, ev, p) for p in ("train", "heldout")}
        table.append({"trip_z": z, "train_false": q["train"]["false_trips"], "train_caught": q["train"]["caught"],
                      "train_events": q["train"]["events"], "heldout_false": q["heldout"]["false_trips"],
                      "heldout_caught": q["heldout"]["caught"], "heldout_events": q["heldout"]["events"],
                      "heldout_bad_per_event": q["heldout"]["bad_per_event"]})
    chosen = next((r["trip_z"] for r in table if r["train_false"] <= P["budget"]), P["grid"][-1])
    return chosen, table


def analyze(data: dict) -> dict:
    P = params(data)
    base = baselines(data)
    scores = seg_scores(data, base, P)
    z_fit, fit_table = fit_trip_level(data, scores, P)
    fb = schedules(scores, z_fit, P)
    ev = evaluate(data, fb, "segment")
    summary = {p: summarize_period(data, ev, p) for p in PERIODS}

    warn_z = P["warn_fraction"] * z_fit
    conds = {s: warn_condition(scores[s]["score"], warn_z, P) for s in SEGMENTS}
    warns = {s: warn_episodes(conds[s], fb[s]) for s in SEGMENTS}
    trips_by_seg = {s: [t["hour"] for t in ev["trips"] if t["stream"] == s] for s in SEGMENTS}

    warn_rows = []
    for s in SEGMENTS:
        for a, b in warns[s]:
            led = any(a <= t - 1 <= b + 12 for t in trips_by_seg[s])
            warn_rows.append({"segment": s, "first": a, "last": b, "led_to_trip": led})
    leads = []
    for t in ev["trips"]:
        if t["false"]:
            continue
        cross = t["hour"] - 1
        w0 = cross
        while w0 - 1 >= 0 and conds[t["stream"]][w0 - 1]:
            w0 -= 1
        leads.append(cross - w0)

    # Per event details: warn hour per affected segment, peak scores per signal.
    for i, e in enumerate(data["events"]):
        x = ev["events"][i]
        x["peak"] = {k: max((scores[s]["z"][k][h] for s in e["segments"] for h in range(e["start"], e["end"])),
                            default=0.0) for k in SIGNALS}
        x["peak_score"] = max(x["peak"].values())
        # A warn raised on the metrics of hour h is seen from hour h+1, the same clock as a trip.
        wh = min((h for s in e["segments"] for h in range(e["start"], e["end"]) if conds[s][h]), default=None)
        x["warn_hour"] = None if wh is None else wh + 1
        for s, d in x["per_stream"].items():
            w1 = next((h for h in range(e["start"], e["end"]) if conds[s][h]), None)
            d["warn"] = None if w1 is None else w1 + 1
            d["lead_signal"] = scores[s]["lead"][d["first"] - 1] if d["first"] is not None else None

    return {"P": P, "base": base, "scores": scores, "z_fit": z_fit, "warn_z": warn_z,
            "clear_z": P["clear_fraction"] * z_fit, "fit_table": fit_table, "fb": fb, "eval": ev,
            "summary": summary, "warn_rows": warn_rows, "leads": leads, "conds": conds}


# ---------------------------------------------------------------------------
# Drill scorecard
# ---------------------------------------------------------------------------
def drill_scorecard(data: dict, target: int = None) -> dict:
    ds = drill_stats(data)
    target = ds["target"] if target is None else target
    rows = []
    for d in data["drills"]:
        gaps = []
        if not d["success"]:
            status = "FAIL"
            gaps.append(d["reason"])
        else:
            if d["minutes"] > target:
                gaps.append(f"slow: {d['minutes']} min against a {target} min target")
            if d["age_days"] > ds["stale_after"]:
                gaps.append(f"stale rules version ({d['age_days']} days old)")
            status = "PASS" if not gaps else "PASS WITH GAPS"
        rows.append({"drill_id": d["drill_id"], "date_hour": d["date_hour"], "scenario": d["scenario"],
                     "status": status, "gaps": "; ".join(gaps), "minutes": d["minutes"], "age_days": d["age_days"]})
    cadence = policy_num(data, "drill_cadence_days")
    scen = []
    for sc in REQUIRED_SCENARIOS:
        mine = [r for r in rows if r["scenario"] == sc]
        last = max(mine, key=lambda r: r["date_hour"]) if mine else None
        days_since = None if last is None else (HOURS - last["date_hour"]) // 24
        if last is None:
            state, why = "NOT READY", "never drilled"
        elif last["status"] != "PASS":
            state, why = "NOT READY", f"last drill {last['drill_id']}: {last['status'].lower()}"
        elif days_since > cadence:
            state, why = "NOT READY", f"last drill {days_since} days ago (cadence {cadence})"
        else:
            state, why = "READY", f"last drill {last['drill_id']} passed {days_since} days ago"
        scen.append({"scenario": sc, "drills": len(mine), "state": state, "why": why, "days_since": days_since})
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("PASS", "PASS WITH GAPS", "FAIL")}
    return {"rows": rows, "scenarios": scen, "counts": counts, "target": target, "cadence": cadence,
            "ready": sum(1 for r in scen if r["state"] == "READY"), "required": len(scen), "stats": ds}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def utility(data: dict, man: dict, thr: dict, ks: dict, drills: dict) -> dict:
    m, t, k = man["heldout"], thr["heldout"], ks["heldout"]
    held_dec = sum(data["m"][s]["dec"][h] for s in SEGMENTS for h in range(TRAIN_END, HOURS))
    # Work from the rounded figures that are printed, so every difference can be redone by hand.
    r_man, r_thr, r_ks = rnd(m["bad_per_event"]), rnd(t["bad_per_event"]), rnd(k["bad_per_event"])
    d_thr = r_thr - r_ks
    d_man = r_man - r_ks
    return {"manual": r_man, "threshold": r_thr, "killswitch": r_ks,
            "delta_vs_threshold": d_thr, "delta_vs_manual": d_man,
            "per_quarter_vs_threshold": d_thr * EVENTS_PER_QUARTER, "per_quarter_vs_manual": d_man * EVENTS_PER_QUARTER,
            "events_per_quarter": EVENTS_PER_QUARTER,
            "sens": [{"events_per_quarter": n, "vs_threshold": d_thr * n, "vs_manual": d_man * n}
                     for n in EVENTS_PER_QUARTER_SENS],
            "haircut_fail_rate": drills["stats"]["fail_rate"],
            "haircut_per_event": d_thr * (1 - drills["stats"]["fail_rate"]),
            "heldout_decisions": held_dec,
            "rate_per_100k": {n: 100000 * v["bad_total"] / held_dec for n, v in
                              (("manual", m), ("threshold", t), ("killswitch", k))}}


# ---------------------------------------------------------------------------
# Per-event payload (the app and the demo use this)
# ---------------------------------------------------------------------------
def event_payload(data: dict, A: dict, man: dict, thr: dict, i: int) -> dict:
    e = data["events"][i]
    kx, mx, tx = A["eval"]["events"][i], man["eval"]["events"][i], thr["eval"]["events"][i]
    mi = man["info"][e["event_id"]]
    return {"event_id": e["event_id"], "type": e["type"], "segments": e["segments"], "start": e["start"],
            "end": e["end"], "bad_rate": e["bad"], "period": e["period"], "ramp": e["ramp"],
            "decisions_in_event": sum(data["m"][s]["dec"][h] for s in e["segments"] for h in range(e["start"], e["end"])),
            "exposure": kx["exposure"],
            "manual": {"cluster_hour": mi["cluster_hour"], "switch_hour": mi["switch_hour"], "acted": mi["acted"],
                       "back_hour": mi["back_hour"], "delay": mx["delay"], "bad_served": mx["bad_served"],
                       "bad_total": mx["bad_total"], "unneeded": mx["unneeded"], "protected": mx["protected"],
                       "excess": mx["excess"], "peak_complaints_3h": mi["complaints_peak_3h"]},
            "threshold": {"caught": tx["caught"], "hour": tx["detect_hour"], "delay": tx["delay"],
                          "bad_served": tx["bad_served"], "bad_total": tx["bad_total"], "unneeded": tx["unneeded"]},
            "killswitch": {"caught": kx["caught"], "delay": kx["delay"], "detect_hour": kx["detect_hour"],
                           "segments_moved": [s for s in SEGMENTS if kx["per_stream"].get(s, {}).get("first") is not None],
                           "other_segments_on_rules": [s for s in sorted(kx["segments_moved"], key=SEGMENTS.index)
                                                       if s not in e["segments"]],
                           "per_segment": kx["per_stream"], "bad_served": kx["bad_served"],
                           "bad_total": kx["bad_total"], "protected": kx["protected"], "unneeded": kx["unneeded"],
                           "excess": kx["excess"], "recovery_after_end": kx["recovery_after_end"],
                           "warn_hour": kx["warn_hour"], "peak": kx["peak"], "peak_score": kx["peak_score"]}}


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------
def natural_units(data: dict, A: dict) -> list:
    """The fitted thresholds in the units a person reads, per segment, for a typical daytime window."""
    P, base = A["P"], A["base"]
    rows = []
    for s in SEGMENTS:
        m = data["m"][s]
        wins = sorted(sum(m["dec"][h - j] for j in range(P["window"])) for h in range(P["window"] - 1, TRAIN_END)
                      if 9 <= h % 24 <= 17)
        n_typ = wins[len(wins) // 2]
        b = base[s]
        row = {"segment": s, "n_typ": n_typ}
        for name, z in (("warn", A["warn_z"]), ("trip", A["z_fit"]), ("clear", A["clear_z"])):
            row[name] = {"error_rate": b["p_err"] + z * math.sqrt(b["p_err"] * (1 - b["p_err"]) / n_typ),
                         "latency": b["mu_lat"] + z * b["sd_lat"] / math.sqrt(P["window"]),
                         "drift": b["mu_drift"] + z * b["sd_drift"] / math.sqrt(P["window"])}
        row["base_err"], row["base_lat"], row["base_drift"] = b["p_err"], b["mu_lat"], b["mu_drift"]
        rows.append(row)
    return rows


def summarize(data: dict) -> dict:
    A = analyze(data)
    man = run_manual(data)
    s2 = analyze_step2(data)
    s1 = summarize_step1(data)
    drills = drill_scorecard(data)
    thr = {"train": s2["tuned"]["train"], "heldout": s2["tuned"]["heldout"], "all": s2["tuned"]["all"]}
    util = utility(data, s1, thr, A["summary"], drills)
    return {"A": A, "man": man, "s1": s1, "s2": s2, "thr": thr, "drills": drills, "util": util}


def _row(label: str, q: dict) -> str:
    return (f"  {label:<26} caught {q['caught']:>2} of {q['events']:>2}   median delay {fmt_h(q['median_delay_h']):>4} h   "
            f"false trips {q['false_trips']:>3}   switches/day {q['switches_per_day']:.2f}   "
            f"bad decisions per event {rnd(q['bad_per_event']):>5,}")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    S = summarize(data)
    A, man, s1, s2, drills, util = S["A"], S["man"], S["s1"], S["s2"], S["drills"], S["util"]
    P, ev, sm = A["P"], A["eval"], A["summary"]
    thr = S["thr"]

    print("\n" + "=" * 100)
    print("Step 4 - With KillSwitch: tiers per segment, hysteresis, cool-off, drills, a way back")
    print("=" * 100)
    print("\nPolicy structure (data/policy.csv): window %d h, rates scored only with at least %d decisions in the window," % (
        P["window"], P["min_decisions"]))
    print("  2 hours running to warn or trip, warn at %.2f x trip level, return only under %.2f x trip level for %d hours," % (
        P["warn_fraction"], P["clear_fraction"], P["clear_hours"]))
    print("  at least %d hours on the rules path after a trip. Plain rules; the fallback quality numbers are stubs." % P["cool_off"])
    print("  Metrics are hourly and an hour decides the next one, so the fastest possible trip is %d hours after an event starts.\n" % P["persist"])

    print(f"FIT on days 1-60: the lowest trip level (in standard errors) with at most {P['budget']} false trips")
    print("The right-hand columns are shown for honesty; days 61-90 were not used to choose.")
    print(f"  {'trip level':>10} {'false trips 1-60':>17} {'caught 1-60':>12} | {'false trips 61-90':>18} {'caught 61-90':>13} {'bad per event 61-90':>20}")
    for r in A["fit_table"]:
        mark = "   <- fitted" if r["trip_z"] == A["z_fit"] else ""
        print(f"  {r['trip_z']:>10.1f} {r['train_false']:>17} {str(r['train_caught']) + ' of ' + str(r['train_events']):>12} | "
              f"{r['heldout_false']:>18} {str(r['heldout_caught']) + ' of ' + str(r['heldout_events']):>13} "
              f"{rnd(r['heldout_bad_per_event']):>20,}{mark}")
    print(f"\nFitted levels: warn {A['warn_z']:.2f}, trip {A['z_fit']:.1f}, clear {A['clear_z']:.2f} standard errors above each segment's normal.")
    print("In units a person reads (typical daytime window; latency and drift are window means):")
    print(f"  {'segment':<15} {'window':>7} {'error rate: normal / warn / trip':>36} {'latency ms: normal / trip':>27} {'drift: normal / trip':>22}")
    for r in natural_units(data, A):
        print(f"  {r['segment']:<15} {r['n_typ']:>7,} {100 * r['base_err']:>8.2f}% / {100 * r['warn']['error_rate']:>5.2f}% / {100 * r['trip']['error_rate']:>5.2f}%"
              f" {r['base_lat']:>12.0f} / {r['trip']['latency']:>5.0f} {r['base_drift']:>12.3f} / {r['trip']['drift']:>5.3f}")

    print("\nTIMELINE per event (KillSwitch, days 1-90). Delay = hours from the start of the event to the first hour on the rules path.")
    print(f"  {'event':<5} {'type':<17} {'segments':<10} {'starts':<14} {'warn':<14} {'tripped':<14} {'delay':>6} {'moved':<11} {'back':>8} {'bad total':>10}")
    for i, e in enumerate(data["events"]):
        x = ev["events"][i]
        warn = hour_label(x["warn_hour"]) if x["warn_hour"] is not None else "-"
        trip = hour_label(x["detect_hour"]) if x["caught"] else "no trip"
        delay = f"{x['delay']} h" if x["caught"] else "n/a"
        trip_segs = [s for s in SEGMENTS if x["per_stream"].get(s, {}).get("first") is not None]
        moved = seg_list(trip_segs) if trip_segs else "-"
        back = f"+{x['recovery_after_end']} h" if x["recovery_after_end"] is not None and x["recovery_after_end"] >= 0 else (
            f"{x['recovery_after_end']} h" if x["recovery_after_end"] is not None else "-")
        print(f"  {e['event_id']:<5} {type_label(e['type']):<17} {seg_list(e['segments']):<10} {hour_label(e['start']):<14} "
              f"{warn:<14} {trip:<14} {delay:>6} {moved:<11} {back:>8} {rnd(x['bad_total']):>10,}")
    print("  back = hours after the event ended when the last tripped segment returned to the model path.")

    print("\nRECOVERY TIMELINE (segments that tripped)")
    print(f"  {'event':<5} {'segment':<15} {'tripped':<14} {'returned':<14} {'hours on rules path':>20} {'after event end':>16}")
    for i, e in enumerate(data["events"]):
        for s, d in ev["events"][i]["per_stream"].items():
            if d["first"] is None:
                continue
            ret = hour_label(d["return"]) if d["return"] is not None else "still on"
            on = f"{d['return'] - d['first']} h" if d["return"] is not None else "n/a"
            aft = f"{d['after_end']:+d} h" if d["after_end"] is not None else "n/a"
            print(f"  {e['event_id']:<5} {s:<15} {hour_label(d['first']):<14} {ret:<14} {on:>20} {aft:>16}")

    print("\nRESULT")
    print("Fitted on days 1-60, scored on days 61-90. Same budget, same data, three approaches:")
    for p in ("train", "heldout"):
        print(f"\n {PERIOD_LABEL[p]}")
        print(_row("manual switch-off (modeled)", s1[p]))
        print(_row("single threshold (tuned)", s2["tuned"][p]))
        print(_row("KillSwitch", sm[p]))
    h, t, m_ = sm["heldout"], s2["tuned"]["heldout"], s1["heldout"]
    print(f"\n Days 61-90 detail")
    print(f"  Bad decisions per 100,000 decisions: manual {util['rate_per_100k']['manual']:.0f}, single threshold "
          f"{util['rate_per_100k']['threshold']:.0f}, KillSwitch {util['rate_per_100k']['killswitch']:.0f}")
    print(f"  KillSwitch protected {h['protected']:,} decisions in the affected segments, moved {h['unneeded']:,} decisions "
          f"in segments no event touched, and stayed on the rules path for {h['excess']:,} decisions after events ended")
    print(f"  Cost of the rules path in bad-decision equivalents: while events were active {rnd(h['protected_cost']):,}, "
          f"after they ended {rnd(h['excess_cost']):,}, in segments no event touched {rnd(h['unneeded_cost']):,}, "
          f"false trips {rnd(h['false_trip_cost']):,}")
    print(f"  Returns {h['returns']}: {h['premature_returns']} before the event ended, {h['retripped']} re-tripped within {RETRIP_H} hours")
    a = sm["all"]
    print(f"  Days 1-90 returns {a['returns']}: {a['premature_returns']} before the event ended, {a['retripped']} re-tripped within {RETRIP_H} hours; "
          f"median {fmt_h(a['median_recovery_after_end_h'])} h from the end of an event to the return")
    n_w = len(A["warn_rows"])
    n_w_trip = sum(1 for r in A["warn_rows"] if r["led_to_trip"])
    lead1 = sum(1 for x in A["leads"] if x >= 1)
    print(f"  Warns raised (days 1-90): {n_w}; {n_w_trip} led to a trip, {n_w - n_w_trip} did not (a person looks and closes them). "
          f"The warn came an hour or more before the trip on {lead1} of {len(A['leads'])} justified trips "
          f"(median lead {fmt_h(statistics.median(A['leads']) if A['leads'] else None)} h)")

    tw, tn = s2["twice"]["all"], s2["tuned"]["all"]
    m_all, k_all = s1["all"], sm["all"]
    k_false = k_all["false_trips"]
    print("\nTHE SIX DEFICIENCIES, BEFORE AND AFTER (days 1-90)")
    print(f"  (1) Detection        manual switched for {m_all['caught']} of {m_all['events']} events; KillSwitch tripped for {k_all['caught']} of {k_all['events']} "
          f"(median {fmt_h(k_all['median_delay_h'])} h from the start of the event)")
    print(f"  (2) Misses and noise single threshold (tuned) missed {tn['missed']} of {tn['events']}; KillSwitch missed {k_all['missed']} "
          f"({', '.join(k_all['missed_ids'])}) with {k_false} false trips; twice-normal raised {tw['false_trips']}")
    print(f"  (3) Flapping         returns that re-tripped within {RETRIP_H} hours: twice-normal {tw['retripped']} of {tw['returns']}; "
          f"KillSwitch {k_all['retripped']} of {k_all['returns']}")
    print(f"  (4) Drills           the scorecard flags {drills['counts']['PASS WITH GAPS'] + drills['counts']['FAIL']} of {drills['stats']['drills']} drills "
          f"and marks {drills['ready']} of {drills['required']} scenarios ready; it scores the drills, it does not fix them")
    print(f"  (5) Recovery         returns before the event ended: twice-normal {tw['premature_returns']}, KillSwitch {k_all['premature_returns']}; "
          f"the price is a median {fmt_h(k_all['median_recovery_after_end_h'])} h on the rules path after an event ends")
    print(f"  (6) All-or-nothing   healthy decisions dragged along by an event's switch: manual {m_all['unneeded']:,}, "
          f"single threshold {tn['unneeded']:,}, twice-normal {tw['unneeded']:,}, KillSwitch {k_all['unneeded']:,} "
          f"(by construction: a segment trips only on its own signals)")

    print("\nDRILL SCORECARD (a drill passes only if it worked, was fast enough and used a fresh rules version)")
    dc = drills["counts"]
    print(f"  {dc['PASS']} PASS, {dc['PASS WITH GAPS']} PASS WITH GAPS, {dc['FAIL']} FAIL of {drills['stats']['drills']} drills "
          f"(target {drills['target']} minutes, rules version at most {drills['stats']['stale_after']} days old)")
    for r in drills["rows"]:
        print(f"    {r['drill_id']} {r['scenario']:<19} {r['status']:<15} {r['gaps']}")
    print(f"  Scenarios ready: {drills['ready']} of {drills['required']}")
    for r in drills["scenarios"]:
        print(f"    {r['scenario']:<19} {r['state']:<10} {r['why']}")
    sens = [drill_scorecard(data, t_)["counts"]["PASS"] for t_ in TARGET_SENS]
    print("  Clean passes if the target were " + ", ".join(f"{t_} min: {n}" for t_, n in zip(TARGET_SENS, sens)) + " (an assumption of the modeled bank).")

    tx_ev = s2["tuned"]["eval"]["events"]
    groups = {"caught by both": [], "caught only by KillSwitch": [], "caught only by the single threshold": [], "caught by neither": []}
    for i, e in enumerate(data["events"]):
        k_c, t_c = ev["events"][i]["caught"], tx_ev[i]["caught"]
        key = ("caught by both" if k_c and t_c else "caught only by KillSwitch" if k_c else
               "caught only by the single threshold" if t_c else "caught by neither")
        groups[key].append(i)
    print("\nWHERE EACH APPROACH WINS (days 1-90, bad decisions in the event windows, false trips not included)")
    print(f"  {'group':<38} {'events':>7} {'KillSwitch':>11} {'single threshold':>17} {'manual':>8}")
    for key, idx in groups.items():
        if not idx:
            continue
        ids = ", ".join(data["events"][i]["event_id"] for i in idx)
        print(f"  {key:<38} {len(idx):>7} {rnd(sum(ev['events'][i]['bad_total'] for i in idx)):>11,} "
              f"{rnd(sum(tx_ev[i]['bad_total'] for i in idx)):>17,} {rnd(sum(man['eval']['events'][i]['bad_total'] for i in idx)):>8,}   {ids}")
    both = groups["caught by both"]
    if both:
        k_b = sum(ev["events"][i]["bad_total"] for i in both)
        t_b = sum(tx_ev[i]["bad_total"] for i in both)
        verdict = ("the single threshold's instant return costs fewer bad decisions than KillSwitch's careful one"
                   if t_b < k_b else "KillSwitch also serves fewer bad decisions on the events both caught")
        print(f"  Where both trip, {verdict}.")

    print("\nUTILITY (days 61-90, per degradation event)")
    print(f"  Decisions served on days 61-90: {util['heldout_decisions']:,}")
    print(f"  Bad decisions per event: manual {util['manual']:,} (modeled), single threshold {util['threshold']:,}, "
          f"KillSwitch {util['killswitch']:,}")
    print(f"  Avoided per event versus the single threshold: {util['threshold']:,} - {util['killswitch']:,} = {util['delta_vs_threshold']:,} (measured on days 61-90)")
    print(f"  Avoided per event versus the manual process:   {util['manual']:,} - {util['killswitch']:,} = {util['delta_vs_manual']:,} (modeled: rests on the {MANUAL_DECISION_DELAY_H} h decision delay)")
    r_man, r_thr, r_ks = util["manual"], util["threshold"], util["killswitch"]
    print(f"  KillSwitch serves {100 * (r_thr - r_ks) / r_thr:.1f}% fewer bad decisions per event than the single threshold "
          f"and {100 * (r_man - r_ks) / r_man:.1f}% fewer than the manual plan (days 61-90)")
    print(f"  Assumed degradation events a quarter (modeled): {util['events_per_quarter']}")
    print(f"  Avoided per quarter versus the single threshold: {rnd(util['delta_vs_threshold'])} x {util['events_per_quarter']} = "
          f"{rnd(util['delta_vs_threshold']) * util['events_per_quarter']:,}")
    print(f"  Avoided per quarter versus the manual process: {rnd(util['delta_vs_manual'])} x {util['events_per_quarter']} = "
          f"{rnd(util['delta_vs_manual']) * util['events_per_quarter']:,} (modeled)")
    print("  Sensitivity to events a quarter (vs the single threshold): " + ", ".join(
        f"{x['events_per_quarter']} -> {rnd(util['delta_vs_threshold']) * x['events_per_quarter']:,}" for x in util["sens"]))
    print(f"  If the fallback itself failed as often as the drills did ({100 * util['haircut_fail_rate']:.0f}%), "
          f"the avoided figure per event would fall to about {rnd(util['haircut_per_event']):,} (modeled)")

    print("\nWHAT IT STILL GETS WRONG (known limit, left in on purpose)")
    silent = [i for i, e in enumerate(data["events"]) if e["type"] == "silent_error"]
    missed_all = [data["events"][i]["event_id"] for i, x in enumerate(ev["events"]) if not x["caught"]]
    for p in ("train", "heldout"):
        ids = [i for i in silent if data["events"][i]["period"] == p]
        miss = [i for i in ids if not ev["events"][i]["caught"]]
        served = sum(ev["events"][i]["bad_served"] for i in miss)
        print(f"  {PERIOD_LABEL[p]}: {len(miss)} of {len(ids)} silent errors missed, {rnd(served):,} bad decisions served in them")
    for i in silent:
        e, x = data["events"][i], ev["events"][i]
        print(f"    {e['event_id']} {seg_long(e['segments'])}, {e['end'] - e['start']} h: peak score {x['peak_score']:.1f} "
              f"(warn level {A['warn_z']:.2f}), {rnd(x['bad_served']):,} bad decisions served, {'tripped by chance' if x['caught'] else 'no trip'}")
    other = [e["event_id"] for e, x in zip(data["events"], ev["events"]) if not x["caught"] and e["type"] != "silent_error"]
    print(f"  Events missed that were not silent errors: {len(other)}" + (f" ({', '.join(other)})" if other else ""))
    print(f"  Silent errors move no signal enough to see; nothing in this repo detects them. A golden-set canary or an outcome")
    print(f"  backtest would (designed, not built). The trip level was fitted on {sm['train']['events']} synthetic events, so treat")
    print(f"  the fitted level as a property of this data, not of any real service; the fit table above shows how it moves.")
    print(f"  The way back is conservative: after events ended KillSwitch kept {sm['all']['excess']:,} decisions on the rules path "
          f"(days 1-90), a cost of {rnd(sm['all']['excess_cost']):,} bad-decision equivalents. A faster return is a design option, not tested here.")
    if A["leads"] and sum(1 for x in A["leads"] if x >= 1) * 2 < len(A["leads"]):
        print("  The warn tier bought little lead time: see the warn line above. It mostly puts a person in the loop on borderline signals.")

    # ---- files
    fit_rows = [["parameter", "scope", "value", "unit", "how_set"],
                ["trip_level", "per segment", f"{A['z_fit']:.1f}", "standard errors", "fitted on days 1-60"],
                ["warn_level", "per segment", f"{A['warn_z']:.2f}", "standard errors", "warn_fraction x trip level"],
                ["clear_level", "per segment", f"{A['clear_z']:.2f}", "standard errors", "clear_fraction x trip level"]]
    with open(OUT_DIR / "step_04_fitted_policy.csv", "w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(fit_rows)
    with open(OUT_DIR / "step_04_events.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["event_id", "period", "type", "segments", "start_hour", "end_hour", "detect_hour", "delay_h",
                    "segments_moved", "recovery_after_end_h", "bad_served", "bad_total"])
        for i, e in enumerate(data["events"]):
            x = ev["events"][i]
            w.writerow([e["event_id"], e["period"], e["type"], ";".join(e["segments"]), e["start"], e["end"],
                        "" if x["detect_hour"] is None else x["detect_hour"], "" if x["delay"] is None else x["delay"],
                        ";".join(sorted(x["segments_moved"], key=SEGMENTS.index)),
                        "" if x["recovery_after_end"] is None else x["recovery_after_end"],
                        rnd(x["bad_served"]), rnd(x["bad_total"])])
    with open(OUT_DIR / "step_04_drill_scorecard.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["drill_id", "scenario", "status", "gaps"])
        for r in drills["rows"]:
            w.writerow([r["drill_id"], r["scenario"], r["status"], r["gaps"]])
    with open(OUT_DIR / "step_04_fit.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["trip_level", "false_trips_1_60", "caught_1_60", "false_trips_61_90", "caught_61_90"])
        for r in A["fit_table"]:
            w.writerow([r["trip_z"], r["train_false"], r["train_caught"], r["heldout_false"], r["heldout_caught"]])
    out = {"z_fit": A["z_fit"], "warn_z": A["warn_z"], "clear_z": A["clear_z"],
           "summary": {p: sm[p] for p in PERIODS}, "utility": util,
           "drills": {k: v for k, v in drills.items() if k != "rows"}}
    with open(OUT_DIR / "step_04_summary.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWrote src/out/step_04_events.csv, step_04_fit.csv, step_04_drill_scorecard.csv, step_04_fitted_policy.csv and step_04_summary.json")


if __name__ == "__main__":
    main()
