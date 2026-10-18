"""Generates the KillSwitch synthetic data. Standard library only, seeded, deterministic.

Run:  python3 _generate.py        (writes six CSVs next to this file)

What it builds
  metrics_hourly.csv       90 days x 24 hours x 4 segments = 8,640 rows of service health signals.
  degradation_events.csv   12 degradation events. This is the truth: when each one starts and
                           ends, which segments it hits and how many decisions it spoils.
  fallback_rules.csv       per segment, the modeled decision quality of the rules path versus the
                           model path. These are STUB numbers set here, not measurements of any
                           real model or rules engine.
  drills.csv               10 planned fallback drills and how each one went.
  policy.csv               the policy design (window, persistence, hysteresis, cool-off, recovery
                           criteria, the fit rule) plus the assumptions of the modeled bank.

The truth is known because the data is synthetic: this script decides when the service is
degraded, so it can say exactly how many decisions each event spoiled. Nothing here comes from a
real bank, service, model, vendor or incident. No model is used anywhere in this repo.

Time. Hour 0 is EPOCH (a constant, never the clock). Days 1 to 60 are hours 0 to 1439 (where
thresholds are set); days 61 to 90 are hours 1440 to 2159 (held out, scored only). An event is
active for start_hour <= h < end_hour (end_hour is the first healthy hour).

Design choices (made from reasoning about how such a service behaves, before any detection
result was computed; see data/README.md):
  * Metric noise is binomial for the two rate signals (error_rate, override_rate), so small
    segments are noisy and night hours are noisy. Latency and drift score have independent
    gaussian noise.
  * Each event type moves a different set of signals. A silent_error moves none of them enough
    to see; it is the known limit.
  * Complaints follow the bad decisions with a lag and are proportional to the bad volume, so a
    small segment produces few complaints. That is why a manual process notices small segments
    late or never.
  * Drift ramps in over 12 hours; outage, tool failure and drift signals decay after the event
    ends (queues drain, the drift score relaxes), which is why signals lag the end of an event.
  * 10 benign one-hour blips (a retry storm, a slow minute) are scattered outside events. They
    are not degradations.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime
from pathlib import Path

SEED = 20261018
OUT = Path(__file__).parent

EPOCH = datetime(2026, 7, 1)        # hour 0 (a Wednesday); a constant, no clock is read
DAYS = 90
HOURS = DAYS * 24                   # 2160
TRAIN_HOURS = 60 * 24               # days 1-60: thresholds are set here
SEGMENTS = ["consumer", "small_business", "affluent", "new_to_bank"]

# Per-segment baseline. vol = decisions per hour at the weekday peak.
SEG = {
    "consumer":       dict(vol=420, err=0.008, lat=180.0, drift=0.080, ovr=0.020, sat_sun=0.85),
    "small_business": dict(vol=95,  err=0.011, lat=210.0, drift=0.085, ovr=0.035, sat_sun=0.35),
    "affluent":       dict(vol=60,  err=0.007, lat=170.0, drift=0.075, ovr=0.030, sat_sun=0.60),
    "new_to_bank":    dict(vol=45,  err=0.016, lat=240.0, drift=0.090, ovr=0.060, sat_sun=0.70),
}
HOUR_PROFILE = [0.20, 0.16, 0.13, 0.12, 0.14, 0.22, 0.38, 0.62, 0.85, 1.00, 1.00, 1.00,
                0.95, 1.00, 1.00, 0.95, 0.90, 0.85, 0.78, 0.70, 0.58, 0.45, 0.34, 0.26]
LAT_SIGMA_FRAC = 0.08               # latency noise, fraction of the segment mean
DRIFT_SIGMA = 0.015                 # drift score noise (absolute)
COMPLAINT_RATE = 0.0015             # baseline complaints per decision
DAY_SIGMA = 0.06                    # day-to-day volume noise
HOUR_SIGMA = 0.08                   # hour-to-hour volume noise

# What each event type does to the signals while it is active (scaled by the event's signal_scale).
#   err/ovr/drift are added; lat is a multiplier; tau is the decay time (hours) of the signals after
#   the event ends; c1 is complaints per spoiled decision; lag is hours from decision to complaint.
TYPES = {
    "model_regression": dict(err=0.030, ovr=0.040, lat=1.00, drift=0.030, c1=0.08, lag=2, tau=0.0),
    "upstream_outage":  dict(err=0.200, ovr=0.015, lat=3.00, drift=0.010, c1=0.15, lag=1, tau=2.0),
    "drift":            dict(err=0.006, ovr=0.020, lat=1.00, drift=0.280, c1=0.04, lag=3, tau=8.0),
    "tool_failure":     dict(err=0.080, ovr=0.010, lat=1.80, drift=0.000, c1=0.10, lag=1, tau=1.5),
    "silent_error":     dict(err=0.001, ovr=0.002, lat=1.00, drift=0.000, c1=0.003, lag=3, tau=0.0),
}

ALL = list(SEGMENTS)
# event_id, start day (1-based), start hour of day, duration hours, type, segments,
# bad_decision_rate, signal_scale, ramp_hours
EVENT_SPECS = [
    ("E01", 5, 14, 6, "tool_failure", ["new_to_bank"], 0.30, 1.0, 0),
    ("E02", 11, 6, 60, "drift", ["affluent"], 0.14, 1.0, 12),
    ("E03", 17, 9, 14, "model_regression", ["consumer", "small_business"], 0.18, 1.0, 0),
    ("E04", 24, 9, 4, "upstream_outage", ALL, 0.35, 1.0, 0),
    ("E05", 31, 10, 36, "silent_error", ["small_business"], 0.10, 1.0, 0),
    ("E06", 41, 22, 8, "tool_failure", ["affluent", "small_business"], 0.28, 0.9, 0),
    ("E07", 52, 8, 30, "silent_error", ["new_to_bank"], 0.09, 1.0, 0),
    ("E08", 63, 11, 16, "model_regression", ["affluent"], 0.20, 1.0, 0),
    ("E09", 68, 15, 5, "upstream_outage", ["consumer", "small_business"], 0.32, 0.9, 0),
    ("E10", 73, 9, 40, "silent_error", ["affluent"], 0.11, 1.0, 0),
    ("E11", 79, 3, 48, "drift", ["new_to_bank"], 0.20, 1.0, 12),
    ("E12", 85, 13, 12, "model_regression", ["consumer"], 0.16, 0.8, 0),
]

# Stub decision quality of the model path and the rules path, per segment. Set here, not measured.
RULES_QUALITY = {
    "consumer":       (0.94, 0.90),
    "small_business": (0.91, 0.84),
    "affluent":       (0.93, 0.85),
    "new_to_bank":    (0.88, 0.76),
}

N_BLIPS = 10                        # benign one-hour blips: 6 error blips, 4 latency blips
BLIP_LATENCY_MULT = 1.5

# Drills: day, hour of day, scenario. Rules-version refresh days (negative = before hour 0).
DRILL_SPECS = [
    (4, 10, "full_switch_off"), (11, 10, "full_switch_off"), (19, 14, "upstream_outage"),
    (27, 10, "segment_switch_off"), (36, 11, "model_regression"), (43, 10, "full_switch_off"),
    (52, 15, "recovery_return"), (63, 10, "tool_failure"), (74, 10, "segment_switch_off"),
    (85, 14, "full_switch_off"),
]
RULES_REFRESH_DAYS = [-35, 33, 70]  # the rules path is refreshed ad hoc, about every 35 to 45 days
STALE_AFTER_DAYS = 30               # a rules version older than this is called stale
DRILL_BASE_FAIL = 0.15              # process failure chance on any drill
DRILL_STALE_EXTRA = 0.45            # extra failure chance when the rules version is stale
SCENARIO_EXTRA_MIN = {"full_switch_off": 0, "segment_switch_off": 8, "upstream_outage": 6,
                      "model_regression": 4, "tool_failure": 10, "recovery_return": 15}
FAIL_REASONS_STALE = ["rules version stale: rejected current product codes",
                      "rules version stale: eligibility table out of date",
                      "rules version stale: rate table out of date"]
FAIL_REASONS_FRESH = ["switch config not deployed to one segment",
                      "on-call engineer lacked permission to flip the switch",
                      "runbook step missing, escalated twice",
                      "rules engine cache cold, requests timed out"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def binom(rng: random.Random, n: int, p: float) -> int:
    if n <= 0 or p <= 0.0:
        return 0
    if p >= 1.0:
        return n
    r = rng.random
    return sum(1 for _ in range(n) if r() < p)


def poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam < 25:
        limit, k, prod = math.exp(-lam), 0, rng.random()
        while prod > limit:
            k += 1
            prod *= rng.random()
        return k
    return max(0, int(round(lam + math.sqrt(lam) * rng.gauss(0, 1))))


def build_events() -> list:
    events = []
    for eid, day, hod, dur, typ, segs, bad, scale, ramp in EVENT_SPECS:
        start = (day - 1) * 24 + hod
        events.append({"event_id": eid, "start_hour": start, "end_hour": start + dur, "type": typ,
                       "segments": list(segs), "bad_decision_rate": bad, "ramp_hours": ramp,
                       "signal_scale": scale})
    return events


def signal_weight(ev: dict, h: int) -> float:
    """Weight in [0, 1] of the event's effect on the signals at hour h (ramp in, decay out)."""
    s, e, r = ev["start_hour"], ev["end_hour"], ev["ramp_hours"]
    tau = TYPES[ev["type"]]["tau"]
    if s <= h < e:
        return min(1.0, (h - s + 1) / r) if r > 0 else 1.0
    if h >= e and tau > 0:
        w_end = min(1.0, (e - s) / r) if r > 0 else 1.0
        w = w_end * math.exp(-(h - e + 1) / tau)
        return w if w > 0.001 else 0.0
    return 0.0


