"""Writes ../demo.html from script output (standard library only).

Every number in demo.html is computed by the functions in the step scripts,
the same ones the terminal output and the Streamlit app use. Nothing is retyped.
The results are SIMULATED; data/_generate.py is a seeded stub, no model is called.

Run from src/ (about 30 seconds):
    python _build_demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

import step_04_with_swapbrief as s4
from step_01_headline_average import load_dataset

HERE = Path(__file__).parent
OUT_HTML = HERE.parent / "demo.html"


def pack_result(r: dict) -> dict:
    return {
        "decision": r["decision"],
        "reasons": r["reasons"],
        "slices": [{"slice": x["slice"], "severity": x["severity"], "n": x["n"], "acc_a": x["acc_a"], "acc_b": x["acc_b"],
                    "delta": x["delta"], "lo": x["lo"], "hi": x["hi"], "tol": x["tol"], "status": x["status"]}
                   for x in r["slices"]],
        "cost": r["cost"],
        "latency": r["latency"],
        "triggers": [{"metric": t["metric"], "threshold": t["threshold_text"], "window": t["window"],
                      "min_sample": t["min_sample"], "action": t["action"]} for t in r["triggers"]],
        "inconclusive": [{"slice": x["slice"], "n": x["n"], "lo": x["lo"], "hi": x["hi"]} for x in r["inconclusive"]],
        "resamples": r["bootstrap_resamples"],
    }


def pack_view(view: dict, sid: int, label: str) -> dict:
    h, ho = view["headline"], view["headline_old"]
    b, bo = view["basic"], view["basic_old"]
    return {
        "id": sid, "label": label, "n_items": view["n_items"],
        "headline": {"decision": h["decision"], "acc_a": h["acc_a"], "acc_b": h["acc_b"], "delta": h["delta"]},
        "headline_old": {"decision": ho["decision"], "delta": ho["delta"]},
        "basic": {"decision": b["decision"], "delta": b["delta"], "lo": b["ci_lo"], "hi": b["ci_hi"], "p": b["mcnemar_p"],
                  "alpha": b["alpha"]},
        "basic_old": {"decision": bo["decision"], "delta": bo["delta"], "p": bo["mcnemar_p"]},
        "retuned": pack_result(view["fair"]["retuned"]),
        "old": pack_result(view["fair"]["old"]),
        "truth": view["truth"],
    }


def collect() -> dict:
    ds = load_dataset()
    scenarios = [pack_view(s4.committed_view(ds), 0, "Committed set: 720 items, the CSVs in data/")]
    for i, text in s4.CURATED:
        scenarios.append(pack_view(s4.scenario_view(i, ds["policy"]), i, "S%03d: %s" % (i, text)))
    records = s4.run_scenarios(policy=ds["policy"])
    scores = s4.score_rules(records)
    return {"scenarios": scenarios, "scores": scores, "utility": s4.utility(scores),
            "migrations_per_year": s4.MIGRATIONS_PER_YEAR, "curated_ok": s4.verify_curated(records)}


def main() -> None:
    data = collect()
    if not all(data["curated_ok"]):
        raise SystemExit("a curated scenario no longer matches its label: " + str(data["curated_ok"]))
    blob = json.dumps(data, separators=(",", ":"))
    # keep the JSON inert inside a <script> block
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    OUT_HTML.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    print("wrote %s (%d scenarios, %d bytes)" % (OUT_HTML.name, len(data["scenarios"]), OUT_HTML.stat().st_size))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SwapBrief — Go or No-Go Brief for a Model Migration · Vijay Saharan</title>
<meta name="description" content="A clickable demo of SwapBrief: a go or no-go decision brief for moving a production GenAI feature to a new model version, with slice intervals, cost per correct answer, tail latency, a prompt-fair comparison and rollback triggers. Simulated data; no model is called.">
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
  .card-title {
    font-size: 11px; font-weight: 500; color: var(--text-secondary);
    text-transform: uppercase; letter-spacing: 0.6px; margin: 0 0 12px;
  }
  .card-body { font-size: 14px; line-height: 1.6; flex: 1; }
  .card-body ul { margin: 6px 0 6px 18px; padding: 0; }
  .card-body li { margin: 2px 0; }
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
  .driver-row { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 13px; }
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
  .status-grey { background: #ecebe7; color: #5a5a5a; }
  .run-meta {
    background: var(--bg-secondary); border-radius: var(--radius-md);
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 16px; line-height: 1.6;
  }
  .run-meta b { color: var(--text-primary); font-weight: 500; }
  .wide { background: var(--bg-primary); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px 18px; margin-bottom: 24px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { text-align: left; font-weight: 500; color: var(--text-secondary); padding: 6px 8px; border-bottom: 1px solid var(--border); white-space: nowrap; }
  td { padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
  td.num { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; white-space: nowrap; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>SwapBrief — Go or No-Go Brief for a Model Migration</h1>
    <p class="tagline">Pick a migration scenario. See how the same evaluation is decided three ways: the headline average, the average plus a significance test, and SwapBrief (slice intervals, cost per correct answer, tail latency, a prompt-fair comparison and rollback triggers).</p>
    <p class="author">Project 13 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">720 simulated items</span>
      <span class="badge">8 slices</span>
      <span class="badge">3 conditions</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">Simulated data, no model called</span>
    </div>
  </header>

  <section class="stats" aria-label="Scenario summary">
    <div class="stat"><p class="stat-label">Headline change</p><p class="stat-value" id="stat-headline">—</p></div>
    <div class="stat"><p class="stat-label">Slices flagged</p><p class="stat-value" id="stat-flagged">—</p></div>
    <div class="stat"><p class="stat-label">Cost per correct vs A</p><p class="stat-value" id="stat-cost">—</p></div>
    <div class="stat"><p class="stat-label">p95 latency vs A</p><p class="stat-value" id="stat-p95">—</p></div>
  </section>

  <div class="controls">
    <label for="scenario-select">Migration scenario</label>
    <select id="scenario-select"></select>
  </div>

  <div class="run-meta" id="run-meta"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next scenario</button>
    <button id="runall-btn">Replay all scenarios</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage decision comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Headline average</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Average plus a significance test</p>
      <div class="card-body" id="card-basic"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With SwapBrief</p>
      <div class="card-body" id="card-swapbrief"></div>
    </div>
  </section>

  <section class="wide" aria-label="Slice table">
    <p class="card-title">Slice table · model B with the retuned prompt minus model A · paired bootstrap 95% interval</p>
    <div id="slice-table"></div>
  </section>

  <section class="wide" aria-label="Rollback triggers">
    <p class="card-title">Rollback triggers · metric, threshold, window</p>
    <div id="trigger-table"></div>
    <p class="meta" id="limit-note"></p>
  </section>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (headline bad-migration rate − SwapBrief bad-migration rate) × migrations per year</p>
    <p style="margin: 8px 0 0;" id="utility-text"></p>
  </section>

  <footer class="footer-links">
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/13-swapbrief-model-migration/README.md">Full walkthrough README</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/13-swapbrief-model-migration/PRD.md">PRD</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/13-swapbrief-model-migration/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/swapbrief-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>
const DATA = __DATA__;
const SCEN = DATA.scenarios;
let currentIdx = 0;

function esc(v) {
  return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function pp(x) { const v = x * 100; return (v >= 0 ? "+" : "") + v.toFixed(1) + " pp"; }
function pct(x) { const v = (x - 1) * 100; return (v >= 0 ? "+" : "") + v.toFixed(1) + "%"; }
function pct1(x) { return (x * 100).toFixed(1) + "%"; }
function decisionClass(d) { return d === "GO" ? "status-green" : (d === "GO WITH GUARDRAILS" || d === "HOLD" ? "status-yellow" : "status-red"); }
function pillClass(d) { return d === "GO" ? "pill-ok" : (d === "GO WITH GUARDRAILS" || d === "HOLD" ? "pill-warn" : "pill-bad"); }
function row(label, value) {
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + '</span></div>';
}
function count(slices, status) { return slices.filter(function (s) { return s.status === status; }).length; }

const sel = document.getElementById("scenario-select");
SCEN.forEach(function (s, i) {
  const opt = document.createElement("option");
  opt.value = i;
  opt.textContent = s.label;
  sel.appendChild(opt);
});
document.getElementById("runall-btn").textContent = "Replay all " + SCEN.length + " scenarios";

function render() {
  const s = SCEN[currentIdx];
  sel.value = currentIdx;
  const r = s.retuned, o = s.old;
  const flagged = r.slices.filter(function (x) { return x.status !== "OK" && x.status !== "IMPROVED"; }).length;

  document.getElementById("stat-headline").textContent = pp(s.headline.delta);
  document.getElementById("stat-flagged").textContent = flagged + " of " + r.slices.length;
  document.getElementById("stat-cost").textContent = pct(r.cost.ratio);
  document.getElementById("stat-p95").textContent = pct(r.latency.p95_ratio);

  let truth = "";
  if (s.truth) {
    const reg = (s.truth.regressed_slices || []);
    truth = " Generator's truth (never shown to the rules): regressed slices " + (reg.length ? reg.join(", ") : "none") +
      "; true cost per correct vs A " + s.truth.cost_ratio.toFixed(2) + "x; true p95 vs A " + s.truth.p95_ratio.toFixed(2) + "x.";
  }
  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(s.label) + "</b> — " + esc(s.n_items) + " items scored for model A, model B with A's old prompt and model B with a retuned prompt. " +
    "Simulated results from a seeded generator (a stub for real evaluation runs), not measurements of any real model. SwapBrief decision " +
    '<span class="status-strip ' + decisionClass(r.decision) + '">' + esc(r.decision) + "</span>." + esc(truth);

  document.getElementById("card-before").innerHTML =
    "<p>Compare one number: B's overall average against A's. Higher means GO.</p>" +
    row("Model A", pct1(s.headline.acc_a)) + row("Model B, retuned prompt", pct1(s.headline.acc_b)) +
    row("Change", pp(s.headline.delta)) + row("Slices looked at", "none") + row("Rollback triggers", "0") +
    '<span class="pill ' + pillClass(s.headline.decision) + '">' + esc(s.headline.decision) + "</span>" +
    '<p class="meta">With A\'s old prompt the same rule says ' + esc(s.headline_old.decision) + " (" + esc(pp(s.headline_old.delta)) + ").</p>";

  document.getElementById("card-basic").innerHTML =
    "<p>Same average, plus a test of whether the difference is bigger than noise.</p>" +
    row("Change", pp(s.basic.delta)) + row("95% interval", pp(s.basic.lo) + " to " + pp(s.basic.hi)) +
    row("McNemar p-value", s.basic.p.toFixed(4)) + row("Slices looked at", "none") + row("Rollback triggers", "0") +
    '<span class="pill ' + pillClass(s.basic.decision) + '">' + esc(s.basic.decision) + "</span>" +
    '<p class="meta">With A\'s old prompt: ' + esc(s.basic_old.decision) + " (p = " + esc(s.basic_old.p.toFixed(4)) + ").</p>";

  let reasons = "";
  r.reasons.slice(0, 4).forEach(function (x) { reasons += "<li>" + esc(x) + "</li>"; });
  document.getElementById("card-swapbrief").innerHTML =
    "<ul>" + reasons + "</ul>" +
    row("Slices regressed / watch / inconclusive", count(r.slices, "REGRESSED") + " / " + count(r.slices, "WATCH") + " / " + count(r.slices, "INCONCLUSIVE")) +
    row("Cost per correct vs A", pct(r.cost.ratio) + " (" + r.cost.status + ")") +
    row("p50 / p95 vs A", pct(r.latency.p50_ratio) + " / " + pct(r.latency.p95_ratio)) +
    row("Rollback triggers", String(r.triggers.length)) +
    '<span class="pill ' + pillClass(r.decision) + '">' + esc(r.decision) + "</span>" +
    '<p class="meta">With A\'s old prompt: ' + esc(o.decision) + ".</p>";

  let t = "<table><thead><tr><th>slice</th><th>severity</th><th>items</th><th>A</th><th>B</th><th>change</th><th>95% interval</th><th>status</th></tr></thead><tbody>";
  r.slices.forEach(function (x) {
    t += "<tr><td>" + esc(x.slice) + "</td><td>" + esc(x.severity) + "</td><td class=\"num\">" + esc(x.n) + "</td><td class=\"num\">" + esc(pct1(x.acc_a)) +
      "</td><td class=\"num\">" + esc(pct1(x.acc_b)) + "</td><td class=\"num\">" + esc(pp(x.delta)) + "</td><td class=\"num\">" +
      esc(pp(x.lo) + " to " + pp(x.hi)) + "</td><td>" + esc(x.status) + "</td></tr>";
  });
  t += "</tbody></table>";
  document.getElementById("slice-table").innerHTML = t;

  let g = "<table><thead><tr><th>metric</th><th>threshold</th><th>window</th><th>min scored responses</th><th>action</th></tr></thead><tbody>";
  r.triggers.forEach(function (x) {
    g += "<tr><td>" + esc(x.metric) + "</td><td class=\"num\">" + esc(x.threshold) + "</td><td>" + esc(x.window) + "</td><td class=\"num\">" +
      esc(x.min_sample ? x.min_sample : "n/a") + "</td><td>" + esc(x.action) + "</td></tr>";
  });
  g += "</tbody></table>";
  document.getElementById("trigger-table").innerHTML = g;

  let limit = "Known limit: slices with too few items stay inconclusive. ";
  if (r.inconclusive.length) {
    limit += "In this scenario: " + r.inconclusive.map(function (x) { return x.slice + " (" + x.n + " items, interval " + pp(x.lo) + " to " + pp(x.hi) + ")"; }).join("; ") + ".";
  } else {
    limit += "No slice is inconclusive in this scenario.";
  }
  document.getElementById("limit-note").textContent = limit;

  const u = DATA.utility, sc = DATA.scores;
  document.getElementById("utility-text").innerHTML =
    "🟢 Headline-average rule: <b>" + esc(pct1(u.headline_rate)) + "</b> of simulated migrations shipped with a real problem it did not flag. SwapBrief: <b>" +
    esc(pct1(u.swapbrief_rate)) + "</b>. Measured on " + esc(sc.n_scenarios) + " seeded scenarios against the generator's truth (<code>step_04_with_swapbrief.py</code>); " +
    esc(sc.n_bad) + " had a real problem. False-GO rate: headline " + esc(pct1(sc.rules.headline.false_go_rate)) + ", aggregate test " +
    esc(pct1(sc.rules.basic.false_go_rate)) + ", SwapBrief " + esc(pct1(sc.rules.swapbrief.false_go_rate)) + ". " +
    "🟡 Migrations per year: <b>" + esc(DATA.migrations_per_year) + "</b> (assumption: 9 production GenAI features, each forced onto a successor about every 18 months). " +
    "Modeled result: <b>" + esc(u.avoided_per_year.toFixed(1)) + " bad migrations avoided per year</b>. " +
    "Known limit: SwapBrief left " + esc(sc.rules.swapbrief.unresolved_regressions) + " of " + esc(sc.total_true_regressed_slices) +
    " true slice regressions unresolved and missed " + esc(sc.rules.swapbrief.missed_regressions) + ". Simulated data throughout.";
}

sel.addEventListener("change", function (e) { currentIdx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", function () { if (currentIdx > 0) currentIdx -= 1; render(); });
document.getElementById("next-btn").addEventListener("click", function () { if (currentIdx < SCEN.length - 1) currentIdx += 1; render(); });
document.getElementById("runall-btn").addEventListener("click", function () {
  let i = 0;
  const iv = setInterval(function () {
    currentIdx = i; render(); i += 1;
    if (i >= SCEN.length) clearInterval(iv);
  }, 1200);
});
document.getElementById("reset-btn").addEventListener("click", function () { currentIdx = 0; render(); });

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
