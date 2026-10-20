"""Writes ../demo.html from the step scripts' own output.

Standard library only. Run from src/:
    python3 _build_demo.py

Every number in the page comes from step_04_with_valueledger.run_scenario(), the same
function the Streamlit app and the step-4 printout use. Nothing is retyped. The page
is static and works offline; the data is embedded as JSON and every dynamic value is
HTML-escaped in the browser before it is written into the page.
"""

from __future__ import annotations

import json
from pathlib import Path

from valueledger_core import SCENARIOS, fmt_int, fmt_signed, fmt_usd, load_data
import step_04_with_valueledger as s4

HERE = Path(__file__).resolve().parent
DEMO = HERE.parent / "demo.html"


def pct(x: float, base: float) -> str:
    return "%+.0f%%" % (100.0 * x / base) if base else "n/a"


def display(r: dict, ds) -> dict:
    cl, pp, e, t, ci = r["claim"], r["prepost"], r["ledger"], r["truth"], r["ledger_ci"]
    errs = r["errors"]
    n = r["n_treated"]
    d = {
        "n_treated": fmt_int(n),
        "n_holdout": fmt_int(r["n_holdout"]),
        "weeks": "%d to %d" % (r["post_weeks"][0], r["post_weeks"][-1]),
        "claim_h": fmt_int(cl["claimed_hours"]),
        "claim_events": fmt_int(cl["events_logged"]),
        "claim_distinct": fmt_int(cl["events_distinct"]),
        "claim_dup": fmt_int(cl["events_logged"] - cl["events_distinct"]),
        "claim_value": fmt_usd(cl["claimed_value_usd"]),
        "assumed": fmt_int(cl["assumed_min_a"]),
        "pre_mean": "%.1f" % pp["pre_mean_min_per_task"],
        "post_mean": "%.1f" % pp["post_mean_min_per_task"],
        "effect_task": "%.1f" % pp["effect_per_task_min"],
        "pp_h": fmt_int(pp["hours"]),
        "pp_lo": fmt_int(r["prepost_ci"][0]),
        "pp_hi": fmt_int(r["prepost_ci"][1]),
        "pp_value": fmt_usd(pp["value_usd"]),
        "gross_h": fmt_int(e["gross_did_hours"]),
        "rework_h": fmt_int(e["rework_hours"]),
        "led_h": fmt_int(e["net_hours"]),
        "led_lo": fmt_int(ci["net_hours"][0]),
        "led_hi": fmt_int(ci["net_hours"][1]),
        "led_value": fmt_usd(e["value_usd"]),
        "hard": fmt_usd(e["hard_usd"]),
        "hard_lo": fmt_usd(ci["hard_usd"][0]),
        "hard_hi": fmt_usd(ci["hard_usd"][1]),
        "soft": fmt_usd(e["soft_usd"]),
        "truth_h": fmt_int(t["net_hours"]),
        "truth_gross": fmt_int(t["gross_hours"]),
        "truth_hard": fmt_usd(t["hard_usd"]),
        "truth_soft": fmt_usd(t["soft_usd"]),
        "truth_value": fmt_usd(t["value_usd"]),
        "hidden_h": fmt_int(t["hidden_drift_hours"]),
        "hidden_pct": pct(t["hidden_drift_hours"], t["net_hours"]),
        "err_claim_h": fmt_signed(errs["claim_hours_error"]),
        "err_claim_pct": pct(errs["claim_hours_error"], t["net_hours"]),
        "err_pp_h": fmt_signed(errs["prepost_hours_error"]),
        "err_pp_pct": pct(errs["prepost_hours_error"], t["net_hours"]),
        "err_led_h": fmt_signed(errs["ledger_hours_error"]),
        "err_led_pct": pct(errs["ledger_hours_error"], t["net_hours"]),
        "cost": fmt_usd(r["cost_usd"]),
        "claim_over_cost": "%.1f" % (cl["claimed_value_usd"] / r["cost_usd"]),
        "led_over_cost": "%.1f" % (e["value_usd"] / r["cost_usd"]),
        "hard_over_cost": "%.2f" % (e["hard_usd"] / r["cost_usd"]),
        "covers_led": "yes" if r["ci_covers_truth"]["ledger"] else "no",
        "covers_pp": "yes" if r["ci_covers_truth"]["prepost"] else "no",
        "dup_pct": "%.1f%%" % (100.0 * (cl["events_logged"] - cl["events_distinct"]) / cl["events_logged"]),
        "slope": "%+.3f" % e["trend_gap_slope"],
        "slope_lo": "%+.3f" % ci["trend_gap_slope"][0],
        "slope_hi": "%+.3f" % ci["trend_gap_slope"][1],
        "placebo": "%+.2f" % e["placebo_effect"],
        "baseline_gap": "%.1f" % (-e["baseline_gap_min"]),
    }
    if "curve" in e:
        cv = e["curve"]
        d.update({
            "steady": "%.1f" % cv["steady_min_per_use"],
            "steady_lo": "%.1f" % ci["steady_min_per_use"][0],
            "steady_hi": "%.1f" % ci["steady_min_per_use"][1],
            "steady_key": "%.1f" % t["steady_min_per_use"],
            "half": "%.1f" % cv["half_life_weeks"],
            "half_lo": "%.1f" % ci["half_life_weeks"][0],
            "half_hi": "%.1f" % ci["half_life_weeks"][1],
            "half_key": "%.1f" % t["half_life_weeks"],
            "early": "%.0f" % cv["early_weekly_net_hours"],
            "late": "%.0f" % cv["steady_weekly_net_hours"],
            "early_key": "%.0f" % t["early_weekly_net_hours"],
            "late_key": "%.0f" % t["steady_weekly_net_hours"],
            "ratio_key": "%.2f" % t["early_over_steady"],
        })
    return d


