"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline. The scorecard is a stub, not a
model, and the data is synthetic.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_model_card_only import GROUPS, POLICY_CUTOFF, default_rates, model_card, prepare
from step_02_accuracy_baseline import accuracy_by_group
from step_03_deficiencies_exposed import AIR_SCREEN, REASONS_LISTED, bootstrap_air, crossing, sweep
from step_04_with_fairlens import label_noise_stress, pick_cutoffs, run_pack, scenario, utility

ROOT = Path(__file__).parent.parent
FOLDER = "17-fairlens-credit-model-fairness"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


def build_payload() -> dict:
    prep = prepare()
    sw = sweep(prep)
    cp = crossing(sw)
    cutoffs = pick_cutoffs(cp)
    defaults = default_rates(prep)
    scn, packs = {}, {}
    for c in cutoffs:
        bs = bootstrap_air(prep, c)
        pack = run_pack(prep, bs, c)
        packs[str(c)] = [{"id": t["id"], "name": t["name"], "verdict": t["verdict"], "numbers": t["numbers"]}
                         for t in pack["tests"]]
        acc = {b["group"]: b["accuracy"] for b in accuracy_by_group(prep["rows"], c)}
        scn[str(c)] = {}
        for g in GROUPS:
            s = scenario(prep, g, c, bs)
            scn[str(c)][g] = {
                "n": s["n"], "approved": s["approved"], "approval": pct(s["approval_rate"]),
                "accuracy": pct(acc[g]), "acc_gap": f"{100 * (max(acc.values()) - acc[g]):.1f}",
                "air": f"{s['air']:.3f}", "lo": f"{s['lo']:.3f}", "hi": f"{s['hi']:.3f}",
                "verdict": s["verdict"], "is_reference": s["is_reference"], "reference": s["reference"],
                "ref_approval": pct(AT_REF(prep, c)), "min_air": f"{s['min_air']:.3f}", "min_group": s["min_group"],
                "overall_acc": pct(s["overall"]["accuracy"]), "overall_apr": pct(s["overall"]["approval_rate"]),
                "default_rate": pct(defaults[g]["rate"]), "declined": s["reasons"]["declined"],
                "reasons": [{"code": r["code"], "text": r["text"], "share": pct(r["share"])} for r in s["reasons"]["top"]],
            }
    base = run_pack(prep, None, POLICY_CUTOFF)
    u = utility(base)
    t = {x["id"]: x for x in base["tests"]}
    ln = label_noise_stress(prep)
    first = next((x for x in ln if x["passes"]), None)
    meta = {
        "applicants": len(prep["rows"]), "groups": len(GROUPS), "tests": len(base["tests"]),
        "policy": POLICY_CUTOFF, "crossing": cp, "screen": f"{AIR_SCREEN:.2f}",
        "model_acc": pct(model_card(prep)["accuracy"]), "model_apr": pct(model_card(prep)["approval_rate"]),
        "spread": f"{t['T1']['spread_pts']:.1f}", "flagged": u["flagged"],
        "min_air": f"{t['T2']['min_air']:.3f}", "min_group": t["T2"]["min_group"],
        "lift_before": f"{t['T4']['before'][0]:.3f}", "lift_after": f"{t['T4']['after'][0]:.3f}",
        "acc_before": pct(t["T4"]["acc_before"]), "acc_after": pct(t["T4"]["acc_after"]),
        "u_delta": f"{u['delta']:.2f}", "u_run": u["tests_run"], "u_base": u["tests_baseline"],
        "u_volume": f"{u['annual_decisions']:,}", "u_total": f"{u['utility']:,.0f}",
        "u_turn": u["turn_on_proxy"], "u_applicants": f"{u['applicants']:,}", "u_turn_share": pct(u["turn_share"], 2),
        "u_turn_annual": f"{u['turn_annual']:,.0f}", "reasons_listed": REASONS_LISTED,
        "label_share": pct(first["wrong_share"]) if first else "", "label_air": f"{first['min_air']:.3f}" if first else "",
        "label_true_air": f"{ln[0]['min_air']:.3f}", "t5_excess": f"{t['T5']['pairs']['excess_pts']:+.1f}",
        "t5_unnamed": t["T5"]["proxy"]["unnamed"], "t5_proxy": t["T5"]["proxy"]["proxy_declines"],
        "cutoffs": cutoffs,
    }
    return {"meta": meta, "scn": scn, "packs": packs}


