"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from step_01_interview_process_map import load_all, rnd
from step_04_with_stepscout import analyze, step_payload, TOP_N, REMOVAL_SHARE

ROOT = Path(__file__).parent.parent
FOLDER = "26-stepscout-task-mining-agent-candidates"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    data = load_all()
    A = analyze(data)
    order = data["order"]
    steps = [step_payload(data, A, s) for s in order]
    sc, cp, ut, hd, d = A["scoring"], A["compare"], A["utility"], A["handling"], A["deficiencies"]
    summ = {
        "cases": len(data["cases"]), "steps": len(order), "days": 30, "workers": ut["n_workers"],
        "vf_ready": cp["vf_ready"], "ss_ready": cp["ss_ready"], "top_n": TOP_N,
        "vf_flagged": cp["vf_flagged"], "happy_pct": d["d1"]["happy_pct"], "variants": d["d1"]["variants"],
        "off_system_pct": d["d2"]["off_system_pct"], "touch_share_pct": d["d3"]["touch_share_pct"],
        "accuracy": sc["accuracy"], "accuracy_pct": sc["accuracy_pct"], "precision_pct": sc["precision_pct"], "recall_pct": sc["recall_pct"],
        "log_alone_pct": hd["log_alone_pct"], "merged_pct": hd["merged_pct"], "recovered_pts": hd["recovered_pts"],
        "offdesk_pct": hd["offdesk_pct"], "removal_pct": int(REMOVAL_SHARE * 100),
        "vf_per_worker": round(ut["vf_per_worker"], 1), "ss_per_worker": round(ut["ss_per_worker"], 1),
        "lift_per_worker": round(ut["per_worker"], 1), "lift_hours": rnd(ut["lift_hours"]),
        "vf_hours": rnd(ut["vf_hours"]), "ss_hours": rnd(ut["ss_hours"]),
        "known_step": A["known"]["step"] if A["known"] else "", "known_name": A["known"]["name"] if A["known"] else "",
        "known_rank": A["known"]["rank"] if A["known"] else 0,
    }
    return {"steps": steps, "s": summ}


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
const ST = D.steps;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function fmt(n, d) { return Number(n).toLocaleString("en-US", {minimumFractionDigits: d || 0, maximumFractionDigits: d || 0}); }
function row(label, value) {
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + "</span></div>";
}

let idx = 0;
const sel = document.getElementById("step-select");
ST.forEach((e, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = e.id + " - " + e.name;
  sel.appendChild(o);
});

function totals(upTo) {
  let map = 0, log = 0, all = 0, stake = 0;
  for (let i = 0; i <= upTo; i++) {
    const e = ST[i];
    all += e.touch_hours;
    if (e.on_map) map += e.touch_hours;
    if (e.status) log += e.touch_hours;
    stake += e.hours_at_stake;
  }
  return { map, log, all, stake };
}

