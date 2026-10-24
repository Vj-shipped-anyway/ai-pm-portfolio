"""Build demo.html from out/step_04_decisions.csv, out/step_04_summary.json and data/rules.json.
Run step_04_with_check.py first. Run (from src/): python3 _build_demo.py"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
with open(os.path.join(HERE, "..", "data", "rules.json"), encoding="utf-8") as fh:
    rules = json.load(fh)

page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chargeback Packet: 100 disputes, one check</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--late:#b3261e;--fix:#8a5a00;--ready:#1e6b3a}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--late:#ff8a80;--fix:#ffc266;--ready:#7fd49a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:17px;margin:28px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut)}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.LATE{color:var(--late);font-weight:600}.FIX{color:var(--fix);font-weight:600}.READY{color:var(--ready);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+7){white-space:nowrap}table{min-width:760px}
.docs label{display:block;margin:0;color:var(--fg)}.docs{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin-top:8px}
#out li{margin:2px 0}
</style></head><body><main>
<h1>Chargeback Packet: 100 disputes, one check</h1>
<p class="s">Synthetic data. Each row is a dispute packet. The truth is the fault I planted; the state is what the checker printed. The evidence list, windows and page limit are assumptions of this prototype, not any card network's rules.</p>
<div class="k" id="k"></div>
<div><label>State <select id="d"><option value="">all</option><option>READY</option><option>FIX</option><option>LATE</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option value="ready">ready</option><option value="defective">defective</option><option value="late">late</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Case</th><th>Code</th><th>Amount</th><th>Planted case</th><th>Truth</th><th>State</th><th>Days left</th><th>Problems</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known misses: content_mismatch and unreadable_scan rows are READY. The checker reads labels, dates, references, amounts and page counts, not files. Source: <code>python3 step_04_with_check.py</code>.</p>
<h2>Try the evidence list</h2>
<p class="s">Pick a reason code and tick the documents in the packet. This shows the completeness part only; the command-line tool also runs the clock and the consistency checks.</p>
<label>Reason code <select id="rc"></select></label>
<div class="docs" id="docs"></div>
<ul id="out"></ul>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, RULES=__RULES__;
function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
var k=document.getElementById('k');
[[SUM.caught+' of '+SUM.visible_defective,'visible faults sent to FIX'],[SUM.late_caught+' of '+SUM.late,'late marked LATE'],[SUM.false_alarms+' of '+SUM.ready,'ready flagged'],[SUM.hidden_passing+' of '+SUM.hidden,'wrong-file packets that pass']].forEach(function(x){var d=el('div');d.appendChild(el('b',x[0]));d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function draw(){var d=document.getElementById('d').value,t=document.getElementById('t').value,b=document.getElementById('b');b.textContent='';var c=0;
ROWS.forEach(function(r){if((d&&r.state!==d)||(t&&r.truth!==t))return;c++;var tr=el('tr');
[r.case_id,r.reason_code,r.amount,r.planted_kind,r.truth,r.state,r.days_left+(r.sent==='draft'?'':' (sent '+r.sent+')'),r.problems].forEach(function(v,i){tr.appendChild(el('td',v,i===5?v:''));});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
document.getElementById('d').onchange=draw;document.getElementById('t').onchange=draw;draw();
var rc=document.getElementById('rc'),docs=document.getElementById('docs'),out=document.getElementById('out');
Object.keys(RULES.reason_codes).sort().forEach(function(c){var o=el('option',c+' '+RULES.reason_codes[c].name);o.value=c;rc.appendChild(o);});
function types(code){var seen={},list=[];RULES.reason_codes[code].slots.forEach(function(s){s.accept.forEach(function(x){if(!seen[x]){seen[x]=1;list.push(x);}});});return list.sort();}
function show(){var spec=RULES.reason_codes[rc.value],have={};
Array.prototype.forEach.call(docs.querySelectorAll('input'),function(i){if(i.checked)have[i.value]=1;});
out.textContent='';var miss=0;
spec.slots.forEach(function(s){var ok=s.accept.some(function(x){return have[x];});
if(s.required&&!ok){miss++;out.appendChild(el('li','Missing: '+s.label+' (need '+(s.accept.length>1?'one of ':'')+s.accept.join(', ')+')'));}});
out.appendChild(el('li',miss?miss+' required item(s) missing. Window: '+spec.window_days+' calendar days from the day the dispute was received.':'Every required item is present. Window: '+spec.window_days+' calendar days from the day the dispute was received.'));}
function build(){docs.textContent='';types(rc.value).forEach(function(x){var l=el('label');var i=document.createElement('input');i.type='checkbox';i.value=x;i.onchange=show;l.appendChild(i);l.appendChild(document.createTextNode(' '+x));docs.appendChild(l);});show();}
rc.onchange=build;build();
</script></body></html>
"""


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)).replace("__RULES__", embed(rules))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
