"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_manual_switch_off import (
    CLUSTER_COMPLAINTS_3H, MANUAL_DECISION_DELAY_H, SEGMENTS, fmt_h, hour_label, load_all, rnd, type_label,
)
from step_04_with_killswitch import event_payload, summarize

ROOT = Path(__file__).parent.parent
FOLDER = "25-killswitch-ai-fallback-drills"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    data = load_all()
    S = summarize(data)
    A, man, s1, s2, util = S["A"], S["man"], S["s1"], S["s2"], S["util"]
    events = []
    for i, e in enumerate(data["events"]):
        p = event_payload(data, A, man, s2["tuned"], i)
        mm, tt, kk = p["manual"], p["threshold"], p["killswitch"]
        per = []
        for s in kk["segments_moved"]:
            d = kk["per_segment"][s]
            per.append({"segment": s.replace("_", " "),
                        "warn": hour_label(d["warn"]) if d.get("warn") is not None else "-",
                        "trip": hour_label(d["first"]), "delay": d["first"] - e["start"],
                        "back": hour_label(d["return"]) if d["return"] is not None else "still on",
                        "after_end": d["after_end"], "lead": d.get("lead_signal")})
        events.append({
            "id": e["event_id"], "period": e["period"], "type": type_label(e["type"]),
            "silent": e["type"] == "silent_error",
            "segments": ", ".join(s.replace("_", " ") for s in e["segments"]), "n_segments": len(e["segments"]),
            "start": hour_label(e["start"]), "hours": e["end"] - e["start"], "day": e["start"] // 24 + 1,
            "bad_rate_pct": round(100 * e["bad"]), "ramp": e["ramp"],
            "decisions": p["decisions_in_event"], "exposure": rnd(p["exposure"]),
            "peak_score": round(kk["peak_score"], 1),
            "manual": {"acted": mm["acted"], "cluster": hour_label(mm["cluster_hour"]) if mm["cluster_hour"] is not None else None,
                       "switch": hour_label(mm["switch_hour"]) if mm["acted"] else None, "delay": mm["delay"],
                       "peak_complaints": mm["peak_complaints_3h"], "bad_served": rnd(mm["bad_served"]),
                       "bad_total": rnd(mm["bad_total"]), "unneeded": mm["unneeded"]},
            "threshold": {"caught": tt["caught"], "hour": hour_label(tt["hour"]) if tt["caught"] else None,
                          "delay": tt["delay"], "bad_total": rnd(tt["bad_total"]), "bad_served": rnd(tt["bad_served"])},
            "ks": {"caught": kk["caught"], "delay": kk["delay"], "segments": per,
                   "protected": kk["protected"], "bad_served": rnd(kk["bad_served"]), "bad_total": rnd(kk["bad_total"]),
                   "other": [s.replace("_", " ") for s in kk["other_segments_on_rules"]]},
        })
    held = {"ks": A["summary"]["heldout"], "man": s1["heldout"], "thr": s2["tuned"]["heldout"]}
    summ = {
        "events": len(events), "segments": len(SEGMENTS), "days": 90,
        "z_fit": A["z_fit"], "warn_z": round(A["warn_z"], 2),
        "held_events": held["ks"]["events"], "held_caught": held["ks"]["caught"],
        "held_median_delay": fmt_h(held["ks"]["median_delay_h"]),
        "man_caught": held["man"]["caught"], "thr_caught": held["thr"]["caught"],
        "bad_per_event": {"manual": rnd(util["manual"]), "threshold": rnd(util["threshold"]), "ks": rnd(util["killswitch"])},
        "delta_thr": rnd(util["delta_vs_threshold"]), "delta_man": rnd(util["delta_vs_manual"]),
        "epq": util["events_per_quarter"],
        "per_quarter_thr": rnd(util["delta_vs_threshold"]) * util["events_per_quarter"],
        "per_quarter_man": rnd(util["delta_vs_manual"]) * util["events_per_quarter"],
        "silent_missed": sum(1 for e in events if e["silent"] and not e["ks"]["caught"]),
        "drills_failed": S["drills"]["stats"]["failed"], "drills": S["drills"]["stats"]["drills"],
        "scen_ready": S["drills"]["ready"], "scen": S["drills"]["required"],
        "ks_false_held": held["ks"]["false_trips"],
        "cluster_n": CLUSTER_COMPLAINTS_3H, "delay_h": MANUAL_DECISION_DELAY_H,
    }
    return {"events": events, "s": summ}


