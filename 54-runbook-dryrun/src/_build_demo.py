"""Build demo.html from out/step_04_cases.csv, out/step_04_summary.json and out/step_04_demo_plan.txt.
Run step_04_with_dryrun.py first. Run (from src/): python3 _build_demo.py"""

from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "out", "step_04_cases.csv"), encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
with open(os.path.join(HERE, "out", "step_04_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
with open(os.path.join(HERE, "out", "step_04_demo_plan.txt"), encoding="utf-8") as fh:
    plan = fh.read()


def embed(obj) -> str:
    return json.dumps(obj).replace("</", "<\\/")


page = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>runbook-dryrun: 94 drill cases, one dry run</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mut:#5b6470;--line:#d9dde3;--blocked:#b3261e;--waiting:#8a5a00;--ready:#1e6b3a;--card:#f5f6f8}
@media (prefers-color-scheme: dark){:root{--bg:#14161a;--fg:#e8eaed;--mut:#9aa3ad;--line:#2c3138;--blocked:#ff8a80;--waiting:#ffc266;--ready:#7fd49a;--card:#1b1e23}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 6px}h2{font-size:16px;margin:20px 0 6px}p.s{color:var(--mut);margin:0 0 16px}
.k{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.k div{border:1px solid var(--line);border-radius:8px;padding:8px 12px}.k b{font-size:20px;display:block}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto;font-size:13px;margin:0}
label{margin-right:12px;color:var(--mut);white-space:nowrap}select{background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:14px;min-width:640px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.BLOCKED{color:var(--blocked);font-weight:600}.WAITING{color:var(--waiting);font-weight:600}.READY{color:var(--ready);font-weight:600}
.wrap{overflow-x:auto}td{white-space:nowrap}
</style></head><body><main>
<h1>runbook-dryrun: 94 drill cases, one dry run</h1>
<p class="s">Synthetic data. Each row is a runbook with a snapshot of state and the approvals on file. The truth is the defect I planted; the verdict is what the dry run printed. Nothing here ran a command.</p>
<div class="k" id="k"></div>
<h2>The bundled example: an approval for one model, a run for another</h2>
<pre id="plan"></pre>
<h2>All cases</h2>
<div><label>Verdict <select id="v"><option value="">all</option><option>BLOCKED</option><option>WAITING</option><option>READY</option></select></label>
<label>Planted truth <select id="t"><option value="">all</option><option>BLOCKED</option><option>WAITING</option><option>READY</option></select></label>
<label>Show <select id="a"><option value="">all cases</option><option value="no">only where verdict and truth differ</option></select></label>
<span id="n" class="s"></span></div>
<div class="wrap"><table><thead><tr><th>Case</th><th>Planted change</th><th>Truth</th><th>Verdict</th><th>First error</th><th>Warnings</th></tr></thead><tbody id="b"></tbody></table></div>
<p class="s">Known limits: mislabeled_effect (a write declared as a read) and world_drift (a snapshot that went stale) are READY, and hn_numeric_text (a number held as text) is BLOCKED although the case is clean. The same author wrote the data and the rules, so these numbers are a ceiling. Source: <code>python3 step_04_with_dryrun.py</code>.</p>
</main>
<script>
var ROWS=__ROWS__, SUM=__SUM__, PLAN=__PLAN__;
var k=document.getElementById('k');
[[SUM.blocked_caught+' of '+SUM.blocked,'blocked cases caught'],[SUM.false_alarms+' of '+SUM.clean_or_waiting,'clean or waiting blocked'],[SUM.waiting_held+' held','at an approval gate'],[SUM.missed+' of '+SUM.blocked,'blocked cases still pass']].forEach(function(x){
var d=document.createElement('div');var b=document.createElement('b');b.textContent=x[0];d.appendChild(b);d.appendChild(document.createTextNode(x[1]));k.appendChild(d);});
document.getElementById('plan').textContent=PLAN;
function draw(){var v=document.getElementById('v').value,t=document.getElementById('t').value,a=document.getElementById('a').value,b=document.getElementById('b');
while(b.firstChild){b.removeChild(b.firstChild);}var c=0;
ROWS.forEach(function(r){var same=r.verdict===r.truth;if((v&&r.verdict!==v)||(t&&r.truth!==t)||(a==='no'&&same))return;c++;var tr=document.createElement('tr');
[r.case_id,r.kind,r.truth,r.verdict,r.first_error,r.warnings].forEach(function(x,i){var td=document.createElement('td');td.textContent=x;if(i===2||i===3)td.className=x;tr.appendChild(td);});b.appendChild(tr);});
document.getElementById('n').textContent=c+' shown';}
['v','t','a'].forEach(function(id){document.getElementById(id).onchange=draw;});draw();
</script></body></html>
"""
page = page.replace("__ROWS__", embed(rows)).replace("__SUM__", embed(summary)).replace("__PLAN__", embed(plan))
with open(os.path.join(HERE, "..", "demo.html"), "w", encoding="utf-8") as fh:
    fh.write(page)
print("Wrote demo.html")