def AT_REF(prep: dict, cutoff: int) -> float:
    """Approval rate of the reference group at one cutoff."""
    from step_03_deficiencies_exposed import group_stats
    gs = group_stats(prep, cutoff)
    return gs["groups"][gs["reference"]]["approval_rate"]


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
  select { flex: 1; min-width: 200px; }
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
  .note { font-size: 12px; color: var(--text-tertiary); margin-top: 8px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
"""

JS = """
const D = __PAYLOAD__;
const M = D.meta;
const GROUPS = ["Group A", "Group B", "Group C"];
const CUTS = M.cutoffs;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

const gsel = document.getElementById("group-select");
const csel = document.getElementById("cutoff-select");
GROUPS.forEach((g, i) => { const o = document.createElement("option"); o.value = i; o.textContent = g; gsel.appendChild(o); });
CUTS.forEach((c, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = c + " points" + (c === M.policy ? " - policy cutoff" : (c === M.crossing ? " - last cutoff where the screen holds" : ""));
  csel.appendChild(o);
});
let gi = 1, ci = CUTS.indexOf(M.policy);

function vClass(v) { return v === "FAIL" ? "tag-bad" : (v === "REVIEW" ? "tag-warn" : "tag-ok"); }
function pillClass(v) { return v === "FAIL" ? "pill-bad" : (v === "REVIEW" ? "pill-warn" : "pill-ok"); }

function render() {
  gsel.value = gi; csel.value = ci;
  const c = CUTS[ci], g = GROUPS[gi];
  const s = D.scn[String(c)][g];
  const tests = D.packs[String(c)];
  const flagged = tests.filter(t => t.verdict !== "PASS").length;

  document.getElementById("stat-acc").textContent = s.overall_acc;
  document.getElementById("stat-apr").textContent = s.approval;
  document.getElementById("stat-air").textContent = s.is_reference ? "1.000" : s.air;
  document.getElementById("stat-flag").textContent = flagged + " of " + tests.length;

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(g) + "</b> at cutoff <b>" + esc(c) + "</b> - " + esc(s.n.toLocaleString("en-US")) + " applicants, " +
    esc(s.approved.toLocaleString("en-US")) + " approved. Reference group (highest approval rate): <b>" + esc(s.reference) + "</b> at " + esc(s.ref_approval) + ".";

  // Card 1: before
  let b = "";
  b += '<div class="driver-row"><span class="driver-label">Model card: accuracy</span><span class="driver-value">' + esc(s.overall_acc) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Model card: approval rate</span><span class="driver-value">' + esc(s.overall_apr) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Fairness tests run</span><span class="driver-value">' + esc(M.u_base) + " of " + esc(M.tests) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Numbers split by group</span><span class="driver-value">none</span></div>';
  b += '<span class="pill pill-ok">accuracy ' + esc(s.overall_acc) + ": looks fine</span>";
  b += '<div class="note">The model card is the only evidence a reviewer is given. The scorecard is a stub, not a model.</div>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: basic approach
  let a = "";
  a += '<div class="driver-row"><span class="driver-label">' + esc(g) + " accuracy</span><span class=\\"driver-value\\">" + esc(s.accuracy) + "</span></div>";
  a += '<div class="driver-row"><span class="driver-label">Below the best group</span><span class="driver-value">' + esc(s.acc_gap) + " points</span></div>";
  a += '<div class="driver-row"><span class="driver-label">Approval rate shown?</span><span class="driver-value">no</span></div>';
  a += '<div class="driver-row"><span class="driver-label">AIR shown?</span><span class="driver-value">no</span></div>';
  a += '<div class="driver-row"><span class="driver-label">Reason codes checked?</span><span class="driver-value">no</span></div>';
  a += '<span class="pill pill-warn">accuracy by group: looks fine, MISSED</span>';
  a += '<div class="note">Accuracy-style checks are correct. They are silent on who is approved.</div>';
  document.getElementById("card-sota").innerHTML = a;

  // Card 3: FairLens
  let h = "";
  const word = s.verdict === "REFERENCE" ? "REFERENCE GROUP" : (s.verdict === "FAIL" ? "FAIL - CAUGHT" : (s.verdict === "REVIEW" ? "REVIEW - FLAGGED" : "PASS"));
  h += '<div class="reltitle">' + esc(g) + ' <span class="tag ' + vClass(s.verdict === "REFERENCE" ? "PASS" : s.verdict) + '">' + esc(word) + "</span></div>";
  h += '<div class="driver-row"><span class="driver-label">Approval rate</span><span class="driver-value">' + esc(s.approval) + " vs " + esc(s.ref_approval) + "</span></div>";
  h += '<div class="driver-row"><span class="driver-label">AIR</span><span class="driver-value">' + (s.is_reference ? "1.000 (reference)" : esc(s.air)) + "</span></div>";
  h += '<div class="driver-row"><span class="driver-label">95% interval</span><span class="driver-value">' + (s.is_reference ? "-" : esc(s.lo) + " to " + esc(s.hi)) + "</span></div>";
  h += '<div class="driver-row"><span class="driver-label">Screen</span><span class="driver-value">' + esc(M.screen) + "</span></div>";
  tests.forEach(t => {
    h += '<div class="fieldrow"><span class="fieldname">' + esc(t.id) + " " + esc(t.name) + '</span><span class="tag ' + vClass(t.verdict) + '">' + esc(t.verdict) + "</span>" +
         '<div class="fieldvals">' + esc(t.numbers) + "</div></div>";
  });
  if (s.reasons.length) {
    h += '<div class="fieldrow"><span class="fieldname">Top reason codes, declined ' + esc(g) + '</span><div class="fieldvals">' +
         s.reasons.map(r => esc(r.code) + " " + esc(r.share)).join(", ") + " (of " + esc(s.declined.toLocaleString("en-US")) + " declines)</div></div>";
  }
  h += '<span class="pill ' + pillClass(s.verdict === "REFERENCE" ? "PASS" : s.verdict) + '">' + esc(word) + "</span>";
  if (s.verdict === "REVIEW") {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">The interval straddles the screen. With this few applicants the data cannot say which side the group is on, so a person reviews it.</div>';
  }
  document.getElementById("card-shield").innerHTML = h;
}

gsel.addEventListener("change", e => { gi = parseInt(e.target.value, 10); render(); });
csel.addEventListener("change", e => { ci = parseInt(e.target.value, 10); render(); });
document.getElementById("next-btn").addEventListener("click", () => {
  gi++; if (gi >= GROUPS.length) { gi = 0; ci = (ci + 1) % CUTS.length; } render();
});
document.getElementById("prev-btn").addEventListener("click", () => {
  gi--; if (gi < 0) { gi = GROUPS.length - 1; ci = (ci - 1 + CUTS.length) % CUTS.length; } render();
});
document.getElementById("reset-btn").addEventListener("click", () => { gi = 1; ci = CUTS.indexOf(M.policy); render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0; const total = GROUPS.length * CUTS.length;
  const iv = setInterval(() => { ci = Math.floor(i / GROUPS.length); gi = i % GROUPS.length; render(); i++; if (i >= total) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    m = p["meta"]
    n_scn = m["groups"] * len(m["cutoffs"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FairLens — Credit-Model Fairness Test Pack · Vijay Saharan</title>
<meta name="description" content="A clickable demo of FairLens: a fairness test pack for a credit-decision model. It computes adverse impact by group with an interval, sweeps the cutoff, ablates a proxy and checks reason codes. Synthetic data and a stub scorecard, not a model.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="FairLens — Credit-Model Fairness Test Pack">
<meta property="og:description" content="Tests a synthetic credit model for the gap overall accuracy hides: adverse impact by group, cutoff sweep, proxy and reason-code checks.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/17-fairlens-credit-model-fairness/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="FairLens — Credit-Model Fairness Test Pack">
<meta name="twitter:description" content="Tests a synthetic credit model for the gap overall accuracy hides: adverse impact by group, cutoff sweep, proxy and reason-code checks.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/17-fairlens-credit-model-fairness/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>FairLens — Credit-Model Fairness Test Pack</h1>
    <p class="tagline">Pick a group and a cutoff and see what accuracy shows, and what {m['tests']} fairness tests show.</p>
    <p class="author">Project 17 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{m['applicants']:,} applicants · {m['groups']} groups</span>
      <span class="badge">Stub scorecard, not a model</span>
      <span class="badge">{m['tests']} named deficiencies</span>
    </div>
  </header>

  <section class="stats" aria-label="Numbers for the selected group and cutoff">
    <div class="stat"><p class="stat-label">Model-card accuracy</p><p class="stat-value" id="stat-acc">—</p></div>
    <div class="stat"><p class="stat-label">Approval rate, this group</p><p class="stat-value" id="stat-apr">—</p></div>
    <div class="stat"><p class="stat-label">AIR, this group</p><p class="stat-value" id="stat-air">—</p></div>
    <div class="stat"><p class="stat-label">Tests returning REVIEW or FAIL</p><p class="stat-value" id="stat-flag">—</p></div>
  </section>

  <div class="controls">
    <label for="group-select">Group</label>
    <select id="group-select"></select>
    <label for="cutoff-select">Cutoff</label>
    <select id="cutoff-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next scenario</button>
    <button id="runall-btn">Replay all {n_scn} scenarios</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Model card only</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Accuracy by group</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With FairLens</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The groups are labels the generator made up and encode no real protected class. The scorecard is a stub, not a trained model, and no model is used anywhere. AIR is a screening statistic, not a legal finding; {m['screen']} is a convention from employment guidance, not a credit-law standard. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (fairness tests run with FairLens − with accuracy only) ÷ tests × credit decisions a year</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> the accuracy-only view runs {m['u_base']} of {m['u_run']} fairness tests (by definition). The pack runs {m['u_run']} of {m['u_run']} and {m['flagged']} of {m['u_run']} return REVIEW or FAIL at the policy cutoff {m['policy']}. The lowest AIR is {m['min_air']} ({esc_py(m['min_group'])}) against {m['spread']} points of approval spread behind {m['model_acc']} accuracy. Neutralizing the postcode points lifts the lowest AIR from {m['lift_before']} to {m['lift_after']} and accuracy from {m['acc_before']} to {m['acc_after']}.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {m['u_volume']} credit decisions a year under this scorecard (an assumption, not a statistic) gives {m['u_delta']} × {m['u_volume']} = <b>{m['u_total']} decisions a year</b> under a model with a full fairness test pack. {m['u_turn']} of {m['u_applicants']} test-set decisions ({m['u_turn_share']}) turn on the postcode points; at the same share the modeled volume would be about {m['u_turn_annual']}. The test set is dense on purpose, so that is not a frequency estimate.</p>
    <p style="margin: 8px 0 0;">🔴 <b>What it still gets wrong:</b> AIR is a screening statistic, and the search for less discriminatory alternatives is one ablation. Real credit data has no group labels: with {m['label_share']} of labels wrong at random the screen passes (lowest AIR {m['label_air']}) when it fails on the true labels ({m['label_true_air']}). The reason-code pair check passes ({m['t5_excess']} points against its control) while {m['t5_proxy']} declines are caused by the postcode points; with {m['reasons_listed']} reasons listed, {m['t5_unnamed']} of them omit the postcode reason.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/fairlens-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>{js}</script>
</body>
</html>
"""


def esc_py(v) -> str:
    import html
    return html.escape(str(v), quote=True)


def main() -> None:
    p = build_payload()
    out = ROOT / "demo.html"
    out.write_text(build_html(p), encoding="utf-8")
    print(f"Wrote {out.name}: {p['meta']['groups'] * len(p['meta']['cutoffs'])} scenarios, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
