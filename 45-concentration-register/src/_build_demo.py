"""Build demo.html from out/step_04_scenarios.csv and out/step_04_summary.json. Run step_04 first.
Run (from src/):  python3 _build_demo.py"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_scenarios.csv"), newline="", encoding="utf-8") as fh:
    rows = [{k: (int(v) if v.isdigit() else v) for k, v in r.items()} for r in csv.DictReader(fh)]
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Concentration register: 12 outage scenarios</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--ok:#1e6b3a;--warn:#8a5a00}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--ok:#7fd49a;--warn:#ffc266}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:24px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}.yes{color:var(--bad);font-weight:600}.no{color:var(--mut)}.miss{color:var(--warn);font-weight:600}
</style></head><body><main>
<h1>Concentration register: 12 outage scenarios</h1>
<p class="s">Synthetic data: 64 services on four invented providers. Each row is one provider or one region going dark. The truth is the loss the generator computed from the real placements; the direct view counts services by provider; the tool follows hard dependencies and standbys using only what the register holds.</p>
<div class="k" id="k"></div>
<div><label>Limit <select id="lim"></select></label>
<label>Scenario <select id="kind"><option value="">all</option><option value="provider">provider</option><option value="region">region</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Scenario</th><th>Direct view</th><th>Tool</th><th>Truth</th><th>Direct flags</th><th>Tool flags</th><th>Truly over</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Where the tool's misses come from</h2>
<p class="s">Critical (scenario, service) pairs lost in truth and not reported, as each missing piece of the register is supplied in turn.</p>
<div class="wrap"><table><thead><tr><th>Register given</th><th>Pairs missed</th></tr></thead><tbody id="a"></tbody></table></div>
<p class="s">Known limit: the tool sees only what the register holds. A service with no placement, a hard dependency nobody listed and a standby that does not take over all make a scenario look better than it is. The tool understates; it never overstates on this data. The same author wrote the data and the rules, so the numbers are a ceiling. Source: <code>python3 step_04_with_register_model.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function pct(n,t){return (100*n/t).toFixed(1)+'%';}
function over(n,t,l){return n*100>l*t;}
function el(tag,text,cls){var e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e;}
var lim=document.getElementById('lim');
[20,25,30,35,40,50].forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v+'%';if(v===SUM.limit_pct)o.selected=true;lim.appendChild(o);});
function draw(){
  var l=Number(lim.value),kind=document.getElementById('kind').value,b=document.getElementById('b'),k=document.getElementById('k');
  while(b.firstChild)b.removeChild(b.firstChild);while(k.firstChild)k.removeChild(k.firstChild);
  var truth=0,tool=0,caught=0,dcaught=0,shown=0;
  ROWS.forEach(function(r){
    var t=r.critical_total,td=over(r.truth_lost,t,l),tl=over(r.tool_lost,t,l),dr=over(r.direct_lost,t,l);
    if(td)truth++;if(tl)tool++;if(td&&tl)caught++;if(td&&dr)dcaught++;
    if(kind&&r.kind!==kind)return;shown++;
    var tr=document.createElement('tr');
    tr.appendChild(el('td',r.scenario));
    tr.appendChild(el('td',r.direct_lost+' of '+t+' ('+pct(r.direct_lost,t)+')'));
    tr.appendChild(el('td',r.tool_lost+' of '+t+' ('+pct(r.tool_lost,t)+')'));
    tr.appendChild(el('td',r.truth_lost+' of '+t+' ('+pct(r.truth_lost,t)+')'));
    tr.appendChild(el('td',dr?'flag':'-',dr?'yes':'no'));
    tr.appendChild(el('td',tl?'flag':'-',tl?'yes':'no'));
    tr.appendChild(el('td',td?'over':'-',td?(tl?'yes':'miss'):'no'));
    b.appendChild(tr);
  });
  [[truth+' of '+ROWS.length,'scenarios truly over '+l+'%'],[caught+' of '+truth,'caught by the tool'],[dcaught+' of '+truth,'caught by the direct view'],[SUM.pairs_tool+' of '+SUM.pairs_truth,'lost pairs the tool reports']].forEach(function(x){
    var d=document.createElement('div'),s=document.createElement('b');s.textContent=x[0];d.appendChild(s);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
  document.getElementById('n').textContent=shown+' shown, '+tool+' flagged by the tool';
}
var a=document.getElementById('a');
SUM.ablation.forEach(function(x){var tr=document.createElement('tr');tr.appendChild(el('td',x.step));tr.appendChild(el('td',String(x.missed)));a.appendChild(tr);});
lim.onchange=draw;document.getElementById('kind').onchange=draw;draw();
</script></body></html>
"""
page = PAGE.replace("__ROWS__", json.dumps(rows).replace("</", "<\\/")).replace("__SUM__", json.dumps(summary).replace("</", "<\\/"))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