def build() -> None:
    ds = load_data()
    scenarios = []
    for spec in SCENARIOS:
        r = s4.run_scenario(spec["key"])
        e, t = r["ledger"], r["truth"]
        guard = {g["cost_center_id"]: g for g in r["guardrail"]}
        rows = []
        for row in e["cc_rows"]:
            g = guard[row["cost_center_id"]]
            rows.append({
                "id": row["cost_center_id"],
                "name": ds.budget[row["cost_center_id"]]["cost_center_name"],
                "cash": row["cash_flag"],
                "net_h": fmt_int(row["net_hours"]),
                "hard": fmt_usd(row["hard_usd"]),
                "soft": fmt_usd(row["soft_usd"]),
                "hard_raw": row["hard_usd"],
                "soft_raw": row["soft_usd"],
                "rework": "%.0f%%" % (100 * g["rework_share"]),
                "hold": g["hold"],
            })
        scenarios.append({
            "key": spec["key"],
            "label": spec["label"],
            "focus": spec["focus"],
            "d": display(r, ds),
            "raw": {
                "claim_h": r["claim"]["claimed_hours"],
                "pp_h": r["prepost"]["hours"],
                "pp_ci": r["prepost_ci"],
                "led_h": e["net_hours"],
                "led_ci": r["ledger_ci"]["net_hours"],
                "truth_h": t["net_hours"],
            },
            "weeks": e["weekly"]["weeks"],
            "did_weekly": e["weekly"]["gross_per_assisted"],
            "fitted": e["curve"]["fitted_gross_per_assisted"] if "curve" in e else None,
            "key_weekly": t["weekly_gross_per_assisted"],
            "assumed": r["claim"]["assumed_min_a"],
            "cc": rows,
        })

    head = next(x for x in scenarios if x["key"] == "all")
    full = s4.run_scenario("all")
    u = full["utility"]
    util = {
        "claim_gap_pp": "%.1f" % u["claim_gap_hours_per_person"],
        "ledger_gap_pp": "%+.1f" % u["ledger_gap_hours_per_person"],
        "removed_pp": "%.1f" % u["phantom_removed_hours_per_person"],
        "removed_full_bias_pp": "%.1f" % u["phantom_removed_if_full_bias_hours_per_person"],
        "bank_headcount": fmt_int(u["bank_headcount_assumed"]),
        "scaled_hours": fmt_int(u["scaled_hours"]),
        "scaled_value": fmt_usd(u["scaled_value_usd"]),
        "n_treated": fmt_int(u["n_treated"]),
        "hard_share_of_claim": head["d"]["truth_hard"],
        "claim_value": head["d"]["claim_value"],
    }
    payload = json.dumps({"scenarios": scenarios, "util": util}, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", payload)
    DEMO.write_text(html, encoding="utf-8")
    print("wrote %s (%d bytes, %d scenarios)" % (DEMO, len(html), len(scenarios)))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ValueLedger — Benefit Realization Tracking for AI Copilots · Vijay Saharan</title>
<meta name="description" content="A clickable demo of ValueLedger: benefit realization tracking for AI copilots in a regulated bank. Compares a vendor-style claim, a pre/post comparison and a difference-in-differences ledger against a known true effect in synthetic data.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="ValueLedger — Benefit Realization Tracking for AI Copilots">
<meta property="og:description" content="Measures what a copilot actually saved against a holdout group, net of rework, and ties the benefit to a budget line.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/12-valueledger-ai-benefit-tracking/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ValueLedger — Benefit Realization Tracking for AI Copilots">
<meta name="twitter:description" content="Measures what a copilot actually saved against a holdout group, net of rework, and ties the benefit to a budget line.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/12-valueledger-ai-benefit-tracking/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>
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
    display: flex; flex-direction: column;
  }
  .card.focus { border-color: #1c2541; box-shadow: 0 0 0 2px rgba(28, 37, 65, 0.18); }
  .card-title {
    font-size: 11px; font-weight: 500; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 12px;
  }
  .card-body { font-size: 14px; line-height: 1.6; flex: 1; }
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
  .meta { font-size: 12px; color: var(--text-tertiary); margin-top: 8px; line-height: 1.5; }
  .muted-note { font-size: 12px; color: var(--text-tertiary); margin: -12px 0 24px; line-height: 1.5; }
  .driver-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; gap: 8px; }
  .driver-label { color: var(--text-secondary); }
  .driver-value { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; text-align: right; }
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
  .status-strip {
    display: inline-block; padding: 2px 10px; border-radius: var(--radius-md);
    font-size: 11px; font-weight: 500; margin-left: 8px;
  }
  .status-red { background: #FCEBEB; color: #791F1F; }
  .status-yellow { background: #FAEEDA; color: #633806; }
  .status-green { background: #EAF3DE; color: #27500A; }
  .run-meta {
    background: var(--bg-secondary); border-radius: var(--radius-md);
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 16px; line-height: 1.6;
  }
  .run-meta b { color: var(--text-primary); font-weight: 500; }
  .bar-track { position: relative; height: 12px; background: var(--bg-tertiary); border-radius: 6px; margin: 8px 0 4px; }
  .bar-fill { height: 100%; border-radius: 6px; }
  .bar-key { position: absolute; top: -4px; bottom: -4px; width: 2px; background: #16a34a; }
  .bar-caption { font-size: 11px; color: var(--text-tertiary); margin-bottom: 8px; }
  .cc-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; gap: 6px; }
  .cc-row span:first-child { color: var(--text-secondary); }
  .cc-row .num { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; text-align: right; }
  svg.spark { width: 100%; height: auto; display: block; margin-top: 6px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>ValueLedger — AI copilot benefit tracking</h1>
    <p class="tagline">Pick a scenario. See one copilot benefit measured three ways: a usage claim, a pre/post comparison, and ValueLedger.</p>
    <p class="author">Project 12 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data, no AI model called</span>
      <span class="badge">320 synthetic people, 26 weeks</span>
      <span class="badge">24 teams, 12 treated</span>
      <span class="badge">6 named deficiencies</span>
    </div>
  </header>

  <section class="stats" aria-label="Scenario summary">
    <div class="stat"><p class="stat-label">People treated / holdout</p><p class="stat-value" id="stat-people">—</p></div>
    <div class="stat"><p class="stat-label">Claim vs answer key</p><p class="stat-value" id="stat-claim">—</p></div>
    <div class="stat"><p class="stat-label">Pre/post vs answer key</p><p class="stat-value" id="stat-pp">—</p></div>
    <div class="stat"><p class="stat-label">ValueLedger vs answer key</p><p class="stat-value" id="stat-led">—</p></div>
  </section>

  <div class="controls">
    <label for="scenario-select">Scenario</label>
    <select id="scenario-select"></select>
  </div>

  <div class="run-meta" id="run-meta"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next scenario</button>
    <button id="runall-btn">Replay all scenarios</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage benefit comparison">
    <div class="card" id="card-before-wrap">
      <p class="card-title"><span class="step-num">1</span>Before — Vendor-style claim</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card" id="card-basic-wrap">
      <p class="card-title"><span class="step-num">2</span>Basic — Pre/post, treated only</p>
      <div class="card-body" id="card-basic"></div>
    </div>
    <div class="card" id="card-new-wrap">
      <p class="card-title"><span class="step-num">3</span>With ValueLedger</p>
      <div class="card-body" id="card-new"></div>
    </div>
  </section>

  <p class="muted-note">Synthetic data: the true effect is known only because the generator injected it, so every method is scored against an answer key. A real bank has no answer key. No AI model is called.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (claimed benefit − true net benefit) × cohort scale</p>
    <p style="margin: 8px 0 0;" id="utility-text"></p>
  </section>

  <footer class="footer-links">
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/12-valueledger-ai-benefit-tracking/README.md">Full walkthrough README</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/12-valueledger-ai-benefit-tracking/PRD.md">PRD</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/12-valueledger-ai-benefit-tracking/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/valueledger-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>
const DATA = __DATA__;
const SCEN = DATA.scenarios;
const UTIL = DATA.util;
let idx = 0;
let timer = null;

function esc(v) {
  return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function fx(v, d) { return esc(Number(v).toFixed(d)); }
function row(label, value) {
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + '</span></div>';
}
function bar(value, truth, maxv, color, caption) {
  const w = Math.max(0, Math.min(100, 100 * value / maxv));
  const k = Math.max(0, Math.min(100, 100 * truth / maxv));
  return '<div class="bar-track"><div class="bar-fill" style="width:' + fx(w, 1) + '%;background:' + esc(color) + '"></div>' +
         '<div class="bar-key" style="left:' + fx(k, 1) + '%"></div></div>' +
         '<div class="bar-caption">' + esc(caption) + '</div>';
}
function errClass(p) {
  const v = Math.abs(parseFloat(p.replace('%', '')));
  if (v >= 50) return "status-red";
  if (v >= 15) return "status-yellow";
  return "status-green";
}
function pillClass(p) {
  const v = Math.abs(parseFloat(p.replace('%', '')));
  if (v >= 50) return "pill-bad";
  if (v >= 15) return "pill-warn";
  return "pill-ok";
}
function spark(s) {
  const W = 280, H = 110, L = 28, R = 6, T = 8, B = 18;
  const all = s.did_weekly.concat(s.key_weekly).concat([s.assumed]);
  const ymax = Math.ceil(Math.max.apply(null, all) + 1), ymin = 0;
  const n = s.weeks.length;
  const x = function (i) { return L + (n === 1 ? 0 : i * (W - L - R) / (n - 1)); };
  const y = function (v) { return T + (H - T - B) * (1 - (v - ymin) / (ymax - ymin)); };
  function line(vals, color, dash, width) {
    const pts = vals.map(function (v, i) { return fx(x(i), 1) + "," + fx(y(v), 1); }).join(" ");
    return '<polyline fill="none" stroke="' + esc(color) + '" stroke-width="' + fx(width, 1) + '"' + (dash ? ' stroke-dasharray="4 3"' : '') + ' points="' + pts + '"/>';
  }
  let g = '<line x1="' + fx(L, 1) + '" y1="' + fx(y(0), 1) + '" x2="' + fx(W - R, 1) + '" y2="' + fx(y(0), 1) + '" stroke="#bbb" stroke-width="1"/>';
  g += line(s.weeks.map(function () { return s.assumed; }), "#dc2626", true, 1.5);
  g += line(s.key_weekly, "#16a34a", false, 2);
  if (s.fitted) { g += line(s.fitted, "#3b82f6", false, 2); }
  s.did_weekly.forEach(function (v, i) { g += '<circle cx="' + fx(x(i), 1) + '" cy="' + fx(y(v), 1) + '" r="2.2" fill="#3b82f6"/>'; });
  g += '<text x="2" y="' + fx(T + 8, 0) + '" font-size="9" fill="#8a8a8a">' + esc(ymax) + '</text>';
  g += '<text x="' + fx(L, 0) + '" y="' + fx(H - 4, 0) + '" font-size="9" fill="#8a8a8a">wk ' + esc(s.weeks[0]) + '</text>';
  g += '<text x="' + fx(W - R - 30, 0) + '" y="' + fx(H - 4, 0) + '" font-size="9" fill="#8a8a8a">wk ' + esc(s.weeks[n - 1]) + '</text>';
  return '<svg class="spark" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Weekly minutes saved per assisted task: vendor assumption, estimate, answer key">' + g + '</svg>';
}

const sel = document.getElementById("scenario-select");
SCEN.forEach(function (s, i) {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = s.label;
  sel.appendChild(o);
});

function render() {
  const s = SCEN[idx], d = s.d, r = s.raw;
  sel.value = idx;
  const maxv = Math.max(r.claim_h, r.pp_h, r.led_h, r.truth_h, r.pp_ci[1]) * 1.02;

  document.getElementById("stat-people").textContent = d.n_treated + " / " + d.n_holdout;
  document.getElementById("stat-claim").textContent = d.err_claim_pct;
  document.getElementById("stat-pp").textContent = d.err_pp_pct;
  document.getElementById("stat-led").textContent = d.err_led_pct;

  document.getElementById("run-meta").innerHTML =
    "Scenario <b>" + esc(s.label) + "</b>. Window: post-launch weeks <b>" + esc(d.weeks) + "</b>. " +
    "Answer key (true net hours freed): <b>" + esc(d.truth_h) + " h</b>. ValueLedger 95% interval covers it: " +
    '<span class="status-strip ' + (d.covers_led === "yes" ? "status-green" : "status-red") + '">' + esc(d.covers_led) + "</span>. " +
    "Pre/post 95% interval covers it: " +
    '<span class="status-strip ' + (d.covers_pp === "yes" ? "status-green" : "status-red") + '">' + esc(d.covers_pp) + "</span>.";

  document.getElementById("card-before").innerHTML =
    '<p>Usage events times an assumed number of minutes saved per use. No holdout, no baseline, no rework, no budget line.</p>' +
    row("Events logged, both tools", d.claim_events) +
    row("Counted twice", d.claim_dup + " (" + d.dup_pct + ")") +
    row("Assumed minutes per use", d.assumed) +
    row("Claimed hours", d.claim_h) +
    row("Implied value", d.claim_value) +
    bar(r.claim_h, r.truth_h, maxv, "#dc2626", "claimed hours; green tick = answer key") +
    '<span class="pill ' + pillClass(d.err_claim_pct) + '">' + esc(d.err_claim_pct) + " vs answer key (" + esc(d.err_claim_h) + " h)</span>";

  document.getElementById("card-basic").innerHTML =
    '<p>Minutes per task before and after, for the treated people only. Measures the work, but credits the tool with everything that changed.</p>' +
    row("Minutes per task, pre", d.pre_mean) +
    row("Minutes per task, post", d.post_mean) +
    row("Reduction per task", d.effect_task + " min") +
    row("Hours saved", d.pp_h) +
    row("95% interval", d.pp_lo + " to " + d.pp_hi) +
    bar(r.pp_h, r.truth_h, maxv, "#f59e0b", "pre/post hours; green tick = answer key") +
    '<span class="pill ' + pillClass(d.err_pp_pct) + '">' + esc(d.err_pp_pct) + " vs answer key (" + esc(d.err_pp_h) + " h)</span>";

  let hold = s.cc.filter(function (c) { return c.hold; }).map(function (c) { return c.id; });
  let hardV = 0, softV = 0;
  s.cc.forEach(function (c) { hardV += c.hard_raw; softV += c.soft_raw; });
  const hardShare = (hardV + softV) > 0 ? Math.max(0, Math.min(100, 100 * hardV / (hardV + softV))) : 0;
  const hardBar = '<div class="bar-track"><div class="bar-fill" style="width:' + fx(hardShare, 1) + '%;background:#16a34a"></div></div>' +
                  '<div class="bar-caption">green = hard cash, grey = soft capacity (' + fx(hardShare, 0) + '% hard)</div>';
  document.getElementById("card-new").innerHTML =
    '<p>Difference-in-differences against the holdout, net of rework, deduplicated, split into hard cash and soft capacity by budget line.</p>' +
    row("DiD gross hours", d.gross_h) +
    row("Rework netted", "-" + d.rework_h) +
    row("Net hours", d.led_h) +
    row("95% interval", d.led_lo + " to " + d.led_hi) +
    bar(r.led_h, r.truth_h, maxv, "#3b82f6", "ValueLedger net hours; green tick = answer key") +
    spark(s) +
    '<div class="meta">Weekly minutes saved per assisted task. Red dashed: vendor assumption. Green: answer key. Blue: estimate' + (s.fitted ? " and fitted curve" : "") + '.</div>' +
    (s.d.steady ? '<div class="meta">Fitted steady state ' + esc(d.steady) + ' min per use (answer key ' + esc(d.steady_key) + '), half-life ' + esc(d.half) + ' weeks (answer key ' + esc(d.half_key) + ').</div>' : '') +
    row("Hard cash (95% interval)", d.hard + " (" + d.hard_lo + " to " + d.hard_hi + ")") +
    row("Soft capacity", d.soft) +
    row("Cash a budget line can absorb, answer key", d.truth_hard + " of " + d.claim_value + " claimed") +
    hardBar +
    '<div class="meta">Quality guardrail holds: ' + esc(hold.length ? hold.join(", ") : "none") + '.</div>' +
    '<span class="pill ' + pillClass(d.err_led_pct) + '">' + esc(d.err_led_pct) + " vs answer key (" + esc(d.err_led_h) + " h)</span>" +
    '<div class="meta">Known limit: a post-launch process change by the enthusiastic teams is invisible to the data. Injected size ' + esc(d.hidden_h) + ' h (' + esc(d.hidden_pct) + ' of true net).</div>';

  ["before", "basic", "new"].forEach(function (k) {
    document.getElementById("card-" + k + "-wrap").classList.remove("focus");
  });
  if (s.focus) {
    const m = { claim: "before", prepost: "basic", ledger: "new" }[s.focus];
    document.getElementById("card-" + m + "-wrap").classList.add("focus");
  }

  document.getElementById("utility-text").innerHTML =
    "🟢 Claimed minus true net, per treated person over 14 weeks: <b>" + esc(UTIL.claim_gap_pp) + " h</b> (the vendor-style claim; step_04_with_valueledger.py). " +
    "ValueLedger minus true net: <b>" + esc(UTIL.ledger_gap_pp) + " h</b>. Phantom benefit removed: <b>" + esc(UTIL.removed_pp) + " h per person</b>, or " +
    esc(UTIL.removed_full_bias_pp) + " h if the whole injected hidden bias had landed. " +
    "🟡 Scaled to <b>" + esc(UTIL.bank_headcount) + "</b> eligible staff (assumption: the same overstatement pattern holds at a bank): about <b>" + esc(UTIL.scaled_hours) + " h</b>, about <b>" + esc(UTIL.scaled_value) + "</b> per 14-week window at the cohort's blended loaded rate. " +
    "🟢 The claimed value was " + esc(UTIL.claim_value) + "; the cash a budget line can absorb, per the answer key, was " + esc(UTIL.hard_share_of_claim) + ".";
}

function stop() { if (timer) { clearInterval(timer); timer = null; } }
sel.addEventListener("change", function (e) { stop(); idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", function () { stop(); if (idx > 0) idx -= 1; render(); });
document.getElementById("next-btn").addEventListener("click", function () { stop(); if (idx < SCEN.length - 1) idx += 1; render(); });
document.getElementById("runall-btn").addEventListener("click", function () {
  stop();
  let i = 0;
  timer = setInterval(function () {
    idx = i; render(); i += 1;
    if (i >= SCEN.length) { stop(); }
  }, 900);
});
document.getElementById("reset-btn").addEventListener("click", function () { stop(); idx = 0; render(); });

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