CSS = """
  :root {
    --bg-primary: #ffffff;
    --bg-secondary: #f6f5f2;
    --bg-tertiary: #ecebe7;
    --text-primary: #1a1a1a;
    --text-secondary: #5a5a5a;
    --text-tertiary: #8a8a8a;
    --border: rgba(0, 0, 0, 0.12);
    --border-strong: rgba(0, 0, 0, 0.25);
    --radius-md: 8px;
    --radius-lg: 12px;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--text-primary);
    background: var(--bg-primary);
    margin: 0;
    line-height: 1.6;
    font-size: 16px;
  }
  .container { max-width: 920px; margin: 0 auto; padding: 32px 24px 64px; }
  .hero { margin-bottom: 32px; }
  .hero h1 { font-size: 28px; font-weight: 500; margin: 0 0 8px; }
  .hero .tagline { font-size: 16px; color: var(--text-secondary); margin: 0 0 12px; }
  .hero .author { font-size: 13px; color: var(--text-tertiary); }
  .hero .author a { color: var(--text-secondary); text-decoration: none; border-bottom: 1px dotted var(--border-strong); }
  .badges { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 0; }
  .badge { display: inline-block; font-size: 11px; font-weight: 500; padding: 4px 10px; border-radius: 999px; background: var(--bg-secondary); color: var(--text-secondary); }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .stat { background: var(--bg-secondary); border-radius: var(--radius-md); padding: 14px 16px; }
  .stat-label { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; }
  .stat-value { font-size: 24px; font-weight: 500; margin: 0; line-height: 1.1; }
  .controls { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
  .controls label { font-size: 13px; color: var(--text-secondary); }
  select, button {
    font-family: inherit; font-size: 14px; padding: 8px 12px;
    border-radius: var(--radius-md); border: 1px solid var(--border);
    background: var(--bg-primary); color: var(--text-primary); cursor: pointer;
  }
  select { flex: 1; min-width: 280px; }
  select:focus, button:focus { outline: 2px solid #1c2541; outline-offset: 1px; }
  button:hover { background: var(--bg-secondary); }
  .actions { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 24px; }
  .card {
    background: var(--bg-primary); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 16px 18px; min-height: 240px;
    display: flex; flex-direction: column; min-width: 0;
  }
  .card-title {
    font-size: 11px; font-weight: 500; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 12px;
  }
  .card-body { font-size: 14px; line-height: 1.6; flex: 1; }
  .card-body p { margin: 0 0 8px; }
  .step-num {
    display: inline-block; background: #E6F1FB; color: #1c2541;
    font-size: 11px; font-weight: 500; padding: 2px 7px;
    border-radius: 999px; margin-right: 6px;
  }
  .pill {
    display: inline-block; font-size: 11px; padding: 3px 8px;
    border-radius: var(--radius-md); font-weight: 500; margin-top: 8px;
  }
  .pill-ok { background: #EAF3DE; color: #27500A; }
  .pill-bad { background: #FCEBEB; color: #791F1F; }
  .pill-warn { background: #FAEEDA; color: #633806; }
  .pill-info { background: #E6F1FB; color: #1c2541; }
  .driver-row { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 13px; }
  .driver-label { color: var(--text-secondary); }
  .driver-value { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; text-align: right; overflow-wrap: anywhere; }
  .fieldrow { border-top: 1px solid var(--border); padding: 6px 0; font-size: 12px; }
  .fieldrow:first-of-type { border-top: 0; }
  .fieldname { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-weight: 500; overflow-wrap: anywhere; }
  .fieldvals { color: var(--text-secondary); overflow-wrap: anywhere; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }
  .tag { display: inline-block; font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 999px; margin-left: 6px; }
  .tag-ok { background: #EAF3DE; color: #27500A; }
  .tag-bad { background: #FCEBEB; color: #791F1F; }
  .tag-warn { background: #FAEEDA; color: #633806; }
  .reltitle { font-size: 12px; font-weight: 500; margin: 10px 0 4px; overflow-wrap: anywhere; }
  .reltitle:first-child { margin-top: 0; }
  .utility-callout {
    background: var(--bg-secondary); border-radius: var(--radius-lg);
    padding: 18px 22px; font-size: 14px; line-height: 1.7;
    color: var(--text-secondary); margin-bottom: 24px;
  }
  .utility-callout b { color: var(--text-primary); font-weight: 500; }
  .formula {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 13px; background: var(--bg-tertiary);
    padding: 8px 12px; border-radius: var(--radius-md);
    display: inline-block; margin: 6px 0;
  }
  .footer-links {
    display: flex; gap: 20px; margin-top: 32px; padding-top: 20px;
    border-top: 1px solid var(--border); font-size: 13px;
    color: var(--text-secondary); flex-wrap: wrap;
  }
  .footer-links a { color: var(--text-secondary); text-decoration: none; border-bottom: 1px dotted var(--border-strong); }
  .run-meta {
    background: var(--bg-secondary); border-radius: var(--radius-md);
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 16px; line-height: 1.6;
  }
  .run-meta b { color: var(--text-primary); font-weight: 500; }
  .framing { font-size: 12px; color: var(--text-tertiary); margin: -12px 0 24px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
"""

