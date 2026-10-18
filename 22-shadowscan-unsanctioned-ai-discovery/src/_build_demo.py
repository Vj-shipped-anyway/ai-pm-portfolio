"""Writes ../demo.html and ../assets/shadowscan-flow.svg from the output of the step scripts.
Standard library only.

Run (from src/):
    python3 _build_demo.py

Every number in the demo and in the diagram is computed by importing the step modules; none is
typed here. The page is static: it embeds one JSON blob and works offline.
"""

from __future__ import annotations

import json
from pathlib import Path

from step_02_blocklist_baseline import summarize as summarize_step2
from step_03_deficiencies_exposed import summarize as summarize_step3
from step_04_with_shadowscan import analyze, describe_option, scenario_options

ROOT = Path(__file__).parent.parent
FOLDER = "22-shadowscan-unsanctioned-ai-discovery"
GH = f"https://github.com/Vj-shipped-anyway/ai-pm-portfolio/blob/main/{FOLDER}"


def build_payload() -> dict:
    a = analyze()
    opts = scenario_options(a)
    described = []
    for o in opts:
        d = describe_option(a, o)
        described.append({"label": o["label"], "kind": d["kind"], "title": d["title"], "meta": d["meta"],
                          "before": d["before"], "red": d["red"], "blue": d["blue"], "green": d["green"]})
    return {"options": described, "s": a["summary"], "s2": summarize_step2(a["data"]), "s3": summarize_step3(a["data"]),
            "n_proxy": len(a["data"]["proxy"]), "n_dns": len(a["data"]["dns"]), "n_users": len(a["data"]["users"]),
            "n_items": len(a["items"])}


# ---------------------------------------------------------------------------
# Diagram. Text widths are estimated and checked so nothing runs outside its box.
# ---------------------------------------------------------------------------
MONO, SANS = 6.6, 5.7        # estimated pixels per character at 11px


def fit(text: str, width: float, per_char: float, label: str) -> str:
    assert len(text) * per_char <= width, f"SVG text too wide for its box ({label}): {text!r}"
    return text


