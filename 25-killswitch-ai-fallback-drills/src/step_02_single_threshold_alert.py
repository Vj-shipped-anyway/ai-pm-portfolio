"""Step 2 - The basic approach: one threshold on the overall error rate.

The obvious first fix for "we will switch it off manually" is a single alert: watch the service's
overall error rate (errors over decisions, all four segments together) and, when an hour crosses
a threshold, move the whole service to the rules path. When the hour is back under the threshold,
move it back. No tiers, no segments, no hysteresis, no cool-off, no volume guard. That is the
basic version and it is deliberately basic.

The fallback is automatic in this step: the metric hour that crosses the threshold decides the
next hour. So there is no human delay here, which makes the comparison with step 1 conservative.

The threshold is set on days 1-60 and scored on days 61-90. Two settings are shown:

  * TUNED   the most sensitive threshold on a fixed grid whose false trips on days 1-60 stay
            within the budget (data/policy.csv: 2 unnecessary fallbacks in 60 days). The same
            budget is used to tune KillSwitch in step 4, so the comparison is like for like.
  * TWICE   twice the normal overall error rate, a common rule of thumb.

A trip is false if no degradation event touching the tripped scope was active in the 6 hours
before the metric crossed. The truth is known because the data is synthetic.

Run (from src/):
    python3 step_02_single_threshold_alert.py

Output: a readable summary, plus out/step_02_sweep.csv and out/step_02_summary.json.
"""

from __future__ import annotations

import csv
import json

from step_01_manual_switch_off import (
    HOURS, OUT_DIR, PERIODS, RETRIP_H, SEGMENTS, TRAIN_END, evaluate, fmt_h, healthy_hours, hour_label, load_all,
    rnd, seg_list, summarize_period, type_label,
)

T_GRID = [0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15]   # candidate thresholds


def overall_series(data: dict) -> list:
    """Overall error rate per hour: errors over decisions, all segments together."""
    m = data["m"]
    out = []
    for h in range(HOURS):
        n = sum(m[s]["dec"][h] for s in SEGMENTS)
        k = sum(round(m[s]["err"][h] * m[s]["dec"][h]) for s in SEGMENTS)
        out.append(k / n)
    return out


def normal_rate(data: dict) -> float:
    """Pooled overall error rate over the healthy hours of days 1-60."""
    m, hh = data["m"], healthy_hours(data)
    n = sum(m[s]["dec"][h] for s in SEGMENTS for h in hh)
    k = sum(round(m[s]["err"][h] * m[s]["dec"][h]) for s in SEGMENTS for h in hh)
    return k / n


def threshold_fb(data: dict, series: list, t: float) -> dict:
    """Service-wide schedule: the hour after an hour above t is served by the rules path."""
    arr = [False] + [series[h] > t for h in range(HOURS - 1)]
    return {s: list(arr) for s in SEGMENTS}


def budget(data: dict) -> int:
    return int(data["policy"]["false_trip_budget_days_1_60"]["value"])


def score(data: dict, series: list, t: float) -> dict:
    ev = evaluate(data, threshold_fb(data, series, t), "service")
    return {"eval": ev, **{p: summarize_period(data, ev, p) for p in PERIODS}}


def sweep(data: dict, series: list) -> list:
    """Every candidate threshold, scored on days 1-60 (the fit period)."""
    out = []
    for t in T_GRID:
        r = score(data, series, t)
        q = r["train"]
        night = sum(1 for x in r["eval"]["trips"] if x["false"] and x["hour"] < TRAIN_END
                    and (x["hour"] % 24 >= 22 or x["hour"] % 24 < 6))
        out.append({"threshold": t, "trips": q["trips"], "false_trips": q["false_trips"],
                    "false_at_night": night, "caught": q["caught"], "events": q["events"],
                    "switches_per_day": q["switches_per_day"]})
    return out


def fit_threshold(data: dict, series: list) -> float:
    """Lowest (most sensitive) candidate whose false trips on days 1-60 stay within the budget."""
    for row in sweep(data, series):
        if row["false_trips"] <= budget(data):
            return row["threshold"]
    return T_GRID[-1]


def analyze(data: dict) -> dict:
    series = overall_series(data)
    t_tuned = fit_threshold(data, series)
    t_twice = 2 * normal_rate(data)
    return {"series": series, "normal": normal_rate(data), "t_tuned": t_tuned, "t_twice": t_twice,
            "sweep": sweep(data, series), "tuned": score(data, series, t_tuned),
            "twice": score(data, series, t_twice)}


def summarize(data: dict) -> dict:
    a = analyze(data)
    return {"normal": a["normal"], "t_tuned": a["t_tuned"], "t_twice": a["t_twice"], "sweep": a["sweep"],
            "tuned": {p: a["tuned"][p] for p in PERIODS}, "twice": {p: a["twice"][p] for p in PERIODS}}


