"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_no_monitoring import simulate, summarize as summarize_step1
from step_02_hash_and_version_check import score_releases, summarize as summarize_step2
from step_03_deficiencies_exposed import summarize as summarize_step3
from step_04_with_schemawatch import analyze

ROOT = Path(__file__).parent.parent
FOLDER = "15-schemawatch-tool-schema-drift"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    data, truth, s = a["data"], a["data"]["truth"], a["summary"]
    s1, s2, s3 = summarize_step1(data), summarize_step2(data), summarize_step3(data)
    flags = {r["release_id"]: r for r in score_releases(data)}
    events = {e["release_id"]: e for e in simulate(data)}
    tools = []
    for tr in a["tool_rows"]:
        tool = tr["tool"]
        calls = data["calls_by_tool"].get(tool, [])
        by_id = {c["call_id"]: c for c in calls}
        rels = []
        for e in [x for x in a["evaluated"] if x["tool"] == tool]:
            fl, ev = flags[e["release_id"]], events.get(e["release_id"])
            examples = []
            for cid in e["newly_broken"][:2]:
                err = e["newly_broken_errors"][cid][0]
                kind, param, msg = err.split(":", 2)
                examples.append({"call_id": cid, "args": json.dumps(by_id[cid]["args"]),
                                 "violation": f"{kind.replace('_', ' ')} on {param}: {msg}"})
            rels.append({
                "id": e["release_id"], "rev": e["to_rev"], "before": e["declared_before"],
                "after": e["declared_after"], "bumped": e["bumped"],
                "ledger_class": fl["release_class"], "version_alert": fl["version_alert"],
                "findings": [{"kind": f["kind"], "param": f["param"], "cls": f["class"],
                              "reason": f["reason"].replace("`", ""), "at_risk": f["at_risk_calls"]} for f in e["findings"]],
                "would_break": len(e["newly_broken"]), "true_broken": e["true_newly_broken"],
                "at_risk": len(e["at_risk"]), "examples": examples,
                "decision": e["decision"], "reason": e["reason"].replace("`", ""), "should": e["should"],
                "event": ({"failed": ev["failed_calls"], "first_h": ev["first_failure_h"],
                           "alert_h": ev["alert_h"]} if ev else None),
            })
        ids = {c["call_id"] for c in calls}
        silent = sum(1 for cid in ids if truth[cid]["misread_unit"] or truth[cid]["misread_meaning"]
                     or truth[cid]["shifted_default"])
        unb_broken = sum(r["true_broken"] for r in rels if not r["bumped"])
        missed = len(ids & a["truth_silent"] - a["flagged_silent"])
        tools.append({"tool": tool, "calls": len(calls), "rank": tr["rank"], "decision": tr["decision"],
                      "would_break": tr["would_break"], "at_risk": tr["at_risk"],
                      "silent": silent, "unbumped_broken": unb_broken, "unflagged_silent": missed,
                      "releases": rels})
    return {"tools": tools, "s": s, "s1": s1, "s2": s2, "s3": s3}


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
  .framing { font-size: 12px; color: var(--text-tertiary); margin: 8px 0 0; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
"""

JS = """
const D = __PAYLOAD__;
const TOOLS = D.tools;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }

let idx = 0;
const sel = document.getElementById("tool-select");
TOOLS.forEach((t, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = String(t.rank) + ". " + t.tool + " - " + t.decision + " - " + String(t.would_break) + " calls break";
  sel.appendChild(o);
});

function totals(upTo) {
  let broken = 0, predicted = 0, unbumped = 0, unflagged = 0;
  for (let i = 0; i <= upTo; i++) {
    const t = TOOLS[i];
    t.releases.forEach(r => { broken += r.true_broken; predicted += r.would_break; if (!r.bumped) unbumped += r.true_broken; });
    unflagged += t.unflagged_silent;
  }
  return { broken, predicted, unbumped, unflagged };
}

function gateClass(d) { return d === "BLOCK" ? "pill-bad" : (d === "REVIEW" ? "pill-warn" : "pill-ok"); }
function clsTag(c) { return c === "breaking" ? "tag-bad" : (c === "behavior_risk" ? "tag-warn" : "tag-ok"); }

