"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline. Every dynamic value is escaped
in the page before it is written into the DOM.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_rag_status_report import summarize as summarize_step1, usd_m
from step_02_rag_attention_list import summarize as summarize_step2
from step_03_deficiencies_exposed import summarize as summarize_step3
from step_04_with_portfolioboard import analyze

ROOT = Path(__file__).parent.parent
FOLDER = "24-portfolioboard-ai-program-portfolio"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"
BAD = {"GREEN": 0, "AMBER": 1, "RED": 2}


def build_payload() -> dict:
    a = analyze()
    data, s = a["data"], a["summary"]
    truth, crit, prog = data["truth"], data["crit"], data["prog"]
    rows = {r["program_id"]: r for r in a["rows"]}
    s1, s2, s3 = summarize_step1(data), summarize_step2(data), summarize_step3(data)
    ordered = sorted(a["rows"], key=lambda r: (-(BAD[r["board"]] - BAD[r["reported"]]), -r["est_benefit_usd"], r["program_id"]))
    programs = []
    for r in ordered:
        pid = r["program_id"]
        t = truth[pid]
        ev = data["ev_by_prog"][pid]
        unmet = [{"name": crit[e["criterion_id"]]["criterion"], "by": crit[e["criterion_id"]]["attested_by"]}
                 for e in ev if not e["met"]]
        stale = [{"name": crit[e["criterion_id"]]["criterion"], "age": e["age"], "max": crit[e["criterion_id"]]["max_age_days"]}
                 for e in ev if e["met"] and e["age"] > crit[e["criterion_id"]]["max_age_days"]]
        ups = [{"id": u, "name": prog[u]["name"], "board": rows[u]["board"], "slipped": rows[u]["slipped"]}
               for u in data["ups"].get(pid, [])]
        on_list = r["reported"] != "GREEN"
        needs = t["true_status"] != "GREEN"
        verdict = ("caught" if on_list and needs else "missed" if (not on_list and needs)
                   else "false alarm" if on_list else "correctly quiet")
        fa = t["false_attestation"]
        programs.append({
            "id": pid, "name": r["name"], "stage": r["stage"], "owner": r["owner"], "reported": r["reported"],
            "board": r["board"], "evidence": r["evidence_status"], "true": t["true_status"],
            "benefit": r["est_benefit_usd"], "benefit_m": usd_m(r["est_benefit_usd"]), "confidence": r["benefit_confidence"],
            "target": r["target_quarter"], "slipped": r["slipped"], "on_list": on_list, "verdict": verdict,
            "criteria": len(ev), "unmet": unmet, "stale": stale, "ups": ups,
            "blocked_by": [{"id": i["program_id"], "why": i["why"], "direct": i["direct"]} for i in r["blocked_by"]],
            "reason": r["reason"], "action": r["action"], "action_reason": r["action_reason"],
            "short": [{"team": x["team"].replace("_", " "), "need": f"{x['need']:.2f}", "ratio": x["ratio_pct"], "pro_rata": f"{x['pro_rata']:.2f}"}
                      for x in r["short_teams"]],
            "later": r["deferred_later"], "blocks": r["blocks"],
            "false_attestation": crit[fa]["criterion"] if fa else "",
            "changed": r["board"] != r["reported"], "green_contradicted": r["reported"] == "GREEN" and r["board"] != "GREEN",
            "at_risk": r["evidence_status"] == "RED", "missed": r["board"] != t["true_status"],
        })
    return {"programs": programs, "s": s, "s1": s1, "s2": s2, "s3": s3, "plan_quarter": s["plan_quarter"]}


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
const PROGS = D.programs;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
function usd(x) { return "$" + (Math.floor((x + 5000) / 10000) / 100).toFixed(2) + "M"; }

let idx = 0;
const sel = document.getElementById("prog-select");
PROGS.forEach((p, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = p.id + " " + p.name + " - reported " + p.reported.toLowerCase() + " - board " + p.board;
  sel.appendChild(o);
});

function totals(upTo) {
  let changed = 0, contradicted = 0, atRisk = 0, missed = 0;
  for (let i = 0; i <= upTo; i++) {
    const p = PROGS[i];
    if (p.changed) changed++;
    if (p.green_contradicted) contradicted++;
    if (p.at_risk) atRisk += p.benefit;
    if (p.missed) missed++;
  }
  return { changed, contradicted, atRisk, missed };
}

