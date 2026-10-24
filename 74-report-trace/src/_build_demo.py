"""Build demo.html from out/step_04_cells.csv and out/step_04_summary.json. Run step_04_with_lineage.py first.
Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_cells.csv"), encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>report-trace: 71 cells, one lineage</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--warn:#8a5a00;--ok:#1e6b3a;--card:#f6f7f9}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--warn:#ffc266;--ok:#7fd49a;--card:#1b1e23}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr{cursor:pointer}tbody tr:hover{background:var(--card)}
td.n{text-align:right;white-space:nowrap}td:nth-child(-n+4){white-space:nowrap}
.UNEXPLAINED,.SOURCE_CHANGED,.DOES_NOT_FOOT{color:var(--bad);font-weight:600}.ADJUSTED{color:var(--warn);font-weight:600}.TRACED,.FOOTS{color:var(--ok);font-weight:600}
.wrap{overflow-x:auto}
#d{border:1px solid var(--line);background:var(--card);border-radius:8px;padding:10px 14px;margin:12px 0;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace}
</style></head><body><main>
<h1>report-trace: 71 cells, one lineage</h1>
<p class="s">Synthetic data. Each row is a cell of an invented loan report. The planted class is what the generator did to that cell; the verdict is what the trace printed. Select a row to see its path back to the source rows.</p>
<div class="k" id="k"></div>
<div><label>Verdict <select id="v"><option value="">all</option></select></label>
<label>Planted class <select id="t"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div id="d">Select a row.</div>
<div class="wrap"><table><thead><tr><th>Cell</th><th>Kind</th><th>Planted class</th><th>Verdict</th><th>Filed</th><th>Rows</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known limit: the source_error rows trace as TRACED. A wrong but plausible days-past-due value is a real source row, and lineage shows where a number came from, not whether the row was right. Source: <code>python3 step_04_with_lineage.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function money(c,unit){var n=parseInt(c,10);if(unit==='bps')return n+' bps';var s=n<0?'-':'';n=Math.abs(n);var d=Math.floor(n/100).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g,',');return s+d+'.'+('0'+(n%100)).slice(-2);}
var k=document.getElementById('k');
[[SUM.found+' of '+SUM.problems,'planted problems found'],[SUM.false_alarms+' of '+SUM.benign,'false alarms'],[SUM.named_ok+' of '+SUM.source_change_cells,'changed rows named exactly'],[SUM.known_limit_cells+' cells','wrong rows that still trace']].forEach(function(x){var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function fill(id,key){var sel=document.getElementById(id),seen={};ROWS.forEach(function(r){seen[r[key]]=1;});Object.keys(seen).sort().forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;sel.appendChild(o);});}
fill('v','verdict');fill('t','truth');
function detail(r){var L=[r.cell_id+'   '+r.label,'planted class: '+r.truth,'verdict: '+r.verdict,'filed value: '+money(r.filed,r.unit)];
if(r.kind==='leaf'){L.push('source rows at filing: '+r.rows+', sum '+money(r.rows_sum,'usd'));L.push('logged adjustments: '+money(r.adjusted,'usd'));L.push('unexplained amount: '+money(r.residual,'usd'));L.push(r.named?'differences from the source today: '+r.named:'source today: every row unchanged');}
else{L.push('source rows beneath it: '+r.rows);if(r.named)L.push(r.named);}
if(r.truth==='source_error')L.push('the trace cannot see this: the source row itself is wrong (known limit)');
document.getElementById('d').textContent=L.join('\\n');}
function draw(){var v=document.getElementById('v').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((v&&r.verdict!==v)||(t&&r.truth!==t))return;c++;var tr=document.createElement('tr');
[r.cell_id,r.kind,r.truth,r.verdict,money(r.filed,r.unit),r.rows].forEach(function(x,i){var td=document.createElement('td');td.textContent=x;if(i===3)td.className=x;if(i>=4)td.className='n';tr.appendChild(td);});
tr.onclick=function(){detail(r);};b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('v').onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