function render() {
  const t = TOOLS[idx];
  sel.value = idx;
  const tt = totals(idx);
  document.getElementById("stat-broken").textContent = String(tt.broken);
  document.getElementById("stat-predicted").textContent = String(tt.predicted);
  document.getElementById("stat-unbumped").textContent = String(tt.unbumped);
  document.getElementById("stat-unflagged").textContent = String(tt.unflagged);

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(t.tool) + "</b> - " + esc(plural(t.calls, "recorded call")) + ", " + esc(plural(t.releases.length, "schema release")) +
    " since v1. Blast-radius rank <b>" + esc(t.rank) + "</b> of " + esc(TOOLS.length) + ". Gate: <b>" + esc(t.decision) + "</b>.";

  // Card 1: before
  let b = "";
  if (!t.releases.length) {
    b += "<p>No schema change since v1. Nothing fails and nothing alerts.</p>";
  }
  t.releases.forEach(r => {
    if (r.event) {
      const alert = r.event.alert_h !== null
        ? "the " + D.s1.alarm_failures + "th failure arrives " + r.event.alert_h + " h after release"
        : "only " + r.event.failed + " calls fail in the week, so the error alarm never fires";
      b += "<p><b>" + esc(r.rev) + ":</b> " + esc(r.event.failed) + " calls fail, the first after " + esc(r.event.first_h) + " h; " + esc(alert) + ".</p>";
    } else {
      b += "<p><b>" + esc(r.rev) + ":</b> no recorded call fails.</p>";
    }
  });
  b += '<div class="driver-row"><span class="driver-label">Calls that mean something else</span><span class="driver-value">' + esc(t.silent) + "</span></div>";
  b += '<span class="pill ' + (t.would_break || t.silent ? "pill-bad" : "pill-ok") + '">' +
       (t.would_break ? "found when calls fail" : (t.silent ? "never fails, never alerts" : "nothing to find")) + "</span>";
  b += '<div class="meta" style="font-size:12px;color:#8a8a8a;margin-top:8px;">Modeled: traffic repeats the recorded week; alert on the ' + esc(D.s1.alarm_failures) + 'th failed call; delivery instant (a floor).</div>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: basic approach
  let s = "";
  if (!t.releases.length) { s += "<p>Nothing changed, so neither check fires.</p>"; }
  t.releases.forEach(r => {
    s += '<div class="reltitle">' + esc(r.id) + "</div>";
    s += '<div class="driver-row"><span class="driver-label">Version check</span><span class="driver-value">' +
         (r.version_alert ? esc(r.before) + " to " + esc(r.after) + ": alert" : "unchanged " + esc(r.after) + ": no alert") + "</span></div>";
    s += '<div class="driver-row"><span class="driver-label">Content hash</span><span class="driver-value">alert</span></div>';
    s += '<div class="driver-row"><span class="driver-label">Ledger says</span><span class="driver-value">' + esc(r.ledger_class.replace("_", " ")) + "</span></div>";
    if (r.ledger_class === "noise_only") {
      s += '<span class="pill pill-warn">false alarm: nothing to do</span>';
    } else if (!r.version_alert) {
      s += '<span class="pill pill-bad">version check silent, ' + esc(r.true_broken) + ' calls break</span>';
    } else {
      s += '<span class="pill pill-info">alert, no ranking, no call count</span>';
    }
  });
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: SchemaWatch
  let h = "";
  if (!t.releases.length) { h += "<p>No release since v1. Gate: ALLOW.</p>"; }
  t.releases.forEach(r => {
    h += '<div class="reltitle">' + esc(r.id) + ' <span class="tag ' + (r.decision === "BLOCK" ? "tag-bad" : (r.decision === "REVIEW" ? "tag-warn" : "tag-ok")) + '">' + esc(r.decision) + "</span></div>";
    r.findings.forEach(f => {
      h += '<div class="fieldrow"><span class="fieldname">' + esc(f.kind.replace(/_/g, " ")) + (f.param ? " " + esc(f.param) : "") + '</span><span class="tag ' + clsTag(f.cls) + '">' + esc(f.cls.replace("_", " ")) + '</span>' +
           '<div class="fieldvals">' + esc(f.reason) + "</div></div>";
    });
    h += '<div class="driver-row"><span class="driver-label">Replay: would break</span><span class="driver-value">' + esc(r.would_break) + " of " + esc(t.calls) + "</span></div>";
    h += '<div class="driver-row"><span class="driver-label">Valid but changed meaning</span><span class="driver-value">' + esc(r.at_risk) + "</span></div>";
    r.examples.forEach(x => {
      h += '<div class="fieldrow"><span class="fieldname">' + esc(x.call_id) + '</span><span class="tag tag-bad">breaks</span><div class="fieldvals mono">' + esc(x.args) + "<br>" + esc(x.violation) + "</div></div>";
    });
    h += '<span class="pill ' + gateClass(r.decision) + '">' + esc(r.decision) + "</span>";
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">' + esc(r.reason) + "</div>";
    if (r.decision !== r.should) {
      h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Ground truth (synthetic):</b> ' +
           (r.decision === "ALLOW" ? "this release changes meaning with no number or unit, so the heuristic cannot see it. Known limit." :
                                     "this release is cosmetic; a number written as a word reads as a changed number. A person clears it.") + "</div>";
    }
  });
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < TOOLS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= TOOLS.length) clearInterval(iv); }, 700);
});

