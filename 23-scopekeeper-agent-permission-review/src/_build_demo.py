"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_status_quo import summarize as summarize_step1
from step_04_with_scopekeeper import analyze

ROOT = Path(__file__).parent.parent
FOLDER = "23-scopekeeper-agent-permission-review"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    data, s = a["data"], a["summary"]
    s1 = summarize_step1(data)
    d = a["deficiencies"]
    cat = data["catalog"]
    unneeded = a["unneeded"]
    rows = []
    for ag in sorted(a["agents"], key=lambda r: r["rank"]):
        aid = ag["agent_id"]
        prop = [r for r in a["proposal"] if r["agent_id"] == aid]
        rec = {r["scope"]: r for r in a["recert"]["rows"] if r["agent_id"] == aid}
        approved = sum(1 for r in prop if rec[r["scope"]]["verdict"] == "approved")
        hi = [{"scope": r["scope"], "ticket": r["ticket_id"]} for r in prop
              if r["needs_approval"] and rec[r["scope"]]["verdict"] == "approved"]
        rare = [{"scope": r["scope"], "why": r["why"], "last": r["last_use_date"], "next": r["next_use_date"],
                 "calls": r["calls_next_quarter"], "removed": r["removed"]}
                for r in a["rare"] if r["agent_id"] == aid]
        actions = [{"scope": r["scope"], "action": r["action"], "after": r["after"], "reason": r["reason"],
                    "impact": r["impact"]} for r in prop if r["action"] != "keep"]
        wild = [{"scope": r["scope"], "reach": r["reach"],
                 "called": 0 if r["action"] == "remove" else len(r["after"])} for r in prop if r["wildcard"]]
        rows.append({
            "id": aid, "purpose": ag["purpose"], "owner": ag["owner"], "tier": ag["tier"],
            "account": ag["service_account"], "shared": ag["shared"], "siblings": ag["siblings"],
            "launched": ag["launched_on"], "rank": ag["rank"], "points": ag["risk_points"],
            "grants": ag["grants"], "reach": ag["reach"], "proposed": ag["proposed"], "cut": ag["cut"],
            "breadth": ag["breadth_pct"], "keep": ag["keep"], "remove": ag["remove"], "narrow": ag["narrow"],
            "calls": ag["calls"], "unapproved": ag["unapproved_tagged"],
            "high_impact": sum(1 for r in prop if r["needs_approval"]), "wildcards": len(wild),
            "post_launch": sum(1 for r in prop if r["post_launch"]),
            "approved": approved, "approved_pct": round(100 * approved / len(prop), 1),
            "recert_removed": [{"scope": r["scope"], "used": r["used"]} for r in prop
                               if rec[r["scope"]]["verdict"] == "removed"],
            "high_impact_approved": hi[:4], "high_impact_approved_n": len(hi),
            "unused": [{"scope": x, "impact": cat[x]["impact"]} for x in ag["unused_scopes"]],
            "proposed_scopes": ag["proposed_scopes"], "actions": actions, "wild": wild, "rare": rare,
            "unused_grants": sum(1 for r in prop if not r["used"]),
            "removed_unneeded": sum(1 for r in prop if r["action"] == "remove" and (aid, r["scope"]) in unneeded),
            "kept_unneeded": [r["scope"] for r in a["kept_unneeded"] if r["agent_id"] == aid],
            "next_q_denied": sum(r["calls"] for r in rare if r["removed"]),
        })
    return {"agents": rows, "s": s, "s1": s1, "d": {k: v for k, v in d.items() if k != "grants"}}


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
const AGENTS = D.agents;
const IMPACT = {read: "reads data", write: "changes data", external_message: "sends a message", money_movement: "moves money"};

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }

let idx = 0;
const sel = document.getElementById("agent-select");
AGENTS.forEach((t, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = String(t.rank) + ". " + t.id + " " + t.purpose + " - " + t.tier + " tier - " + String(t.cut) + " of " + String(t.reach) + " scopes unused";
  sel.appendChild(o);
});

function totals(upTo) {
  let approved = 0, unused = 0, removed = 0, denied = 0;
  for (let i = 0; i <= upTo; i++) {
    const t = AGENTS[i];
    approved += t.approved; unused += t.unused_grants; removed += t.removed_unneeded; denied += t.next_q_denied;
  }
  return { approved, unused, removed, denied };
}

