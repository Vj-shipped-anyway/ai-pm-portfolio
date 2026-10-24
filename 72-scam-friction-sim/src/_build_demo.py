"""Build demo.html from out/step_04_grid.csv and out/step_04_summary.json. Run step_04_scored_hold.py first.
Run (from src/): python3 _build_demo.py"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_grid.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scam friction sim: a 20-minute hold</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--stop:#1e6b3a;--cost:#b3261e;--bar:#e6e9ee}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--stop:#7fd49a;--cost:#ff8a80;--bar:#262b32}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
label{display:block;margin:0 0 10px;color:var(--mut)}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;margin-left:6px;max-width:100%}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
td.n{text-align:right;white-space:nowrap}th.n{text-align:right}
.bar{display:inline-block;height:8px;background:var(--stop);border-radius:4px;vertical-align:middle;margin-right:8px}
.bar.c{background:var(--cost)}.cell{display:flex;align-items:center;justify-content:flex-end}.t{background:var(--bar);border-radius:4px;display:inline-block;width:80px;height:8px;margin-right:8px;overflow:hidden}
.t .bar{margin:0;display:block;border-radius:0}
tr.pick td{font-weight:600}
</style></head><body><main>
<h1>Scam friction sim: a 20-minute hold</h1>
<p class="s">Synthetic data, invented customer behaviour. Each row is a policy applied to the same 12,000 payments. Change the two assumptions and watch the numbers move.</p>
<label>Share of victims coached through the hold <select id="c"><option value="0.0">none</option><option value="0.2" selected>0.2 (the default assumption)</option><option value="0.5">0.5</option><option value="0.8">0.8</option></select></label>
<label>How common scams are <select id="w"><option value="1" selected>as drawn (330 in 12,000)</option><option value="10">one-tenth as common</option></select></label>
<div class="wrap"><table><thead><tr><th>Policy</th><th class="n">Scam value stopped</th><th class="n">Legitimate held</th><th class="n">Legitimate lost</th><th class="n">Holds per scam stopped</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s" id="note"></p>
<p class="s">Known limit: scams to a payee the customer has paid for weeks are never held by any row. Source: <code>python3 step_04_scored_hold.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function cell(tr,text,cls){var td=document.createElement('td');td.className=cls||'';td.textContent=text;tr.appendChild(td);return td;}
function barCell(tr,text,pct,cls){var td=document.createElement('td');td.className='n';var d=document.createElement('div');d.className='cell';
var t=document.createElement('span');t.className='t';var b=document.createElement('span');b.className='bar'+(cls?' '+cls:'');b.style.width=Math.max(0,Math.min(100,pct))+'%';t.appendChild(b);d.appendChild(t);
var s=document.createElement('span');s.textContent=text;d.appendChild(s);td.appendChild(d);tr.appendChild(td);}
function draw(){
 var c=parseFloat(document.getElementById('c').value),w=parseInt(document.getElementById('w').value,10),body=document.getElementById('b');
 while(body.firstChild){body.removeChild(body.firstChild);}
 var shown=0;
 ROWS.forEach(function(r){
  if(parseFloat(r.coach_rate)!==c||parseInt(r.legit_weight,10)!==w){return;}
  shown++;
  var tr=document.createElement('tr');
  if(r.policy.indexOf('warn')>=0){tr.className='pick';}
  cell(tr,r.policy);
  barCell(tr,r.stopped_pct+'%',parseFloat(r.stopped_pct)*3);
  barCell(tr,r.legit_held+' ('+r.legit_held_pct+'%)',parseFloat(r.legit_held_pct)*5,'c');
  cell(tr,r.legit_lost,'n');
  cell(tr,r.holds_per_stopped===''?'n/a':r.holds_per_stopped,'n');
  body.appendChild(tr);
 });
 document.getElementById('note').textContent=shown+' policies. Bold row: hold at score '+SUM.hold_score+' or more, warn at '+SUM.warn_score+' and '+(SUM.hold_score-1)+'. Legitimate counts are per '+(w===1?'11670':'116700')+' legitimate payments.';
}
document.getElementById('c').onchange=draw;document.getElementById('w').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows)).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