function statusPill(s) { return s === "RED" ? "pill-bad" : (s === "AMBER" ? "pill-warn" : "pill-ok"); }
function statusTag(s) { return s === "RED" ? "tag-bad" : (s === "AMBER" ? "tag-warn" : "tag-ok"); }
function actionPill(a) { return a === "PAUSE" ? "pill-bad" : (a === "DEFER" ? "pill-warn" : "pill-ok"); }

function render() {
  const p = PROGS[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-changed").textContent = String(tt.changed);
  document.getElementById("stat-contradicted").textContent = String(tt.contradicted);
  document.getElementById("stat-risk").textContent = usd(tt.atRisk);
  document.getElementById("stat-missed").textContent = String(tt.missed);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(p.id) + " " + esc(p.name) + "</b> - stage " + esc(p.stage) + ", owner " + esc(p.owner) + ", " +
    esc(plural(p.criteria, "gate criterion")) + " in force. Program " + esc(idx + 1) + " of " + esc(PROGS.length) + ".";

  // Card 1: the report as sent
  let b = "";
  b += "<p>Owner <b>" + esc(p.owner) + "</b> reports <b>" + esc(p.reported) + "</b>.</p>";
  b += '<div class="driver-row"><span class="driver-label">Owner-estimated benefit</span><span class="driver-value">' + esc(p.benefit_m) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Owner confidence</span><span class="driver-value">' + esc(p.confidence) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Target quarter</span><span class="driver-value">' + esc(p.target) + "</span></div>";
  let stamp, stampCls;
  if (p.reported === "GREEN" && p.true !== "GREEN") { stamp = "MISSED: reported green"; stampCls = "pill-bad"; }
  else if (p.reported !== p.true) { stamp = "WRONG: reported " + p.reported.toLowerCase(); stampCls = "pill-bad"; }
  else { stamp = "matches, nothing behind it"; stampCls = "pill-info"; }
  b += '<span class="pill ' + stampCls + '">' + esc(stamp) + "</span>";
  b += '<div class="fieldvals" style="font-size:12px;margin-top:8px;">The report carries no gate evidence, capacity, dependencies or work in progress.</div>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: attention list, and the evidence it cannot see
  let s = "";
  s += '<div class="driver-row"><span class="driver-label">On the attention list (amber or red)</span><span class="driver-value">' + (p.on_list ? "yes" : "no") + "</span></div>";
  s += '<div class="driver-row"><span class="driver-label">True status (generator)</span><span class="driver-value">' + esc(p.true) + "</span></div>";
  const vcls = p.verdict === "caught" || p.verdict === "correctly quiet" ? "pill-ok" : (p.verdict === "missed" ? "pill-bad" : "pill-warn");
  s += '<span class="pill ' + vcls + '">attention list: ' + esc(p.verdict) + "</span>";
  s += '<div class="reltitle" style="margin-top:12px;">Gate evidence behind it</div>';
  if (!p.unmet.length && !p.stale.length) {
    s += '<div class="fieldvals">All ' + esc(p.criteria) + " criteria met with fresh evidence.</div>";
  }
  p.unmet.forEach(u => {
    s += '<div class="fieldrow"><span class="fieldname">' + esc(u.name) + '</span><span class="tag tag-bad">not met</span><div class="fieldvals">attested by ' + esc(u.by) + "</div></div>";
  });
  p.stale.forEach(u => {
    s += '<div class="fieldrow"><span class="fieldname">' + esc(u.name) + '</span><span class="tag tag-warn">stale</span><div class="fieldvals">' + esc(u.age) + " days old against " + esc(u.max) + "</div></div>";
  });
  if (p.slipped) {
    s += '<div class="fieldrow"><span class="fieldname">Target ' + esc(p.target) + '</span><span class="tag tag-warn">slipped</span></div>';
  }
  p.ups.forEach(u => {
    s += '<div class="fieldrow"><span class="fieldname">Depends on ' + esc(u.id) + '</span><span class="tag ' + statusTag(u.board) + '">' + esc(u.board.toLowerCase()) + (u.slipped ? ", slipped" : "") + '</span><div class="fieldvals">' + esc(u.name) + "</div></div>";
  });
  if (p.false_attestation) {
    s += '<div class="fieldvals" style="font-size:12px;margin-top:8px;"><b>Ground truth (synthetic):</b> the generator planted a false attestation: ' + esc(p.false_attestation) + " is marked met with fresh evidence and is not truly met.</div>";
  }
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: PortfolioBoard
  let h = "";
  const word = p.board !== p.reported ? "FLAGGED " + p.board : "CONFIRMED " + p.board;
  h += '<div class="reltitle">' + esc(word) + ' <span class="tag ' + statusTag(p.board) + '">' + esc(p.board) + "</span></div>";
  h += '<div class="fieldvals" style="font-size:12px;margin-bottom:6px;">' + esc(p.reason) + "</div>";
  if (p.blocked_by.length) {
    h += '<div class="driver-row"><span class="driver-label">Blocked by</span><span class="driver-value">' + esc(p.blocked_by.map(x => x.id + " (" + x.why + (x.direct ? "" : ", chain") + ")").join(", ")) + "</span></div>";
  }
  if (p.blocks) {
    h += '<div class="driver-row"><span class="driver-label">Blocks</span><span class="driver-value">' + esc(plural(p.blocks, "program")) + "</span></div>";
  }
  p.short.forEach(x => {
    h += '<div class="fieldrow"><span class="fieldname">' + esc(x.team) + '</span><span class="tag tag-warn">' + esc(x.ratio) + "% subscribed before pauses</span>" +
         '<div class="fieldvals">' + esc(D.plan_quarter) + ": needs " + esc(x.need) + " FTE, pro-rata share " + esc(x.pro_rata) + "</div></div>";
  });
  h += '<span class="pill ' + actionPill(p.action) + '">' + esc(p.action) + " in " + esc(D.plan_quarter) + "</span>";
  h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">' + esc(p.action_reason) + ".</div>";
  if (p.at_risk) {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Benefit at risk (modeled):</b> ' + esc(p.benefit_m) + " of owner-estimated benefit.</div>";
  }
  if (p.missed) {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Known limit:</b> the board shows ' + esc(p.board) + " and the true status is " + esc(p.true) + ". The board reads attested evidence and cannot see a false attestation.</div>";
  }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < PROGS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= PROGS.length) clearInterval(iv); }, 600);
});

