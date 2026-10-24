"""Build demo.html from out/step_04_runs.csv and out/step_04_summary.json. Run step_04_trajectory_scorer.py first.
Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_runs.csv"), encoding="utf-8", newline="") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trajectory Eval: 240 runs, graded two ways</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fail:#b3261e;--pass:#1e6b3a;--warn:#8a5a00;--card:#f5f6f8}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fail:#ff8a80;--pass:#7fd49a;--warn:#ffc266;--card:#1c1f25}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:20px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:150px;flex:1 1 150px}.k b{font-size:20px;display:block}
.f{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
label{color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
.wrap{overflow-x:auto;margin-top:12px}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr{cursor:pointer}tbody tr:hover,tbody tr.sel{background:var(--card)}
.fail{color:var(--fail);font-weight:600}.pass{color:var(--pass);font-weight:600}
#d{border:1px solid var(--line);border-radius:8px;padding:12px;background:var(--card);margin-top:12px}
#d ol{margin:6px 0 0;padding-left:22px}#d li{font:13px/1.5 ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
#d li.err{color:var(--warn)}
</style></head><body><main>
<h1>Trajectory Eval: 240 runs, graded two ways</h1>
<p class="s">Synthetic data. Each row is one recorded agent run on one of 20 bank-operations tasks. The planted behavior is what I built into the run; the two verdicts are what the final-answer check and the trajectory scorer printed. Select a row to read the calls.</p>
<div class="k" id="k"></div>
<div class="f">
<label>Task <select id="t"><option value="">all</option></select></label>
<label>Planted behavior <select id="p"><option value="">all</option></select></label>
<label>View <select id="v"><option value="">all runs</option><option value="blind">final answer passes, trajectory fails</option><option value="miss">defective, trajectory passes</option><option value="alarm">sound, trajectory fails</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Run</th><th>Task</th><th>Planted behavior</th><th>Truth</th><th>Final answer</th><th>Trajectory</th><th>Score</th></tr></thead><tbody id="b"></tbody></table></div>
<div id="d"><b id="dh">Select a run</b><p class="s" id="dr"></p><ol id="dl"></ol></div>
<p class="s">Known miss: note_leak runs pass, because the scorer does not read free text inside an argument. Known false alarm: unlisted_alias runs fail, because the rubric does not list the equivalent tool they used. Source: <code>python3 step_04_trajectory_scorer.py</code>. The same author wrote the runs and the rubric, so these numbers are a ceiling, not a rate on real agent traces.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.final_answer_passes+' of '+SUM.runs,'runs the final-answer check passes'],[SUM.trajectory_passes+' of '+SUM.runs,'runs the trajectory scorer passes'],[SUM.defective_caught+' of '+SUM.defective,'defective runs caught (answer alone: '+SUM.defective_caught_by_answer+')'],[SUM.hard_negatives_failed+' of '+SUM.hard_negatives,'hard negatives failed']].forEach(function(x){var d=document.createElement('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function uniq(key){var s={};ROWS.forEach(function(r){s[r[key]]=1;});return Object.keys(s).sort();}
function fill(id,vals){var s=document.getElementById(id);vals.forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o);});}
fill('t',uniq('task_id'));fill('p',uniq('profile'));
function show(r,tr){
  document.querySelectorAll('tbody tr.sel').forEach(function(x){x.classList.remove('sel');});tr.classList.add('sel');
  document.getElementById('dh').textContent=r.run_id+' on '+r.task_id+', planted behavior: '+r.profile;
  document.getElementById('dr').textContent=r.trajectory==='pass'?'Trajectory passes.':'Trajectory fails. '+r.reasons;
  var ol=document.getElementById('dl');ol.textContent='';
  r.trace.split(' > ').forEach(function(c){ol.appendChild(el('li',c,c.indexOf(' !error')>-1?'err':''));});
}
function draw(){
  var t=document.getElementById('t').value,p=document.getElementById('p').value,v=document.getElementById('v').value,b=document.getElementById('b');b.textContent='';var c=0;
  ROWS.forEach(function(r){
    if((t&&r.task_id!==t)||(p&&r.profile!==p))return;
    if(v==='blind'&&!(r.final_answer==='pass'&&r.trajectory==='fail'))return;
    if(v==='miss'&&!(r.truth==='fail'&&r.trajectory==='pass'))return;
    if(v==='alarm'&&!(r.truth==='pass'&&r.trajectory==='fail'))return;
    c++;var tr=document.createElement('tr');
    [r.run_id,r.task_id,r.profile,r.truth==='pass'?'sound':'defective',r.final_answer,r.trajectory,r.score].forEach(function(x,i){var td=el('td',x,(i===4||i===5)?x:'');tr.appendChild(td);});
    tr.onclick=function(){show(r,tr);};b.appendChild(tr);});
  document.getElementById('n').textContent=c+' shown';}
['t','p','v'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", json.dumps(rows).replace("</", "<\\/")).replace("__SUM__", json.dumps(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
