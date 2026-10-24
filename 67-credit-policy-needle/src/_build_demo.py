"""Build demo.html from out/step_04_cells.csv and out/step_04_summary.json. Run step_04_with_gate.py first.

Run (from src/):  python3 _build_demo.py
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
try:
    with open(os.path.join(OUT, "step_04_cells.csv"), newline="", encoding="utf-8") as fh:
        cells = list(csv.DictReader(fh))
    with open(os.path.join(OUT, "step_04_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
except FileNotFoundError:
    raise SystemExit("run step_04_with_gate.py first: src/out/ has no step 4 output")

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Credit Policy Needle: where a reader loses the exception</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--ok:#1e6b3a;--okbg:#e6f4ea;--mid:#8a5a00;--midbg:#fff3d6;--bad:#b3261e;--badbg:#fde8e6}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--ok:#7fd49a;--okbg:#17301f;--mid:#ffc266;--midbg:#332708;--bad:#ff8a80;--badbg:#3a1714}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 14px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 6px;font:inherit}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:460px;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:center}th:first-child,td:first-child{text-align:left}
td.ok{background:var(--okbg);color:var(--ok);font-weight:600}td.mid{background:var(--midbg);color:var(--mid);font-weight:600}td.bad{background:var(--badbg);color:var(--bad);font-weight:600}
.PASS{color:var(--ok)}.FAIL{color:var(--bad)}
code{font-size:13px}
</style></head><body><main>
<h1>Credit Policy Needle: where a reader loses the exception</h1>
<p class="s">Synthetic data. Three invented credit policy manuals (50, 150 and 300 pages) and 210 questions. The four readers are small functions, not models: a control and three with one planted fault each. Each cell shows the questions answered correctly out of the questions asked, for one form of exception at one depth of the rule clause.</p>
<div><label>Reader <select id="r"></select></label><label>Manual <select id="l"><option value="">all three</option><option value="50">50 pages</option><option value="150">150 pages</option><option value="300">300 pages</option></select></label></div>
<p class="s" id="fault"></p>
<div class="k" id="k"></div>
<div class="wrap"><table><thead id="h"></thead><tbody id="b"></tbody></table></div>
<h2>The audit, scored against the planted exceptions</h2>
<div class="wrap"><table><tbody id="a"></tbody></table></div>
<p class="s">Known misses: the audit does not list an exception worded as a restated limit, and it lists a pointer that says "except" though it is not an exception. A reader that never opens an exception passes every question where the exception does not apply; the paired question where it does apply is what fails it. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var CELLS=__CELLS__, SUM=__SUM__;
var FORMS=['plain','inline','adjacent','crossref','restated','register','nested'], DEPTHS=[0,25,50,75,100];
var rs=document.getElementById('r'), ls=document.getElementById('l');
['control','truncating','base_only','retrieval'].forEach(function(n){var o=document.createElement('option');o.value=n;o.textContent=n;rs.appendChild(o);});
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function draw(){
  var r=rs.value, len=ls.value, agg={}, p=0, t=0, bad=0, n=0;
  CELLS.forEach(function(c){
    if(c.reader!==r||(len&&c.length_pages!==len))return;
    var k=c.form+'|'+c.depth_pct, a=agg[k]||(agg[k]={p:0,t:0});
    a.p+=Number(c.passed);a.t+=Number(c.total);p+=Number(c.passed);t+=Number(c.total);
    n++;if(Number(c.passed)/Number(c.total)<0.9)bad++;
  });
  document.getElementById('fault').textContent='This reader '+SUM.readers[r].fault+'.';
  var k=document.getElementById('k');k.textContent='';
  [[p+' of '+t,'questions pass'],[bad+' of '+n,'cells below 90%'],[SUM.readers[r].gate,'gate, all three manuals']].forEach(function(x,i){
    var d=el('div');d.appendChild(el('b',x[0],i===2?x[0]:''));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
  var h=document.getElementById('h');h.textContent='';var hr=el('tr');hr.appendChild(el('th','form'));
  DEPTHS.forEach(function(d){hr.appendChild(el('th','depth '+d+'%'));});h.appendChild(hr);
  var b=document.getElementById('b');b.textContent='';
  FORMS.forEach(function(f){
    var tr=el('tr');tr.appendChild(el('td',f));
    DEPTHS.forEach(function(d){var a=agg[f+'|'+d]||{p:0,t:0};
      tr.appendChild(el('td',a.p+' of '+a.t,a.p===a.t?'ok':(a.p===0?'bad':'mid')));});
    b.appendChild(tr);
  });
}
var A=SUM.audit, ab=document.getElementById('a');
[['exception clauses planted',A.exceptions],['listed by the audit',A.listed],['missed (restated limits)',A.missed],
 ['look-alikes planted',A.look_alikes],['look-alikes listed by mistake',A.false_alarms],
 ['clauses that do not name their rule',A.no_name],['of those, listed as not named',A.no_name_listed]].forEach(function(x){
  var tr=el('tr');tr.appendChild(el('td',x[0]));tr.appendChild(el('td',String(x[1])));ab.appendChild(tr);});
rs.onchange=draw;ls.onchange=draw;draw();
</script></body></html>
"""
page = PAGE.replace("__CELLS__", json.dumps(cells)).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
