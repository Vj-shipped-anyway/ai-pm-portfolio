"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_01_ticket_queue_status_quo import AS_OF, CATEGORY_NAMES, fmt_hour, summarize as summarize_step1
from step_04_with_incidentledger import analyze, interest_order, view

ROOT = Path(__file__).parent.parent
FOLDER = "19-incidentledger-ai-incident-response"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def cat(c: str) -> str:
    return CATEGORY_NAMES.get(c, c)


def build_payload() -> dict:
    a = analyze()
    data, s = a["data"], a["summary"]
    s1, s3 = summarize_step1(data), a["step3"]
    names = {p["clock_id"]: p["name"] for p in data["policy"]}
    incidents = []
    for x in interest_order(a):
        v = view(a, x)
        inc, t, p = v["inc"], v["truth"], v["pred"]
        det = {d["clock_id"]: d for d in v["clocks_det"]}
        clocks = []
        for c in v["clocks"]:
            clocks.append({
                "name": c["name"], "hours": c["hours"], "status": c["status"],
                "due": fmt_hour(c["due"]) if c["due"] is not None else "",
                "sent": fmt_hour(c["sent_at"]) if c["sent_at"] is not None else "",
                "left": c["hours_left"], "over": c["hours_over"],
                "since_detection": c.get("hours_since_detection"),
                "det_status": det[c["clock_id"]]["status"],
            })
        truth_dl = []
        for r in v["truth_deadlines"]:
            truth_dl.append({"name": names[r["clock_id"]], "status": r["status"],
                             "due": fmt_hour(r["due"]) if r["due"] is not None else "",
                             "late_by": (r["sent_at"] - r["due"]) if r["status"] == "late" else None,
                             "over": (AS_OF - r["due"]) if r["status"] == "breached" else None,
                             "left": (r["due"] - AS_OF) if r["status"] == "running" else None})
        acts = v["actions"]
        incidents.append({
            "id": x, "title": inc["title"], "description": inc["description"], "system": inc["system"],
            "prio": inc["reporter_priority"], "rep_cat": inc["reporter_category"].strip(),
            "change_id": inc["change_id"], "qpos": v["queue_position"],
            "reported": fmt_hour(inc["reported_at"]),
            "determined": fmt_hour(inc["determined_at"]) if inc["determined_at"] is not None else "",
            "true_cat": cat(t["category"]), "true_sev": t["severity"], "root_cause": t["root_cause"],
            "same_rc": v["same_root_cause"], "hard": t["hard_case"],
            "pred_cat": cat(p["category"]), "pred_rule": p["rule"], "pred_conf": p["confidence"],
            "cat_ok": v["category_ok"], "sev": v["severity"], "reasons": v["reasons"],
            "missed": v["missed"], "clocks": clocks, "truth_dl": truth_dl,
            "acts": {"total": len(acts),
                     "overdue": sum(1 for q in acts if q["state"] == "overdue"),
                     "no_evidence": sum(1 for q in acts if q["state"] == "closed_no_evidence"),
                     "ok": sum(1 for q in acts if q["state"] == "closed_ok"),
                     "on_track": sum(1 for q in acts if q["state"] == "open_on_track")},
            "links": [{"id": y, "ok": v["links_ok"][y]} for y in v["links"]],
            "unlinked": [y for y in v["same_root_cause"] if y not in v["links"]],
        })
    return {"incidents": incidents, "s": s, "s1": s1, "s3": s3, "as_of": fmt_hour(AS_OF),
            "n_raw_labels": s1["raw_labels"]}


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
  .fieldname { font-weight: 500; overflow-wrap: anywhere; }
  .fieldvals { color: var(--text-secondary); overflow-wrap: anywhere; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }
  .tag { display: inline-block; font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 999px; margin-left: 6px; }
  .tag-ok { background: #EAF3DE; color: #27500A; }
  .tag-bad { background: #FCEBEB; color: #791F1F; }
  .tag-warn { background: #FAEEDA; color: #633806; }
  .tag-idle { background: #ecebe7; color: #5a5a5a; }
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
const INC = D.incidents;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }

let idx = 0;
const sel = document.getElementById("incident-select");
INC.forEach((t, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = t.id + " - queue " + t.prio + ", rubric " + t.sev + " - " + t.missed + " missed - " + t.title.slice(0, 44);
  sel.appendChild(o);
});

function clockTag(c) {
  if (c.status === "on_time") return ['tag-ok', 'on time'];
  if (c.status === "late") return ['tag-bad', 'late by ' + c.over + ' h'];
  if (c.status === "breached") return ['tag-bad', 'breached, ' + c.over + ' h past due'];
  if (c.status === "running") return ['tag-warn', c.left + ' h left'];
  return ['tag-idle', 'not started'];
}

function render() {
  const t = INC[idx];
  sel.value = idx;
  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(t.id) + "</b> - " + esc(t.title) + ". System <b>" + esc(t.system) + "</b>, reported " + esc(t.reported) +
    ". Incident " + esc(idx + 1) + " of " + esc(INC.length) + " in this list.";

  // Card 1: the ticket as filed
  let b = '<p>' + esc(t.description) + '</p>';
  b += '<div class="driver-row"><span class="driver-label">Priority picked by the reporter</span><span class="driver-value">' + esc(t.prio) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Category typed</span><span class="driver-value">' + esc(t.rep_cat) + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Linked change</span><span class="driver-value">' + esc(t.change_id || "none") + "</span></div>";
  b += '<div class="driver-row"><span class="driver-label">Deadline field / link field</span><span class="driver-value">none / none</span></div>';
  b += '<div class="driver-row"><span class="driver-label">Follow-ups</span><span class="driver-value">' + esc(t.acts.total) + " listed, no flags</span></div>";
  b += '<span class="pill pill-info">a ticket in a queue</span>';
  document.getElementById("card-before").innerHTML = b;

  // Card 2: the queue, with the truth beside it
  let s = "";
  s += '<div class="driver-row"><span class="driver-label">Work order position</span><span class="driver-value">' + esc(t.qpos) + " of " + esc(INC.length) + "</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Queue marks it urgent</span><span class="driver-value">' + ((t.prio === "P1" || t.prio === "P2") ? "yes" : "no") + "</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Deadlines shown</span><span class="driver-value">0 of ' + esc(t.truth_dl.length) + " that apply</span></div>";
  s += '<div class="driver-row"><span class="driver-label">Rubric says</span><span class="driver-value">' + esc(t.true_sev) + ", " + esc(t.true_cat) + "</span></div>";
  const gap = parseInt(t.prio.slice(1), 10) - parseInt(t.true_sev.slice(1), 10);
  s += '<span class="pill ' + (gap > 0 ? "pill-bad" : (gap < 0 ? "pill-warn" : "pill-ok")) + '">' +
       (gap > 0 ? "under-rated by the queue" : (gap < 0 ? "over-rated by the queue" : "priority matches the rubric")) + "</span>";
  if (t.truth_dl.length) {
    s += '<div class="reltitle">What happened to its deadlines</div>';
    t.truth_dl.forEach(c => {
      const g = clockTag({status: c.status, over: c.status === "late" ? c.late_by : c.over, left: c.left});
      s += '<div class="fieldrow"><span class="fieldname">' + esc(c.name) + '</span><span class="tag ' + g[0] + '">' + esc(g[1]) + "</span></div>";
    });
  }
  if (t.same_rc.length) {
    s += '<div class="fieldvals" style="font-size:12px;margin-top:6px;">Same root cause as ' + esc(t.same_rc.join(", ")) + ". The queue links none.</div>";
  }
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: IncidentLedger
  let h = '<div class="reltitle">' + esc(t.sev) + " - " + esc(t.pred_cat) + ' <span class="tag ' + (t.missed ? "tag-bad" : "tag-ok") + '">' + (t.missed ? "CAUGHT: " + esc(t.missed) + " missed" : "RATED") + "</span></div>";
  h += '<div class="fieldvals" style="font-size:12px;">Rubric: ' + esc(t.reasons.join("; ")) + ".</div>";
  h += '<div class="fieldvals" style="font-size:12px;">Category rule: ' + esc(t.pred_rule) + ".</div>";
  if (!t.cat_ok) {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Ground truth (synthetic):</b> ' + esc(t.true_cat) + ". " +
         (t.pred_conf === "review" ? "The classifier flagged its own doubt. Known limit." : "Wrong with no flag. Known limit; the clocks are unaffected.") + "</div>";
  }
  if (!t.clocks.length) { h += "<p>No notification clock applies under the modeled policy.</p>"; }
  t.clocks.forEach(c => {
    const g = clockTag(c);
    let line = '<span class="fieldname">' + esc(c.name) + '</span><span class="tag ' + g[0] + '">' + esc(g[1]) + "</span>";
    let sub = c.due ? "due " + esc(c.due) : "no determination recorded: " + esc(c.since_detection) + " h since detection";
    if (c.det_status !== c.status && c.due) { sub += "; from detection: " + esc(c.det_status.replace("_", " ")); }
    h += '<div class="fieldrow">' + line + '<div class="fieldvals">' + sub + "</div></div>";
  });
  if (t.acts.total) {
    h += '<div class="driver-row"><span class="driver-label">Follow-ups</span><span class="driver-value">' + esc(t.acts.overdue) + " overdue, " + esc(t.acts.no_evidence) + " closed with no evidence</span></div>";
  }
  h += '<div class="driver-row"><span class="driver-label">Linked tickets</span><span class="driver-value">' +
       (t.links.length ? esc(t.links.map(l => l.id + (l.ok ? "" : " (not the same root cause)")).join(", ")) : "none") + "</span></div>";
  if (t.unlinked.length) {
    h += '<div class="fieldvals" style="font-size:12px;margin-top:6px;"><b>Ground truth (synthetic):</b> same root cause as ' + esc(t.unlinked.join(", ")) + ". The linker did not connect it. Known limit.</div>";
  }
  h += '<span class="pill ' + (t.missed ? "pill-bad" : "pill-ok") + '">' + (t.missed ? "clocks flagged" : "no deadline missed") + "</span>";
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < INC.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= INC.length) clearInterval(iv); }, 250);
});

