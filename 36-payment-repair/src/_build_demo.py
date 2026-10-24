"""Build demo.html from out/step_04_decisions.csv and out/step_04_summary.json. Run step_04_with_repair_tool.py first.

Run (from src/):  python3 _build_demo.py
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_decisions.csv"), newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)


def embed(obj) -> str:
    """JSON that is safe inside a script element."""
    return json.dumps(obj, sort_keys=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>payment-repair: 500 messages, four routes</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--pass:#1e6b3a;--repaired:#1d5fa8;--hold:#8a5a00;--return:#b3261e}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--pass:#7fd49a;--repaired:#8ab4f8;--hold:#ffc266;--return:#ff8a80}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px;min-width:120px}.k b{font-size:20px;display:block}
label{margin-right:12px;color:var(--mut);display:inline-block;margin-bottom:6px}
select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px;max-width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:760px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.PASS{color:var(--pass);font-weight:600}.REPAIRED{color:var(--repaired);font-weight:600}.HOLD{color:var(--hold);font-weight:600}.RETURN{color:var(--return);font-weight:600}
.wrap{overflow-x:auto}td:nth-child(-n+7){white-space:nowrap}
</style></head><body><main>
<h1>payment-repair: 500 messages, four routes</h1>
<p class="s">Synthetic pacs.008-style messages. Each was built complete and then damaged by a named recipe, so the answer key knows the true value. The approver in this run is a scripted test double, not a person.</p>
<div class="k" id="k"></div>
<div><label>After approval <select id="r"><option value="">all</option><option>PASS</option><option>REPAIRED</option><option>HOLD</option><option>RETURN</option></select></label>
<label>Recipe <select id="c"><option value="">all</option></select></label>
<label>Value check <select id="v"><option value="">all</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Message</th><th>Recipe</th><th>Intended</th><th>No approval</th><th>With approval</th><th>Fields changed</th><th>Value check</th><th>Note</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known limits: the bic_present_wrong rows pass because the tool checks presence and shape, not consistency with the IBAN; the cdtr_bic_stale and cdtr_ctry_foreign rows are wrong proposals that the scripted approver approves. Source: <code>python3 step_04_with_repair_tool.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__;
var k=document.getElementById('k');
[[SUM.route_match+' of '+SUM.messages,'route matches the planted intent'],[SUM.auto_correct+' of '+SUM.auto_fields,'repairs without a person, equal to the true value'],[SUM.probes_blocked+' of '+SUM.probes_attempted,'bad approvals blocked'],[String(SUM.wrong_applied),'wrong values applied after approval'],[SUM.bad_released+' released vs '+SUM.basic_bad+' of 500','messages with a wrong or unusable value: this tool vs the basic script']].forEach(function(x){
  var d=document.createElement('div'),b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
function fill(id,key){var s=document.getElementById(id),seen={};ROWS.forEach(function(r){seen[r[key]]=1;});Object.keys(seen).sort().forEach(function(v){var o=document.createElement('option');o.textContent=v;o.value=v;s.appendChild(o);});}
fill('c','recipe');fill('v','value_check');
function draw(){var r=document.getElementById('r').value,c=document.getElementById('c').value,v=document.getElementById('v').value,b=document.getElementById('b');b.textContent='';var n=0;
ROWS.forEach(function(x){if((r&&x.route_after_approval!==r)||(c&&x.recipe!==c)||(v&&x.value_check!==v))return;n++;var tr=document.createElement('tr');
[x.msg_id,x.recipe,x.intended_route,x.route_before_approval,x.route_after_approval,x.changes,x.value_check,x.note].forEach(function(t,i){var td=document.createElement('td');td.textContent=t;if(i>=2&&i<=4)td.className=t;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=n+' shown';}
['r','c','v'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8", newline="\n") as fh:
    fh.write(page)
print("Wrote demo.html")