def bad_weight(ev: dict, h: int) -> float:
    """Weight in [0, 1] of the share of decisions spoiled at hour h (no decay: decisions are fine
    again at end_hour)."""
    s, e, r = ev["start_hour"], ev["end_hour"], ev["ramp_hours"]
    if s <= h < e:
        return min(1.0, (h - s + 1) / r) if r > 0 else 1.0
    return 0.0


def choose_blips(events: list, rng: random.Random) -> list:
    """Benign one-hour blips, away from events (and their signal decay)."""
    blocked = set()
    for ev in events:
        for h in range(ev["start_hour"] - 6, ev["end_hour"] + 80):
            blocked.add(h)
    blips, used = [], set()
    kinds = ["error"] * 6 + ["latency"] * 4
    for kind in kinds:
        while True:
            h = rng.randrange(24, HOURS - 24)
            if h in blocked or any(abs(h - u) < 12 for u in used):
                continue
            used.add(h)
            seg = rng.choice(SEGMENTS)
            amp = round(rng.uniform(0.025, 0.045), 3) if kind == "error" else BLIP_LATENCY_MULT
            blips.append({"hour": h, "segment": seg, "kind": kind, "amp": amp})
            break
    blips.sort(key=lambda b: b["hour"])
    return blips


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build() -> dict:
    events = build_events()
    rng_v = random.Random(SEED * 10 + 1)     # decision volume
    rng_e = random.Random(SEED * 10 + 2)     # error counts
    rng_o = random.Random(SEED * 10 + 3)     # override counts
    rng_l = random.Random(SEED * 10 + 4)     # latency and drift score
    rng_c = random.Random(SEED * 10 + 5)     # complaints
    rng_b = random.Random(SEED * 10 + 6)     # blips
    rng_d = random.Random(SEED * 10 + 7)     # drills

    blips = choose_blips(events, rng_b)
    blip_at = {(b["hour"], b["segment"]): b for b in blips}

    # Decision volume per segment and hour.
    dec = {s: [0] * HOURS for s in SEGMENTS}
    day_factor = {s: [1.0 + DAY_SIGMA * rng_v.gauss(0, 1) for _ in range(DAYS)] for s in SEGMENTS}
    for h in range(HOURS):
        day, hod = divmod(h, 24)
        is_sat_sun = (EPOCH.weekday() + day) % 7 >= 5
        for s in SEGMENTS:
            p = SEG[s]
            level = p["vol"] * HOUR_PROFILE[hod] * (p["sat_sun"] if is_sat_sun else 1.0) * day_factor[s][day]
            dec[s][h] = max(1, int(round(level * (1.0 + HOUR_SIGMA * rng_v.gauss(0, 1)))))

    # Which events touch which segment.
    by_seg = {s: [ev for ev in events if s in ev["segments"]] for s in SEGMENTS}

    rows = []
    for h in range(HOURS):
        for s in SEGMENTS:
            p = SEG[s]
            n = dec[s][h]
            p_err, q_ovr = p["err"], p["ovr"]
            lat_mult, drift_add = 1.0, 0.0
            for ev in by_seg[s]:
                w = signal_weight(ev, h)
                if w <= 0:
                    continue
                t = TYPES[ev["type"]]
                k = w * ev["signal_scale"]
                p_err += t["err"] * k
                q_ovr += t["ovr"] * k
                lat_mult += (t["lat"] - 1.0) * k
                drift_add += t["drift"] * k
            b = blip_at.get((h, s))
            if b:
                if b["kind"] == "error":
                    p_err += b["amp"]
                else:
                    lat_mult *= b["amp"]
            err_cnt = binom(rng_e, n, min(0.95, p_err))
            ovr_cnt = binom(rng_o, n, min(0.95, q_ovr))
            lat = max(0.5 * p["lat"], p["lat"] * lat_mult * (1.0 + LAT_SIGMA_FRAC * rng_l.gauss(0, 1)))
            drift = max(0.0, p["drift"] + drift_add + DRIFT_SIGMA * rng_l.gauss(0, 1))
            lam = n * COMPLAINT_RATE
            for ev in by_seg[s]:
                t = TYPES[ev["type"]]
                hp = h - t["lag"]
                if hp >= 0:
                    bw = bad_weight(ev, hp)
                    if bw > 0:
                        lam += dec[s][hp] * ev["bad_decision_rate"] * bw * t["c1"]
            comp = poisson(rng_c, lam)
            rows.append((h, s, n, round(err_cnt / n, 5), round(lat, 1), round(drift, 4),
                         round(ovr_cnt / n, 5), comp))

    # Drills.
    drills = []
    for i, (day, hod, scenario) in enumerate(DRILL_SPECS, 1):
        date_hour = (day - 1) * 24 + hod
        last_refresh = max(d for d in RULES_REFRESH_DAYS if d * 24 <= date_hour)
        age = (date_hour - last_refresh * 24) // 24
        stale = age > STALE_AFTER_DAYS
        p_fail = DRILL_BASE_FAIL + (DRILL_STALE_EXTRA if stale else 0.0)
        fail = rng_d.random() < p_fail
        if fail:
            pool = FAIL_REASONS_STALE if stale else FAIL_REASONS_FRESH
            reason, minutes, success = rng_d.choice(pool), "", "no"
        else:
            reason, success = "", "yes"
            minutes = rng_d.randint(22, 58) + SCENARIO_EXTRA_MIN[scenario]
        drills.append((f"D{i:02d}", date_hour, scenario, minutes, success, reason, age))

    return {"events": events, "rows": rows, "blips": blips, "drills": drills}


