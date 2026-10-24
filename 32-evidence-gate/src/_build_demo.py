"""Build demo.html from out/step_04_decisions.json and out/step_04_summary.json.
Run step_04_with_gate.py first. Run (from src/): python3 _build_demo.py"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.json"), encoding="utf-8") as fh:
    rows = json.load(fh)
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def js(obj) -> str:
    """JSON for an inline script: '<' is escaped so no string can close the script element."""
    return json.dumps(obj).replace("<", "\\u003c")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evidence Gate: __N__ pull requests, one gate</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--card:#f6f7f9;--block:#b3261e;--review:#8a5a00;--allow:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--card:#1b1e23;--block:#ff8a80;--review:#ffc266;--allow:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:20px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:110px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCK{color:var(--block);font-weight:600}.REVIEW{color:var(--review);font-weight:600}.ALLOW{color:var(--allow);font-weight:600}
.wrap{overflow-x:auto}button.l{background:none;border:0;color:var(--fg);text-decoration:underline;cursor:pointer;font:inherit;padding:0}
#d{border:1px solid var(--line);border-radius:8px;background:var(--card);padding:12px 14px;margin-top:16px}
#d pre{white-space:pre-wrap;word-break:break-word;font:13px/1.45 ui-monospace,Menlo,monospace;margin:6px 0 0}
#d ul{margin:6px 0 0;padding-left:20px}
</style></head><body><main>
<h1>Evidence Gate: __N__ pull requests, one gate</h1>
<p class="s">Synthetic data. Each row is a pull request description with an AI change record. The truth is the evidence state I planted; the decision is what the gate printed. Pick a row to read the description and the findings.</p>
<div class="k" id="k"></div>
<div><label>Decision <select id="fd"><option value="">all</option><option>BLOCK</option><option>REVIEW</option><option>ALLOW</option></select></label>
<label>Planted truth <select id="ft"><option value="">all</option><option value="should_block">should_block</option><option value="needs_review">needs_review</option><option value="fine">fine</option></select></label>
<label>Planted defect <select id="fk"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>PR</th><th>Use case</th><th>Planted defect</th><th>Truth</th><th>Decision</th></tr></thead><tbody id="b"></tbody></table></div>
<div id="d" hidden><h2 id="dt"></h2><pre id="db"></pre><h2>Findings</h2><ul id="df"></ul></div>
<p class="s">Known misses: wrong_content (a real file, the wrong evidence) and stale_registry (the registry holds the use case too low) are allowed; unregistered_understated reaches review, not a block; table_format is blocked although the evidence is real. Source: <code>python3 step_04_with_gate.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.blocked+' of '+SUM.should_block,'should-block blocked'],[SUM.fine_blocked+' of '+SUM.fine,'fine blocked'],[SUM.needs_review_sent+' of '+SUM.needs_review,'wrong label to review'],[SUM.to_review+' of '+SUM.pull_requests,'for a reviewer'],[SUM.missed+' of '+SUM.should_block,'should-block allowed']].forEach(function(x){
  var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var kinds=[];ROWS.forEach(function(r){if(kinds.indexOf(r.kind)<0)kinds.push(r.kind);});kinds.sort();
var fk=document.getElementById('fk');kinds.forEach(function(x){var o=document.createElement('option');o.textContent=x;o.value=x;fk.appendChild(o);});
function show(r){
  document.getElementById('d').hidden=false;
  document.getElementById('dt').textContent=r.pr_id+' ('+r.use_case+') decision '+r.decision;
  document.getElementById('db').textContent=r.body||'(empty description)';
  var ul=document.getElementById('df');ul.textContent='';
  if(!r.findings.length){var e=document.createElement('li');e.textContent='no finding: every required item is listed, ticked, referenced and in date';ul.appendChild(e);}
  r.findings.forEach(function(f){var li=document.createElement('li');li.textContent='['+f.class+'] '+f.kind+': '+f.reason;ul.appendChild(li);});
}
function draw(){
  var d=document.getElementById('fd').value,t=document.getElementById('ft').value,q=document.getElementById('fk').value,b=document.getElementById('b');
  b.textContent='';var c=0;
  ROWS.forEach(function(r){
    if((d&&r.decision!==d)||(t&&r.truth!==t)||(q&&r.kind!==q))return;c++;
    var tr=document.createElement('tr');
    [r.pr_id,r.use_case,r.kind,r.truth,r.decision].forEach(function(v,i){
      var td=document.createElement('td');
      if(i===0){var bt=document.createElement('button');bt.className='l';bt.textContent=v;bt.onclick=function(){show(r);};td.appendChild(bt);}
      else{td.textContent=v;if(i===4)td.className=v;}
      tr.appendChild(td);});
    b.appendChild(tr);});
  document.getElementById('n').textContent=c+' shown';
}
['fd','ft','fk'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__N__", str(len(rows))).replace("__ROWS__", js(rows)).replace("__SUM__", js(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