render();
"""


def build_html(p: dict) -> str:
    s, s1, s3 = p["s"], p["s1"], p["s3"]
    c, u = s["clocks"], s["util"]
    n = len(p["incidents"])
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    a = s3["a"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IncidentLedger — AI Incident Response · Vijay Saharan</title>
<meta name="description" content="A clickable demo of IncidentLedger: AI incident response with a severity rubric, notification clocks, a follow-up tracker and linked incidents. Synthetic data.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="IncidentLedger — AI Incident Response">
<meta property="og:description" content="Rates AI incidents by rubric, starts the notification clocks and tracks follow-ups instead of a ticket queue.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/19-incidentledger-ai-incident-response/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="IncidentLedger — AI Incident Response">
<meta name="twitter:description" content="Rates AI incidents by rubric, starts the notification clocks and tracks follow-ups instead of a ticket queue.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta name="twitter:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/19-incidentledger-ai-incident-response/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>IncidentLedger — AI Incident Response</h1>
    <p class="tagline">Pick an incident and see the ticket queue, then the rubric, the clocks and the follow-ups.</p>
    <p class="author">Project 19 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">{n} incidents · {c['applicable']} notification deadlines</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">No model: plain rules</span>
    </div>
  </header>

  <section class="stats" aria-label="Totals over all incidents">
    <div class="stat"><p class="stat-label">Deadlines missed, none shown by the queue</p><p class="stat-value">{c['missed']} of {c['applicable']}</p></div>
    <div class="stat"><p class="stat-label">S1 or S2 filed P3 or P4</p><p class="stat-value">{a['severe_filed_low']} of {a['severe']}</p></div>
    <div class="stat"><p class="stat-label">Missed deadlines flagged by the clocks</p><p class="stat-value">{s['missed_warned']} of {s['missed_total']}</p></div>
    <div class="stat"><p class="stat-label">Categories right (misses are hard cases)</p><p class="stat-value">{s['class_correct']} of {s['class_total']}</p></div>
  </section>

  <div class="controls">
    <label for="incident-select">Incident</label>
    <select id="incident-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next incident</button>
    <button id="runall-btn">Replay all {n} incidents</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — The ticket as filed</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Ticket queue by priority</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With IncidentLedger</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The generator decided each incident's category, severity and root cause, and who sent which notice when, so the truth is known. No model is used. Deadline lengths and rubric thresholds are assumptions of a modeled bank, not legal advice. Every number on this page is generated from the scripts in <code>src/</code>; the clocks are read at {p['as_of']}.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (deadline misses and unstarted clocks per incident, queue − IncidentLedger) × incidents per quarter</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> of {c['applicable']} notification deadlines, {c['missed']} were missed ({c['late']} sent late, {c['breached']} never sent) and {c['not_started']} never started. The queue showed none of them: {u['missed']} + {u['not_started']} = {u['queue_unflagged']} problems over {n} incidents ({u['per_incident_queue']:.3f} per incident). IncidentLedger flags all {s['missed_warned']} missed clocks and leaves the {u['with_unflagged']} that cannot start without a determination ({u['per_incident_with']:.3f} per incident). Category right on {s['class_correct']} of {s['class_total']}; the {s['class_misses']} misses are the hard cases written into the data.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {u['incidents_per_quarter']} AI incidents a quarter (an assumption, not a statistic; the synthetic set holds {n}) gives ({u['per_incident_queue']:.3f} − {u['per_incident_with']:.3f}) × {u['incidents_per_quarter']} = <b>about {u['per_quarter']:.1f} missed deadlines avoided a quarter</b>. Assumes a person acts on every countdown before the deadline.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/incidentledger-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {len(p['incidents'])} incidents, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
