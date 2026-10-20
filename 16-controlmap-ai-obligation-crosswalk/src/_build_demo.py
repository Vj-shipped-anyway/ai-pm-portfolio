"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_04_with_controlmap import analyze, explain, picker_order

ROOT = Path(__file__).parent.parent
FOLDER = "16-controlmap-ai-obligation-crosswalk"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    data, s = a["data"], a["summary"]
    by_theme = {}
    for o in data["obligations"]:
        by_theme.setdefault(o["theme"], []).append(o)
    items = []
    for r in picker_order(a["rows"]):
        e = explain(a, r["obligation_id"])
        e["same"] = [{"id": o["obligation_id"], "short": r2["short"]}
                     for o in by_theme[r["theme"]] for r2 in a["rows"] if r2["obligation_id"] == o["obligation_id"]]
        e["sheet_ok"], e["cm_ok"] = bool(r["sheet_ok"]), bool(r["ok"])
        e["sheet_marked"] = r["sheet_status"] == "COVERED"
        items.append(e)
    return {"items": items, "s": s}


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
const ITEMS = D.items;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }

let idx = 0;
const sel = document.getElementById("ob-select");
ITEMS.forEach((t, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = t.oid + " - " + t.short + " - " + t.theme + " - " + t.cm.status;
  sel.appendChild(o);
});

function totals(upTo) {
  let sheetOk = 0, cmOk = 0, sheetWrong = 0, cmWrong = 0;
  for (let i = 0; i <= upTo; i++) {
    const t = ITEMS[i];
    if (t.sheet_ok) sheetOk++;
    if (t.cm_ok) cmOk++;
    if (t.sheet_marked && !t.sheet_ok) sheetWrong++;
    if (!t.cm_ok) cmWrong++;
  }
  return { sheetOk, cmOk, sheetWrong, cmWrong };
}

function statusClass(s) { return s === "COVERED" ? "pill-ok" : (s === "UNCOVERED" ? "pill-bad" : "pill-warn"); }
function statusTag(s) { return s === "COVERED" ? "tag-ok" : (s === "UNCOVERED" ? "tag-bad" : "tag-warn"); }