def fmt_policy() -> list:
    return [
        ("window_hours", "all signals", "3", "hours", "design",
         "Rolling window the four signals are pooled over before they are scored."),
        ("min_window_decisions", "error_rate and override_rate", "60", "decisions", "design",
         "Below this many decisions in the window the two rate signals are not scored (too few to judge)."),
        ("persistence_hours", "trip and warn", "2", "hours", "design",
         "The level must hold this many hours running before a warn or a trip fires."),
        ("trip_level", "per segment", "fitted", "standard errors", "fitted_by_step_04",
         "Fitted on days 1-60 by step_04: the lowest candidate whose false trips stay within the budget."),
        ("warn_fraction", "warn tier", "0.75", "fraction of trip level", "design",
         "Warn level = warn_fraction x trip level. A warn alerts a person; it does not switch anything."),
        ("clear_fraction", "hysteresis band", "0.50", "fraction of trip level", "design",
         "A segment may return only when its score stays below clear_fraction x trip level."),
        ("clear_hours", "recovery criteria", "4", "hours", "design",
         "The score must stay below the clear level this many hours running before the segment returns."),
        ("cool_off_hours", "fallback", "6", "hours", "design",
         "Minimum time a segment stays on the rules path after a trip, whatever the signals do."),
        ("trip_level_candidates", "fit grid", "3.0;3.5;4.0;4.5;5.0;5.5;6.0;7.0;8.0;10.0", "standard errors", "design",
         "Candidate trip levels the fit tries, lowest first."),
        ("false_trip_budget_days_1_60", "fit rule", "2", "false trips", "assumption of a modeled bank",
         "At most two unnecessary fallbacks in the 60 fit days. Both the single threshold and KillSwitch are tuned to it."),
        ("fit_days", "scoring", "1-60", "days", "design", "Thresholds are set on these days."),
        ("held_out_days", "scoring", "61-90", "days", "design", "Scored only; never used to set a threshold."),
        ("justify_grace_hours", "scoring", "6", "hours", "design",
         "A trip is justified if an event touching the tripped segment was active in the 6 hours before the metric crossed."),
        ("re_trip_window_hours", "scoring", "6", "hours", "design",
         "A return counts as re-tripped if the segment falls back again within this many hours."),
        ("manual_cluster_complaints_3h", "status quo", "12", "complaints in 3 hours, all segments", "assumption of a modeled bank",
         "A person notices a problem when complaints reach this count in a rolling 3-hour window (about 4 times a normal daytime window)."),
        ("manual_decision_delay_hours", "status quo", "4", "hours", "assumption of a modeled bank",
         "Time from noticing to the switch actually being flipped, and again from the end of the event to flipping it back."),
        ("drill_target_minutes", "drill scorecard", "30", "minutes", "assumption of a modeled bank",
         "A drill passes the scorecard only if the fallback was live within this time."),
        ("max_rules_version_age_days", "drill scorecard", "30", "days", "assumption of a modeled bank",
         "A drill on an older rules version is stale, even if the switch worked."),
        ("drill_cadence_days", "drill scorecard", "45", "days", "assumption of a modeled bank",
         "A scenario not drilled for longer than this at the end of the period is overdue."),
    ]


