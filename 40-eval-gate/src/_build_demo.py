"""Build demo.html from out/step_04_decisions.csv. Run step_04_with_gate.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Eval Gate: 64 candidate deploys, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+5){white-space:nowrap}
</style></head><body><main>
<h1>Eval Gate: 64 candidate deploys, one gate</h1>
<p class="s">Synthetic data. Each row is a candidate deploy that ran a 30-probe set. The truth is the event I planted; the decision is what the gate printed, given the pin the team had set for that run.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="d"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted event <select id="e"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Run</th><th>Planted event</th><th>Truth</th><th>Decision</th><th>Pass rate / baseline</th><th>Served id (pin)</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: the drift_subtle rows, where the id is unchanged and the pass rate moved about two points, are allowed. A pin that someone moves without reading the vendor notice also defeats the first rule. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;}
var k=document.getElementById('k');
[[SUM.should_block_stopped+' of '+SUM.should_block,'should-block stopped'],[SUM.should_review_flagged+' of '+SUM.should_review,'should-review flagged'],[SUM.fine_blocked+' of '+SUM.fine,'fine runs blocked'],[SUM.exact_match+' of '+SUM.runs,'decision matches truth']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds={};ROWS.forEach(function(r){kinds[r.planted_kind]=1;});
var es=document.getElementById('e');Object.keys(kinds).sort().forEach(function(v){es.appendChild(el('option',v));});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,e=es.value,b=document.getElementById('b');
while(b.firstChild)b.removeChild(b.firstChild);var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t)||(e&&r.planted_kind!==e))return;c++;var tr=el('tr');
var served=r.served+(r.served===r.pin?'':' (pin '+r.pin+')');
[r.run_id,r.planted_kind,r.truth,r.decision,r.pass_rate+' / '+r.baseline,served,r.findings].forEach(function(v,i){tr.appendChild(el('td',v,i===3?v:''));});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['d','t','e'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows).replace("<", "\\u003c")).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
