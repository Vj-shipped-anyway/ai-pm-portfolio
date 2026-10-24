"""Build demo.html from out/step_04_brief.json and out/step_04_scenarios.csv.
Run step_04_with_swapbrief.py first. Run (from src/):  python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_brief.json"), encoding="utf-8") as fh:
    brief = json.load(fh)
with open(os.path.join(HERE, "out", "step_04_scenarios.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>swapbrief: the average says GO</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--bad:#b3261e;--mid:#8a5a00;--ok:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--bad:#ff8a80;--mid:#ffc266;--ok:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 8px}p.s{color:var(--mut);margin:0 0 12px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 12px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
.k span{color:var(--mut);font-size:13px}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
.wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px;min-width:560px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.NOGO,.BLOCK,.REGRESSED{color:var(--bad);font-weight:600}.GUARD,.WATCH,.INCONCLUSIVE{color:var(--mid);font-weight:600}.GO,.OK,.IMPROVED{color:var(--ok);font-weight:600}
ul{padding-left:20px;margin:6px 0}
</style></head><body><main>
<h1>swapbrief: the average says GO</h1>
<p class="s">Synthetic data. A model migration judged three ways. The committed set first, then 80 simulated migrations whose real problems I planted. Nothing here was measured on a real model.</p>
<h2>The committed set (600 paired items)</h2>
<div class="k" id="cards"></div>
<div class="wrap"><table><thead><tr><th>Metric</th><th>Baseline</th><th>Candidate</th><th>Change</th><th>Interval</th><th>Status</th></tr></thead><tbody id="metrics"></tbody></table></div>
<p class="s" id="slicenote"></p>
<div class="wrap"><table><thead><tr><th>Slice</th><th>Items</th><th>Change</th><th>Interval</th><th>Status</th></tr></thead><tbody id="slices"></tbody></table></div>
<h2>Rollback triggers, written before launch</h2>
<ul id="trig"></ul>
<h2>80 simulated migrations</h2>
<div class="k" id="kpi"></div>
<div><label>Real problem <select id="f1"><option value="">all</option><option value="1">yes</option><option value="0">no</option></select></label>
<label>swapbrief says <select id="f2"><option value="">all</option><option>GO</option><option>GO WITH GUARDRAILS</option><option>NO-GO</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Scenario</th><th>Planted as</th><th>Real problem in</th><th>Headline</th><th>Vendor sheet</th><th>swapbrief</th><th>True cost ratio</th><th>True p95 ratio</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="s" id="limit"></p>
</main>
<script>
var BRIEF=__BRIEF__, ROWS=__ROWS__, SUM=__SUM__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function cls(v){return String(v).replace(/[^A-Za-z]/g,'').replace('GOWITHGUARDRAILS','GUARD');}
function pct(x){return (x*100).toFixed(1)+'%';}
function pp(x){return (x>=0?'+':'')+(x*100).toFixed(1)+' pp';}
function tile(parent,big,small){var d=el('div');d.appendChild(el('b',big));d.appendChild(el('span',small));parent.appendChild(d);}
function row(parent,vals,statusAt){var tr=el('tr');vals.forEach(function(v,i){tr.appendChild(el('td',v,i===statusAt?cls(v):''));});parent.appendChild(tr);}
var a=BRIEF.accuracy,c=BRIEF.cost,l=BRIEF.latency;
var cards=document.getElementById('cards');
tile(cards,BRIEF.headline,'headline average ('+pp(a.delta)+')');
tile(cards,BRIEF.decision,'swapbrief');
tile(cards,c.ratio.toFixed(2)+'x','cost per correct answer');
tile(cards,l.p95_ratio.toFixed(2)+'x','p95 latency (p50 '+l.p50_ratio.toFixed(2)+'x)');
var m=document.getElementById('metrics');
row(m,['Accuracy',pct(a.a),pct(a.b),pp(a.delta),pp(a.lo)+' to '+pp(a.hi),BRIEF.headline],5);
row(m,['Cost per correct answer','$'+c.cpc_a.toFixed(5),'$'+c.cpc_b.toFixed(5),c.ratio.toFixed(2)+'x',c.lo.toFixed(2)+'x to '+c.hi.toFixed(2)+'x',c.status],5);
row(m,['p95 latency',l.p95_a.toFixed(0)+' ms',l.p95_b.toFixed(0)+' ms',l.p95_ratio.toFixed(2)+'x',l.lo.toFixed(2)+'x to '+l.hi.toFixed(2)+'x',l.status],5);
row(m,['p50 latency',l.p50_a.toFixed(0)+' ms',l.p50_b.toFixed(0)+' ms',l.p50_ratio.toFixed(2)+'x',l.p50_lo.toFixed(2)+'x to '+l.p50_hi.toFixed(2)+'x',''],5);
document.getElementById('slicenote').textContent='Decision: '+BRIEF.decision+'. '+BRIEF.block_reasons.concat(BRIEF.guard_reasons).join('; ')+'.';
var sl=document.getElementById('slices');
BRIEF.slices.forEach(function(s){row(sl,[s.slice+(s.critical?' [critical]':''),s.n,pp(s.delta),pp(s.lo)+' to '+pp(s.hi),s.status],4);});
var tg=document.getElementById('trig');
BRIEF.triggers.forEach(function(t){tg.appendChild(el('li',t.metric+' '+t.threshold+' over '+t.window+': '+t.action));});
var kp=document.getElementById('kpi');
tile(kp,SUM.false_go.headline+' of '+SUM.bad,'headline average: false GO');
tile(kp,SUM.false_go.basic+' of '+SUM.bad,'average + vendor sheet: false GO');
tile(kp,SUM.false_go.swapbrief+' of '+SUM.bad,'swapbrief: false GO');
tile(kp,SUM.good_guarded+' of '+SUM.good,'good migrations given guardrails');
function causes(r){var o=[];if(r.bad_cost==='1')o.push('cost');if(r.bad_p95==='1')o.push('p95');if(r.bad_slice==='1')o.push('slice');return o.length?o.join(', '):'none';}
function draw(){var f1=document.getElementById('f1').value,f2=document.getElementById('f2').value,b=document.getElementById('rows');while(b.firstChild)b.removeChild(b.firstChild);var n=0;
ROWS.forEach(function(r){if((f1&&r.bad!==f1)||(f2&&r.swapbrief!==f2))return;n++;
var tr=el('tr');[r.scenario,r.kind,causes(r),r.headline,r.basic,r.swapbrief,r.true_cost_ratio,r.true_p95_ratio].forEach(function(v,i){tr.appendChild(el('td',v,(i>=3&&i<=5)?cls(v):''));});b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
document.getElementById('limit').textContent='Known limit: '+SUM.slice_regressions_missed+' of '+SUM.slice_regressions+' real slice regressions pass unflagged. The same author wrote the data and the rules, so these rates are a ceiling for the rules on worlds I defined. Source: python3 step_04_with_swapbrief.py.';
document.getElementById('f1').onchange=draw;document.getElementById('f2').onchange=draw;draw();
</script></body></html>
"""


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = PAGE.replace("__BRIEF__", embed(brief)).replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
