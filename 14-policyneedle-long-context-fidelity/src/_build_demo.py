"""Writes ../demo.html from the script output. Standard library only.

Every number in demo.html comes from harness.py and step_04_with_policyneedle.py at build
time. Nothing is typed in by hand. Re-run after any change to the data or the harness:

    python3 _build_demo.py      (from src/)

The page is static and works offline. All dynamic values are escaped in the browser.
"""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

import harness as h
import step_01_short_document_test as s1
import step_02_fixed_needle_test as s2
import step_04_with_policyneedle as s4

ROOT = Path(__file__).resolve().parent.parent
FORM_SHORT = {"plain": "plain", "superseded": "superseded", "exception": "exception",
              "table": "table", "two_section": "two-section", "distractor": "distractor"}


def build_data() -> dict:
    r1 = s1.compute()
    r2 = s2.compute()
    r4 = s4.compute()
    probes = h.long_probes(h.load_probes())
    cells = r4["cells"]
    scenarios = []
    for reader in h.READERS:
        rk = reader["key"]
        known = h.known_fault_cells(probes, rk)
        flagged_all = h.flagged_cells(cells, rk)
        for length in h.LENGTHS:
            grid = [[cells[(rk, f, length, d)][0] for f in h.FORMS] for d in h.DEPTHS]
            k_len = {c for c in known if c[1] == length}
            f_len = {c for c in flagged_all if c[1] == length}
            loc = [{"form": FORM_SHORT[f], "text": h.localize(cells, rk, f, length)} for f in h.FORMS
                   if h.localize(cells, rk, f, length) != "none"]
            kinds = Counter(r["diagnosis"] for r in r4["rows"] if r["reader"] == rk and r["length"] == length and not r["passed"])
            g = r4["per_reader"][rk]["gate_by_length"][length]
            short = r1["per_reader"][rk]
            fixed = r2["table"][rk]["per_length"][length]
            scenarios.append({
                "id": "{}-{}".format(rk, length), "reader_key": rk, "reader": reader["label"],
                "fault": reader["fault"], "pages": length,
                "short": {"passed": short["passed"], "n": short["n"]},
                "fixed": {"passed": fixed["passed"], "n": fixed["n"], "depth": s2.FIXED_DEPTH},
                "grid": grid, "cells": len(h.FORMS) * len(h.DEPTHS),
                "known": len(k_len), "flagged": len(f_len), "true_flags": len(k_len & f_len),
                "misses": len(k_len - f_len), "false_flags": len(f_len - k_len),
                "localization": loc, "kinds": dict(sorted(kinds.items())),
                "gate": {"verdict": g["verdict"], "overall": round(100.0 * g["overall"], 1), "broken": g["broken"]},
            })
    pr, ut, lim = r4["per_reader"], r4["utility"], r4["limit"]
    return {
        "forms": [FORM_SHORT[f] for f in h.FORMS], "depths": h.DEPTHS,
        "scenarios": scenarios,
        "summary": {
            "probes": r4["n_probes"], "reads": 4 * r4["n_probes"], "doc_chars": r1["doc_chars"],
            "short_probes": r1["n_probes"], "truncate_at": h.TRUNCATE_AT,
            "known_cells": ut["failing_cells"], "pn_caught": ut["pn_caught"], "needle_caught": ut["needle_caught"],
            "short_caught": ut["short_caught"],
            "catch_pn": round(100 * ut["catch_pn"], 1), "catch_needle": round(100 * ut["catch_needle"], 1),
            "catch_short": round(100 * ut["catch_short"], 1),
            "assistants": ut["assistants_per_year"], "assistants_low": ut["assistants_range"][0],
            "assistants_high": ut["assistants_range"][1],
            "utility": round(ut["utility"], 1),
            "misses": sum(pr[k]["misses"] for k in s4.STUBS),
            "false_flags": sum(pr[k]["false_flags"] for k in h.READER_KEYS),
            "true_flags": sum(pr[k]["true_flags"] for k in s4.STUBS),
            "unscorable": lim["unscorable"], "scorable_n": len(lim["scorable"]),
            "verbose_passed": lim["verbose_passed"], "verbose_n": lim["verbose_n"],
            "verbose_flagged": lim["verbose_flagged_cells"], "verbose_cells": lim["verbose_cells"],
        },
    }


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PolicyNeedle — Long-Context Fidelity Probes · Vijay Saharan</title>
<meta name="description" content="A clickable demo of PolicyNeedle: long-context fidelity probes for assistants that answer from policy manuals. Synthetic manuals, four stub readers (not models), a per-slice pass matrix, fault localization and a CI-style gate.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="AI PM Portfolio · Vijay Saharan">
<meta property="og:title" content="PolicyNeedle — Long-Context Fidelity Probes">
<meta property="og:description" content="Probes where assistants lose facts in long policy manuals, and flags the failing form and depth.">
<meta property="og:url" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/14-policyneedle-long-context-fidelity/demo.html">
<meta property="og:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 77 runnable prototypes on synthetic data">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="PolicyNeedle — Long-Context Fidelity Probes">
<meta name="twitter:description" content="Probes where assistants lose facts in long policy manuals, and flags the failing form and depth.">
<meta name="twitter:image" content="https://vj-shipped-anyway.github.io/ai-pm-portfolio/assets/og-card.png">
<meta name="twitter:image:alt" content="AI PM portfolio card: How AI gets into bank operations, 77 runnable prototypes on synthetic data">
<link rel="canonical" href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/14-policyneedle-long-context-fidelity/demo.html">
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
    display: flex; flex-direction: column; min-width: 0;
  }
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
  .run-meta {
    background: var(--bg-secondary); border-radius: var(--radius-md);
    padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 16px; line-height: 1.6;
  }
  .run-meta b { color: var(--text-primary); font-weight: 500; }
  .big { font-size: 22px; font-weight: 500; margin: 0 0 6px; line-height: 1.2; }
  .heat { border-collapse: collapse; width: 100%; font-size: 11px; margin: 8px 0 4px; table-layout: fixed; }
  .heat th, .heat td { padding: 3px 2px; text-align: center; border: 1px solid var(--border); overflow: hidden; }
  .heat th { color: var(--text-secondary); font-weight: 500; background: var(--bg-secondary); }
  .heat td.c3 { background: #EAF3DE; color: #27500A; }
  .heat td.c2 { background: #FAEEDA; color: #633806; }
  .heat td.c1 { background: #F5D9B5; color: #5a2d05; }
  .heat td.c0 { background: #FCEBEB; color: #791F1F; }
  .loc { font-size: 12px; margin: 4px 0 0; padding: 0; list-style: none; color: var(--text-secondary); }
  .loc b { color: var(--text-primary); font-weight: 500; }
  .note-synthetic { font-size: 12px; color: var(--text-tertiary); margin: 0 0 16px; }
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>PolicyNeedle — long-context fidelity probes</h1>
    <p class="tagline">Pick a stub reader and a manual length. See it tested three ways.</p>
    <p class="author">Project 14 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">{{PROBES}} probes</span>
      <span class="badge">4 stub readers, not models</span>
      <span class="badge">6 named deficiencies</span>
      <span class="badge">synthetic data</span>
    </div>
  </header>

  <section class="stats" aria-label="Running totals for the scenarios replayed so far">
    <div class="stat"><p class="stat-label">Short test flagged</p><p class="stat-value" id="stat-short">0</p></div>
    <div class="stat"><p class="stat-label">Fixed needle flagged</p><p class="stat-value" id="stat-needle">0</p></div>
    <div class="stat"><p class="stat-label">PolicyNeedle flagged</p><p class="stat-value" id="stat-pn">0</p></div>
    <div class="stat"><p class="stat-label">False flags on control</p><p class="stat-value" id="stat-false">0</p></div>
  </section>

  <div class="controls">
    <label for="scenario-select">Scenario</label>
    <select id="scenario-select"></select>
  </div>

  <div class="run-meta" id="run-meta"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next scenario</button>
    <button id="runall-btn">Replay all 12 scenarios</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Short-document test</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — One fixed needle</p>
      <div class="card-body" id="card-basic"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With PolicyNeedle</p>
      <div class="card-body" id="card-pn"></div>
    </div>
  </section>

  <p class="note-synthetic">Everything on this page is synthetic. The four readers are small functions written to have known faults. They are stubs, not models, and their answers are not observed behavior of any real model.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (catch rate with PolicyNeedle − catch rate with short-document testing) × assistants launched per year</p>
    <p style="margin: 8px 0 0;" id="utility-text"></p>
  </section>

  <footer class="footer-links">
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/14-policyneedle-long-context-fidelity/README.md">Full walkthrough README</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/14-policyneedle-long-context-fidelity/PRD.md">PRD</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/14-policyneedle-long-context-fidelity/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/policyneedle-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>
const DATA = __POLICYNEEDLE_DATA__;
const S = DATA.scenarios;
const SUM = DATA.summary;

let currentIdx = 0;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function fmt(n) { return Number(n).toLocaleString("en-US"); }

const sel = document.getElementById("scenario-select");
S.forEach((s, i) => {
  const opt = document.createElement("option");
  opt.value = i;
  opt.textContent = s.reader + " · " + s.pages + " pages";
  sel.appendChild(opt);
});

function pillClass(v) { return v === "PASS" ? "pill-ok" : "pill-bad"; }
function statusClass(v) { return v === "PASS" ? "status-green" : "status-red"; }

function renderStats() {
  let short = 0, needle = 0, pn = 0, falseFlags = 0;
  for (let i = 0; i <= currentIdx; i++) {
    const s = S[i];
    const stub = s.reader_key !== "control";
    if (stub && s.short.passed < s.short.n) short += 1;
    if (stub && s.fixed.passed < s.fixed.n) needle += 1;
    if (stub && s.flagged > 0) pn += 1;
    if (!stub && s.flagged > 0) falseFlags += 1;
  }
  document.getElementById("stat-short").textContent = short;
  document.getElementById("stat-needle").textContent = needle;
  document.getElementById("stat-pn").textContent = pn;
  document.getElementById("stat-false").textContent = falseFlags;
}

function heatTable(s) {
  let h = '<table class="heat" aria-label="Probes passed out of 3, by depth and form"><tr><th>depth</th>';
  DATA.forms.forEach(f => { h += "<th>" + esc(f) + "</th>"; });
  h += "</tr>";
  DATA.depths.forEach((d, di) => {
    h += "<tr><th>" + esc(d) + "%</th>";
    s.grid[di].forEach(v => { h += '<td class="c' + esc(v) + '">' + esc(v) + "</td>"; });
    h += "</tr>";
  });
  return h + "</table>";
}

function render() {
  const s = S[currentIdx];
  sel.value = currentIdx;
  const stub = s.reader_key !== "control";

  document.getElementById("run-meta").innerHTML =
    "<b>" + esc(s.reader) + "</b> on a <b>" + esc(s.pages) + "-page</b> manual. Known fault of this stub: " + esc(s.fault) +
    " Gate verdict <span class=\"status-strip " + statusClass(s.gate.verdict) + "\">" + esc(s.gate.verdict) + "</span>.";

  document.getElementById("card-before").innerHTML =
    '<p class="big">' + esc(s.short.passed) + " of " + esc(s.short.n) + " pass</p>" +
    "<p>A " + esc(DATA.summary.short_probes) + "-question spot test on a 6-page excerpt of plain clauses. " +
    (stub ? "The stub passes, and so would a release carrying this fault."
          : "The control passes, as it should.") + "</p>" +
    '<div class="driver-row"><span class="driver-label">Excerpt length</span><span class="driver-value">' + esc(fmt(SUM.doc_chars)) + " chars</span></div>" +
    '<div class="driver-row"><span class="driver-label">Amendments, footnotes, tables</span><span class="driver-value">none</span></div>' +
    '<span class="pill ' + (s.short.passed < s.short.n ? "pill-bad" : "pill-ok") + '">' + (s.short.passed < s.short.n ? "fault visible" : "no fault visible") + "</span>" +
    '<p class="meta">Teams stop here because everything passes. The test has no structure for the fault to act on.</p>';

  const needleFlag = s.fixed.passed < s.fixed.n;
  document.getElementById("card-basic").innerHTML =
    '<p class="big">' + esc(s.fixed.passed) + " of " + esc(s.fixed.n) + " pass</p>" +
    "<p>One plain clause per probe, always at depth " + esc(s.fixed.depth) + "%, in this " + esc(s.pages) + "-page manual.</p>" +
    '<div class="driver-row"><span class="driver-label">Depths tested</span><span class="driver-value">1 of 5</span></div>' +
    '<div class="driver-row"><span class="driver-label">Forms of fact tested</span><span class="driver-value">1 of 6</span></div>' +
    '<span class="pill ' + (needleFlag ? "pill-warn" : "pill-info") + '">' + (needleFlag ? "flags a fault, cannot place it" : "no fault visible") + "</span>" +
    '<p class="meta">' + (stub && !needleFlag
      ? "This stub passes a single fixed position. Its fault is not about position, so the test cannot see it."
      : (needleFlag ? "The limit of this stub sits before the middle of this manual, so the middle fails. The test cannot say which depths or forms fail."
                    : "Nothing to flag.")) + "</p>";

  let loc = "";
  if (s.localization.length) {
    loc = '<ul class="loc">' + s.localization.map(x => "<li><b>" + esc(x.form) + "</b>: " + esc(x.text) + "</li>").join("") + "</ul>";
  } else {
    loc = '<ul class="loc"><li>No cell flagged.</li></ul>';
  }
  const broken = s.gate.broken.length ? '<p class="meta">' + s.gate.broken.map(esc).join(". ") + ".</p>" : '<p class="meta">All gate thresholds met.</p>';
  document.getElementById("card-pn").innerHTML =
    '<p class="meta" style="margin:0">Probes passed out of 3, depth by form</p>' + heatTable(s) +
    '<div class="driver-row"><span class="driver-label">Cells flagged</span><span class="driver-value">' + esc(s.flagged) + " of " + esc(s.cells) + "</span></div>" +
    '<div class="driver-row"><span class="driver-label">Known fault cells / true flags</span><span class="driver-value">' + esc(s.known) + " / " + esc(s.true_flags) + "</span></div>" +
    '<div class="driver-row"><span class="driver-label">Misses / false flags</span><span class="driver-value">' + esc(s.misses) + " / " + esc(s.false_flags) + "</span></div>" +
    loc +
    '<span class="pill ' + pillClass(s.gate.verdict) + '">Gate ' + esc(s.gate.verdict) + " · overall " + esc(s.gate.overall) + "%</span>" + broken;

  renderStats();
}

document.getElementById("utility-text").innerHTML =
  "🟢 Measured on the stubs (<code>step_04_with_policyneedle.py</code>): PolicyNeedle flags <b>" + esc(SUM.pn_caught) + " of " + esc(SUM.known_cells) +
  "</b> known failing cells (<b>" + esc(SUM.catch_pn) + "%</b>), with <b>" + esc(SUM.misses) + "</b> misses and <b>" + esc(SUM.false_flags) +
  "</b> false flags. The short-document test flags <b>" + esc(SUM.short_caught) + "</b> (<b>" + esc(SUM.catch_short) + "%</b>); a single fixed needle flags <b>" +
  esc(SUM.needle_caught) + "</b> (<b>" + esc(SUM.catch_needle) + "%</b>). " +
  "🟡 Modeled: <b>" + esc(SUM.assistants) + " assistants launched per year</b> at a large bank (my assumption, range " + esc(SUM.assistants_low) + "-" + esc(SUM.assistants_high) +
  "), so (" + esc(SUM.catch_pn) + "% − " + esc(SUM.catch_short) + "%) × " + esc(SUM.assistants) + " = <b>" + esc(SUM.utility) + " launches a year with their long-document faults caught before launch</b>. " +
  "The catch rates describe the harness against stubs with known faults, not any real model, and the product assumes each launch carries at least one such fault. " +
  "Known limit: scoring is exact match on synthetic wording, so " + esc(SUM.unscorable.length) + " probe types cannot be scored (" + esc(SUM.unscorable.join(", ")) +
  "). A correct but wordy answer scores " + esc(SUM.verbose_passed) + " of " + esc(SUM.verbose_n) + ".";

sel.addEventListener("change", e => { currentIdx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (currentIdx > 0) currentIdx -= 1; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (currentIdx < S.length - 1) currentIdx += 1; render(); });
document.getElementById("runall-btn").addEventListener("click", () => {
  let i = 0;
  const iv = setInterval(() => {
    currentIdx = i;
    render();
    i += 1;
    if (i >= S.length) clearInterval(iv);
  }, 700);
});
document.getElementById("reset-btn").addEventListener("click", () => { currentIdx = 0; render(); });

render();
</script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    payload = json.dumps(data, sort_keys=True, ensure_ascii=True).replace("</", "<\\/")
    page = TEMPLATE.replace("__POLICYNEEDLE_DATA__", payload)
    page = page.replace("{{PROBES}}", html.escape(str(data["summary"]["probes"])))
    out = ROOT / "demo.html"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("Wrote {} ({:,} bytes, {} scenarios)".format(out, len(page.encode("utf-8")), len(data["scenarios"])))


if __name__ == "__main__":
    main()
