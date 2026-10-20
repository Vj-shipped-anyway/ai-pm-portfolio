"""Writes ../demo.html and ../assets/adoptionpulse-flow.svg from the output of the step scripts.
Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo and in the flow diagram is computed by importing the step modules; none is
typed here. The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_license_counts_status_quo import WEEKS
from step_02_login_adoption_baseline import ADOPTION_OK_PCT
from step_03_deficiencies_exposed import summarize as summarize_step3
from step_04_with_adoptionpulse import TYPE_LABEL, TYPE_ORDER, analyze

ROOT = Path(__file__).parent.parent
FOLDER = "21-adoptionpulse-ai-enablement-funnel"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    data, s = a["data"], a["summary"]
    s3 = summarize_step3(data)
    units = []
    for r in a["ranked"]:
        units.append({
            "unit": r["unit"], "rank": r["rank"], "licensed": r["licensed"], "logged_in": r["logged_in"],
            "login_pct": r["login_pct"], "activated": r["activated"], "habitual": r["habitual"],
            "proficient": r["proficient"], "habitual_pct": r["habitual_pct"], "champion": r["champion"],
            "trained_pct": r["trained_pct"], "gain": r["gain"], "leak": r["leak"],
            "leak_users": r["leak_users"], "leak_gap": abs(r["leak_gap_points"]), "action": r["action"],
            "types": [[TYPE_LABEL[t], r["truth_types"][t]] for t in TYPE_ORDER],
            "truth_stages": r["truth_stages"], "correct": r["correct"],
            "login_cum": r["login_cum"], "active": r["active_share"],
        })
    return {"units": units, "s": s, "s3": {"d2": s3["d2"], "d3": {k: v for k, v in s3["d3"].items() if k != "unit_rows"}},
            "ok": ADOPTION_OK_PCT}


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
  .card.red { border-top: 3px solid #dc2626; }
  .card.blue { border-top: 3px solid #2563eb; }
  .card.green { border-top: 3px solid #059669; }
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
  .fieldname { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-weight: 500; overflow-wrap: anywhere; }
  .fieldvals { color: var(--text-secondary); overflow-wrap: anywhere; }
  .bars { display: flex; align-items: flex-end; gap: 3px; height: 48px; margin: 6px 0 2px; }
  .bar { flex: 1; min-width: 4px; border-radius: 2px 2px 0 0; }
  .bar-red { background: #fca5a5; }
  .bar-green { background: #6ee7b7; }
  .bar-caption { font-size: 11px; color: var(--text-tertiary); margin: 0 0 6px; }
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
const UNITS = D.units;
const S = D.s;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function row(label, value) {
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + '</span></div>';
}
function bars(series, cls) {
  let h = '<div class="bars">';
  series.forEach((v, i) => {
    const px = Math.max(2, Math.round(Number(v) * 0.46));
    h += '<span class="bar ' + cls + '" style="height:' + px + 'px" title="week ' + (i + 1) + ': ' + esc(v) + '%"></span>';
  });
  return h + '</div>';
}

let idx = 0;
const sel = document.getElementById("unit-select");
UNITS.forEach((u, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = (u.rank ? String(u.rank) : "-") + ". " + u.unit + " - " + String(u.licensed) + " users - " + String(u.habitual_pct) + "% habitual";
  sel.appendChild(o);
});

function render() {
  const u = UNITS[idx];
  sel.value = idx;
  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(u.unit) + "</b> - " + esc(u.licensed) + " licensed users, " + (u.champion ? "a champion assigned" : "no champion") +
    ", " + esc(u.trained_pct) + "% completed training. " +
    (u.rank ? "Rank <b>" + esc(u.rank) + "</b> of " + esc(S.units_to_act) + " units with habitual users to gain." : "Not ranked: no habitual users to gain at the estate rate.");

  // Card 1: license and login view
  let b = row("Licenses issued", u.licensed) + row("Logged in at least once", u.logged_in) + row("Reported adoption", u.login_pct + "%");
  b += '<span class="pill ' + (u.login_pct >= D.ok ? "pill-warn" : "pill-info") + '">' +
       (u.login_pct >= D.ok ? "reads as healthy: nothing to act on" : "reads as below the " + esc(D.ok) + "% cut") + '</span>';
  b += bars(u.login_cum, "bar-red");
  b += '<p class="bar-caption">Cumulative logged-in share, weeks 1 to ' + esc(u.login_cum.length) + '. A person who logged in once stays counted.</p>';
  b += '<div class="fieldvals" style="font-size:12px;">It does not say who uses the tool, how often or how well. Modeled: the healthy cut is an assumption.</div>';
  document.getElementById("card-login").innerHTML = b;

  // Card 2: the funnel truth
  const ts = u.truth_stages;
  const truthHab = ts.habitual + ts.proficient;
  let t = "";
  u.types.forEach(x => { t += row(x[0], x[1]); });
  t += '<div class="fieldrow">' + row("Habitual or better", truthHab + " of " + u.licensed) +
       row("Started, not habitual", ts.activated) + row("Never started", ts.licensed) +
       row("Champion in the unit", u.champion ? "yes" : "no") + row("Training completed", u.trained_pct + "%") + '</div>';
  t += '<span class="pill pill-info">synthetic truth: the generator decided it</span>';
  document.getElementById("card-truth").innerHTML = t;

  // Card 3: AdoptionPulse
  const flagged = u.gain > 0 || u.leak !== "";
  let h = '<span class="pill ' + (flagged ? "pill-ok" : "pill-info") + '">' + (flagged ? "FLAGGED" : "ON TRACK") + '</span>';
  h += row("Licensed", u.licensed) + row("Activated", u.activated) + row("Habitual", u.habitual) + row("Proficient", u.proficient);
  h += row("Habitual rate", u.habitual_pct + "% (estate " + S.habitual_pct + "%)");
  h += '<div class="fieldrow"><span class="fieldname">' + (u.leak ? "leak: " + esc(u.leak) : "leak: none") + '</span>' +
       '<div class="fieldvals">' + (u.leak ? esc(u.leak_users) + " users, " + esc(u.leak_gap) + " points below the estate rate. " : "At or above the estate rate at every stage. ") +
       esc(u.action) + '</div></div>';
  h += row("Habitual users to gain", u.gain) + row("Staged as the generator decided", u.correct + " of " + u.licensed);
  h += bars(u.active, "bar-green");
  h += '<p class="bar-caption">Share of licensed users with an AI session, by week.</p>';
  document.getElementById("card-pulse").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < UNITS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= UNITS.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s = p["s"]
    ut, tr, ch, lim = s["utility"], s["training"], s["champion"], s["limit"]
    n_units = len(p["units"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AdoptionPulse — AI Enablement Funnel · Vijay Saharan</title>
<meta name="description" content="A clickable demo of AdoptionPulse: AI adoption measured by stage, unit and week instead of license counts and logins. Synthetic data, no model.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="AdoptionPulse — AI Enablement Funnel">
<meta property="og:description" content="Stages AI adoption from licensed to proficient by team, instead of reporting license counts and logins.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/21-adoptionpulse-ai-enablement-funnel/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="AdoptionPulse — AI Enablement Funnel">
<meta name="twitter:description" content="Stages AI adoption from licensed to proficient by team, instead of reporting license counts and logins.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/21-adoptionpulse-ai-enablement-funnel/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>AdoptionPulse — AI Enablement Funnel</h1>
    <p class="tagline">Pick an org unit and compare what a login count says with what its people do.</p>
    <p class="author">Project 21 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{s['licensed']} users · {s['units']} units · {WEEKS} weeks</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Estate totals">
    <div class="stat"><p class="stat-label">Reported adoption (login view)</p><p class="stat-value">{s['reported_pct']}%</p></div>
    <div class="stat"><p class="stat-label">Habitual (4 of the last 6 weeks)</p><p class="stat-value">{s['habitual_pct']}%</p></div>
    <div class="stat"><p class="stat-label">Staged correctly, AdoptionPulse</p><p class="stat-value">{s['ap_correct']} of {s['licensed']}</p></div>
    <div class="stat"><p class="stat-label">Staged correctly, login flag, best case</p><p class="stat-value">{s['base_best']} of {s['licensed']}</p></div>
  </section>

  <div class="controls">
    <label for="unit-select">Org unit</label>
    <select id="unit-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next unit</button>
    <button id="runall-btn">Replay all {n_units} units</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-card comparison">
    <div class="card red">
      <p class="card-title"><span class="step-num">1</span>Before and basic — Licenses and logins</p>
      <div class="card-body" id="card-login"></div>
    </div>
    <div class="card blue">
      <p class="card-title"><span class="step-num">2</span>Truth — What the generator decided</p>
      <div class="card-body" id="card-truth"></div>
    </div>
    <div class="card green">
      <p class="card-title"><span class="step-num">3</span>With AdoptionPulse</p>
      <div class="card-body" id="card-pulse"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The generator decided what each person does, so the truth is known. No model is used: the stage rules are plain thresholds (assumptions of a modeled bank). The champion and training effects are planted by construction. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (share of licensed users correctly staged, with AdoptionPulse − with the login flag) × licensed users</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> AdoptionPulse stages {s['ap_correct']} of {s['licensed']} users ({ut['ap_share_pct']}%) the way the generator decided. The login flag, mapped to the four stages with hindsight so it gets its best case, gets {s['base_best']} of {s['licensed']} ({ut['baseline_share_pct']}%). {s['funnel']['activated'] - s['funnel']['habitual']} of {s['funnel']['activated']} activated users never became habitual, and the login view counts all of them as adopted. Known limit: {lim['rule_proficient_poor']} of {lim['rule_proficient']} users staged proficient produce poor work, which weekly counts cannot show.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> ({ut['ap_share_pct']}% − {ut['baseline_share_pct']}%) × {ut['modeled_population']:,} licensed staff = <b>about {ut['utility_users']} users correctly staged</b>. The licensed population is an assumption (the modeled bank's full license count), and it assumes the accuracy measured here holds on real usage data.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/adoptionpulse-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>{js}</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Flow diagram: numbers come from the same summary; a width check keeps text inside its box.
# ---------------------------------------------------------------------------
CHAR_PX = {"title": 7.4, "sub": 6.8, "meta": 6.4, "num": 6.8}


def _fits(text: str, kind: str, box_w: int, pad: int = 12) -> str:
    est = len(text) * CHAR_PX[kind]
    assert est <= box_w - pad - 6, f"svg text too wide for its box ({est:.0f} > {box_w - pad - 6}): {text}"
    return text


def build_svg(p: dict) -> str:
    s = p["s"]
    n_rows = s["licensed"] * WEEKS
    fit = _fits
    xml = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    t = {
        "s1_meta": f"{n_rows:,} usage rows",
        "s2_meta": f"{s['ap_correct']} of {s['licensed']} staged right",
        "s3_meta": f"{s['units']} units staged",
        "s4_meta": f"{s['units_to_act']} of {s['units']} units to help",
        "strip_a": f"Login view: {s['reported_pct']}% adopted",
        "strip_b": f"AdoptionPulse: {s['habitual_pct']}% habitual",
        "strip_c": "known limit: use counted, not value",
    }
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 460" role="img" aria-labelledby="title desc">
  <title id="title">AdoptionPulse: weekly AI usage flowing through stage rules, a cut by unit, and a ranked action list</title>
  <desc id="desc">Five-stage flow showing how weekly AI usage is staged as licensed, activated, habitual or proficient, cut by org unit, training and champion coverage, ranked by habitual users to gain, and turned into a rule-based action. A comparison strip contrasts the login view with AdoptionPulse on the synthetic data.</desc>

  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#5a5a5a"/>
    </marker>
    <style>
      .stage-box {{ fill: #ffffff; stroke: #1c2541; stroke-width: 1.5; }}
      .stage-box-eval {{ fill: #ffffff; stroke: #1d4e89; stroke-width: 1.5; }}
      .stage-box-gate {{ fill: #ffffff; stroke: #d97706; stroke-width: 1.5; }}
      .stage-box-block {{ fill: #ffffff; stroke: #b91c1c; stroke-width: 1.5; }}
      .stage-box-ship {{ fill: #ffffff; stroke: #16a34a; stroke-width: 1.5; }}
      .stage-title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 500; fill: #1a1a1a; }}
      .stage-sub {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 11px; fill: #5a5a5a; }}
      .stage-num {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #1c2541; }}
      .arrow-line {{ stroke: #5a5a5a; stroke-width: 1.5; fill: none; }}
      .meta-text {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; fill: #8a8a8a; }}
      .meta-strong {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #14532d; }}
      .meta-block {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #7f1d1d; }}
      .timer {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #791F1F; }}
      .timer-fast {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #27500A; }}
      .header {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 18px; font-weight: 500; fill: #1a1a1a; }}
      .subheader {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; fill: #5a5a5a; }}
      .badge-bg {{ fill: #E6F1FB; }}
      .badge-text {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 10px; font-weight: 500; fill: #1c2541; }}
    </style>
  </defs>

  <text x="20" y="32" class="header">AdoptionPulse - from weekly usage to the unit that needs help</text>
  <text x="20" y="52" class="subheader">A login count says who opened the tool. AdoptionPulse stages each person, finds the leak and ranks the units.</text>

  <!-- Trigger badge -->
  <rect x="20" y="78" width="250" height="22" rx="4" class="badge-bg"/>
  <text x="28" y="93" class="badge-text">Trigger: a week of AI usage lands</text>

  <!-- Stage 1: USAGE FEED -->
  <rect x="20" y="120" width="155" height="110" rx="8" class="stage-box"/>
  <text x="32" y="140" class="stage-num">1 . USAGE FEED</text>
  <text x="32" y="162" class="stage-title">{fit('Weekly AI usage', 'title', 155)}</text>
  <text x="32" y="180" class="stage-sub">{fit('sessions prompts', 'sub', 155)}</text>
  <text x="32" y="195" class="stage-sub">{fit('accepted advanced', 'sub', 155)}</text>
  <text x="32" y="210" class="stage-sub">{fit('per user per week', 'sub', 155)}</text>
  <text x="32" y="223" class="meta-text">{fit(xml(t['s1_meta']), 'meta', 155)}</text>

  <!-- Arrow 1 -->
  <line x1="180" y1="175" x2="222" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <!-- Stage 2: STAGE RULES -->
  <rect x="225" y="120" width="180" height="110" rx="8" class="stage-box-eval"/>
  <text x="237" y="140" class="stage-num">2 . STAGE RULES</text>
  <text x="237" y="162" class="stage-title">{fit('Stage every user', 'title', 180)}</text>
  <text x="237" y="180" class="stage-sub">{fit('licensed activated', 'sub', 180)}</text>
  <text x="237" y="195" class="stage-sub">{fit('habitual proficient', 'sub', 180)}</text>
  <text x="237" y="210" class="stage-sub">{fit('thresholds in a file', 'sub', 180)}</text>
  <text x="237" y="225" class="meta-strong">{fit(xml(t['s2_meta']), 'meta', 180)}</text>

  <!-- Arrow 2 -->
  <line x1="410" y1="175" x2="452" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <!-- Stage 3: CUT -->
  <rect x="455" y="120" width="200" height="110" rx="8" class="stage-box-eval"/>
  <text x="467" y="140" class="stage-num">3 . CUT AND COMPARE</text>
  <text x="467" y="162" class="stage-title">{fit('By unit and week', 'title', 200)}</text>
  <text x="467" y="180" class="stage-sub">{fit('funnel per org unit', 'sub', 200)}</text>
  <text x="467" y="195" class="stage-sub">{fit('retention by week', 'sub', 200)}</text>
  <text x="467" y="210" class="stage-sub">{fit('training and champion', 'sub', 200)}</text>
  <text x="467" y="225" class="meta-strong">{fit(xml(t['s3_meta']), 'meta', 200)}</text>

  <!-- Arrow 3 -->
  <line x1="660" y1="175" x2="702" y2="175" class="arrow-line" marker-end="url(#arrow)"/>

  <!-- Stage 4: RANK -->
  <rect x="705" y="120" width="180" height="110" rx="8" class="stage-box-gate"/>
  <text x="717" y="140" class="stage-num">4 . RANK + ACTION</text>
  <text x="717" y="162" class="stage-title">{fit('Units to act on', 'title', 180)}</text>
  <text x="717" y="180" class="stage-sub">{fit('rank by users to gain', 'sub', 180)}</text>
  <text x="717" y="195" class="stage-sub">{fit('leak + rule action', 'sub', 180)}</text>
  <text x="717" y="210" class="stage-sub">{fit('rules, not tested', 'sub', 180)}</text>
  <text x="717" y="225" class="meta-block">{fit(xml(t['s4_meta']), 'meta', 180)}</text>

  <!-- Arrow 4 (down) -->
  <path d="M 795 230 L 795 256 L 410 256 L 410 286" class="arrow-line" marker-end="url(#arrow)"/>

  <!-- Stage 5: ACT -->
  <rect x="240" y="290" width="340" height="90" rx="8" class="stage-box-block"/>
  <text x="252" y="310" class="stage-num">5 . THE PROGRAM LEAD ACTS</text>
  <text x="252" y="330" class="stage-title">{fit('Help the unit, then re-stage', 'title', 340)}</text>
  <text x="252" y="352" class="stage-sub">{fit('champion . training . coaching', 'sub', 340)}</text>
  <text x="252" y="368" class="meta-block">{fit('actions are rules: never tested', 'meta', 340)}</text>

  <!-- Arrow 5 (back) -->
  <path d="M 240 330 L 100 330 L 100 380" class="arrow-line" marker-end="url(#arrow)"/>

  <!-- Final: NEXT REPORT -->
  <rect x="20" y="385" width="160" height="55" rx="8" class="stage-box-ship"/>
  <text x="32" y="405" class="stage-title">{fit('next weekly run', 'title', 160)}</text>
  <text x="32" y="423" class="stage-sub">{fit('did the leak close', 'sub', 160)}</text>
  <text x="32" y="436" class="meta-strong">{fit('design: never run', 'meta', 160)}</text>

  <!-- Comparison strip -->
  <rect x="600" y="290" width="285" height="90" rx="8" fill="#f6f5f2" stroke="none"/>
  <text x="612" y="310" class="stage-title">{fit('Same people, two views', 'title', 285)}</text>
  <text x="612" y="332" class="timer">{fit(xml(t['strip_a']), 'sub', 285)}</text>
  <text x="612" y="350" class="timer-fast">{fit(xml(t['strip_b']), 'sub', 285)}</text>
  <text x="612" y="370" class="meta-strong">{fit(xml(t['strip_c']), 'meta', 285)}</text>
</svg>
"""


def main() -> None:
    p = build_payload()
    (ROOT / "assets").mkdir(exist_ok=True)
    svg = ROOT / "assets" / "adoptionpulse-flow.svg"
    svg.write_text(build_svg(p), encoding="utf-8")
    out = ROOT / "demo.html"
    out.write_text(build_html(p), encoding="utf-8")
    print(f"Wrote {out.name}: {len(p['units'])} units, {len(out.read_text(encoding='utf-8')):,} characters")
    print(f"Wrote assets/{svg.name}")


if __name__ == "__main__":
    main()
