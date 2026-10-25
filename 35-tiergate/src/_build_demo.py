"""Build demo.html from out/step_04_results.csv and out/step_04_summary.json.

Run step_04_with_tiergate.py first.  Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_results.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TierGate Skill: 200 intake forms, one recompute</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--ok:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--ok:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:140px}
.k b{font-size:20px;display:block}.k span{color:var(--mut);font-size:13px}
.f{display:flex;flex-wrap:wrap;gap:12px;align-items:center}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;margin-left:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:820px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}
.under{color:var(--bad);font-weight:600}.over{color:var(--warn);font-weight:600}.match{color:var(--ok);font-weight:600}
</style></head><body><main>
<h1>TierGate Skill: 200 intake forms, one recompute</h1>
<p class="s">Synthetic data. Each row is an AI use-case intake form. The reference tier is the written rubric applied to the true inputs, which the tool never sees. Same author wrote the data and the rules, so the numbers are a ceiling.</p>
<div class="k" id="k"></div>
<div class="f">
<label>Against the declared tier <select id="a"><option value="">all</option><option>UNDER-DECLARED</option><option>OVER-DECLARED</option><option>MATCH</option></select></label>
<label>Against the reference <select id="r"><option value="">all</option><option value="equal">equal</option><option value="below">below (a miss)</option><option value="above">above (a false alarm)</option></select></label>
<label>Planted <select id="p"><option value="">all</option><option value="none">none</option><option value="some">any planted situation</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Use case</th><th>Declared</th><th>Form as written</th><th>TierGate</th><th>Reference</th><th>Against declared</th><th>Planted</th><th>Flags</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">The rows marked below are the known limit: the form is wrong and no second source disagrees. Source: <code>python3 step_04_with_tiergate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function tile(big,small){var d=document.createElement('div'),b=document.createElement('b'),s=document.createElement('span');b.textContent=big;s.textContent=small;d.appendChild(b);d.appendChild(s);document.getElementById('k').appendChild(d);}
tile(SUM.declared_exact+' / '+SUM.form_exact+' / '+SUM.tool_exact+' of '+SUM.forms,'tier equals reference: declared / form as written / TierGate');
tile(SUM.declared_full_caught+' / '+SUM.form_full_caught+' / '+SUM.tool_full_caught+' of '+SUM.full,'tier 3-4 forms caught, same order');
tile(SUM.declared_under+' to '+SUM.tool_under,'forms below the reference, declared to TierGate');
tile(SUM.declared_over+' to '+SUM.tool_over,'forms above the reference, declared to TierGate');
function outcome(r){var t=Number(r.recomputed_tier),f=Number(r.reference_tier);return t<f?'below':t>f?'above':'equal';}
function draw(){
var a=document.getElementById('a').value,o=document.getElementById('r').value,p=document.getElementById('p').value,body=document.getElementById('b');
while(body.firstChild){body.removeChild(body.firstChild);}
var c=0;
ROWS.forEach(function(r){
if(a&&r.status!==a)return;if(o&&outcome(r)!==o)return;
if(p==='none'&&r.planted!=='none')return;if(p==='some'&&r.planted==='none')return;
c++;var tr=document.createElement('tr');
[r.use_case_id,r.title,r.declared_tier,r.form_tier,r.recomputed_tier,r.reference_tier,r.status,r.planted.split(';').join(', '),r.flags.split(' | ').join(', ')].forEach(function(v,i){
var td=document.createElement('td');td.textContent=v;
if(i===6)td.className=v==='UNDER-DECLARED'?'under':v==='OVER-DECLARED'?'over':'match';
tr.appendChild(td);});
body.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['a','r','p'].forEach(function(id){document.getElementById(id).onchange=draw;});
draw();
</script></body></html>
"""
def safe(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = PAGE.replace("__ROWS__", safe(rows)).replace("__SUM__", safe(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
