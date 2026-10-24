"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_contract.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Feature Contract: __N__ batches, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fail:#b3261e;--warn:#8a5a00;--pass:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fail:#ff8a80;--warn:#ffc266;--pass:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.FAIL{color:var(--fail);font-weight:600}.WARN{color:var(--warn);font-weight:600}.PASS{color:var(--pass);font-weight:600}
.wrap{overflow-x:auto}.wrap table{min-width:720px}td:nth-child(-n+6){white-space:nowrap}
</style></head><body><main>
<h1>Feature Contract: __N__ batches, one gate</h1>
<p class="s">Synthetic data. Each row is one delivery of model-input data from a feed. The truth is the change I planted; the decision is what the contract check printed.</p>
<div class="k" id="k"></div>
<h2>By planted change</h2>
<div class="wrap"><table><thead><tr><th>Planted change</th><th>Truth</th><th>FAIL</th><th>WARN</th><th>PASS</th></tr></thead><tbody id="g"></tbody></table></div>
<h2>Every batch</h2>
<div><label>Decision <select id="d"><option value="">all</option><option>FAIL</option><option>WARN</option><option>PASS</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="bad">bad</option><option value="ok">ok</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Batch</th><th>Feed</th><th>Planted change</th><th>Field</th><th>Truth</th><th>Decision</th><th>Findings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: null_zero_fill and unit_in_range stay inside the declared type, range and null rate, and unit_cents passes where the declared range is wide enough to hold the larger numbers. Source: <code>python3 step_04_with_contract.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function cell(tr,text,cls){var td=document.createElement('td');td.textContent=text;if(cls)td.className=cls;tr.appendChild(td);}
var k=document.getElementById('k');
[[SUM.bad_stopped+' of '+SUM.bad,'bad batches stopped'],[SUM.harmless_blocked+' of '+SUM.harmless,'harmless blocked'],[SUM.to_read+' of '+SUM.batches,'to read'],[SUM.missed+' of '+SUM.bad,'bad still passing']].forEach(function(x){
var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds={};ROWS.forEach(function(r){var o=kinds[r.change_kind]||(kinds[r.change_kind]={truth:r.truth,FAIL:0,WARN:0,PASS:0});o[r.decision]+=1;});
var g=document.getElementById('g');
Object.keys(kinds).sort().forEach(function(name){var o=kinds[name],tr=document.createElement('tr');cell(tr,name);cell(tr,o.truth);cell(tr,o.FAIL);cell(tr,o.WARN);cell(tr,o.PASS);g.appendChild(tr);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');
while(b.firstChild)b.removeChild(b.firstChild);var c=0;
ROWS.forEach(function(r){if((d&&r.decision!==d)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
cell(tr,r.batch_id);cell(tr,r.feed);cell(tr,r.change_kind);cell(tr,r.field);cell(tr,r.truth);cell(tr,r.decision,r.decision);cell(tr,r.findings);b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = (PAGE.replace("__N__", str(summary["batches"]))
        .replace("__ROWS__", json.dumps(rows).replace("<", "\\u003c"))
        .replace("__SUM__", json.dumps(summary).replace("<", "\\u003c")))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
