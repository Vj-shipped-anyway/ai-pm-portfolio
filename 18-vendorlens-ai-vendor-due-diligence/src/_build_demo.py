"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_status_quo import DOC_TYPES, summarize as summarize_step1
from step_02_questionnaire_checklist import summarize as summarize_step2
from step_03_deficiencies_exposed import summarize as summarize_step3
from step_04_with_vendorlens import analyze, questionnaire_tag, vendorlens_tag

ROOT = Path(__file__).parent.parent
FOLDER = "18-vendorlens-ai-vendor-due-diligence"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    data = a["data"]
    s1, s2, s3, s4 = summarize_step1(data), summarize_step2(data), summarize_step3(data), a["summary"]
    share = {x["provider"]: x["share_pct"] for x in a["conc"]["rows"]}
    vendors = []
    for r in a["rows"]:
        vid = r["vendor_id"]
        v = data["by_id"][vid]
        ans = data["answers"][vid]
        t = data["truth"][vid]
        qtag, qfail = questionnaire_tag(r)
        vendors.append({
            "id": vid, "rank": r["rank"], "service": r["service_type"], "tier": r["criticality"],
            "data_access": r["data_access"], "provider": r["provider"] if r["provider_disclosed"] else "",
            "provider_share": share.get(r["provider"]) if r["provider_disclosed"] else None,
            "critical_use_cases": v["critical_use_cases"],
            "yes": sum(1 for x in ans.values() if x == "yes"), "partial": sum(1 for x in ans.values() if x == "partial"),
            "no": sum(1 for x in ans.values() if x == "no"), "ck_pass": r["checklist_pass"],
            "q_tag": qtag, "q_fail": qfail,
            "age_days": r["age_days"], "exit_clause": v["exit_clause"], "exit_tested": v["exit_tested"],
            "portability_days": v["portability_days"], "audit_right": v["audit_right"], "notice_days": v["model_change_notice_days"],
            "evidence": r["evidence"],
            "truth": t["true_risk"], "latent": t["latent"], "overclaimed": t["overclaimed"],
            "true_provider": t["true_provider"], "provider_disclosed": t["provider_disclosed"],
            "vl_class": r["class"], "risk": r["risk"], "control_score": r["control_score"], "yes_unbacked": r["yes_unbacked"],
            "contradicted": r["yes_by_backing"]["contradicted"],
            "exit_state": r["exit_state"], "exit_score": r["exit_score"], "modeled_exit": round(r["modeled_exit_days"]),
            "allowed_exit": r["allowed_exit_days"], "conc_flag": r["conc_flag"], "cadence_days": r["cadence_days"],
            "overdue": r["overdue"], "days_overdue": r["days_overdue"], "next_review": r["next_review"],
            "reasons": [[k, txt] for k, txt in r["reasons"]], "vl_tag": vendorlens_tag(r),
        })
    return {"vendors": vendors, "doc_types": list(DOC_TYPES),
            "s1": {k: s1[k] for k in ("vendors", "documents", "critical", "pii", "questions")},
            "s2": {k: s2[k] for k in ("passes", "fails", "pass_pct", "true_high", "pass_high", "high_found", "pass_rule_pct")},
            "s3": {"d1": s3["d1"], "d2": {k: v for k, v in s3["d2"].items() if k != "rows"},
                   "d3": s3["d3"], "d4": s3["d4"], "d5": s3["d5"], "d6": s3["d6"]},
            "s4": {k: s4[k] for k in (
                "vendors", "classes", "high_tp", "pred_high", "true_high", "high_precision_pct", "high_recall_pct",
                "checklist_found", "checklist_fail", "checklist_precision_pct", "queue_size", "topk_found",
                "passed_high_total", "passed_high_caught", "top_provider", "top_share_pct", "true_top_share_pct",
                "understated_points", "unknown_vendors", "unknown_use_cases", "unknown_pct", "critical_use_cases",
                "found_rate_vendorlens", "found_rate_checklist", "estate_vendors", "utility_vendors",
                "class_correct", "class_correct_pct", "critical_exit_not_ready", "critical")}}


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
  .note { font-size: 12px; color: var(--text-tertiary); margin-top: 8px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
"""

JS = """
const DATA = __PAYLOAD__;
const V = DATA.vendors;
const DOC = {independent_control_report: "Control report", penetration_test: "Penetration test", model_documentation: "Model documentation"};
const EV = {valid: "valid", stale: "stale", out_of_scope: "out of scope", missing: "missing"};
const DATAL = {customer_pii: "customer PII", internal: "internal data", none: "no data"};
const PART = {control: "Evidence", exit: "Exit", contract: "Contract", concentration: "Concentration"};

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function monthsOf(d) { return Math.round(d / 30.4375); }

const START = Math.max(0, V.findIndex(v => v.ck_pass && v.truth === "high" && v.vl_class === "high"));
let idx = START;
const sel = document.getElementById("vendor-select");
V.forEach((v, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = String(v.rank) + ". " + v.id + " - " + v.tier + " - questionnaire " + (v.ck_pass ? "PASS" : "FAIL") + " - VendorLens " + v.vl_class.toUpperCase();
  sel.appendChild(o);
});

function totals(upTo) {
  let seen = 0, qfound = 0, vfound = 0, passed = 0;
  for (let i = 0; i <= upTo; i++) {
    const v = V[i];
    if (v.truth === "high") {
      seen++;
      if (v.ck_pass) { passed++; } else { qfound++; }
      if (v.vl_class === "high") { vfound++; }
    }
  }
  return { seen, qfound, vfound, passed };
}

function classTag(c) { return c === "high" ? "tag-bad" : (c === "medium" ? "tag-warn" : "tag-ok"); }
function classPill(c) { return c === "high" ? "pill-bad" : (c === "medium" ? "pill-warn" : "pill-ok"); }
function row(label, value) {
  return '<div class="driver-row"><span class="driver-label">' + esc(label) + '</span><span class="driver-value">' + esc(value) + "</span></div>";
}

function render() {
  const v = V[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-seen").textContent = String(tt.seen);
  document.getElementById("stat-qfound").textContent = String(tt.qfound);
  document.getElementById("stat-vfound").textContent = String(tt.vfound);
  document.getElementById("stat-passed").textContent = String(tt.passed);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(v.id) + "</b> - " + esc(v.service) + ". " + esc(v.tier) + " vendor, " + esc(DATAL[v.data_access]) + ", " +
    esc(v.critical_use_cases) + " critical use case" + (v.critical_use_cases === 1 ? "" : "s") + ". Upstream provider: " +
    esc(v.provider || "not disclosed") + ". VendorLens rank <b>" + esc(v.rank) + "</b> of " + esc(V.length) + ".";

  // Card 1: before - what the bank holds
  let b = "";
  b += row("Service", v.service);
  b += row("Criticality", v.tier);
  b += row("Data access", DATAL[v.data_access]);
  b += row("Upstream provider", v.provider || "not disclosed");
  b += row("Last assessed", v.age_days + " days ago");
  b += row("Exit clause", v.exit_clause === "yes" ? "yes" + (v.exit_tested === "yes" ? ", tested" : ", never tested") : "none");
  b += '<span class="pill pill-info">a questionnaire and a vendor record</span>';
  b += '<div class="note">Modeled bank: one flat 24-month review cycle; documents on file are filed, not read against the answers.</div>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: the questionnaire
  let s = "";
  s += row("Answers", v.yes + " yes, " + v.partial + " partial, " + v.no + " no");
  s += row("Yes rate", (Math.round(1000 * v.yes / (v.yes + v.partial + v.no)) / 10).toFixed(1) + "% against " + DATA.s2.pass_rule_pct + "%");
  s += '<div class="reltitle">Verdict <span class="tag ' + (v.ck_pass ? "tag-ok" : "tag-bad") + '">' + (v.ck_pass ? "PASS" : "FAIL") + "</span></div>";
  s += row("Truth (synthetic)", v.truth.toUpperCase() + " risk");
  s += row("Answers over-claimed", String(v.overclaimed) + " of 20");
  DATA.doc_types.forEach(dt => { s += row(DOC[dt], EV[v.evidence[dt]]); });
  s += '<span class="pill ' + (v.q_fail ? "pill-bad" : "pill-ok") + '">' + esc(v.q_tag) + "</span>";
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: VendorLens
  let h = "";
  h += '<div class="reltitle">' + esc(v.id) + ' <span class="tag ' + classTag(v.vl_class) + '">' + esc(v.vl_class.toUpperCase()) + "</span></div>";
  h += row("Risk score", v.risk + " of 100");
  h += row("Control score", v.control_score + " of 100 (" + v.yes_unbacked + " yes with no valid document)");
  let conc;
  if (v.conc_flag) { conc = "FLAGGED: " + v.provider + " at " + DATA.s4.top_share_pct + "%"; }
  else if (!v.provider) { conc = "unknown: provider not disclosed"; }
  else { conc = v.provider + " at " + v.provider_share + "%, below 40%"; }
  h += row("Concentration", conc);
  h += row("Exit readiness", v.exit_state + " (" + v.exit_score + " of 100)");
  h += row("Modeled exit", v.modeled_exit + " days vs " + v.allowed_exit + " allowed");
  h += row("Review cadence", "every " + monthsOf(v.cadence_days) + " months; " + (v.overdue ? "overdue by " + v.days_overdue + " days" : "next due " + v.next_review));
  v.reasons.forEach(r => {
    h += '<div class="fieldrow"><span class="fieldname">' + esc(PART[r[0]]) + '</span><div class="fieldvals">' + esc(r[1]) + "</div></div>";
  });
  h += '<span class="pill ' + (v.vl_tag === "CAUGHT" ? "pill-ok" : (v.vl_tag === "MISSED" ? "pill-bad" : (v.vl_tag === "FLAGGED" ? "pill-warn" : "pill-info"))) + '">' + esc(v.vl_tag) + "</span>";
  if (v.vl_tag === "MISSED") {
    h += '<div class="note"><b>Ground truth (synthetic):</b> truly high risk. Known limit: the generator gave it a risk factor no answer, document or contract reveals, and evidence authenticity is not verified.</div>';
  } else if (v.vl_tag === "FLAGGED") {
    h += '<div class="note"><b>Ground truth (synthetic):</b> ' + esc(v.truth) + " risk. A false alarm that a person clears in review.</div>";
  } else {
    h += '<div class="note"><b>Ground truth (synthetic):</b> ' + esc(v.truth) + " risk.</div>";
  }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < V.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = START; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= V.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s1, s2, s4 = p["s1"], p["s2"], p["s4"]
    n = len(p["vendors"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    rate_vl, rate_q = s4["found_rate_vendorlens"], s4["found_rate_checklist"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VendorLens — AI Vendor Due Diligence · Vijay Saharan</title>
<meta name="description" content="A clickable demo of VendorLens: AI vendor due diligence scored on evidence, upstream concentration and exit readiness instead of a questionnaire. Synthetic data, no model.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="VendorLens — AI Vendor Due Diligence">
<meta property="og:description" content="Scores AI vendors on evidence, upstream-provider concentration and exit readiness instead of a self-filled questionnaire.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/18-vendorlens-ai-vendor-due-diligence/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="VendorLens — AI Vendor Due Diligence">
<meta name="twitter:description" content="Scores AI vendors on evidence, upstream-provider concentration and exit readiness instead of a self-filled questionnaire.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/18-vendorlens-ai-vendor-due-diligence/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>VendorLens — AI Vendor Due Diligence</h1>
    <p class="tagline">Pick a vendor and see the questionnaire verdict, the truth, and the VendorLens score side by side.</p>
    <p class="author">Project 18 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{n} vendors · {s1['questions']} questions · {s1['documents']} documents</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected vendor">
    <div class="stat"><p class="stat-label">Truly high-risk vendors seen</p><p class="stat-value" id="stat-seen">—</p></div>
    <div class="stat"><p class="stat-label">Found by the questionnaire (fail)</p><p class="stat-value" id="stat-qfound">—</p></div>
    <div class="stat"><p class="stat-label">Found by VendorLens (HIGH)</p><p class="stat-value" id="stat-vfound">—</p></div>
    <div class="stat"><p class="stat-label">High risk, passed the questionnaire</p><p class="stat-value" id="stat-passed">—</p></div>
  </section>

  <div class="controls">
    <label for="vendor-select">Vendor</label>
    <select id="vendor-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next vendor</button>
    <button id="runall-btn">Replay all {n} vendors</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — On file today</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Questionnaire</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With VendorLens</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. Vendor ids and model providers are invented codes, and the generator decided every vendor's true risk. No model is used: the scoring is plain rules. Weights, the HIGH line and the 40% concentration line are my assumptions. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (high-risk vendors found per vendor with VendorLens − with the questionnaire) × vendors in a bank's AI estate</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> the questionnaire passes {s2['passes']} of {n} vendors, including {s2['pass_high']} of the {s2['true_high']} that are truly high risk. A failed questionnaire finds {s4['checklist_found']} of {s4['true_high']} ({s4['checklist_found']} of {s4['checklist_fail']} fails, precision {s4['checklist_precision_pct']}%). VendorLens rates {s4['pred_high']} vendors HIGH and {s4['high_tp']} are truly high risk (precision {s4['high_precision_pct']}%, recall {s4['high_recall_pct']}%). At the same queue size of {s4['queue_size']}, {s4['topk_found']} of {s4['true_high']} are in VendorLens's top {s4['queue_size']}. {s4['top_provider']} carries {s4['top_share_pct']}% of critical use cases; the truth is {s4['true_top_share_pct']}% because {s4['unknown_vendors']} vendors do not disclose their provider.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s4['estate_vendors']} vendors in a bank's AI estate (an assumption, not a statistic) gives ({rate_vl:.3f} − {rate_q:.3f}) × {s4['estate_vendors']} = <b>{s4['utility_vendors']} more high-risk vendors found</b>. {n} vendors is a small test set: one vendor moves a rate by {100 / n:.1f} points.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/vendorlens-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['vendors'])} vendors, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
