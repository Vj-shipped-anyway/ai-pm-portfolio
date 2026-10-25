"""Build demo.html from out/step_04_rows.csv and out/step_04_summary.json. Run step_04_controlmap.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_rows.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ControlMap CLI: __N__ obligations, one status each</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--ok:#1e6b3a;--warn:#8a5a00;--bad:#b3261e;--info:#1d4f91;--wrong:#fdf0ef}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--ok:#7fd49a;--warn:#ffc266;--bad:#ff8a80;--info:#8ab4f8;--wrong:#2a1b1a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);white-space:nowrap}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tr.wrong td{background:var(--wrong)}
.COVERED{color:var(--ok);font-weight:600}.STALE,.PARTIAL{color:var(--warn);font-weight:600}.UNCOVERED{color:var(--bad);font-weight:600}.UNMAPPED{color:var(--info);font-weight:600}
.wrap{overflow-x:auto}td.id{white-space:nowrap}small{color:var(--mut);display:block}
</style></head><body><main>
<h1>ControlMap CLI: __N__ obligations, one status each</h1>
<p class="s">Synthetic data. Each row is an obligation. The truth column is what I planted; the other columns are what each method printed. Shaded rows are the ones ControlMap gets wrong.</p>
<div class="k" id="k"></div>
<div><label>ControlMap says <select id="d"><option value="">all</option><option>COVERED</option><option>STALE</option><option>PARTIAL</option><option>UNCOVERED</option><option>UNMAPPED</option></select></label>
<label>Truth <select id="t"><option value="">all</option><option>COVERED</option><option>STALE</option><option>PARTIAL</option><option>UNCOVERED</option></select></label>
<label><input type="checkbox" id="w"> only where ControlMap is wrong</label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>ID</th><th>Theme and statement</th><th>Applies to</th><th>Truth</th><th>Typed column</th><th>Keyword sheet</th><th>ControlMap</th><th>Why</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: controls worded outside the dictionary, a control whose text denies a phrase it meets, a phrase used in another sense, and themes with no dictionary row (shown as UNMAPPED). Source: <code>python3 step_04_controlmap.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function add(parent,tag,text,cls){var e=document.createElement(tag);e.textContent=text;if(cls){e.className=cls;}parent.appendChild(e);return e;}
var k=document.getElementById('k');
[[SUM.right_controlmap+' of '+SUM.obligations,'ControlMap: right status'],[SUM.right_sheet+' of '+SUM.obligations,'keyword sheet'],[SUM.right_register+' of '+SUM.obligations,'typed column'],[(SUM.wrong-SUM.wrong_unmapped)+' of '+SUM.obligations,'ControlMap wrong and silent']].forEach(function(x){var d=document.createElement('div');add(d,'b',x[0]);add(d,'span',x[1]);k.appendChild(d);});
function draw(){
  var d=document.getElementById('d').value,t=document.getElementById('t').value,w=document.getElementById('w').checked,b=document.getElementById('b'),c=0;
  while(b.firstChild){b.removeChild(b.firstChild);}
  ROWS.forEach(function(r){
    if((d&&r.controlmap!==d)||(t&&r.truth!==t)||(w&&r.right==='yes')){return;}
    c++;
    var tr=document.createElement('tr');if(r.right==='no'){tr.className='wrong';}
    add(tr,'td',r.obligation_id,'id');
    var th=add(tr,'td',r.theme);add(th,'small',r.statement);
    add(tr,'td',r.applies_to.split(';').join(', '));
    [r.truth,r.register,r.sheet,r.controlmap].forEach(function(v){add(tr,'td',v,v);});
    add(tr,'td',r.reason);
    b.appendChild(tr);
  });
  document.getElementById('n').textContent=c+' shown';
}
['d','t','w'].forEach(function(id){document.getElementById(id).onchange=draw;});
draw();
</script></body></html>
"""
page = (PAGE.replace("__N__", str(summary["obligations"]))
        .replace("__ROWS__", json.dumps(rows).replace("<", "\\u003c"))
        .replace("__SUM__", json.dumps(summary).replace("<", "\\u003c")))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