function render() {
  const e = ST[idx];
  sel.value = idx;
  const t = totals(idx);
  document.getElementById("stat-map").textContent = fmt(t.map);
  document.getElementById("stat-log").textContent = fmt(t.log);
  document.getElementById("stat-all").textContent = fmt(t.all);
  document.getElementById("stat-stake").textContent = fmt(t.stake);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(e.id) + "</b> " + esc(e.name) + " - " + esc(fmt(e.runs)) + " runs and " + esc(fmt(e.touch_hours, 1)) + " touch hours in the 30 days, median " +
    esc(fmt(e.median_min, 1)) + " minutes a run, mostly in the " + esc(e.main_app) + ". The answer key (the generator's own) says <b>" + esc(e.key) + "</b>.";

  // Card 1: interview map
  let b = "";
  if (e.on_map) {
    b += "<p>On the map. The expert says " + esc(e.sme_minutes) + " minutes for the step.</p>";
    b += row("Minutes stated", e.sme_minutes);
    b += row("Median minutes measured, per run", fmt(e.median_min, 1));
    b += row("Runs in 30 days", fmt(e.runs));
    b += '<span class="pill pill-ok">DOCUMENTED</span>';
  } else {
    b += "<p>Not on the map. The interview describes one happy path and this step is not on it.</p>";
    b += row("Runs in 30 days", fmt(e.runs));
    b += row("Touch hours", fmt(e.touch_hours, 1));
    b += '<span class="pill pill-bad">NOT ON THE MAP</span>';
  }
  document.getElementById("card-before").innerHTML = b;

  // Card 2: case-system log, volume first
  let s = "";
  if (e.status) {
    s += "<p>The step posts the status <span class='mono'>" + esc(e.status) + "</span>, so the log sees it. The list ranks it by volume times the time since the previous status.</p>";
    s += row("Rank by volume x time", "#" + e.log_rank);
    s += row("Volume", fmt(e.log_volume));
    s += row("Mean minutes since previous status", fmt(e.log_mean_min, 1));
    s += row("Hours the list credits", fmt(e.log_hours));
    s += row("Touch hours measured", fmt(e.touch_hours, 1));
    if (e.in_vf_top10) {
      s += '<span class="pill ' + (e.agent_ready_key ? "pill-ok" : "pill-bad") + '">' + (e.agent_ready_key ? "TOP 10, AGENT-READY" : "TOP 10, NOT AGENT-READY") + "</span>";
    } else {
      s += '<span class="pill pill-warn">BELOW THE TOP 10</span>';
    }
  } else {
    s += "<p>The step posts no status. The log never records that it happened, so a list built from it cannot propose it.</p>";
    s += row("Touch hours measured", fmt(e.touch_hours, 1));
    s += '<span class="pill pill-bad">NEVER SEEN</span>';
  }
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: StepScout
  let h = "";
  h += row("Class from observable features", e.predicted);
  h += '<ul style="margin:6px 0 6px 18px;padding:0;font-size:12px;color:#5a5a5a;">';
  e.reasons.forEach(r => { h += "<li>" + esc(r) + "</li>"; });
  h += "</ul>";
  h += row("Control screen", e.screen);
  e.screen_notes.forEach(n => { h += '<div class="fieldvals" style="font-size:12px;margin:2px 0 4px;">' + esc(n) + "</div>"; });
  if (e.agent_ready_pred) {
    h += row("Modeled hours at stake", fmt(e.hours_at_stake, 1));
    h += row("Rank among candidates", "#" + e.ss_rank + (e.in_ss_top10 ? " (top " + D.s.top_n + ")" : ""));
  }
  if (e.correct) {
    h += '<span class="pill pill-ok">MATCHES THE KEY</span>';
  } else if (e.agent_ready_pred && !e.agent_ready_key) {
    h += '<span class="pill pill-warn">MISSED: known limit</span>';
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">The key says ' + esc(e.key) + ". On the desktop this step is a short pick with tight timing, no free text and no overrides. The judgment happens in a phone call that no file records, so nothing observable separates it from a rule.</div>";
  } else {
    h += '<span class="pill pill-info">MORE CAUTIOUS THAN THE KEY</span>';
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">The key says ' + esc(e.key) + ". The step stays agent-ready; a person reviews it. Cost: a lower readiness weight in the ranking.</div>";
  }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", ev => { idx = parseInt(ev.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < ST.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= ST.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s = dict(p["s"])
    for k in ("known_step", "known_name"):
        s[k] = html.escape(str(s[k]), quote=True)
    n = s["steps"]
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StepScout — Task Mining to Agent Candidates · Vijay Saharan</title>
<meta name="description" content="A clickable demo of StepScout: task-level mining of desktop and system events, a readiness and control screen per step, a ranked candidate list with hours at stake and a build brief an engineer can pick up. Synthetic data, rules only.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="StepScout — Task Mining to Agent Candidates">
<meta property="og:description" content="Mines desktop and system events to find which workflow steps an agent can take over, screens them for controls, and writes the build brief.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/26-stepscout-task-mining-agent-candidates/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="StepScout — Task Mining to Agent Candidates">
<meta name="twitter:description" content="Mines desktop and system events to find which workflow steps an agent can take over, screens them for controls, and writes the build brief.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/26-stepscout-task-mining-agent-candidates/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>StepScout — Task Mining to Agent Candidates</h1>
    <p class="tagline">Pick a workflow step and see what the interview map, the log-based list and StepScout each say about it.</p>
    <p class="author">Project 26 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{s['cases']:,} cases · {n} steps · {s['days']} days</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">Rules only, no model</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected step">
    <div class="stat"><p class="stat-label">Touch hours the interview map covers</p><p class="stat-value" id="stat-map">—</p></div>
    <div class="stat"><p class="stat-label">Touch hours the log records as steps</p><p class="stat-value" id="stat-log">—</p></div>
    <div class="stat"><p class="stat-label">Touch hours StepScout measures</p><p class="stat-value" id="stat-all">—</p></div>
    <div class="stat"><p class="stat-label">Hours at stake in agent-ready steps (modeled)</p><p class="stat-value" id="stat-stake">—</p></div>
  </section>

  <div class="controls">
    <label for="step-select">Step</label>
    <select id="step-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next step</button>
    <button id="runall-btn">Replay all {n} steps</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — The interview map</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Case-system log, volume first</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With StepScout</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. Steps run in workflow order and the totals add touch hours from S01 to the selected step. The answer key is the generator's own, and the classifier never reads it. Hours at stake are modeled: an agent removes {s['removal_pct']}% of a step's touch time, an assumption. Task mining of employee desktops is a privacy and works-council question this prototype only designs for. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (agent-ready hours at stake per worker in StepScout's top {s['top_n']} − in the volume-first top {s['top_n']}) × workers</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on the answer key:</b> the volume-first top {s['top_n']} holds {s['vf_ready']} agent-ready steps and {s['vf_flagged']} that touch restricted data or a four-eyes control, with no control screen. StepScout's top {s['top_n']} holds {s['ss_ready']} agent-ready steps. It classifies {s['accuracy']} of {s['steps']} steps correctly ({s['accuracy_pct']}%), with {s['precision_pct']}% precision and {s['recall_pct']}% recall for agent-ready steps. Known miss: {s['known_step']} {s['known_name']}, ranked #{s['known_rank']}.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> ({s['ss_per_worker']} − {s['vf_per_worker']}) = {s['lift_per_worker']} hours per worker per 30 days × {s['workers']} workers = <b>{s['lift_hours']:,} hours per 30 days</b>, assuming an agent removes {s['removal_pct']}% of touch time and both teams build their top {s['top_n']}.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/stepscout-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['steps'])} steps, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
