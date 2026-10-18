"""Writes ../demo.html from the step scripts' output (standard library only).

Run the four step scripts first (they write src/out/*.json), then:

    python3 _build_demo.py

Every number in demo.html comes from src/out/step_01_results.json ... step_04_results.json
and from the CSVs in ../data. Nothing is retyped. Every dynamic value is HTML-escaped
in the page (esc() in the script block).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import step_01_spreadsheet_fifo as s1

HERE = Path(__file__).parent
OUT = HERE / "out"
DEMO = HERE.parent / "demo.html"


def load(name: str):
    p = OUT / name
    if not p.exists():
        sys.exit("Missing %s. Run step_01 to step_04 first (python3 step_0N_*.py from src/)." % p)
    with open(p) as fh:
        return json.load(fh)


def pick_scenarios(cases: dict, r2: dict, r3: dict, r4: dict) -> list:
    """One illustrative submission per deficiency, then the clean case, the limit, the cost and a false link."""
    rows = {r["use_case_id"]: r for r in r4["rows"]}
    basic = {r["use_case_id"]: r for r in r2["rows"]}
    chosen: list = []

    def has(uid: str, code: str) -> bool:
        return any(f["code"] == code for f in rows[uid]["flags"])

    def fixed(uid: str) -> bool:
        return rows[uid]["recomputed"] == rows[uid]["reference"] and rows[uid]["declared"] < rows[uid]["reference"]

    def add(candidates: list, story: str) -> None:
        taken = [c[0] for c in chosen]
        for uid in candidates:
            if uid not in taken:
                chosen.append((uid, story))
                return

    def best(ids: list) -> list:
        return sorted(ids, key=lambda u: (-rows[u]["reference"], u))

    ids = sorted(rows)
    hid = r4["headline_id"]
    add([hid], "Tier %d declared, tier %d true" % (rows[hid]["declared"], rows[hid]["reference"]))
    add(best([u for u in ids if has(u, "DATA_CLASS_BELOW_CATALOG") and fixed(u)]),
        "Data class understated against the catalog")
    add(best([u for u in ids if has(u, "CUSTOMER_FACING_CUE") and cases[u]["true_customer_facing"] == "yes" and fixed(u)]),
        "Customer-facing answered no")
    add(best([u for u in ids if has(u, "VENDOR_NOT_DECLARED") and fixed(u)]),
        "Vendor dependency left off the form")
    add([u for u in ids if rows[u]["linked_to"] and rows[u]["link_true"]
         and cases[u]["self_declared_tier"] != cases[rows[u]["linked_to"]]["self_declared_tier"]]
        + [u for u in ids if rows[u]["linked_to"] and rows[u]["link_true"]], "Same use case submitted twice")
    add(best([u for u in ids if basic[u]["approved"] and basic[u]["missing_reference"]
              and rows[u]["gate"] == "HOLD" and rows[u]["recomputed"] == rows[u]["reference"]]),
        "Approved with evidence missing")
    add([u for u in ids if rows[u]["declared"] == rows[u]["recomputed"] == rows[u]["reference"]
         and not [f for f in rows[u]["flags"] if f["code"] != "DATA_CLASS_ABOVE_CATALOG"] and rows[u]["gate"] == "READY"],
        "Clean case: nothing to flag")
    add(r4["both_wrong_mis_ids"], "Known limit: form and catalog both wrong")
    add([u for u in ids if rows[u]["recomputed"] > rows[u]["reference"]], "TierGate tiers higher than the reference")
    add([u for u in ids if rows[u]["linked_to"] and not rows[u]["link_true"]], "Proposed link that is a false positive")
    return chosen


def main() -> None:
    r1, r2, r3, r4 = (load("step_01_results.json"), load("step_02_results.json"),
                      load("step_03_deficiencies.json"), load("step_04_results.json"))
    cases = {}
    with open(HERE.parent / "data" / "intake_submissions.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            cases[r["use_case_id"]] = r
    rows = {r["use_case_id"]: r for r in r4["rows"]}
    basic = {r["use_case_id"]: r for r in r2["rows"]}

    scenarios = []
    for uid, story in pick_scenarios(cases, r2, r3, r4):
        c, x, b = cases[uid], rows[uid], basic[uid]
        scenarios.append({
            "id": uid, "story": story, "title": c["title"], "unit": c["sponsor_unit"], "date": c["submitted_date"],
            "dataset": c["dataset_name"],
            "form": {"customer_facing": c["customer_facing"] or "(blank)", "decision_autonomy": c["decision_autonomy"],
                     "data_class": c["data_class"], "vendor_model": c["vendor_model"],
                     "regulatory_scope": c["regulatory_scope"], "exposure": c["financial_exposure_band"]},
            "truth": {"customer_facing": c["true_customer_facing"], "data_class": c["true_data_class"],
                      "vendor_model": c["true_vendor_model"]},
            "declared": x["declared"], "reference": x["reference"], "recomputed": x["recomputed"], "score": x["score"],
            "basic": {"approved": b["approved"], "missing_declared": b["missing_declared"],
                      "missing_reference": b["missing_reference"]},
            "tg": {"gate": x["gate"], "missing": x["missing"], "flags": x["flags"], "linked_to": x["linked_to"],
                   "link_true": x["link_true"], "link_score": x["link_score"], "causes": x["causes"]},
            "waits": {"before": x["wait_before"], "basic": x["wait_basic"], "fifo": x["wait_fifo"],
                      "ordered": x["wait_ordered"]},
            "hours": {"before": s1.UNIFORM_REVIEW_H, "basic": s1.TIER_REVIEW_H[x["declared"]],
                      "tiergate": x["review_hours"]},
        })

    q = r4["queue"]
    data = {
        "n": r4["n_cases"],
        "headline": {
            "acc_declared": 1 - r4["err_declared"], "acc_tiergate": r4["accuracy"],
            "recall_declared": r4["declared_hi_recall"], "recall_tiergate": r4["hi_recall"],
            "gap_basic": r4["basic_gap_detection_rate"], "gap_tiergate": r4["gap_detection_rate"],
            "wait_before": q["hi_before"], "wait_fifo": q["hi_fifo"], "wait_ordered": q["hi_ordered"],
            "lo_fifo": q["lo_fifo"], "lo_ordered": q["lo_ordered"],
            "load_before": q["load_before"], "load_tiergate": q["load_tiergate"],
            "hours_before": q["hours_before"], "hours_basic": q["hours_basic"], "hours_tiergate": q["hours_tiergate"],
            "deficiencies": {"a": r3["a"]["n"], "b": r3["b"]["below_catalog_n"], "c": r3["c"]["n"],
                             "d": r3["d"]["omitted_n"], "e": r3["e"]["groups_n"], "f": r3["f"]["n"]},
            "both_wrong_n": r4["both_wrong_n"], "both_wrong_mis_n": r4["both_wrong_mis_n"],
            "over_n": r4["over_n"], "under_n": r4["under_n"],
            "approved_gap_basic": r4["basic_approved_missing_ref_n"], "approved_basic": r4["basic_approved_n"],
            "approved_gap_tg": r4["ready_missing_ref_n"], "approved_tg": r4["ready_n"],
        },
        "utility": r4["utility"],
        "assumptions": r4["assumptions"],
        "scenarios": scenarios,
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", payload)
    DEMO.write_text(html, encoding="utf-8")
    print("Wrote %s (%d bytes, %d scenarios)" % (DEMO, len(html.encode("utf-8")), len(scenarios)))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TierGate — AI Use-Case Intake and Risk Tiering · Vijay Saharan</title>
<meta name="description" content="A clickable demo of TierGate: AI use-case intake and risk tiering for a regulated bank. Pick one of ten synthetic submissions from a set of 150 and see the sponsor's declared tier, the recomputed tier, the discrepancies, the evidence gate and the queue effect.">
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
  .framing { font-size: 12px; color: var(--text-tertiary); margin: -8px 0 24px; line-height: 1.5; }
  .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .stat { background: var(--bg-secondary); border-radius: var(--radius-md); padding: 14px 16px; }
  .stat-label { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; }
  .stat-value { font-size: 24px; font-weight: 500; margin: 0; line-height: 1.1; }
  .stat-sub { font-size: 11px; color: var(--text-tertiary); margin: 4px 0 0; }
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
  .meta { font-size: 12px; color: var(--text-tertiary); margin-top: 8px; line-height: 1.5; }
  .driver-row { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: 13px; }
  .driver-label { color: var(--text-secondary); }
  .driver-value { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 12px; text-align: right; overflow-wrap: anywhere; }
  .flagrow { border-top: 1px solid var(--border); padding: 6px 0; font-size: 12px; }
  .flagrow:first-of-type { border-top: 0; }
  .flagcode { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-weight: 500; overflow-wrap: anywhere; }
  .flagtext { color: var(--text-secondary); overflow-wrap: anywhere; }
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
  @media (max-width: 720px) {
    .grid { grid-template-columns: 1fr; }
    .stats { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>TierGate — AI Use-Case Intake and Risk Tiering</h1>
    <p class="tagline">Pick an intake submission and compare the tier the sponsor declared with the tier TierGate recomputes.</p>
    <p class="author">Project 11 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges" id="badges"></div>
  </header>

  <section class="stats" aria-label="Headline measures">
    <div class="stat"><p class="stat-label">🟢 Tier accuracy</p><p class="stat-value" id="stat-acc">—</p><p class="stat-sub" id="stat-acc-sub"></p></div>
    <div class="stat"><p class="stat-label">🟢 Tier 3-4 recall</p><p class="stat-value" id="stat-recall">—</p><p class="stat-sub" id="stat-recall-sub"></p></div>
    <div class="stat"><p class="stat-label">🟢 Evidence-gap detection</p><p class="stat-value" id="stat-gap">—</p><p class="stat-sub" id="stat-gap-sub"></p></div>
    <div class="stat"><p class="stat-label">🟡 Tier 3-4 mean wait (days)</p><p class="stat-value" id="stat-wait">—</p><p class="stat-sub" id="stat-wait-sub"></p></div>
  </section>

  <div class="controls">
    <label for="case-select">Intake submission</label>
    <select id="case-select"></select>
  </div>

  <div class="run-meta" id="run-meta"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next submission</button>
    <button id="runall-btn">Replay all submissions</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage intake comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Spreadsheet</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Trust the declared tier</p>
      <div class="card-body" id="card-basic"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With TierGate</p>
      <div class="card-body" id="card-tg"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. The reference tier is true by construction (the written rubric applied to the hidden true attributes), so accuracy measures recovery from noisy inputs, not how real banks behave. No AI model is used: the rubric, the cross-checks and the duplicate score are plain rules. Every number on this page is generated from the scripts in src/. Vocabulary follows SR 11-7, NIST AI RMF and EU AI Act.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (self-declared error rate − TierGate error rate) × AI use cases reviewed per year</p>
    <p style="margin: 8px 0 0;" id="utility-text"></p>
  </section>

  <footer class="footer-links">
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/11-tiergate-ai-usecase-intake/README.md">Full walkthrough README</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/11-tiergate-ai-usecase-intake/PRD.md">PRD</a>
    <a href="https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/11-tiergate-ai-usecase-intake/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/tiergate-flow.svg">Flow diagram</a>
    <a href="https://vj-shipped-anyway.github.io/ai-pm-portfolio/">All projects</a>
    <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">LinkedIn</a>
  </footer>
</div>

<script>
const DATA = __DATA__;
const SC = DATA.scenarios;
const H = DATA.headline;

function esc(v) {
  return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function pct(x) { return (100 * x).toFixed(1) + "%"; }
function d1(x) { return Number(x).toFixed(1); }
function row(label, value) {
  return `<div class="driver-row"><span class="driver-label">${esc(label)}</span><span class="driver-value">${esc(value)}</span></div>`;
}
function pill(cls, text) { return `<span class="pill ${esc(cls)}">${esc(text)}</span>`; }
function tierClass(t) { return t >= 4 ? "status-red" : (t === 3 ? "status-yellow" : "status-green"); }
function tierStrip(t) { return `<span class="status-strip ${tierClass(t)}">Tier ${esc(t)}</span>`; }
function list(a) { return a.length ? a.join(", ") : "none"; }

let idx = 0;
let timer = null;

const sel = document.getElementById("case-select");
SC.forEach((s, i) => {
  const o = document.createElement("option");
  o.value = i;
  o.textContent = `${s.id} — ${s.story}`;
  sel.appendChild(o);
});

document.getElementById("badges").innerHTML = [
  `${DATA.n} synthetic submissions`, "6 named deficiencies", "4 tiers", "Plain rules, no AI model"
].map(t => `<span class="badge">${esc(t)}</span>`).join("");

document.getElementById("stat-acc").textContent = pct(H.acc_tiergate);
document.getElementById("stat-acc-sub").textContent = `self-declared ${pct(H.acc_declared)}`;
document.getElementById("stat-recall").textContent = pct(H.recall_tiergate);
document.getElementById("stat-recall-sub").textContent = `self-declared ${pct(H.recall_declared)}`;
document.getElementById("stat-gap").textContent = pct(H.gap_tiergate);
document.getElementById("stat-gap-sub").textContent = `basic approach ${pct(H.gap_basic)}`;
document.getElementById("stat-wait").textContent = `${d1(H.wait_ordered)}`;
document.getElementById("stat-wait-sub").textContent = `tier-ordered; FIFO ${d1(H.wait_fifo)}; spreadsheet ${d1(H.wait_before)}`;

const U = DATA.utility;
document.getElementById("utility-text").innerHTML =
  `🟢 Self-declared error rate <b>${esc(pct(U.err_declared))}</b>; TierGate error rate <b>${esc(pct(U.err_tiergate))}</b> (measured on the ${esc(DATA.n)} synthetic submissions; the reference tier is true by construction). ` +
  `🟡 Annual intake <b>${esc(U.annual_intake)}</b> submissions (modeled: ${esc(d1(U.per_week))} per week in this set × 50 weeks, at a $50B-asset US retail bank that sees the same rate). ` +
  `🟡 Mis-tiered use cases avoided per year: <b>${esc(d1(U.avoided_per_year))}</b> (an expected value). ` +
  `Cost, measured: TierGate tiers <b>${esc(H.over_n)}</b> cases above the reference (conservative customer-facing checks) and misses <b>${esc(H.both_wrong_mis_n)}</b> of the <b>${esc(H.both_wrong_n)}</b> cases where the form and the catalog are both wrong. ` +
  `🟡 Review hours: spreadsheet ${esc(d1(H.hours_before))}, declared tier ${esc(d1(H.hours_basic))}, TierGate ${esc(d1(H.hours_tiergate))}. ` +
  `🟡 Tier 1-2 wait rises from ${esc(d1(H.lo_fifo))} to ${esc(d1(H.lo_ordered))} business days when the queue is ordered by tier.`;

function render() {
  const s = SC[idx];
  sel.value = idx;
  const f = s.form;
  document.getElementById("run-meta").innerHTML =
    `<b>${esc(s.id)}</b> · ${esc(s.date)} · ${esc(s.unit)} — <b>${esc(s.title)}</b>. ` +
    `Form: customer-facing <b>${esc(f.customer_facing)}</b>, autonomy <b>${esc(f.decision_autonomy)}</b>, data class <b>${esc(f.data_class)}</b>, ` +
    `vendor <b>${esc(f.vendor_model)}</b>, scope <b>${esc(f.regulatory_scope)}</b>, exposure <b>${esc(f.exposure)}</b>, dataset <b>${esc(s.dataset)}</b>.`;

  // 1 Before
  document.getElementById("card-before").innerHTML =
    `<p>The row sits in the sheet with the tier the sponsor typed. It gets the same standard review as every other row, in arrival order.</p>` +
    row("Tier on the sheet", s.declared) +
    row("Review given (modeled)", d1(s.hours.before) + " h") +
    row("Queue wait, mean (modeled)", d1(s.waits.before) + " days") +
    row("Evidence owed", "not recorded") +
    row("Duplicate flag", "none") +
    pill("pill-bad", "same review for every row");

  // 2 Basic
  const b = s.basic;
  const t = s.truth;
  let basicNote;
  if (s.declared === s.reference) {
    basicNote = "The declared tier matches the reference tier.";
  } else if (s.declared < s.reference) {
    basicNote = `The declared tier is ${s.reference - s.declared} below the reference tier, so the case gets a lighter review and a shorter checklist than its risk calls for.`;
  } else {
    basicNote = "The declared tier is above the reference tier: extra review effort.";
  }
  document.getElementById("card-basic").innerHTML =
    `<p>${esc(basicNote)}</p>` +
    row("Declared tier", s.declared) +
    row("Reference tier", s.reference) +
    row("Hidden truth: customer-facing", t.customer_facing) +
    row("Hidden truth: data class", t.data_class) +
    row("Hidden truth: vendor model", t.vendor_model) +
    row("Approved by the basic approach", b.approved ? "yes" : "held") +
    row("Evidence missing vs reference tier", list(b.missing_reference)) +
    (b.approved && b.missing_reference.length
      ? pill("pill-bad", "approved with required evidence missing")
      : (s.declared === s.reference ? pill("pill-ok", "declared tier correct") : pill("pill-warn", "tier wrong or evidence held ad hoc")));

  // 3 TierGate
  const g = s.tg;
  const flagHtml = g.flags.length
    ? g.flags.map(fl => `<div class="flagrow"><span class="flagcode">${esc(fl.code)}</span><br><span class="flagtext">${esc(fl.reason)}</span></div>`).join("")
    : `<div class="flagrow"><span class="flagtext">No discrepancy: form, catalog and registry agree.</span></div>`;
  let linkHtml = "none";
  if (g.linked_to) {
    linkHtml = `${g.linked_to} (overlap ${Number(g.link_score).toFixed(2)}, ${g.link_true ? "true duplicate" : "false positive"})`;
  }
  let verdict;
  if (s.recomputed === s.reference) {
    verdict = pill("pill-ok", "matches reference tier");
  } else {
    verdict = pill("pill-bad", (s.recomputed < s.reference ? "below" : "above") + " reference: " + (g.causes.length ? g.causes.join("; ") : "see flags"));
  }
  document.getElementById("card-tg").innerHTML =
    `<p>${esc(s.score)} rubric points on the checked inputs: ${tierStrip(s.recomputed)}</p>` +
    row("Declared / recomputed / reference", `${s.declared} / ${s.recomputed} / ${s.reference}`) +
    row("Gate", g.gate) +
    row("Evidence still missing", list(g.missing)) +
    row("Duplicate link", linkHtml) +
    row("Review depth (modeled)", d1(s.hours.tiergate) + " h") +
    row("Wait: FIFO / tier-ordered (modeled)", `${d1(s.waits.fifo)} / ${d1(s.waits.ordered)} days`) +
    `<div style="margin-top:6px;">${flagHtml}</div>` +
    verdict;
}

function go(i) { idx = Math.max(0, Math.min(SC.length - 1, i)); render(); }
sel.addEventListener("change", e => go(parseInt(e.target.value, 10)));
document.getElementById("prev-btn").addEventListener("click", () => go(idx - 1));
document.getElementById("next-btn").addEventListener("click", () => go(idx + 1));
document.getElementById("runall-btn").addEventListener("click", () => {
  if (timer) { clearInterval(timer); }
  let i = 0;
  timer = setInterval(() => {
    go(i);
    i += 1;
    if (i >= SC.length) { clearInterval(timer); timer = null; }
  }, 1100);
});
document.getElementById("reset-btn").addEventListener("click", () => {
  if (timer) { clearInterval(timer); timer = null; }
  go(0);
});

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