def build_svg(p: dict) -> str:
    s, s2 = p["s"], p["s2"]
    u = s["unsanctioned"]
    ac = s["actions"]
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731

    def box(x, y, w, h, cls, num, title, subs, meta, meta_cls):
        inner = w - 24
        out = [f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" class="{cls}"/>',
               f'  <text x="{x + 12}" y="{y + 20}" class="stage-num">{esc(fit(num, inner, SANS, num))}</text>',
               f'  <text x="{x + 12}" y="{y + 42}" class="stage-title">{esc(fit(title, inner, 7.4, title))}</text>']
        for i, t in enumerate(subs):
            out.append(f'  <text x="{x + 12}" y="{y + 60 + 15 * i}" class="stage-sub">{esc(fit(t, inner, MONO, t))}</text>')
        out.append(f'  <text x="{x + 12}" y="{y + h - 13}" class="{meta_cls}">{esc(fit(meta, inner, SANS + 0.3, meta))}</text>')
        return "\n".join(out)

    parts = []
    parts.append(box(20, 120, 150, 118, "stage-box", "1 . LOGS", "Proxy and DNS",
                     ["proxy: path, bytes", "DNS: a name only", "no content read"],
                     f"{p['n_proxy']:,} + {p['n_dns']:,} rows", "meta-text"))
    parts.append(box(220, 120, 185, 118, "stage-box-eval", "2 . CLASSIFY", "Domain and path",
                     ["catalog: sanctioned", "feed or rules: flagged", "SaaS AI path: embedded"],
                     f"{u['tp']:,} of {s['unsanctioned_visible']:,} found", "meta-strong"))
    parts.append(box(455, 120, 195, 118, "stage-box-eval", "3 . RANK", "By data exposure",
                     ["bytes out x dept weight", "x distinct staff", "proxy rows only"],
                     f"{s['found_domains']} of {s['true_domains']} tools found", "meta-strong"))
    parts.append(box(700, 120, 200, 118, "stage-box-gate", "4 . ACT", "Block, sanction, coach",
                     ["owner department named", "catalog alternative shown", "a person confirms"],
                     f"{ac.get('block', 0)} block {ac.get('sanction', 0)} sanction {ac.get('coach', 0)} coach", "meta-block"))
    arrows = [(175, 179, 217), (410, 179, 452), (655, 179, 697)]
    arrow_xml = "\n".join(f'  <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" class="arrow-line" marker-end="url(#arrow)"/>' for x1, y, x2 in arrows)

    bx = box(240, 290, 340, 118, "stage-box-block", "5 . REVIEW QUEUE", "Sanction goes to intake first",
             ["TierGate intake, VendorLens diligence", "(designed, none built)"],
             f"false positives: {s['fp_sessions']} sessions on {len(s['fp_domains'])} domains", "meta-block")
    strip_title = fit("Same logs, two views", 261, 7.4, "strip")
    l1 = fit(f"Blocklist: {s['blocklist_tp']:,} of {s['unsanctioned_visible']:,} found", 261, 6.0, "strip1")
    l2 = fit(f"ShadowScan: {u['tp']:,} of {s['unsanctioned_visible']:,} found", 261, 6.0, "strip2")
    l3 = fit(f"known limit: {s['off_sessions']} off-network sessions unseen", 261, 5.9, "strip3")
    final = box(20, 290, 190, 118, "stage-box-ship", "OWNER", "Department gets a call", ["the next action,", "with the evidence"],
                f"{s['items']} ranked items", "meta-strong")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 430" role="img" aria-labelledby="title desc">
  <title id="title">ShadowScan: from proxy and DNS log rows to a ranked next action</title>
  <desc id="desc">Four-stage flow. Proxy and DNS logs are classified by catalog, feed, generation-style path and upload-heavy ratio, ranked by data exposure, and turned into a block, sanction or coach recommendation that a person reviews. A comparison strip contrasts a blocklist with ShadowScan on the synthetic data.</desc>

  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#5a5a5a"/>
    </marker>
    <style>
      .stage-box {{ fill: #ffffff; stroke: #1c2541; stroke-width: 1.5; }}
      .stage-box-eval {{ fill: #ffffff; stroke: #1d4e89; stroke-width: 1.5; }}
      .stage-box-gate {{ fill: #ffffff; stroke: #d97706; stroke-width: 1.5; }}
      .stage-box-block {{ fill: #ffffff; stroke: #b91c1c; stroke-width: 1.5; }}
      .stage-box-ship {{ fill: #ffffff; stroke: #16a34a; stroke-width: 1.5; }}
      .stage-title {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 500; fill: #1a1a1a; }}
      .stage-sub {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 11px; fill: #5a5a5a; }}
      .stage-num {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #1c2541; }}
      .arrow-line {{ stroke: #5a5a5a; stroke-width: 1.5; fill: none; }}
      .meta-text {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; fill: #8a8a8a; }}
      .meta-strong {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #14532d; }}
      .meta-block {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; font-weight: 500; fill: #7f1d1d; }}
      .timer {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #791F1F; }}
      .timer-fast {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; font-size: 10px; fill: #27500A; }}
      .header {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 18px; font-weight: 500; fill: #1a1a1a; }}
      .subheader {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; fill: #5a5a5a; }}
      .badge-bg {{ fill: #E6F1FB; }}
      .badge-text {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 10px; font-weight: 500; fill: #1c2541; }}
    </style>
  </defs>

  <text x="20" y="32" class="header">ShadowScan - from a log row to a ranked next action</text>
  <text x="20" y="52" class="subheader">Proxy and DNS logs in. Each domain and path classified, ranked by data exposure, then block, sanction or coach.</text>

  <rect x="20" y="78" width="290" height="22" rx="4" class="badge-bg"/>
  <text x="28" y="93" class="badge-text">Input: a batch of proxy rows and DNS lookups</text>

{chr(10).join(parts)}

{arrow_xml}

  <path d="M 800 238 L 800 264 L 410 264 L 410 288" class="arrow-line" marker-end="url(#arrow)"/>

{bx}

  <path d="M 240 340 L 210 340" class="arrow-line" marker-end="url(#arrow)"/>

{final}

  <rect x="610" y="290" width="285" height="118" rx="8" fill="#f6f5f2" stroke="none"/>
  <text x="622" y="312" class="stage-title">{esc(strip_title)}</text>
  <text x="622" y="337" class="timer">{esc(l1)}</text>
  <text x="622" y="357" class="timer-fast">{esc(l2)}</text>
  <text x="622" y="385" class="meta-strong">{esc(l3)}</text>
</svg>
"""


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
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
  .stat-value { font-size: 22px; font-weight: 500; margin: 0; line-height: 1.1; }
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
    border-radius: var(--radius-md); font-weight: 500; margin: 0 0 8px;
  }
  .pill-ok { background: #EAF3DE; color: #27500A; }
  .pill-bad { background: #FCEBEB; color: #791F1F; }
  .pill-warn { background: #FAEEDA; color: #633806; }
  .pill-info { background: #E6F1FB; color: #1c2541; }
  .truth { border-top: 1px solid var(--border); margin-top: 8px; padding-top: 8px; font-size: 13px; color: #1e3a8a; }
  .truth p { margin: 0 0 6px; }
  .nextaction { border-top: 1px solid var(--border); margin-top: 8px; padding-top: 8px; font-size: 13px; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }
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
const OPTS = D.options;

function esc(v) {
  return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function tone(t) { return t === "good" ? "pill-ok" : (t === "warn" ? "pill-warn" : "pill-bad"); }
function paras(lines) { return lines.map(l => "<p>" + esc(l) + "</p>").join(""); }

let idx = 0;
const sel = document.getElementById("pick-select");
OPTS.forEach((o, i) => {
  const e = document.createElement("option");
  e.value = i;
  e.textContent = o.label;
  sel.appendChild(e);
});

function render() {
  const o = OPTS[idx];
  sel.value = idx;
  document.getElementById("run-meta").innerHTML = "<b>" + esc(o.title) + "</b> - " + esc(o.meta);

  document.getElementById("card-before").innerHTML = paras(o.before) +
    '<span class="pill pill-info">a name and a count</span>';

  document.getElementById("card-sota").innerHTML =
    '<span class="pill ' + tone(o.red.tone) + '">' + esc(o.red.tag) + "</span>" + paras(o.red.lines) +
    '<div class="truth"><b>Truth (synthetic)</b>' + o.blue.map(l => "<p>" + esc(l) + "</p>").join("") + "</div>";

  let g = '<span class="pill ' + tone(o.green.tone) + '">' + esc(o.green.tag) + "</span>" + paras(o.green.lines);
  if (o.green.next) { g += '<div class="nextaction"><b>Next action:</b> ' + esc(o.green.next) + "</div>"; }
  if (o.green.note) { g += '<div class="nextaction">' + esc(o.green.note) + "</div>"; }
  document.getElementById("card-shield").innerHTML = g;
}

sel.addEventListener("change", e => { idx = parseInt(e.target.value, 10); render(); });
document.getElementById("prev-btn").addEventListener("click", () => { if (idx > 0) idx--; render(); });
document.getElementById("next-btn").addEventListener("click", () => { if (idx < OPTS.length - 1) idx++; render(); });
document.getElementById("reset-btn").addEventListener("click", () => { idx = 0; render(); });

render();
"""


def build_html(p: dict) -> str:
    s, s2, s3 = p["s"], p["s2"], p["s3"]
    u = s["unsanctioned"]
    js = JS.replace("__PAYLOAD__", json.dumps({"options": p["options"]}, separators=(",", ":")).replace("</", "<\\/"))
    n_opts = len(p["options"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ShadowScan — Unsanctioned AI Discovery · Vijay Saharan</title>
<meta name="description" content="A clickable demo of ShadowScan: finds the AI tools staff already use and ranks them by data exposure, not by a blocklist hit count. Synthetic data, plain rules, no model.">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header class="hero">
    <h1>ShadowScan — Unsanctioned AI Discovery</h1>
    <p class="tagline">Pick a domain or a department and compare a blocklist with ShadowScan on synthetic logs.</p>
    <p class="author">Project 22 · AI PM Portfolio · <a href="https://www.linkedin.com/in/vijaysaharan/" rel="noopener">Vijay Saharan</a></p>
    <div class="badges">
      <span class="badge">Synthetic data</span>
      <span class="badge">No model: plain rules</span>
      <span class="badge">{p['n_proxy']:,} proxy rows · {p['n_dns']:,} DNS rows</span>
      <span class="badge">6 named deficiencies</span>
    </div>
  </header>

  <section class="stats" aria-label="Whole-extract totals">
    <div class="stat"><p class="stat-label">Found by the blocklist</p><p class="stat-value">{s['blocklist_tp']:,} of {s['unsanctioned_visible']:,}</p></div>
    <div class="stat"><p class="stat-label">Found by ShadowScan</p><p class="stat-value">{u['tp']:,} of {s['unsanctioned_visible']:,}</p></div>
    <div class="stat"><p class="stat-label">False alarms from the list</p><p class="stat-value">{s2['fp_lookalike']:,}</p></div>
    <div class="stat"><p class="stat-label">Off-network, in no log</p><p class="stat-value">{s['off_sessions']}</p></div>
  </section>

  <div class="controls">
    <label for="pick-select">Pick one</label>
    <select id="pick-select"></select>
  </div>

  <div class="run-meta" id="run-meta" aria-live="polite"></div>

  <div class="actions">
    <button id="prev-btn">Previous</button>
    <button id="next-btn">Next</button>
    <button id="reset-btn">Reset</button>
  </div>

  <section class="grid" aria-label="Three-stage comparison">
    <div class="card">
      <p class="card-title"><span class="step-num">1</span>Before — Proxy report</p>
      <div class="card-body" id="card-before"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">2</span>Basic — Blocklist</p>
      <div class="card-body" id="card-sota"></div>
    </div>
    <div class="card">
      <p class="card-title"><span class="step-num">3</span>With ShadowScan</p>
      <div class="card-body" id="card-shield"></div>
    </div>
  </section>

  <p class="framing">Portfolio prototype on synthetic data, not a production case study. {n_opts} picks: the highest-exposure domains found, four edge cases, then the ten departments. The generator decided which domains are AI tools, so the truth is known. No model is used: the classifier is a catalog lookup, a feed lookup, a path pattern and a byte-ratio test. Every number on this page is generated from the scripts in <code>src/</code>.</p>

  <section class="utility-callout">
    <p style="margin: 0 0 6px;"><b>Utility delivered</b></p>
    <p class="formula">Utility = (sessions found per staff member with ShadowScan − with a blocklist) × staff using AI outside the catalog</p>
    <p style="margin: 8px 0 0;">🟢 <b>Measured on this synthetic set:</b> the blocklist finds {s['blocklist_tp']:,} of {s['unsanctioned_visible']:,} unsanctioned AI sessions ({s['sota_per_user']:.3f} per staff member who used one); ShadowScan finds {u['tp']:,} ({s['mine_per_user']:.3f} per staff member), {s['beyond_blocklist']:,} of them beyond the list. It finds {s['found_domains']} of {s['true_domains']} unapproved AI domains; the list hits {s['blocklist_domains_hit']}. Precision is {u['precision']*100:.1f}% against {s['blocklist_precision']*100:.1f}% for the list.</p>
    <p style="margin: 8px 0 0;">🟡 <b>Modeled:</b> {s['modeled_staff']:,} staff × {int(s['modeled_share']*100)}% using AI outside the catalog = {s['people']:,} people (an assumption, not a statistic) gives ({s['mine_per_user']:.3f} − {s['sota_per_user']:.3f}) × {s['people']:,} = <b>about {round(s['utility'], -1):,.0f} extra sessions brought into view per two-week window</b>. The {s['off_sessions']} off-network sessions stay invisible to both.</p>
  </section>

  <footer class="footer-links">
    <a href="{GH}/README.md">Full walkthrough README</a>
    <a href="{GH}/PRD.md">PRD</a>
    <a href="{GH}/ARCHITECTURE.md">Architecture</a>
    <a href="./assets/shadowscan-flow.svg">Flow diagram</a>
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
    svg = ROOT / "assets" / "shadowscan-flow.svg"
    svg.parent.mkdir(exist_ok=True)
    svg.write_text(build_svg(p), encoding="utf-8")
    print(f"Wrote {out.name}: {len(p['options'])} picks, {len(out.read_text(encoding='utf-8')):,} characters")
    print(f"Wrote assets/{svg.name}")


if __name__ == "__main__":
    main()