JS = """
const D = __PAYLOAD__;
const EV = D.events;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function fmt(n) { return Number(n).toLocaleString("en-US"); }

let idx = 0;
const sel = document.getElementById("event-select");
EV.forEach((e, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = e.id + " - day " + e.day + " - " + e.type + " - " + e.segments + " - " + (e.period === "heldout" ? "held out" : "fit period");
  sel.appendChild(o);
});

function totals(upTo) {
  let man = 0, thr = 0, ks = 0, silent = 0;
  for (let i = 0; i <= upTo; i++) {
    const e = EV[i];
    man += e.manual.bad_total; thr += e.threshold.bad_total; ks += e.ks.bad_total;
    if (e.silent && !e.ks.caught) silent += e.ks.bad_served;
  }
  return { man, thr, ks, silent };
}

function render() {
  const e = EV[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-man").textContent = fmt(tt.man);
  document.getElementById("stat-thr").textContent = fmt(tt.thr);
  document.getElementById("stat-ks").textContent = fmt(tt.ks);
  document.getElementById("stat-silent").textContent = fmt(tt.silent);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(e.id) + "</b> - " + esc(e.type) + " in " + esc(e.segments) + ", from " + esc(e.start) + " for " + esc(e.hours) +
    " hours. " + esc(e.bad_rate_pct) + "% of the decisions in the affected segments were bad while it lasted: <b>" + esc(fmt(e.exposure)) +
    "</b> bad decisions if nothing is done. " + (e.period === "heldout" ? "Held out: no threshold was set on this event." : "Fit period: the trip level was fitted on days 1-60.");

  // Card 1: manual
  let b = "";
  if (e.manual.acted) {
    b += "<p>Complaints reach " + esc(D.s.cluster_n) + " in 3 hours at <b>" + esc(e.manual.cluster) + "</b>. After a " + esc(D.s.delay_h) + " hour decision delay the switch is flipped at <b>" +
         esc(e.manual.switch) + "</b>, " + esc(e.manual.delay) + " hours in. All four segments move.</p>";
  } else if (e.manual.cluster) {
    b += "<p>Complaints cluster at " + esc(e.manual.cluster) + ", but the " + esc(D.s.delay_h) + " hour decision delay lands after the event has ended. Nothing is switched.</p>";
  } else {
    b += "<p>Complaints never cluster: the busiest 3 hours reach " + esc(e.manual.peak_complaints) + " against a notice level of " + esc(D.s.cluster_n) + ". Nobody switches.</p>";
  }
  b += '<div class="driver-row"><span class="driver-label">Bad decisions served</span><span class="driver-value">' + esc(fmt(e.manual.bad_served)) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Healthy decisions moved</span><span class="driver-value">' + esc(fmt(e.manual.unneeded)) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Bad decisions, total</span><span class="driver-value">' + esc(fmt(e.manual.bad_total)) + "</span></div>";
  b += '<span class="pill ' + (e.manual.acted ? "pill-warn" : "pill-bad") + '">' + (e.manual.acted ? "LATE" : "MISSED") + "</span>";
  b += '<div style="font-size:12px;color:#8a8a8a;margin-top:8px;">Modeled: notice at ' + esc(D.s.cluster_n) + ' complaints in 3 hours, ' + esc(D.s.delay_h) + ' hours to flip, perfect triage. A floor on the harm.</div>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: single threshold
  let s = "";
  if (e.threshold.caught) {
    s += "<p>The overall error rate crosses the threshold at <b>" + esc(e.threshold.hour) + "</b>, " + esc(e.threshold.delay) + " hours in. All four segments move.</p>";
  } else {
    s += "<p>The overall error rate never crosses the threshold. The event moves it too little, so nothing trips.</p>";
  }
  s += '<div class="driver-row"><span class="driver-label">Bad decisions served</span><span class="driver-value">' + esc(fmt(e.threshold.bad_served)) + "</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Bad decisions, total</span><span class="driver-value">' + esc(fmt(e.threshold.bad_total)) + "</span></div>";
  s += '<span class="pill ' + (e.threshold.caught ? "pill-info" : "pill-bad") + '">' + (e.threshold.caught ? "tripped, no segment view" : "MISSED") + "</span>";
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: KillSwitch
  let h = "";
  if (e.ks.caught) {
    e.ks.segments.forEach(g => {
      h += '<div class="fieldrow"><span class="fieldname">' + esc(g.segment) + '</span><span class="tag tag-ok">trip ' + esc(g.delay) + ' h in</span>' +
           '<div class="fieldvals">warn ' + esc(g.warn) + "<br>trip " + esc(g.trip) + "<br>back " + esc(g.back) +
           (g.after_end !== null ? " (" + esc(Math.abs(g.after_end)) + " h " + (g.after_end >= 0 ? "after" : "before") + " the event ended)" : "") + "</div></div>";
    });
    if (e.ks.other.length) {
      h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">' + esc(e.ks.other.join(", ")) + " also ran on the rules path: a false trip on noise, counted in the fit.</div>";
    }
    h += '<div class="driver-row"><span class="driver-label">Decisions protected</span><span class="driver-value">' + esc(fmt(e.ks.protected)) + "</span></div>";
    h += '<div class="driver-row"><span class="driver-label">Bad decisions served</span><span class="driver-value">' + esc(fmt(e.ks.bad_served)) + "</span></div>";
    h += '<div class="driver-row"><span class="driver-label">Bad decisions, total</span><span class="driver-value">' + esc(fmt(e.ks.bad_total)) + "</span></div>";
    h += '<span class="pill pill-ok">CAUGHT in ' + esc(e.ks.delay) + " h</span>";
    if (e.threshold.bad_total < e.ks.bad_total) {
      h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Known cost:</b> the single threshold served fewer bad decisions here because it came back sooner. KillSwitch waits for clean signals.</div>';
    }
  } else {
    h += "<p>A silent error moves no signal enough to see: the highest score was " + esc(e.peak_score) + " standard errors against a warn level of " + esc(D.s.warn_z) + ". KillSwitch cannot trip on what no metric shows.</p>";
    h += '<div class="driver-row"><span class="driver-label">Bad decisions served</span><span class="driver-value">' + esc(fmt(e.ks.bad_served)) + "</span></div>";
    h += '<span class="pill pill-warn">MISSED: known limit</span>';
  }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", ev => { idx = parseInt(ev.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < EV.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= EV.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s = p["s"]
    n = s["events"]
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KillSwitch — AI Fallback and Degradation Drills · Vijay Saharan</title>
<meta name="description" content="A clickable demo of KillSwitch: per-segment warn and trip tiers, hysteresis, a way back and a drill scorecard for an AI decision service's fallback path. Synthetic data, stub rules path.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="KillSwitch — AI Fallback and Degradation Drills">
<meta property="og:description" content="Trips a degraded segment to a rules fallback by threshold, scores the drills, and tracks the safe way back.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/25-killswitch-ai-fallback-drills/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 77 runnable prototypes on synthetic data">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="KillSwitch — AI Fallback and Degradation Drills">
<meta name="twitter:description" content="Trips a degraded segment to a rules fallback by threshold, scores the drills, and tracks the safe way back.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta name="twitter:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 77 runnable prototypes on synthetic data">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/25-killswitch-ai-fallback-drills/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>KillSwitch — AI Fallback and Degradation Drills</h1>
    <p class="tagline">Pick a degradation event and watch the manual switch-off, one threshold and KillSwitch handle it.</p>
    <p class="author">Project 25 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{n} events · {s['segments']} segments · {s['days']} days</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">Stub rules path, not a model</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected event">
    <div class="stat"><p class="stat-label">Bad decisions, manual</p><p class="stat-value" id="stat-man">—</p></div>
    <div class="stat"><p class="stat-label">Bad decisions, one threshold</p><p class="stat-value" id="stat-thr">—</p></div>
    <div class="stat"><p class="stat-label">Bad decisions, KillSwitch</p><p class="stat-value" id="stat-ks">—</p></div>
    <div class="stat"><p class="stat-label">Served in missed silent errors (known limit)</p><p class="stat-value" id="stat-silent">—</p></div>
  </section>

  <div class="controls">
    <label for="event-select">Event</label>
    <select id="event-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next event</button>
    <button id="runall-btn">Replay all {n} events</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Manual switch-off</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — One overall threshold</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With KillSwitch</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. Totals run from E01 to the selected event and count expected bad decisions inside event windows. The trip level was fitted on days 1-60 and scored on days 61-90. The rules path quality numbers are stubs set by the generator, and no model is used anywhere. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (bad decisions per event without KillSwitch − with it) × degradation events per quarter</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on the {s['held_events']} held-out events (days 61-90):</b> {s['bad_per_event']['threshold']:,} bad decisions per event with the tuned single threshold, {s['bad_per_event']['ks']:,} with KillSwitch, so {s['delta_thr']:,} avoided per event. KillSwitch tripped for {s['held_caught']} of {s['held_events']} events, median {s['held_median_delay']} hours in, with {s['ks_false_held']} false {'trip' if s['ks_false_held'] == 1 else 'trips'}. The single threshold tripped for {s['thr_caught']}.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['epq']} degradation events a quarter (an assumption, not a statistic) gives {s['delta_thr']:,} × {s['epq']} = <b>{s['per_quarter_thr']:,} bad decisions avoided per quarter</b> against the single threshold. Against the manual plan the figure is {s['delta_man']:,} per event, {s['per_quarter_man']:,} per quarter, and rests on a {s['delay_h']} hour decision delay and a complaint-cluster notice level of {s['cluster_n']} that are assumptions.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/killswitch-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>{js}</script>
</body>
</html>
"""


def main() -> None:
    p = build_payload()
    out = ROOT / "demo.html"
    out.write_text(build_html(p), encoding="utf-8")
    print(f"Wrote {out.name}: {len(p['events'])} events, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
