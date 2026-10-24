"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_gate.py first.
Run (from src/): python3 _build_demo.py"""
import contextlib
import csv
import io
import json
import os

import prompt_diff_risk

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    prompt_diff_risk.main(["--demo"])


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prompt Diff Risk: 70 prompt pull requests, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a;--code:#f3f4f6}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a;--code:#1d2026}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+5){white-space:nowrap}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:13px;margin:0}
</style></head><body><main>
<h1>Prompt Diff Risk: 70 prompt pull requests, one gate</h1>
<p class="s">Synthetic data. Each row is a pull request that edits the system prompt of one bank-support assistant. The truth is the edit I planted; the decision is what the classifier printed. Which probes would fail is planted too: no model was called.</p>
<div class="k" id="k"></div>
<h2>The bundled example (<code>python3 prompt_diff_risk.py --demo</code>)</h2>
<pre id="demo"></pre>
<h2>All 70 pull requests</h2>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option>high</option><option>medium</option><option>low</option></select></label>
<label>Planted edit <select id="e"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>PR</th><th>Assistant</th><th>Planted edit</th><th>Truth</th><th>Decision</th><th>Probes run</th><th>Findings</th><th>Slices</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: route_swap and tone_offlist (a one-word swap in a long sentence with no rule word, tone word, tool name or number) are allowed, and some constraint_quiet rows pass or are only sent to review. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, DEMO=__DEMO__;
function el(tag,text,cls){var x=document.createElement(tag);x.textContent=text;if(cls){x.className=cls;}return x;}
var k=document.getElementById('k');
[[SUM.high_blocked+' of '+SUM.high,'high-risk blocked'],[SUM.medium_flagged+' of '+SUM.medium,'medium-risk flagged'],[SUM.harmless_blocked+' of '+SUM.harmless,'harmless blocked'],[SUM.to_read+' of '+SUM.pull_requests,'to read'],[SUM.probes_run+' of '+SUM.probes_full,'probes run']].forEach(function(x){var d=document.createElement('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
document.getElementById('demo').textContent=DEMO;
var kinds={};ROWS.forEach(function(r){kinds[r.change_kind]=1;});
var es=document.getElementById('e');Object.keys(kinds).sort().forEach(function(v){var o=document.createElement('option');o.textContent=v;o.value=v;es.appendChild(o);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,e=es.value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t)||(e&&r.change_kind!==e))return;c++;var tr=document.createElement('tr');
[r.pr_id,r.assistant,r.change_kind,r.truth,r.decision,r.probes_run,r.findings,r.slices].forEach(function(v,i){var td=document.createElement('td');td.textContent=v;if(i===4)td.className=v;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['d','t','e'].forEach(function(i){document.getElementById(i).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)).replace("__DEMO__", embed(buf.getvalue().rstrip("\n")))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