def write_all() -> dict:
    d = build()
    with open(OUT / "metrics_hourly.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["hour", "segment", "decisions", "error_rate", "latency_p95_ms", "drift_score",
                    "override_rate", "complaints"])
        for r in d["rows"]:
            w.writerow(r)
    with open(OUT / "degradation_events.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["event_id", "start_hour", "end_hour", "type", "segments", "bad_decision_rate",
                    "ramp_hours", "signal_scale"])
        for ev in d["events"]:
            w.writerow([ev["event_id"], ev["start_hour"], ev["end_hour"], ev["type"],
                        ";".join(ev["segments"]), ev["bad_decision_rate"], ev["ramp_hours"], ev["signal_scale"]])
    with open(OUT / "fallback_rules.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["segment", "model_path_quality", "rules_path_quality", "quality_gap", "label"])
        for s in SEGMENTS:
            m, r = RULES_QUALITY[s]
            w.writerow([s, m, r, round(m - r, 2), "stub: set by the generator, not a measurement"])
    with open(OUT / "drills.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["drill_id", "date_hour", "scenario", "minutes_to_fallback", "success",
                    "failure_reason", "rules_version_age_days"])
        for r in d["drills"]:
            w.writerow(r)
    with open(OUT / "policy.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["parameter", "scope", "value", "unit", "set_by", "note"])
        for r in fmt_policy():
            w.writerow(r)
    return d


def main() -> None:
    d = write_all()
    rows = d["rows"]
    print(f"metrics_hourly.csv      {len(rows):,} rows ({DAYS} days x 24 hours x {len(SEGMENTS)} segments)")
    print(f"degradation_events.csv  {len(d['events'])} events")
    print(f"fallback_rules.csv      {len(SEGMENTS)} segments (stub quality numbers)")
    print(f"drills.csv              {len(d['drills'])} drills")
    print(f"policy.csv              {len(fmt_policy())} parameters")
    print(f"benign blips injected   {len(d['blips'])} (not degradations)")
    print(f"total decisions         {sum(r[2] for r in rows):,}")


if __name__ == "__main__":
    main()