def _line(label: str, q: dict) -> str:
    return (f"  {label:<11} caught {q['caught']:>2} of {q['events']:>2}   median delay {fmt_h(q['median_delay_h']):>4} h   "
            f"false trips {q['false_trips']:>3}   switches/day {q['switches_per_day']:.2f}   "
            f"bad decisions per event {rnd(q['bad_per_event']):>5,}")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_all()
    a = analyze(data)
    series = a["series"]
    nrm = a["normal"]

    print("\n" + "=" * 100)
    print("Step 2 - The basic approach: one threshold on the overall error rate")
    print("=" * 100)
    print("\nRule: an hour with overall error rate above the threshold moves ALL segments to the rules path for")
    print("the next hour; the first hour under it moves them back. No tiers, segments, hysteresis or volume guard.")
    print(f"Normal overall error rate on healthy hours of days 1-60: {100 * nrm:.2f}%. The fit budget is "
          f"{budget(data)} false trips in days 1-60.\n")

    print("THRESHOLD SWEEP on days 1-60 (the fit period). Lower = more sensitive.")
    print(f"  {'threshold':>9} {'trips':>6} {'false trips':>12} {'of them 22:00-06:00':>20} {'events caught':>14} {'switches/day':>13}")
    for r in a["sweep"]:
        mark = "   <- tuned (most sensitive within budget)" if r["threshold"] == a["t_tuned"] else ""
        print(f"  {100 * r['threshold']:>8.1f}% {r['trips']:>6} {r['false_trips']:>12} {r['false_at_night']:>20} "
              f"{str(r['caught']) + ' of ' + str(r['events']):>14} {r['switches_per_day']:>13.2f}{mark}")

    for key, label, t in (("tuned", "TUNED", a["t_tuned"]), ("twice", "TWICE NORMAL", a["t_twice"])):
        r = a[key]
        print(f"\n{label}: threshold {100 * t:.2f}%")
        for p in ("train", "heldout", "all"):
            print(_line(r[p]["label"], r[p]))
        ev = r["eval"]
        print(f"  {'event':<5} {'type':<17} {'segments':<10} {'tripped':<15} {'delay':>6} {'bad total':>10}   (days 1-90)")
        for e, x in zip(data["events"], ev["events"]):
            tripped = hour_label(x["detect_hour"]) if x["caught"] else "never"
            delay = f"{x['delay']} h" if x["caught"] else "n/a"
            print(f"  {e['event_id']:<5} {type_label(e['type']):<17} {seg_list(e['segments']):<10} {tripped:<15} "
                  f"{delay:>6} {rnd(x['bad_total']):>10,}")

    t, w = a["tuned"], a["twice"]
    print("\nRESULT")
    print(f"  Tuned threshold {100 * a['t_tuned']:.1f}%: days 1-60 false trips {t['train']['false_trips']}, "
          f"events caught {t['train']['caught']} of {t['train']['events']}; "
          f"days 61-90 false trips {t['heldout']['false_trips']}, events caught {t['heldout']['caught']} of {t['heldout']['events']}")
    print(f"  Missed at the tuned threshold: {', '.join(t['all']['missed_ids'])} "
          f"({t['all']['missed']} of {t['all']['events']})")
    print(f"  Twice-normal threshold {100 * a['t_twice']:.1f}%: events caught {w['all']['caught']} of {w['all']['events']}, "
          f"false trips {w['all']['false_trips']}, {w['all']['switches']} fallback switches in 90 days "
          f"({w['all']['switches_per_day']:.2f} a day, worst day {w['all']['worst_day_switches']})")
    print(f"  Returns that re-tripped within {RETRIP_H} hours: tuned {t['all']['retripped']} of {t['all']['returns']}, "
          f"twice-normal {w['all']['retripped']} of {w['all']['returns']}")
    sw = a["sweep"]
    k = [r["threshold"] for r in sw].index(a["t_tuned"])
    if k > 0:
        r = sw[k - 1]
        print(f"  One step more sensitive ({100 * r['threshold']:.1f}%) breaks the budget with {r['false_trips']} false trips on days 1-60; "
              f"{r['false_at_night']} of them start between 22:00 and 06:00, when few decisions make the overall rate noisy.")
    sil = [i for i, e in enumerate(data["events"]) if e["type"] == "silent_error"]
    sil_hit = sum(1 for i in sil if w["eval"]["events"][i]["caught"])
    print(f"  At twice normal it also trips during {sil_hit} of {len(sil)} silent errors, which move no signal "
          f"({w['all']['switches_per_day']:.2f} switches a day), so 'events caught' overstates detection at that setting.")

    with open(OUT_DIR / "step_02_sweep.csv", "w", newline="") as f:
        cw = csv.writer(f, lineterminator="\n")
        cw.writerow(["threshold", "trips", "false_trips", "events_caught", "events", "switches_per_day"])
        for r in a["sweep"]:
            cw.writerow([r["threshold"], r["trips"], r["false_trips"], r["caught"], r["events"],
                         round(r["switches_per_day"], 3)])
    with open(OUT_DIR / "step_02_summary.json", "w") as f:
        json.dump({"normal": nrm, "t_tuned": a["t_tuned"], "t_twice": a["t_twice"],
                   "tuned": {p: t[p] for p in PERIODS}, "twice": {p: w[p] for p in PERIODS}}, f, indent=2, default=str)
    print("\nWrote src/out/step_02_sweep.csv and step_02_summary.json")


if __name__ == "__main__":
    main()