function render() {
  const t = AGENTS[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-approved").textContent = String(tt.approved);
  document.getElementById("stat-unused").textContent = String(tt.unused);
  document.getElementById("stat-removed").textContent = String(tt.removed);
  document.getElementById("stat-denied").textContent = String(tt.denied);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(t.id) + "</b> - " + esc(t.purpose) + ". Owner " + esc(t.owner) + ", " + esc(t.tier) + " tier, launched " + esc(t.launched) +
    ". Service account " + esc(t.account) + (t.shared ? " (shared with " + esc(t.siblings.join(", ")) + ")" : " (its own)") +
    ". Risk rank <b>" + esc(t.rank) + "</b> of " + esc(AGENTS.length) + ".";

  // Card 1: before - grants and calls are never compared
  let b = "";
  b += "<p><b>" + esc(t.grants) + "</b> grants reach <b>" + esc(t.reach) + "</b> scopes. " + esc(t.high_impact) + " are high-impact, " +
       esc(t.wildcards) + " wildcard, " + esc(t.post_launch) + " added after launch.</p>";
  b += "<p>The call log shows <b>" + esc(t.proposed) + "</b> of " + esc(t.reach) + " scopes called in 90 days. <b>" + esc(t.cut) + "</b> never.</p>";
  t.unused.slice(0, 6).forEach(u => {
    b += '<div class="driver-row"><span class="driver-label">' + esc(u.scope) + '</span><span class="driver-value">' + esc(IMPACT[u.impact]) + "</span></div>";
  });
  if (t.unused.length > 6) {
    b += '<div class="driver-row"><span class="driver-label">and ' + esc(t.unused.length - 6) + ' more never called</span><span class="driver-value"></span></div>';
  }
  b += '<div class="driver-row"><span class="driver-label">Calls with this agent tag</span><span class="driver-value">' + esc(t.calls) + "</span></div>";
  if (t.unapproved) {
    b += '<div class="driver-row"><span class="driver-label">Calls with no human approval</span><span class="driver-value">' + esc(t.unapproved) + "</span></div>";
  }
  b += '<span class="pill ' + (t.cut ? "pill-bad" : "pill-ok") + '">' + (t.cut ? "grants and calls never compared" : "nothing unused") + "</span>";
  document.getElementById("card-before").innerHTML = b;

  // Card 2: basic approach - annual recertification
  let s = "";
  s += '<div class="reltitle">Annual recertification</div>';
  s += '<div class="driver-row"><span class="driver-label">Approved</span><span class="driver-value">' + esc(t.approved) + " of " + esc(t.grants) + " (" + esc(t.approved_pct.toFixed(1)) + "%)</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Removed</span><span class="driver-value">' + esc(t.recert_removed.length) + "</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Sees</span><span class="driver-value">ticket, grant date</span></div>';
  s += '<div class="driver-row"><span class="driver-label">Does not see</span><span class="driver-value">any call</span></div>';
  if (t.high_impact_approved_n) {
    s += '<div class="reltitle">High-impact grants approved (' + esc(t.high_impact_approved_n) + ")</div>";
    t.high_impact_approved.forEach(h => {
      s += '<div class="fieldrow"><span class="fieldname">' + esc(h.scope) + '</span><span class="tag tag-warn">approved</span><div class="fieldvals">' + esc(h.ticket || "no ticket") + "</div></div>";
    });
  }
  t.recert_removed.forEach(r => {
    s += '<div class="fieldrow"><span class="fieldname">' + esc(r.scope) + '</span><span class="tag ' + (r.used ? "tag-bad" : "tag-ok") + '">removed</span><div class="fieldvals">' +
         (r.used ? "no ticket reference, but the agent used it: calls would be denied" : "no ticket reference, and it was unused") + "</div></div>";
  });
  s += '<span class="pill ' + (t.recert_removed.length ? "pill-warn" : "pill-bad") + '">' +
       (t.recert_removed.length ? "removed by paperwork, not by use" : "approved 100%: nothing cut") + "</span>";
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: ScopeKeeper
  let h = "";
  h += '<div class="reltitle">' + esc(t.id) + ' <span class="tag ' + (t.cut ? "tag-ok" : "tag-warn") + '">' + (t.cut ? "CAUGHT" : "NOTHING TO CUT") + "</span></div>";
  t.actions.forEach(a => {
    h += '<div class="fieldrow"><span class="fieldname">' + esc(a.scope) + '</span><span class="tag ' + (a.action === "remove" ? "tag-bad" : "tag-warn") + '">' + esc(a.action) + "</span>" +
         '<div class="fieldvals">' + (a.action === "narrow" ? "replace by " + esc(a.after.join(", ")) + ": " : "") + esc(a.reason) + "</div></div>";
  });
  h += '<div class="driver-row"><span class="driver-label">Grants: keep / remove / narrow</span><span class="driver-value">' + esc(t.keep) + " / " + esc(t.remove) + " / " + esc(t.narrow) + "</span></div>";
  h += '<div class="driver-row"><span class="driver-label">Breadth score</span><span class="driver-value">' + esc(t.breadth.toFixed(1)) + "%</span></div>";
  h += '<div class="driver-row"><span class="driver-label">Proposed set</span><span class="driver-value">' + esc(t.proposed) + " scopes</span></div>";
  h += '<div class="fieldvals" style="font-size:12px;margin:4px 0 6px;">' + esc(t.proposed_scopes.join(", ")) + "</div>";
  h += '<div class="driver-row"><span class="driver-label">Replay of this agent&#39;s ' + esc(t.calls) + ' tagged calls</span><span class="driver-value">0 denied (by construction)</span></div>';
  t.rare.forEach(r => {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Known limit:</b> ' + esc(r.scope) + " is a quarterly scope (" + esc(r.why) + "), last used " + esc(r.last) + ". " +
         (r.removed ? "The log shows no use in 90 days, so it is removed. Next use " + esc(r.next) + ", " + esc(r.calls) + " calls, would be denied unless the owner marks it periodic."
                    : "It stays only because another agent on the shared account called the scope.") + "</div>";
  });
  if (t.kept_unneeded.length) {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Also kept:</b> ' + esc(t.kept_unneeded.join(", ")) + " stay because untagged calls on the shared account are credited to every agent that could have made them. Ground truth (synthetic): this agent does not need them.</div>";
  }
  h += '<span class="pill ' + (t.cut ? "pill-ok" : "pill-warn") + '">' + (t.cut ? "cut " + esc(t.cut) + " of " + esc(t.reach) : "nothing to cut") + "</span>";
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < AGENTS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= AGENTS.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s, s1 = p["s"], p["s1"]
    n = len(p["agents"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScopeKeeper — Agent Permission Review · Vijay Saharan</title>
<meta name="description" content="A clickable demo of ScopeKeeper: it compares what each AI agent is allowed to do with what it called in 90 days and proposes the smallest scope set. Synthetic data, no model.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="ScopeKeeper — Agent Permission Review">
<meta property="og:description" content="Compares an agent&#x27;s granted scopes with its real calls and proposes the smallest scope set that still works.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/23-scopekeeper-agent-permission-review/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="ScopeKeeper — Agent Permission Review">
<meta name="twitter:description" content="Compares an agent&#x27;s granted scopes with its real calls and proposes the smallest scope set that still works.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/23-scopekeeper-agent-permission-review/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>ScopeKeeper — Agent Permission Review</h1>
    <p class="tagline">Pick an agent and compare the annual review, the 90-day call log and the proposed scope set.</p>
    <p class="author">Project 23 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{n} agents · {s['grants']} grants · {s['calls']:,} calls</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals through the selected agent">
    <div class="stat"><p class="stat-label">Grants the review approved</p><p class="stat-value" id="stat-approved">—</p></div>
    <div class="stat"><p class="stat-label">Grants unused in 90 days</p><p class="stat-value" id="stat-unused">—</p></div>
    <div class="stat"><p class="stat-label">Unneeded grants removed</p><p class="stat-value" id="stat-removed">—</p></div>
    <div class="stat"><p class="stat-label">Legit calls denied next quarter (known limit)</p><p class="stat-value" id="stat-denied">—</p></div>
  </section>

  <div class="controls">
    <label for="agent-select">Agent</label>
    <select id="agent-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next agent</button>
    <button id="runall-btn">Replay all {n} agents</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Grants and calls never compared</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Annual recertification</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With ScopeKeeper</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The generator decided which grants each agent needs, so the truth is known. No model is used: the diff, proposal, replay and ranking are plain rules. Every number on this page comes from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (unneeded grants removed per agent with ScopeKeeper − with annual recertification) × agents in the estate</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> {s['unneeded_grants']} of {s['grants']} grants are not needed by the agent that holds them. The annual review removed {s['rec_removed_unneeded']} of them ({s['rec_removed_unneeded_pct']}%); ScopeKeeper removed {s['sk_removed_unneeded']} ({s['sk_removed_unneeded_pct']}%). That is {s['per_agent_sk']} against {s['per_agent_rec']} unneeded grants removed per agent. The dry-run replay of the 90 days denied {s['replay_denied']} of {s['replay_calls']:,} calls (by construction). The known limit: {s['rare_removed']} quarterly grants are removed too, and the next quarter would deny {s['next_q_denied']} legitimate calls until owners mark them periodic.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['agents_in_estate']} agents in a bank's estate (an assumption, not a statistic) gives ({s['per_agent_sk']} − {s['per_agent_rec']}) × {s['agents_in_estate']} = about <b>{s['utility_grants']} unneeded grants removed</b>, and about {s['utility_denied_calls']} legitimate calls denied next quarter until the periodic scopes are attested.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/scopekeeper-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['agents'])} agents, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
