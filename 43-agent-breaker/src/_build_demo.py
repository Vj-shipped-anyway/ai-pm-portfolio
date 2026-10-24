"""Build demo.html from out/step_04_*.{csv,json}. Run step_04_with_breaker.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(name):
    with open(os.path.join(HERE, "out", name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


faults, timeline = read("step_04_faults.csv"), read("step_04_timeline.csv")
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj):
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-breaker: 25 planted faults, one breaker</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--fault:#c98a00;--open:#b3261e;--half:#2f6fb5;--forced:#6b5aa8}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--fault:#e0a93a;--open:#ff8a80;--half:#7db3f0;--forced:#b9a8f0}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:24px 0 8px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
.lane{position:relative;height:14px;background:var(--line);border-radius:3px;margin:3px 0}
.lane i{position:absolute;top:0;height:100%;border-radius:2px;min-width:3px}
.fault{background:var(--fault)}.OPEN{background:var(--open)}.HALF_OPEN{background:var(--half)}.FORCED_OPEN{background:var(--forced)}
.ag{margin:12px 0 0;font-weight:600}.ln{font-size:12px;color:var(--mut);margin:0}
.ax{display:flex;justify-content:space-between;font-size:12px;color:var(--mut)}
.leg span{display:inline-block;margin-right:14px;font-size:13px;color:var(--mut)}.leg i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top;white-space:nowrap}
.wrap{overflow-x:auto}
</style></head><body><main>
<h1>agent-breaker: 25 planted faults, one breaker</h1>
<p class="s">Synthetic data: five agents, three days, 25 faults I planted. The truth is what the generator did; the breaker never sees it. The same author wrote the data and the rules, so read these as a ceiling.</p>
<div class="k" id="k"></div>
<div><label>Agent <select id="a"><option value="">all</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="must_trip">must_trip</option><option value="must_not_trip">must_not_trip</option><option value="hard_miss">hard_miss</option></select></label>
<span id="n" class="s"></span></div>
<h2>Timeline: planted faults above, breaker state below</h2>
<p class="leg"><span><i class="fault"></i>fault</span><span><i class="OPEN"></i>OPEN, held for a person</span><span><i class="HALF_OPEN"></i>HALF_OPEN, probing</span><span><i class="FORCED_OPEN"></i>operator switch</span></p>
<div id="tl"></div>
<div class="ax"><span>day 1</span><span>day 2</span><span>day 3</span></div>
<h2>Faults</h2>
<div class="wrap"><table><thead><tr><th>Fault</th><th>Agent</th><th>Kind</th><th>Truth</th><th>Harmful calls</th><th>Served: person</th><th>Served: common</th><th>Served: breaker</th><th>Common tripped</th><th>Breaker tripped</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: silent errors (the agent reports ok and is wrong), a slow burn below the trip rate, and the low-volume agent whose window never fills. Two long blips (5 or 6 failures in a row) trip it because a count cannot tell them from an outage. Source: <code>python3 step_04_with_breaker.py</code>.</p>
</main>
<script>
var FAULTS=__FAULTS__, TL=__TL__, SUM=__SUM__;
function el(tag,cls,text){var e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;}
var k=document.getElementById('k');
[[SUM.harm_breaker+' of '+SUM.harm_total,'harmful calls served by the breaker'],[SUM.harm_common+' of '+SUM.harm_total,'served by the common breaker'],[SUM.harm_person+' of '+SUM.harm_total,'served with a person on a schedule'],[SUM.must_trip_tripped+' of '+SUM.must_trip,'must-trip faults tripped'],[SUM.must_not_trip_tripped+' of '+SUM.must_not_trip,'must-not-trip faults tripped'],[SUM.tamper_detected_with_head+' of '+SUM.tamper_tests,'log tamper tests detected']].forEach(function(x){var d=el('div');d.appendChild(el('b',null,x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
var agents=[];FAULTS.forEach(function(f){if(agents.indexOf(f.agent)<0)agents.push(f.agent);});agents.sort();
var sel=document.getElementById('a');agents.forEach(function(a){var o=el('option',null,a);o.value=a;sel.appendChild(o);});
function lane(rows,cls){var l=el('div','lane');rows.forEach(function(r){var s=el('i',cls||r.label);s.style.left=(100*r.start_min/SUM.minutes)+'%';s.style.width=(100*(r.end_min-r.start_min)/SUM.minutes)+'%';s.title=r.label+' '+r.start_min+' to '+r.end_min+' min';l.appendChild(s);});return l;}
function draw(){var a=sel.value,t=document.getElementById('t').value,tl=document.getElementById('tl'),b=document.getElementById('b');tl.textContent='';b.textContent='';
agents.forEach(function(ag){if(a&&ag!==a)return;tl.appendChild(el('p','ag',ag));
tl.appendChild(lane(TL.filter(function(r){return r.agent===ag&&r.lane==='fault';}),'fault'));
tl.appendChild(lane(TL.filter(function(r){return r.agent===ag&&r.lane==='breaker';})));});
var c=0;FAULTS.forEach(function(f){if((a&&f.agent!==a)||(t&&f.truth_class!==t))return;c++;var tr=el('tr');
var trip=f.breaker_tripped==='1'?'tripped after '+f.breaker_minutes_to_trip+' min':'no';
[f.fault_id,f.agent,f.kind,f.truth_class,f.harm_calls,f.person_served,f.common_served,f.breaker_served,f.common_tripped==='1'?'yes':'no',trip].forEach(function(v){var td=el('td',null,v);tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' faults shown';}
sel.onchange=draw;document.getElementById('t').onchange=draw;draw();
</script></body></html>
"""
page = page.replace("__FAULTS__", embed(faults)).replace("__TL__", embed(timeline)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
