"""Writes ../demo.html from the output of the step scripts. Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo is computed by importing the step modules; none is typed here.
The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_03_deficiencies_exposed import deficiencies
from step_04_with_corpusgate import analyze, story_detail

ROOT = Path(__file__).parent.parent
FOLDER = "20-corpusgate-rag-entitlements"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    de = deficiencies(a["data"], a["sq"])
    s = a["summary"]
    stories = []
    for st in a["stories"]:
        d = story_detail(a, st["query_id"])
        for x in d["unfiltered"] + d["gate"]["results"]:
            x.pop("score", None)
            x.pop("acl", None)
        stories.append({"tag": st["tag"], "label": st["label"], "detail": d})
    return {"stories": stories, "s": {k: v for k, v in s.items() if not isinstance(v, (dict, list))},
            "eval": {k: v for k, v in de["eval"].items() if not isinstance(v, dict)},
            "guards": {"index_acl": de["stale"]["leaked"], "flat": de["flat"]["leaked"], "label": de["label"]["leaked"]},
            "n_stories": len(stories)}


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
  .card-red { border-top: 3px solid #dc2626; }
  .card-blue { border-top: 3px solid #2563eb; }
  .card-green { border-top: 3px solid #059669; }
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
const STORIES = D.stories;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

let idx = 0;
const sel = document.getElementById("story-select");
STORIES.forEach((t, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = t.label;
  sel.appendChild(o);
});

function labelOf(x) { return x.shown_label === x.true_label ? x.shown_label : x.shown_label + ", really " + x.true_label; }

function render() {
  const st = STORIES[idx];
  const d = st.detail, u = d.user, g = d.gate;
  sel.value = idx;

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(d.query_id) + "</b> asked by <b>" + esc(u.id) + "</b> (" + esc(u.dept) + ", " + esc(u.role) + "): &ldquo;" + esc(d.text) + "&rdquo;. " +
    "This user may read " + esc(u.readable) + " of " + esc(u.docs) + " documents; " + esc(d.n_relevant) + " are relevant to the question.";

  // Card 1: before - relevance only
  let b = "";
  let leaks = 0;
  d.unfiltered.forEach(x => {
    if (!x.readable) leaks++;
    b += '<div class="fieldrow"><span class="fieldname">' + esc(x.doc_id) + '</span><span class="tag ' + (x.readable ? "tag-ok" : "tag-bad") + '">' +
         (x.readable ? "OK" : "LEAK") + '</span><span class="tag tag-warn" style="background:#ecebe7;color:#5a5a5a">' + esc(labelOf(x)) + '</span>' +
         '<div class="fieldvals">' + esc(x.title) + (x.pii !== "none" ? " (personal data in text)" : "") + "</div></div>";
  });
  b += '<div class="driver-row"><span class="driver-label">Relevance eval, this question</span><span class="driver-value">precision ' + d.precision.toFixed(2) + ", recall " + d.recall.toFixed(2) + "</span></div>";
  b += '<span class="pill ' + (leaks ? "pill-bad" : "pill-ok") + '">' + (leaks ? leaks + " of " + d.unfiltered.length + " results the user may not read" : "every result is readable") + "</span>";
  b += '<div class="note">The eval never looks at who is asking' + (leaks ? ", so it scores a leaked document as correct." : ".") + "</div>";
  document.getElementById("card-before").innerHTML = b;

  // Card 2: the truth, and what the cheap guards do
  let s = '<div class="reltitle">Source of truth</div>';
  s += '<div class="fieldvals">Direct groups: <span class="mono">' + esc(u.direct.join(", ")) + "</span><br>Through the group tree: " + esc(u.effective.length) + " groups.</div>";
  d.unfiltered.forEach(x => {
    s += '<div class="fieldrow"><span class="fieldname">' + esc(x.doc_id) + '</span><div class="fieldvals">' + esc(x.why) + "</div></div>";
  });
  s += '<div class="reltitle">Cheap guards, run alone</div>';
  [["index_acl", "ACL copy from index time"], ["flat", "Flat group check"], ["label", "Label-only filter"]].forEach(p => {
    const q = d.guards[p[0]];
    s += '<div class="driver-row"><span class="driver-label">' + esc(p[1]) + '</span><span class="driver-value">' + esc(q.leaked) + " leak, " + esc(q.withheld) + " hidden</span></div>";
  });
  document.getElementById("card-sota").innerHTML = s;

  // Card 3: with CorpusGate
  let h = "";
  const parts = [];
  if (g.removed_acl) parts.push(g.removed_acl + " blocked");
  if (g.held_pii.length) parts.push(g.held_pii.length + " held for personal data");
  if (g.redacted.length) parts.push(g.redacted.length + " redacted");
  h += '<span class="pill ' + ((g.leaked.length || g.pii_served.length) ? "pill-warn" : "pill-ok") + '" style="margin-top:0">' + esc(parts.length ? parts.join(", ") : "nothing to block") + "</span>";
  g.results.forEach(x => {
    let t = "";
    if (g.leaked.indexOf(x.doc_id) >= 0) t = '<span class="tag tag-warn">still leaks</span>';
    else if (g.pii_served.indexOf(x.doc_id) >= 0) t = '<span class="tag tag-warn">personal data passed</span>';
    else if (g.redacted.indexOf(x.doc_id) >= 0) t = '<span class="tag tag-ok">redacted</span>';
    h += '<div class="fieldrow"><span class="fieldname">' + esc(x.doc_id) + "</span>" + t + '<div class="fieldvals">' + esc(x.title) + "</div></div>";
  });
  g.held_pii.forEach(x => {
    h += '<div class="fieldrow"><span class="fieldname">' + esc(x.doc_id) + '</span><span class="tag tag-warn">held</span><div class="fieldvals">' + esc(x.kind.replace("_", "-")) + " value found; held out of the index for the owner to review</div></div>";
  });
  h += '<div class="driver-row"><span class="driver-label">Better matches withheld</span><span class="driver-value">' + esc(g.removed_acl) + "</span></div>";
  if (g.recall_before !== null) {
    h += '<div class="driver-row"><span class="driver-label">Readable recall, this question</span><span class="driver-value">' + g.recall_before.toFixed(2) + " to " + g.recall_after.toFixed(2) + "</span></div>";
  }
  if (g.leaked.length) {
    h += '<div class="note"><b>Known limit:</b> access was revoked after the last sync of the source lists, so the gate still allows this document.</div>';
  }
  if (g.pii_served.length) {
    h += '<div class="note"><b>Known limit:</b> personal data in a format the patterns do not match is indexed and served as written.</div>';
  }
  document.getElementById("card-shield").innerHTML = h;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < STORIES.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => { idx = i; render(); i++; if (i >= STORIES.length) clearInterval(iv); }, 900);
});

render();
"""


