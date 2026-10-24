"""Build demo.html from out/step_04_scorecard.json, out/step_04_groups.csv and out/step_04_planted.csv.
Run step_04_with_scorecard.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


with open(os.path.join(HERE, "out", "step_04_scorecard.json"), encoding="utf-8") as fh:
    card = json.load(fh)
s = card["score"]
data = {
    "decision": card["decision"], "checks": card["checks"], "groups": rows("step_04_groups.csv"), "planted": rows("step_04_planted.csv"),
    "kpi": {"headline": s["headline"], "end_to_end": s["end_to_end"], "lower": s["interval"][0], "upper": s["interval"][1],
            "fails": sum(1 for c in card["checks"] if c["result"] == "FAIL"), "checks": len(card["checks"]),
            "found": card["planted_found"], "planted": card["planted"], "both_wrong": card["agreements_both_wrong"],
            "agree": s["agree"], "matched": s["matched"], "proposed": s["proposed"]},
}
page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shadow Score: one number, ten checks</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--pass:#1e6b3a;--fail:#b3261e;--skip:#8a5a00;--bar:#4a6fa5;--bar2:#d9dde3}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--pass:#7fd49a;--fail:#ff8a80;--skip:#ffc266;--bar:#8fb0e0;--bar2:#2c3138}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:26px 0 6px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;font:inherit}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.wrap{overflow-x:auto}
.PASS,.ok{color:var(--pass);font-weight:600}.FAIL,.below{color:var(--fail);font-weight:600}.SKIP,.too_few{color:var(--skip);font-weight:600}
.bar{display:inline-block;width:90px;height:8px;background:var(--bar2);border-radius:4px;vertical-align:middle;margin-left:8px}
.bar i{display:block;height:8px;background:var(--bar);border-radius:4px}
</style></head><body><main>
<h1>Shadow Score: one number, ten checks</h1>
<p class="s">Synthetic data. A card-dispute agent ran in shadow mode; people recorded their own outcome. The first number a report would give is the left tile; the rest is what the scorecard adds.</p>
<div class="k" id="k"></div>
<h2>Checks</h2>
<div class="wrap"><table><thead><tr><th>Id</th><th>Check</th><th>Threshold</th><th>Measured</th><th>Result</th></tr></thead><tbody id="c"></tbody></table></div>
<p class="s" id="dec"></p>
<h2>Groups</h2>
<p class="s"><label>Split by <select id="g"><option value="segment">segment</option><option value="week">week</option><option value="reviewer">reviewer</option><option value="class">recorded outcome</option></select></label>
A group is judged from 30 proposals. A smaller group that would have been flagged is marked too_few and is not counted.</p>
<div class="wrap"><table><thead><tr><th>Group</th><th>Cases</th><th>Proposed</th><th>Agreed</th><th>Agreement</th><th>Status</th></tr></thead><tbody id="b"></tbody></table></div>
<h2>Planted problems against what was flagged</h2>
<div class="wrap"><table><thead><tr><th>Id</th><th>Group</th><th>Planted as</th><th>Scorecard</th></tr></thead><tbody id="p"></tbody></table></div>
<p class="s" id="lim"></p>
<p class="s">Source: <code>python3 step_04_with_scorecard.py</code>. The planted list belongs to the generator; the scorecard never reads it.</p>
</main>
<script>
var D=__DATA__;
function pct(x){return (100*x).toFixed(1)+'%';}
function cell(tr,v,cls){var td=document.createElement('td');td.textContent=v;if(cls)td.className=cls;tr.appendChild(td);return td;}
var K=D.kpi,k=document.getElementById('k');
[[pct(K.headline),'first-report rate ('+K.agree+' of '+K.proposed+')'],[pct(K.end_to_end),'counting abstentions ('+K.agree+' of '+K.matched+')'],[pct(K.lower)+' to '+pct(K.upper),'95% interval on the first number'],[K.fails+' of '+K.checks,'checks fail'],[K.found+' of '+K.planted,'planted problems found']].forEach(function(x){var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var c=document.getElementById('c');
D.checks.forEach(function(x){var tr=document.createElement('tr');cell(tr,x.id);cell(tr,x.name);cell(tr,x.threshold);cell(tr,x.measured);cell(tr,x.result,x.result);c.appendChild(tr);if(x.detail&&x.result!=='PASS'){var t2=document.createElement('tr'),td=cell(t2,x.detail);td.colSpan=5;td.style.color='var(--mut)';c.appendChild(t2);}});
document.getElementById('dec').textContent='Decision: '+D.decision+'. HOLD means at least one check fails and the agent stays in shadow mode; CLEAR would mean no failed check, not approval.';
function draw(){var t=document.getElementById('g').value,b=document.getElementById('b');b.textContent='';
D.groups.forEach(function(r){if(r.group_type!==t)return;var tr=document.createElement('tr');cell(tr,r.group);cell(tr,r.cases);cell(tr,r.proposed);cell(tr,r.agreed);
var td=cell(tr,r.rate===''?'n/a':pct(parseFloat(r.rate)));if(r.rate!==''){var bar=document.createElement('span'),i=document.createElement('i');bar.className='bar';i.style.width=(100*parseFloat(r.rate))+'%';bar.appendChild(i);td.appendChild(bar);}
cell(tr,r.status==='too_few'?'too few to judge':r.status==='below'?'below the floor':'ok',r.status);b.appendChild(tr);});}
document.getElementById('g').onchange=draw;draw();
var st={};D.groups.forEach(function(r){st[r.group_type+'|'+r.group]=r;});
var p=document.getElementById('p');
D.planted.forEach(function(x){var r=st[x.group_type+'|'+x.group],tr=document.createElement('tr');cell(tr,x.problem_id);cell(tr,x.group_type+' '+x.group);cell(tr,x.real==='1'?'a real problem':'a look-alike');
var v=x.real==='1'?(r.status==='below'?'found':'MISSED'):(r.status==='too_few'?'too few to judge':r.status==='below'?'FALSE ALARM':'ok');cell(tr,v,v==='found'||v==='ok'?'ok':v==='too_few'||v==='too few to judge'?'too_few':'below');p.appendChild(tr);});
document.getElementById('lim').textContent='Known limits: a planted problem that sits just above the floor passes, and '+K.both_wrong+' of '+K.agree+' agreements are cases where the agent and the person are both wrong. Two files cannot show those.';
</script></body></html>
"""
page = page.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