render();
"""


def build_html(p: dict) -> str:
    s, s1, s3 = p["s"], p["s1"], p["s3"]
    n = len(p["programs"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PortfolioBoard — AI Program Portfolio · Vijay Saharan</title>
<meta name="description" content="A clickable demo of PortfolioBoard: an AI program portfolio run on gate evidence, capacity and dependencies instead of owner-picked red-amber-green. Synthetic data.">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>PortfolioBoard — AI Program Portfolio</h1>
    <p class="tagline">Pick a program and compare the owner's color with the gate evidence, the capacity and the dependencies behind it.</p>
    <p class="author">Project 24 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{n} programs · {s1['criteria']} gate criteria · 4 teams</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected program">
    <div class="stat"><p class="stat-label">Statuses that change</p><p class="stat-value" id="stat-changed">—</p></div>
    <div class="stat"><p class="stat-label">Green reports contradicted</p><p class="stat-value" id="stat-contradicted">—</p></div>
    <div class="stat"><p class="stat-label">Benefit at risk (modeled)</p><p class="stat-value" id="stat-risk">—</p></div>
    <div class="stat"><p class="stat-label">Missed by the board (known limit)</p><p class="stat-value" id="stat-missed">—</p></div>
  </section>

  <div class="controls">
    <label for="prog-select">Program</label>
    <select id="prog-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next program</button>
    <button id="runall-btn">Walk all {n} programs</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — The monthly report</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Attention list, and the evidence</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With PortfolioBoard</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The generator decided which evidence is missing, stale or false, so the truth is known. No model is used: status, capacity, dependency and pause rules are plain rules. Benefit figures are owner estimates, never measured. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (programs shown with the true status: PortfolioBoard − report) ÷ programs × people affected</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> {s['changed']} of {s['programs']} programs change status once evidence is applied. The report shows the true status for {s['rag_correct']} of {s['programs']} programs; PortfolioBoard for {s['board_correct']} of {s['programs']}. {s3['a_green_fail']} of {s3['green_reported']} programs reported green fail a gate criterion, model risk review is short in {s['mr_over_before']} of {s['mr_quarters']} quarters, and {s['planted_false_attestations']} false attestations stay invisible to the board.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['owners']} distinct owners plus {s['sponsors_modeled']} sponsors (an assumption of one sponsor per {s['programs_per_sponsor']} programs) gives {s['people']} people. ({s['board_correct']} − {s['rag_correct']}) ÷ {s['programs']} × {s['people']} = <b>{s['utility_people']} owners and sponsors</b> who see a true status for their program. Assumes the board's statuses are read and acted on.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/portfolioboard-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['programs'])} programs, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