render();
"""


def build_html(p: dict) -> str:
    s, s1 = p["s"], p["s1"]
    n_tools = len(p["tools"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SchemaWatch — Tool-Schema Drift Detection · Vijay Saharan</title>
<meta name="description" content="A clickable demo of SchemaWatch: tool-schema drift detection for tool-calling agents. It diffs each schema release, replays recorded calls, ranks the blast radius and gates the release. Synthetic data.">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>SchemaWatch — Tool-Schema Drift Detection</h1>
    <p class="tagline">Pick a tool. See what happens to the same recorded calls three ways: with nothing watching, with a version or hash check, and with SchemaWatch (structural diff, description heuristic, replay, release gate).</p>
    <p class="author">Project 15 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">{n_tools} synthetic tools</span>
      <span class="badge">{s['changes']} injected changes</span>
      <span class="badge">{s['calls']:,} recorded calls</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">release gate</span>
    </div>
    <p class="framing">Portfolio prototype on synthetic data, not a production case study. The truth is known because the generator injected every change. No model is used: the diff, heuristic, validator and gate are plain rules. Every number below is generated from the scripts in <code>src/</code>.</p>
  </header>

  <section class="stats" aria-label="Running totals through the selected tool">
    <div class="stat"><p class="stat-label">Calls that break</p><p class="stat-value" id="stat-broken">—</p></div>
    <div class="stat"><p class="stat-label">Predicted by replay</p><p class="stat-value" id="stat-predicted">—</p></div>
    <div class="stat"><p class="stat-label">Broken, version never bumped</p><p class="stat-value" id="stat-unbumped">—</p></div>
    <div class="stat"><p class="stat-label">Misread, not flagged (known limit)</p><p class="stat-value" id="stat-unflagged">—</p></div>
  </section>

  <div class="controls">
    <label for="tool-select">Tool</label>
    <select id="tool-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next tool</button>
    <button id="runall-btn">Replay all {n_tools} tools</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Nothing watches</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Version or hash</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With SchemaWatch</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (calls broken or misread per change without SchemaWatch − with it) × schema changes per quarter</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> {s['affected_without']:,} of {s['calls']:,} recorded calls are broken or misread across {s['changes']} changes ({s['per_change_without']} per change). With the gate holding every BLOCK and REVIEW, {s['affected_with']} remain ({s['per_change_with']} per change): the {s['limit_changes']} meaning changes with no number or unit, which the heuristic cannot see. Replay predicted {s['replay_pred_broken']} of {s['replay_true_broken']} broken calls with {s['replay_fp']} false positives and {s['replay_fn']} misses; classification matched the ledger on {s['class_correct']} of {s['class_total']} changes.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['changes_per_quarter']} schema changes per quarter across a {s['tools']}-tool estate (an assumption, not a statistic) gives ({s['per_change_without']} − {s['per_change_with']}) × {s['changes_per_quarter']} = <b>{int(s['utility_per_quarter'])} calls per quarter</b> per recorded week of exposure per change. Assumes every BLOCK and REVIEW is acted on before the release reaches the agent.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/schemawatch-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['tools'])} tools, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