function render() {
  const t = ITEMS[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-sheet").textContent = String(tt.sheetOk);
  document.getElementById("stat-cm").textContent = String(tt.cmOk);
  document.getElementById("stat-sheetwrong").textContent = String(tt.sheetWrong);
  document.getElementById("stat-cmwrong").textContent = String(tt.cmWrong);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(t.oid) + "</b> - " + esc(t.short) + ", theme <b>" + esc(t.theme) + "</b>, applies to " + esc(t.applies_to) +
    ". Obligation " + esc(idx + 1) + " of " + esc(ITEMS.length) + '.<br><span class="mono" style="font-size:12px;">' + esc(t.statement) + "</span>";

  // Card 1: before
  let b = "<p>On the <b>" + esc(t.short) + "</b> list, " + esc(t.oid) + " is one row with its own evidence request.</p>";
  if (t.same.length > 1) {
    b += "<p>The same theme is on " + esc(plural(t.same.length, "row")) + ": " + t.same.map(x => esc(x.id) + " (" + esc(x.short) + ")").join(", ") +
         ". Each list asks the control owners for its own evidence.</p>";
  } else {
    b += "<p>No other list carries this theme.</p>";
  }
  b += '<div class="driver-row"><span class="driver-label">Control, scope, evidence date</span><span class="driver-value">not on the list</span></div>';
  b += '<span class="pill pill-info">' + (t.same.length > 1 ? "asked " + esc(t.same.length) + " times" : "asked once") + "</span>";
  document.getElementById("card-before").innerHTML = b;

  // Card 2: keyword sheet
  const sh = t.sheet;
  let s = '<div class="driver-row"><span class="driver-label">Sheet says</span><span class="driver-value">' + esc(sh.status) + "</span></div>";
  sh.items.forEach(it => {
    s += '<div class="fieldrow"><span class="fieldname">' + esc(it.id) + "</span>" +
         '<span class="tag ' + (it.is_true ? "tag-ok" : "tag-bad") + '">' + (it.is_true ? "Meets it" : "Does not meet it") + "</span>" +
         '<div class="fieldvals">' + esc(it.name) + " - shares " + it.shared.map(w => "\\u201c" + esc(w) + "\\u201d").join(", ") + "</div></div>";
  });
  if (sh.n_more) { s += '<div class="fieldvals" style="font-size:12px;">and ' + esc(sh.n_more) + " more control" + (sh.n_more === 1 ? "" : "s") + " linked the same way.</div>"; }
  if (!sh.items.length) { s += "<p>No control shares two words with this obligation.</p>"; }
  s += '<span class="pill ' + (sh.tag === "RIGHT" ? "pill-ok" : "pill-bad") + '">' + esc(sh.tag) + "</span>";
  s += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">' + esc(sh.why.charAt(0).toUpperCase() + sh.why.slice(1)) + ".</div>";
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: ControlMap
  const cm = t.cm;
  let h = '<div class="reltitle">' + esc(t.oid) + ' <span class="tag ' + statusTag(cm.status) + '">' + esc(cm.status) + "</span></div>";
  cm.items.forEach(it => {
    h += '<div class="fieldrow"><span class="tag ' + (it.coverage === "full" ? "tag-ok" : "tag-warn") + '" style="margin-left:0;margin-right:6px;">' + esc(it.coverage) + "</span>" +
         '<span class="fieldvals">' + esc(it.text) + "</span></div>";
  });
  if (!cm.items.length) { h += "<p>No active control contains a phrase from this theme's dictionary group.</p>"; }
  h += '<div class="driver-row"><span class="driver-label">Truth (synthetic)</span><span class="driver-value">' + esc(t.truth.status) + "</span></div>";
  h += '<span class="pill ' + (cm.ok ? "pill-ok" : "pill-warn") + '">' + esc(cm.tag) + "</span>";
  h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">' + esc(t.truth.why.charAt(0).toUpperCase() + t.truth.why.slice(1)) + ".</div>";
  if (cm.note) { h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Known limit:</b> ' + esc(cm.note) + "</div>"; }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < ITEMS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= ITEMS.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s = p["s"]
    n = len(p["items"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ControlMap — AI Obligation to Control Crosswalk · Vijay Saharan</title>
<meta name="description" content="A clickable demo of ControlMap: it maps AI obligations to controls and fresh evidence with a theme dictionary, a scope check and an evidence-freshness check, and compares that with a keyword spreadsheet. Synthetic data.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="ControlMap — AI Obligation to Control Crosswalk">
<meta property="og:description" content="Maps AI obligations from four frameworks to controls and evidence, and shows which are uncovered, stale or serve nothing.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/16-controlmap-ai-obligation-crosswalk/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ControlMap — AI Obligation to Control Crosswalk">
<meta name="twitter:description" content="Maps AI obligations from four frameworks to controls and evidence, and shows which are uncovered, stale or serve nothing.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/16-controlmap-ai-obligation-crosswalk/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>ControlMap — AI Obligation to Control Crosswalk</h1>
    <p class="tagline">Pick an obligation and compare a keyword spreadsheet with ControlMap on the same synthetic controls and evidence.</p>
    <p class="author">Project 16 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{s['obligations']} obligations · {s['controls']} controls · 4 frameworks</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected obligation">
    <div class="stat"><p class="stat-label">Right status: keyword sheet</p><p class="stat-value" id="stat-sheet">—</p></div>
    <div class="stat"><p class="stat-label">Right status: ControlMap</p><p class="stat-value" id="stat-cm">—</p></div>
    <div class="stat"><p class="stat-label">Sheet marks covered, wrongly</p><p class="stat-value" id="stat-sheetwrong">—</p></div>
    <div class="stat"><p class="stat-label">ControlMap wrong (known limit)</p><p class="stat-value" id="stat-cmwrong">—</p></div>
  </section>

  <div class="controls">
    <label for="ob-select">Obligation</label>
    <select id="ob-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next obligation</button>
    <button id="runall-btn">Replay all {n} obligations</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — One list per framework</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Keyword spreadsheet</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With ControlMap</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. Obligation statements are paraphrases written for this exercise, not the text of any rule. The generator decided which control meets which obligation, so the truth is known. No model is used. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (right-status rate with ControlMap − with the keyword sheet) × obligation entries tracked</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> the keyword sheet gives the right status to {s['sheet_ok']} of {s['obligations']} obligations; ControlMap to {s['cm_ok']} of {s['obligations']}. Pair precision is {s['precision_pct']}% and recall {s['recall_pct']}% against the truth map. ControlMap lists {s['orphans_found']} of the {s['true_orphans']} orphan controls and sends {s['requests_theme']} evidence requests instead of {s['requests_framework']}. The dictionary was written by the author of the data, so these scores are an upper bound.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['business_lines']} business lines each track their own copy of the {s['obligations']}-obligation list (an assumption, not a statistic), so {s['tracked_entries']} entries. ({s['cm_ok']}/{s['obligations']} − {s['sheet_ok']}/{s['obligations']}) × {s['tracked_entries']} = <b>{s['utility_entries']} obligation entries</b> given the right status. Assumes the copies behave like this set.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/controlmap-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['items'])} obligations, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