def build_html(p: dict) -> str:
    s, ev = p["s"], p["eval"]
    payload = json.dumps(p, separators=(",", ":")).replace("</", "<\\/")
    js = JS.replace("__PAYLOAD__", payload)
    g = p["guards"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CorpusGate — Entitlement-Aware Retrieval · Vijay Saharan</title>
<meta name="description" content="A clickable demo of CorpusGate: retrieval for an internal assistant that checks who may read each document before ranking, and scans personal data at ingestion. Synthetic data; the retriever is a stub, not a model.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="CorpusGate — Entitlement-Aware Retrieval">
<meta property="og:description" content="Checks that assistant retrieval respects who may read each document, and scans for personal data at ingestion.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/20-corpusgate-rag-entitlements/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="CorpusGate — Entitlement-Aware Retrieval">
<meta name="twitter:description" content="Checks that assistant retrieval respects who may read each document, and scans for personal data at ingestion.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta name="twitter:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 27 runnable prototypes on synthetic data">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/20-corpusgate-rag-entitlements/demo.html">
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAzMiAzMic+PHJlY3Qgd2lkdGg9JzMyJyBoZWlnaHQ9JzMyJyByeD0nNicgZmlsbD0nIzFjMjU0MScvPjx0ZXh0IHg9JzE2JyB5PScyMicgZm9udC1mYW1pbHk9J0FyaWFsJyBmb250LXNpemU9JzE1JyBmb250LXdlaWdodD0nNzAwJyB0ZXh0LWFuY2hvcj0nbWlkZGxlJyBmaWxsPSd3aGl0ZSc+VlM8L3RleHQ+PC9zdmc+">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>CorpusGate — Entitlement-Aware Retrieval</h1>
    <p class="tagline">Pick a question and see what the assistant returns, with and without a check on who may read each document.</p>
    <p class="author">Project 20 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">Stub retriever, not a model</span>
      <span class="badge">{s['n_docs']} documents · {s['n_users']} users · {s['n_queries']} queries</span>
      <span class="badge">6 named deficiencies</span>
    </div>
  </header>

  <section class="stats" aria-label="Totals over all {s['n_queries']} test questions">
    <div class="stat"><p class="stat-label">Results the user may not read, no check</p><p class="stat-value">{s['leaked_before']} of {s['results']:,}</p></div>
    <div class="stat"><p class="stat-label">Same, with CorpusGate</p><p class="stat-value">{s['leaked_after']} of {s['results']:,}</p></div>
    <div class="stat"><p class="stat-label">Canaries that leak, with CorpusGate</p><p class="stat-value">{s['canary_leaked_cg']} of {s['canaries']}</p></div>
    <div class="stat"><p class="stat-label">Injected personal data found</p><p class="stat-value">{s['pii_found']} of {s['pii_injected']}</p></div>
  </section>

  <div class="controls">
    <label for="story-select">Question</label>
    <select id="story-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next question</button>
    <button id="runall-btn">Replay all {p['n_stories']} questions</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card card-red">
      <p class="card-title"><span class="step-num">1</span>Before — Relevance only</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card card-blue">
      <p class="card-title"><span class="step-num">2</span>Basic — The truth and cheap guards</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card card-green">
      <p class="card-title"><span class="step-num">3</span>With CorpusGate</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The generator decided every access list, so the truth is known. The retriever is a stub (plain TF-IDF), not a model; no model is used. The totals above cover all {s['n_queries']} test questions and every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (unreadable results per 100 queries without CorpusGate − with it) × assistant users</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> {s['leaked_before']} of {s['results']:,} results went to a user who may not read them ({s['leak_per_100_before']:.2f} per 100 queries), and the relevance eval scored {ev['leaked_scored_as_hits']} of them as correct. With CorpusGate {s['leaked_after']} remain ({s['leak_per_100_after']:.2f} per 100 queries), all from the {s['changes_after_sync']} ACL changes made after the last sync. The cheap guards alone leave {g['index_acl']} (ACL copy from index time), {g['flat']} (flat group check) and {g['label']} (label-only filter). Readable recall@5 goes from {s['readable_recall_before']:.3f} to {s['readable_recall_after']:.3f}; holding personal-data documents out of the index costs {s['readable_recall_pre'] - s['readable_recall_after']:.3f} of that.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['assistant_users']:,} assistant users (an assumption, not a statistic) gives ({s['leak_per_100_before']:.2f} − {s['leak_per_100_after']:.2f}) × {s['assistant_users']:,} = <b>{int(s['utility']):,} unreadable results kept from users</b> if each runs 100 queries.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/corpusgate-flow.svg">Flow diagram</a>
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
    print(f"Wrote {out.name}: {p['n_stories']} questions, {len(out.read_text(encoding='utf-8')):,} characters")


if __name__ == "__main__":
    main()
