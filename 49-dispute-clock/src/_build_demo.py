"""Build demo.html from out/step_04_clocks.csv and out/step_04_summary.json. Run step_04 first.

Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_clocks.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>dispute-clock: __N__ clocks on __D__ disputes</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--late:#b3261e;--run:#1b5fa8;--ok:#1e6b3a;--none:#6b6f76;--warn:#8a5a00}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--late:#ff8a80;--run:#8ab4f8;--ok:#7fd49a;--none:#9aa3ad;--warn:#ffc266}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:110px}.k b{font-size:20px;display:block}
.f{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}
label{color:var(--mut)}select,input[type=text]{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font:inherit}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
.wrap{overflow-x:auto}
.late,.breached{color:var(--late);font-weight:600}.running{color:var(--run);font-weight:600}.on_time{color:var(--ok);font-weight:600}.not_started{color:var(--none)}
.no{color:var(--warn);font-weight:600}
</style></head><body><main>
<h1>dispute-clock: __N__ clocks on __D__ disputes</h1>
<p class="s">Synthetic data, read as of __ASOF__. Windows are assumptions of a modeled bank, not read from any rule. Each row is one clock on one dispute: what the tool printed, and the status the generator planted.</p>
<div class="k" id="k"></div>
<div class="f">
<label>Status <select id="st"><option value="">all</option></select></label>
<label>Clock <select id="ck"><option value="">all</option></select></label>
<label><input type="checkbox" id="dis"> only where tool and plan differ</label>
<label>Dispute <input type="text" id="q" size="10" placeholder="DSP-0001"></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Dispute</th><th>Type</th><th>Clock</th><th>Start</th><th>Due</th><th>Sent</th><th>Tool says</th><th>Days</th><th>Plan says</th><th>Hard case</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known limits: a paused investigation is read as running the whole time, and a dispute recorded as extended is given the longer window even when it never applied. Source: <code>python3 step_04_business_day_clocks.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.right+' of '+SUM.clocks,'tool matches the plan'],[SUM.missed_found+' of '+SUM.missed_truth,'missed clocks found'],[String(SUM.false_alarms),'false alarms'],[SUM.disputes_with_miss+' of '+SUM.disputes,'disputes with a miss'],[String(SUM.due_soon),'due within '+SUM.due_soon_days+' days']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function fill(id,values){var s=document.getElementById(id);values.forEach(function(v){var o=el('option',v);o.value=v;s.appendChild(o);});}
function uniq(key){var seen={},out=[];ROWS.forEach(function(r){if(!seen[r[key]]){seen[r[key]]=1;out.push(r[key]);}});return out.sort();}
fill('st',uniq('status'));fill('ck',uniq('clock_id'));
function draw(){
 var st=document.getElementById('st').value,ck=document.getElementById('ck').value,dis=document.getElementById('dis').checked,q=document.getElementById('q').value.trim().toUpperCase(),b=document.getElementById('b'),c=0;
 while(b.firstChild)b.removeChild(b.firstChild);
 ROWS.forEach(function(r){
  if((st&&r.status!==st)||(ck&&r.clock_id!==ck)||(dis&&r.match==='yes')||(q&&r.dispute_id.indexOf(q)<0))return;
  c++;var tr=document.createElement('tr');
  [r.dispute_id,r.dispute_type,r.clock_id+' '+r.clock_name,r.start,r.due,r.sent,r.status,r.days,r.planted_status,r.hard_case].forEach(function(v,i){
   var td=el('td',v);if(i===6)td.className=r.status;if(i===8&&r.match==='no')td.className='no';tr.appendChild(td);});
  b.appendChild(tr);});
 document.getElementById('n').textContent=c+' shown';}
['st','ck','dis'].forEach(function(id){document.getElementById(id).onchange=draw;});
document.getElementById('q').oninput=draw;draw();
</script></body></html>
"""
data = json.dumps(rows).replace("</", "<\\/")
page = (page.replace("__ROWS__", data).replace("__SUM__", json.dumps(summary)).replace("__N__", str(summary["clocks"]))
        .replace("__D__", str(summary["disputes"])).replace("__ASOF__", summary["as_of"]))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
